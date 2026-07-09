import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter_foreground_task/flutter_foreground_task.dart';
import 'package:vosk_flutter_2/vosk_flutter_2.dart';

import 'briefing_api.dart';
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

  // 웨이크워드 "포비" 의 STT 오인식 변형들(소형 모델 로그 기반: 후비/보비 등).
  static const List<String> _wakeWords = [
    '포비', '포피', '보비', '보피', '포브', '뽀비', '포뷔',
    '후비', '부비', '호비', '뽀삐', '포미', '후피',
  ];
  // 브리핑 명령으로 볼 키워드(브리핑 오인식 변형 포함).
  static const List<String> _briefKeywords = [
    '브리핑', '프리핑', '브리', '브링', '요약', '하루', '일정',
  ];

  // grammar(문법 제한) 후보: Vosk 가 이 단어들만 후보로 인식하고 나머지는
  // '[unk]' 로 흘린다 → 헛인식↓, 목표 단어 적중률↑. 모델 사전에 있는(로그에서
  // 실제로 출력된) 단어 위주로 구성한다. '포비' 는 사전에 없을 수 있어(OOV)
  // 오인식 실단어(후비/보비 등)를 넣는다.
  static const List<String> _grammar = [
    '후비', '보비', // 웨이크워드 후보: 로그에서 모델이 '포비'를 실제로 출력한 실단어
    '브리핑', '오늘', '요약', '하루', '일정', // 명령/공통
    '[unk]',
  ];

  // 웨이크워드만 들린 뒤 명령을 기다리는 시간.
  static const Duration _armWindow = Duration(seconds: 6);
  // 직전 트리거 후 이 시간 안엔 재트리거 안 함(중복 낭독 방지).
  static const Duration _triggerCooldown = Duration(seconds: 10);

  final VoiceSttService _mic = VoiceSttService(); // 마이크 권한 확보용 재사용.
  final VoiceTtsService _tts = VoiceTtsService();

  final _vosk = VoskFlutterPlugin.instance();
  Model? _model;
  Recognizer? _recognizer;
  SpeechService? _speech;
  StreamSubscription<String>? _resultSub;

  bool _running = false;
  bool _busy = false; // 명령 처리/TTS 중 — 인식 결과 무시.
  DateTime? _armedUntil;
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
    _armedUntil = null;
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

    if (hasWake && hasBrief && canTrigger) {
      _trigger();
    } else if (hasWake) {
      _armedUntil = DateTime.now().add(_armWindow); // 명령 대기 시작.
      debugPrint('Hotword: "포비" 감지 → 명령 대기');
    } else if (hasBrief && _isArmed() && canTrigger) {
      _trigger();
    }
  }

  bool _isArmed() =>
      _armedUntil != null && DateTime.now().isBefore(_armedUntil!);

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
  Future<void> _trigger() async {
    _busy = true;
    _armedUntil = null;
    _lastTriggerAt = DateTime.now();
    try {
      await _speech?.stop(); // TTS 소리를 되받아 인식하지 않도록 정지.
      await _speakBriefing();
    } finally {
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
  Future<void> _speakBriefing() async {
    // 브리핑 요청(네트워크/LLM)을 먼저 시작하고, 그동안 짧은 응답을 재생한다(병렬).
    final briefingFuture = briefingApi.getDailyBriefing();
    await _tts.speak('네, 오늘 브리핑 확인할게요.');
    try {
      final b = await briefingFuture;
      final fromPoints = [b.summary, ...b.keyPoints]
          .where((s) => s.trim().isNotEmpty)
          .join('. ');
      final raw = (b.ttsText != null && b.ttsText!.trim().isNotEmpty)
          ? b.ttsText!.trim()
          : fromPoints;
      final text = raw.trim().isEmpty ? '오늘 브리핑을 불러오지 못했습니다.' : raw;
      // 2) /voice/tts 서버 왕복 생략 → 기기 TTS 로 바로 재생(지연 감소).
      await _tts.speak(text);
    } catch (e) {
      debugPrint('브리핑 재생 실패: $e');
      await _tts.speak('브리핑을 불러오지 못했어요.');
    }
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
