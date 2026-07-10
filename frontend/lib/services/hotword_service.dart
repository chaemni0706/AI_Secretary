import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter_foreground_task/flutter_foreground_task.dart';
import 'package:vosk_flutter_2/vosk_flutter_2.dart';

import 'assistant_text_sanitizer.dart';
import 'dashboard_api.dart';
import 'preference_store.dart';
import 'schedule_api.dart';
import 'voice_stt_service.dart' show VoiceSttService;
import 'voice_tts_service.dart';

/// 웨이크워드("포비") 상시 대기 → 명령 인식 → 브리핑/일정등록 파이프라인.
///
/// 엔진: Vosk(오픈소스, 오프라인, 한국어 모델). grammar(문법 제한) 모드로
/// 후보 단어만 인식해 헛인식을 줄인다. 화면이 꺼져도 동작하도록
/// flutter_foreground_task 로 마이크 타입 포그라운드 서비스를 띄워 프로세스를
/// 살려두고(웨이크락), 인식은 메인 격리자의 이 서비스가 계속 수행한다.
///
/// 지원 명령(웨이크워드와 같은 발화에 함께 있어야 실행):
///   * "브리핑"          → 해당 날짜(오늘/내일/모레) 일정 브리핑 낭독.
///   * "일정/등록/추가"  → 2단계 일정 등록. Vosk 는 문법 제한이라 자유로운
///     날짜·제목을 한 번에 못 잡으므로, 트리거만 감지한 뒤 자유 음성 인식
///     ([VoiceSttService])으로 일정 문장을 받아 파싱·저장한다.
///
/// 모델은 첫 실행 때 [_modelUrl] 에서 자동으로 내려받아 기기에 캐시한다.
/// (assets 번들 불필요 → APK 경량 + 팀원 수동 준비 불필요. 이후엔 캐시 재사용.)
class HotwordService {
  // Vosk 한국어 소형 모델(zip) URL. 첫 실행 때만 받고 이후엔 기기 캐시 사용.
  static const String _modelUrl =
      'https://alphacephei.com/vosk/models/vosk-model-small-ko-0.22.zip';
  static const int _sampleRate = 16000; // Vosk 소형 모델 표준 샘플레이트.

  // 웨이크워드 "포비" 변형(오탐 줄이려 흔히 겹치는 음절은 제외).
  static const List<String> _wakeWords = ['포비', '포피', '뽀비', '뽀삐', '후비', '보비'];
  // 명령 키워드: 오탐 줄이려 흔한 단어를 빼고 구별력 높은 '브리핑' 만 쓴다.
  // (웨이크워드와 같은 발화에 함께 있어야 실행)
  static const List<String> _briefKeywords = ['브리핑'];
  // 일정 등록 트리거 키워드. 이 중 하나가 웨이크워드와 함께 감지되면
  // 2단계 일정 등록 흐름(자유 음성 인식 → 파싱 → 저장)으로 진입한다.
  static const List<String> _scheduleKeywords = ['일정', '등록', '추가'];

  // grammar(문법 제한) 후보: Vosk 가 이 단어들만 후보로 인식하고 나머지는
  // '[unk]' 로 흘린다 → 헛인식↓, 목표 단어 적중률↑. 모델 사전에 있는(로그에서
  // 실제로 출력된) 단어 위주로 구성한다. '포비' 는 사전에 없을 수 있어(OOV)
  // 오인식 실단어(후비/보비 등)를 넣는다.
  static const List<String> _grammar = [
    '후비', '보비', // 웨이크워드 후보(모델이 '포비'를 이렇게 출력)
    '오늘', '내일', '모레', '브리핑', // 상대 날짜 + 브리핑 명령
    '일정', '등록', '추가', // 일정 등록 트리거
    '[unk]',
  ];

