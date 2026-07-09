import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter_foreground_task/flutter_foreground_task.dart';
import 'package:vosk_flutter_2/vosk_flutter_2.dart';

import 'dashboard_api.dart';
import 'voice_stt_service.dart' show VoiceSttService;
import 'voice_tts_service.dart';

/// 웨이크워드("포비") 상시 대기 → 명령 인식 → 브리핑 재생 파이프라인.
///
/// 엔진: Vosk(오픈소스, 오프라인, 한국어 모델). grammar(문법 제한) 모드로
/// 후보 단어만 인식해 헛인식을 줄인다. 화면이 꺼져도 동작하도록
/// flutter_foreground_task 로 마이크 타입 포그라운드 서비스를 띄워 프로세스를
/// 살려두고(웨이크락), 인식은 메인 격리자의 이 서비스가 계속 수행한다.
///
/// 모델은 첫 실행 때 [_modelUrl] 에서 자동으로 내려받아 기기에 캐시한다.
/// (assets 번들 불필요 → APK 경량 + 팀원 수동 준비 불필요. 이후엔 캐시 재사용.)
class HotwordService {
  // Vosk 한국어 소형 모델(zip) URL. 첫 실행 때만 받고 이후엔 기기 캐시 사용.
  static const String _modelUrl =
      'https://alphacephei.com/vosk/models/vosk-model-small-ko-0.22.zip';
  static const int _sampleRate = 16000; // Vosk 소형 모델 표준 샘플레이트.

  // 웨이크워드 "포비" 변형(오탐 줄이려 흔히 겹치는 음절은 제외).
  static const List<String> _wakeWords = [
    '포비', '포피', '뽀비', '뽀삐', '후비', '보비',
  ];
  // 명령 키워드: 오탐 줄이려 흔한 단어(일정/하루/브리 등)를 빼고 구별력 높은
  // '브리핑' 만 쓴다. (웨이크워드와 같은 발화에 함께 있어야 실행)
  static const List<String> _briefKeywords = ['브리핑'];

  // grammar(문법 제한) 후보: Vosk 가 이 단어들만 후보로 인식하고 나머지는
  // '[unk]' 로 흘린다 → 헛인식↓, 목표 단어 적중률↑. 모델 사전에 있는(로그에서
  // 실제로 출력된) 단어 위주로 구성한다. '포비' 는 사전에 없을 수 있어(OOV)
  // 오인식 실단어(후비/보비 등)를 넣는다.
  static const List<String> _grammar = [
    '후비', '보비', // 웨이크워드 후보(모델이 '포비'를 이렇게 출력)
    '오늘', '내일', '모레', '브리핑', // 상대 날짜 + 명령
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
  DateTime? _lastTriggerAt;

  bool get isRunning => _running;

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
          notificationText: '"포비"라고 부르면 브리핑을 읽어드려요.',
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
    if (!_running || _busy) return;

    final text = _extractText(resultJson);
    if (text.isEmpty) return;
    final t = text.replaceAll(' ', '');
    debugPrint('Vosk 인식: "$text"');

    final hasWake = _wakeWords.any(t.contains);
    final hasBrief = _briefKeywords.any(t.contains);
    final canTrigger = !_inCooldown();

    // 오탐 방지: 웨이크워드와 '브리핑' 이 같은 발화에 함께 있을 때만 실행.
    // (단독 "포비" 나 "브리핑" 은 무시 → 일상 대화 중 오작동 방지)
    if (hasWake && hasBrief && canTrigger) {
      _trigger(_parseDayOffset(t));
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
      if (_running) {
        try {
          await _speech?.start();
        } catch (e) {
          debugPrint('인식 재개 실패: $e');
        }
      }
      _busy = false;
    }
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
      final items = dash.schedules.where((s) {
        if (dayOffset != 0) return true;
        final st = s.startTime;
        return st == null || st.isEmpty || st.compareTo(now) >= 0;
      }).toList()
        ..sort((a, b) => (a.startTime ?? '').compareTo(b.startTime ?? ''));

      if (items.isEmpty) {
        await _tts.speak(
            dayOffset == 0 ? '오늘 남은 일정이 없어요.' : '$label 일정이 없어요.');
        return;
      }

      final sb = StringBuffer();
      sb.write(dayOffset == 0
          ? '오늘 남은 일정은 ${items.length}건이에요. '
          : '$label 일정은 ${items.length}건이에요. ');
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