  // 인식 재개 직후 이 시간 안엔 재트리거 안 함(스피커 잔향 오인식 방지).
  // 짧게 유지해 "오늘 브리핑 → 바로 내일 브리핑" 연속 요청이 가능하게 한다.
  static const Duration _triggerCooldown = Duration(seconds: 2);

  final VoiceSttService _mic = VoiceSttService(); // 마이크 권한 확보용 재사용.
  final VoiceTtsService _tts = VoiceTtsService();

  final _vosk = VoskFlutterPlugin.instance();
  Model? _model;
  Recognizer? _recognizer;
  SpeechService? _speech;
  StreamSubscription<String>? _resultSub;

  bool _running = false;
  bool _busy = false; // 명령 처리/TTS 중 — 인식 결과 무시.
  bool _suspended = false; // 일시정지 중(특정 화면에서 마이크 양보) — 트리거 무시.
  DateTime? _lastTriggerAt;

  bool get isRunning => _running;

  /// 실행 상태는 유지한 채 인식만 일시정지한다(모델·포그라운드 서비스 유지).
  /// 자체 음성 입출력을 쓰는 화면(예: AI 챗봇)에서 마이크 충돌·오작동을 막기
  /// 위해 화면 진입 시 호출하고, 벗어날 때 [resumeListening] 으로 재개한다.
  Future<void> suspendListening() async {
    if (!_running || _suspended) return;
    _suspended = true;
    try {
      await _speech?.stop(); // 마이크를 놓아 화면의 STT 가 쓰게 한다.
    } catch (e) {
      debugPrint('Hotword 일시정지 실패: $e');
    }
    debugPrint('Hotword: 일시정지(마이크 양보)');
  }

  /// [suspendListening] 으로 멈춘 인식을 재개한다. 실행 중이 아니거나 명령
  /// 처리 중([_busy])이면 재개하지 않는다(진행 중 흐름의 finally 가 재개함).
  Future<void> resumeListening() async {
    if (!_running || !_suspended) return;
    _suspended = false;
    if (_busy) return;
    try {
      await _speech?.start();
      debugPrint('Hotword: 재개');
    } catch (e) {
      debugPrint('Hotword 재개 실패: $e');
    }
  }

  /// 상시 대기 시작.
  Future<bool> start() async {
    if (_running) return true;
    if (!await _mic.ensureMicPermission()) {
      debugPrint('Hotword: 마이크 권한 없음 → 시작 취소');
      return false;
    }
    await _tts.init();
    // 화면이 꺼져도 프로세스가 살아있도록 포그라운드 서비스(마이크 타입) 구동.
    await _startForegroundService();
    try {
      // 첫 실행 때 URL 에서 받아 기기에 캐시(이미 있으면 즉시 반환).
      final modelPath = await ModelLoader().loadFromNetwork(_modelUrl);
      _model = await _vosk.createModel(modelPath);
      // 문법 제한 모드로 생성(정확도↑). grammar 단어에 사전에 없는 게 있어
      // 실패하면(OOV) 자유인식으로 폴백해 최소한 동작은 하게 한다.
      try {
        _recognizer = await _vosk.createRecognizer(
          model: _model!,
          sampleRate: _sampleRate,
          grammar: _grammar,
        );
        debugPrint('Recognizer: grammar 모드');
      } catch (e) {
        debugPrint('grammar recognizer 실패 → 자유인식 폴백: $e');
        _recognizer = await _vosk.createRecognizer(
          model: _model!,
          sampleRate: _sampleRate,
        );
      }
      _speech = await _vosk.initSpeechService(_recognizer!);
      _resultSub = _speech!.onResult().listen(_onResult);
      await _speech!.start();
      _running = true;
      _suspended = false;
      debugPrint('Hotword(Vosk): "포비" 대기 시작');
      return true;
    } catch (e) {
      debugPrint('Hotword 초기화 실패: $e');
      await _cleanup();
      await _stopForegroundService();
      return false;
    }
  }

  /// 상시 대기 종료 + 리소스 해제.
  Future<void> stop() async {
    _running = false;
    _suspended = false;
    await _cleanup();
    await _stopForegroundService();
    debugPrint('Hotword(Vosk): 대기 종료');
  }

  // --- 포그라운드 서비스(화면 꺼짐 상시 대기) ------------------------------

  /// 알림 권한 + 배터리 최적화 예외를 확보하고 포그라운드 서비스를 시작한다.
  Future<void> _startForegroundService() async {
    try {
      if (await FlutterForegroundTask.checkNotificationPermission() !=
          NotificationPermission.granted) {
        await FlutterForegroundTask.requestNotificationPermission();
      }
      if (!await FlutterForegroundTask.isIgnoringBatteryOptimizations) {
        await FlutterForegroundTask.requestIgnoreBatteryOptimization();
      }

      FlutterForegroundTask.init(
        androidNotificationOptions: AndroidNotificationOptions(
          channelId: 'hotword_service',
          channelName: '음성 비서 대기',
          channelDescription: '"포비" 음성 호출을 대기하는 동안 표시됩니다.',
          onlyAlertOnce: true,
        ),
        iosNotificationOptions: const IOSNotificationOptions(),
        foregroundTaskOptions: ForegroundTaskOptions(
          eventAction: ForegroundTaskEventAction.repeat(900000), // 15분 no-op
          autoRunOnBoot: false,
          autoRunOnMyPackageReplaced: false,
          allowWakeLock: true, // 화면 꺼져도 CPU 유지
          allowWifiLock: true,
        ),
      );

      if (await FlutterForegroundTask.isRunningService) {
        await FlutterForegroundTask.restartService();
      } else {
        await FlutterForegroundTask.startService(
          serviceId: 512,
          notificationTitle: '포비 대기 중',
          notificationText: '"포비 브리핑" 또는 "포비 일정 등록"이라고 불러보세요.',
          callback: hotwordFgCallback,
        );
      }
    } catch (e) {
      // 실패해도 앱 전경 상태에서는 인식이 동작하도록 진행.
      debugPrint('포그라운드 서비스 시작 실패(전경에서는 계속 동작): $e');
    }
  }

  Future<void> _stopForegroundService() async {
    try {
      if (await FlutterForegroundTask.isRunningService) {
        await FlutterForegroundTask.stopService();
      }
    } catch (e) {
      debugPrint('포그라운드 서비스 중지 실패: $e');
    }
  }

  Future<void> _cleanup() async {
    try {
      await _resultSub?.cancel();
      await _speech?.stop();
    } catch (_) {}
    _resultSub = null;
    _speech = null;
    _recognizer = null;
    _model = null;
  }

  // --- 내부 흐름 -----------------------------------------------------------

  /// Vosk 최종 발화 결과(JSON 문자열: {"text": "..."}).
  void _onResult(String resultJson) {
    if (!_running || _busy || _suspended) return;

    final text = _extractText(resultJson);
    if (text.isEmpty) return;
    final t = text.replaceAll(' ', '');
    debugPrint('Vosk 인식: "$text"');

    final hasWake = _wakeWords.any(t.contains);
    final hasBrief = _briefKeywords.any(t.contains);
    final hasSchedule = _scheduleKeywords.any(t.contains);
    final canTrigger = !_inCooldown();

    // 오탐 방지: 웨이크워드가 같은 발화에 함께 있을 때만 실행.
    // (단독 "포비"/"브리핑"/"일정" 은 무시 → 일상 대화 중 오작동 방지)
    if (!hasWake || !canTrigger) return;
    // '브리핑' 이 함께 있으면 브리핑 우선("포비 오늘 일정 브리핑" 도 브리핑).
    if (hasBrief) {
      _trigger(_parseDayOffset(t));
    } else if (hasSchedule) {
      _triggerAddSchedule();
    }
  }

  /// 명령에서 상대 날짜 오프셋 추출(모레=2, 내일=1, 그 외/오늘=0).
  int _parseDayOffset(String t) {
    if (t.contains('모레')) return 2;
    if (t.contains('내일')) return 1;
    return 0;
  }

  /// 직전 트리거 후 쿨다운 안이면 true (중복 낭독 방지).
  bool _inCooldown() =>
      _lastTriggerAt != null &&
      DateTime.now().difference(_lastTriggerAt!) < _triggerCooldown;

  String _extractText(String resultJson) {
    try {
      final map = jsonDecode(resultJson);
      if (map is Map && map['text'] is String) {
        return (map['text'] as String).trim();
      }
    } catch (_) {}
    return '';
  }

  /// 브리핑 실행: 인식 일시정지 → 브리핑 TTS → 대기 재개.
  Future<void> _trigger(int dayOffset) async {
    _busy = true;
    try {
      await _speech?.stop(); // TTS 소리를 되받아 인식하지 않도록 정지.
      await _speakBriefing(dayOffset);
    } finally {
      // 낭독 직후 스피커 잔향이 마이크로 되들어와 재트리거되는 걸 막기 위해,
      // 인식 재개 전 잠깐 대기(에코가 지나가는 창을 인식 OFF 로 흘려보냄).
      await Future.delayed(const Duration(milliseconds: 800));
      _lastTriggerAt = DateTime.now(); // 재개 시점부터 짧은 쿨다운 시작.
      // 처리 도중 화면 전환 등으로 일시정지됐으면 재개하지 않는다.
      if (_running && !_suspended) {
        try {
          await _speech?.start();
        } catch (e) {
          debugPrint('인식 재개 실패: $e');
        }
      }
      _busy = false;
    }
  }

  /// 일정 등록 트리거 처리: 핫워드 인식 정지 → 자유 음성으로 일정 문장 캡처 →
  /// 파싱·저장 → 안내 TTS → 대기 재개. (브리핑 흐름 [_trigger] 과 동일한
  /// 정지/재개·쿨다운 규칙을 따른다.)
  Future<void> _triggerAddSchedule() async {
    _busy = true;
    try {
      await _speech?.stop(); // Vosk 마이크를 놓아 자유 STT 가 마이크를 쓰게 한다.
      await _captureAndCreateSchedule();
    } finally {
      await Future.delayed(const Duration(milliseconds: 800));
      _lastTriggerAt = DateTime.now();
      if (_running && !_suspended) {
        try {
          await _speech?.start();
        } catch (e) {
          debugPrint('인식 재개 실패: $e');
        }
      }
      _busy = false;
    }
  }

  /// "등록할 일정을 말씀해주세요" 안내 → 자유 음성 1회 캡처 → 백엔드 파싱 →
  /// 등록 가능하면 저장하고 확인 TTS, 아니면 부족한 정보를 안내한다.
  /// (VoiceScheduleScreen 의 parse→createFromDraft 흐름과 동일한 API 사용.)
  Future<void> _captureAndCreateSchedule() async {
    await _tts.speak('네, 등록할 일정을 말씀해주세요.');
    // 안내 음성이 마이크로 되들어가 STT 를 방해하지 않도록 잠깐 대기.
    await Future.delayed(const Duration(milliseconds: 400));

    final text = (await _listenForCommand())?.trim() ?? '';
    if (text.isEmpty) {
      await _tts.speak('일정을 알아듣지 못했어요. 다시 시도해주세요.');
      return;
    }
    debugPrint('일정 등록 발화: "$text"');

    try {
      await preferenceStore.ensureLoaded();
      final result = await scheduleApi.parse(
        text,
        inputType: 'voice',
        currentDatetime: _nowIso(),
        assistantTone: preferenceStore.assistantTone,
        responseLength: preferenceStore.responseLength,
        reminderStrength: preferenceStore.reminderStrength,
      );
      if (!result.isRegisterable) {
        // 날짜/시간/제목이 빠졌으면 백엔드 안내(tts_text)나 기본 문구로 재요청.
        await _tts.speak(
          sanitizeAssistantText(
            result.ttsText,
            fallback: '날짜와 시간을 포함해서 다시 말씀해주세요. 예: 내일 오후 2시에 회의 일정.',
          ),
        );
        return;
      }
      await scheduleApi.createFromDraft(
        result.scheduleDraft,
        intent: result.intent,
      );
      triggerDashboardRefresh(); // 홈/캘린더 대시보드 새로고침(다른 저장 경로와 동일).
      await _tts.speak(_confirmSpeech(result.scheduleDraft));
    } catch (e) {
      debugPrint('음성 일정 등록 실패: $e');
      await _tts.speak('일정을 저장하지 못했어요. 다시 시도해주세요.');
    }
  }

  /// 자유 음성 인식을 1회 수행하고 최종 인식 문장을 반환한다(없으면 null).
  /// Vosk(문법 제한) 로는 자유로운 날짜·제목을 못 잡으므로 여기선 기기의
  /// 받아쓰기 STT([VoiceSttService])를 쓴다.
  Future<String?> _listenForCommand() async {
    final completer = Completer<String?>();
    var latest = '';
    var done = false;
    void finish() {
      if (done) return;
      done = true;
      if (!completer.isCompleted) completer.complete(latest);
    }

    final ready = await _mic.initialize(
      onStatus: (s) {
        if (s == 'done' || s == 'notListening') finish();
      },
      onError: (_) => finish(),
    );
    if (!ready) {
      debugPrint('일정 등록: STT 초기화 실패');
      return null;
    }

    await _mic.startListening(
      onResult: (r) {
        if (r.text.isNotEmpty) latest = r.text;
        if (r.isFinal) finish();
      },
      onError: (_) => finish(),
      localeId: 'ko_KR',
      listenFor: const Duration(seconds: 15),
      pauseFor: const Duration(seconds: 3),
    );

    // 안전 타임아웃: 상태 콜백이 안 와도 응답을 매듭짓는다.
    return completer.future.timeout(
      const Duration(seconds: 20),
      onTimeout: () {
        finish();
        return latest;
      },
    );
  }

  /// 저장된 일정 초안으로 확인용 낭독 문장을 만든다.
  /// 예: "3월 15일 오후 2시 회의 일정 넣었어요."
  String _confirmSpeech(Map<String, dynamic> draft) {
    final title = (draft['title'] ?? '').toString().trim();
    final date = (draft['date'] ?? '').toString(); // YYYY-MM-DD
    final start = (draft['start_time'] ?? '').toString(); // HH:mm

    final parts = <String>[];
    final md = _spokenDate(date);
    if (md.isNotEmpty) parts.add(md);
    final tm = _spokenTime(start);
    if (tm.isNotEmpty) parts.add(tm);
    if (title.isNotEmpty) parts.add(title);
    final body = parts.join(' ');
    return body.isEmpty ? '일정을 넣었어요.' : '$body 일정 넣었어요.';
  }

  /// 'YYYY-MM-DD' → 'M월 D일'(파싱 실패 시 빈 문자열).
  String _spokenDate(String ymd) {
    final p = ymd.split('-');
    if (p.length != 3) return '';
    final mo = int.tryParse(p[1]);
    final d = int.tryParse(p[2]);
    if (mo == null || d == null) return '';
    return '$mo월 $d일';
  }

  /// 현재 시각을 오프셋 포함 ISO8601 로(백엔드 상대 날짜 계산 기준).
  String _nowIso() {
    final now = DateTime.now();
    final o = now.timeZoneOffset;
    final sign = o.isNegative ? '-' : '+';
    final hh = o.inHours.abs().toString().padLeft(2, '0');
    final mm = (o.inMinutes.abs() % 60).toString().padLeft(2, '0');
    final base = now.toIso8601String().split('.').first;
    return '$base$sign$hh:$mm';
  }

  /// 오늘 브리핑을 받아 음성으로 읽는다(BriefingScreen 과 동일한 텍스트 규칙).
  Future<void> _speakBriefing(int dayOffset) async {
    final target = DateTime.now().add(Duration(days: dayOffset));
    final label = dayOffset == 0
        ? '오늘'
        : dayOffset == 1
        ? '내일'
        : dayOffset == 2
        ? '모레'
        : '${target.month}월 ${target.day}일';
    // 오늘이면 서버 기준 today(null), 그 외엔 계산한 날짜(YYYY-MM-DD) 전달.
    final date = dayOffset == 0
        ? null
        : '${target.year}-${_two(target.month)}-${_two(target.day)}';

    // 해당 날짜 대시보드(일정)를 먼저 요청하고, 그동안 짧은 응답을 재생(병렬).
    final dashFuture = dashboardApi.getTodayDashboard(date: date);
    await _tts.speak('네, $label 일정 확인할게요.');
    try {
      final dash = await dashFuture;
      final now = _nowHm();
      // 오늘이면 "현재 시각 이후" 일정만, 미래 날짜면 그날 전체. 시간순 정렬.
      final items =
          dash.schedules.where((s) {
              if (dayOffset != 0) return true;
              final st = s.startTime;
              return st == null || st.isEmpty || st.compareTo(now) >= 0;
            }).toList()
            ..sort((a, b) => (a.startTime ?? '').compareTo(b.startTime ?? ''));

      if (items.isEmpty) {
        await _tts.speak(dayOffset == 0 ? '오늘 남은 일정이 없어요.' : '$label 일정이 없어요.');
        return;
      }

      final sb = StringBuffer();
      sb.write(
        dayOffset == 0
            ? '오늘 남은 일정은 ${items.length}건이에요. '
            : '$label 일정은 ${items.length}건이에요. ',
      );
      for (final s in items) {
        final t = _spokenTime(s.startTime);
        sb.write(t.isEmpty ? '${s.title}. ' : '$t ${s.title}. ');
      }
      // 기기 TTS 로 바로 재생(/voice/tts 왕복 생략).
      await _tts.speak(sb.toString());
    } catch (e) {
      debugPrint('일정 브리핑 실패: $e');
      await _tts.speak('$label 일정을 불러오지 못했어요.');
    }
  }

  static String _two(int n) => n.toString().padLeft(2, '0');

  String _nowHm() {
    final n = DateTime.now();
    return '${_two(n.hour)}:${_two(n.minute)}';
  }

  /// 'HH:mm' → '오전/오후 h시 m분'(0분이면 분 생략). 값이 없으면 빈 문자열.
  String _spokenTime(String? hhmm) {
    if (hhmm == null || !hhmm.contains(':')) return '';
    final p = hhmm.split(':');
    final h = int.tryParse(p[0]) ?? 0;
    final m = int.tryParse(p[1]) ?? 0;
    final ampm = h < 12 ? '오전' : '오후';
    final h12 = (h % 12 == 0) ? 12 : h % 12;
    return m == 0 ? '$ampm $h12시' : '$ampm $h12시 $m분';
  }
}

/// 전역 인스턴스(기존 `*_service` / `*_api` 싱글턴 패턴과 동일).
final hotwordService = HotwordService();

/// 포그라운드 서비스 콜백(최상위 함수 필수). 실제 음성 인식은 메인 격리자의
/// [HotwordService] 가 수행하고, 이 핸들러는 프로세스를 살려두는 역할만 한다.
@pragma('vm:entry-point')
void hotwordFgCallback() {
  FlutterForegroundTask.setTaskHandler(_HotwordFgTaskHandler());
}

class _HotwordFgTaskHandler extends TaskHandler {
  @override
  Future<void> onStart(DateTime timestamp, TaskStarter starter) async {}

  @override
  void onRepeatEvent(DateTime timestamp) {}

  @override
  Future<void> onDestroy(DateTime timestamp, bool isTimeout) async {}
}
