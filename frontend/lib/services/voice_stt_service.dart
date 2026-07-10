import 'package:flutter/foundation.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:speech_to_text/speech_to_text.dart';

/// 음성 인식 결과 1건.
class SttResult {
  final String text;
  final bool isFinal;
  const SttResult(this.text, this.isFinal);
}

/// STT 실패 상황별 사용자 안내 문구.
///
/// 화면마다 문구가 제각각이면 UX 가 흔들리므로, "권한 거부 / 사용 불가 /
/// 무음 / 오류" 4가지 표준 문구를 한 곳에 모아둔다. 화면은 이 값을 그대로
/// 노출하면 된다.
class SttMessages {
  static const String micDenied = '마이크 권한이 필요해요. 설정에서 마이크 권한을 허용해주세요.';
  static const String unavailable = '이 기기에서는 음성 인식을 사용할 수 없어요.';
  static const String empty = '음성을 인식하지 못했어요. 다시 말씀해주세요.';
  static const String error = '음성 인식 중 오류가 발생했어요. 다시 시도해주세요.';
}

/// `speech_to_text` 를 감싸는 온디바이스 STT 서비스.
///
/// MVP 정책: 서버 STT(Whisper 등)를 쓰지 않고 기기의 음성 인식으로 텍스트만
/// 얻는다. 얻은 텍스트는 기존 API(/ai/schedule/parse, /emotion/analyze 등)로
/// 그대로 전달한다. 서버에는 음성 파일이 아니라 인식 결과 텍스트만 보낸다.
///
/// 안정성 원칙:
///  - 모든 동작은 예외로 앱이 죽지 않도록 방어적으로 처리한다.
///  - `startListening()` 은 이전 세션이 정리되지 않아 두 번째 인식이 멈추는
///    문제를 막기 위해, 시작 전에 진행 중 세션을 항상 취소하고 시작한다.
///
/// 공개 API(권장 이름):
///   initialize() / startListening() / stopListening() / cancelListening() / dispose()
/// 기존 화면 호환을 위해 init() / listen() / stop() / cancel() 별칭도 유지한다.
class VoiceSttService {
  final SpeechToText _speech = SpeechToText();

  /// initialize() 성공 여부(엔진 사용 가능). 최초 1회만 실제 초기화한다.
  bool _available = false;

  bool get isAvailable => _available;
  bool get isListening => _speech.isListening;

  // --------------------------------------------------------------------- //
  // 권한
  // --------------------------------------------------------------------- //

  /// 마이크 권한 확인/요청. 권한이 있으면 true.
  Future<bool> ensureMicPermission() async {
    try {
      final status = await Permission.microphone.status;
      if (status.isGranted) return true;
      final result = await Permission.microphone.request();
      return result.isGranted;
    } catch (e) {
      debugPrint('STT permission error: $e');
      return false;
    }
  }

  // --------------------------------------------------------------------- //
  // 초기화
  // --------------------------------------------------------------------- //

  /// 엔진 초기화. 최초 1회만 실제 초기화하고, 이후에는 캐시된 결과를 반환한다.
  ///
  /// [onStatus] / [onError] 는 speech_to_text 의 상태/오류 콜백으로 그대로
  /// 전달된다(예: 'listening' / 'notListening' / 'done').
  Future<bool> initialize({
    void Function(String status)? onStatus,
    void Function(String error)? onError,
  }) async {
    if (_available) return true;
    try {
      _available = await _speech.initialize(
        onStatus: (s) {
          debugPrint('STT status: $s');
          onStatus?.call(s);
        },
        onError: (e) {
          debugPrint('STT error: ${e.errorMsg} (permanent=${e.permanent})');
          onError?.call(e.errorMsg);
        },
      );
    } catch (e) {
      debugPrint('STT init exception: $e');
      _available = false;
    }
    return _available;
  }

  /// [initialize] 의 기존 이름 별칭(호환용).
  Future<bool> init({
    void Function(String status)? onStatus,
    void Function(String error)? onError,
  }) => initialize(onStatus: onStatus, onError: onError);

  // --------------------------------------------------------------------- //
  // 듣기 시작 / 종료 / 취소
  // --------------------------------------------------------------------- //

  /// 음성 인식을 시작한다. 한국어(ko_KR) 우선. 결과는 [onResult] 로 스트리밍된다.
  ///
  /// 두 번째 이후 호출에서도 정상 동작하도록, 시작 전에 진행 중인 세션을 항상
  /// 취소해 상태를 초기화한다. 초기화 전이면 [onError] 로 안내 문구를 돌려주고
  /// false 를 반환한다. 예외는 삼켜 앱이 죽지 않는다.
  ///
  /// 반환값: 실제로 듣기가 시작됐으면 true, 아니면 false.
  Future<bool> startListening({
    required void Function(SttResult) onResult,
    void Function(String message)? onError,
    String localeId = 'ko_KR',
    Duration listenFor = const Duration(seconds: 30),
    Duration pauseFor = const Duration(seconds: 3),
  }) async {
    // 엔진이 준비되지 않았으면 시작하지 않는다(무반응 대신 명확한 안내).
    if (!_available) {
      debugPrint('STT startListening blocked: not initialized');
      onError?.call(SttMessages.unavailable);
      return false;
    }

    // 이전 세션이 남아 두 번째 인식이 멈추는 문제 방지: 항상 취소 후 시작.
    try {
      if (_speech.isListening) {
        await _speech.cancel();
      }
    } catch (e) {
      debugPrint('STT pre-listen cancel error: $e');
    }

    try {
      await _speech.listen(
        onResult: (r) => onResult(SttResult(r.recognizedWords, r.finalResult)),
        listenOptions: SpeechListenOptions(
          partialResults: true,
          cancelOnError: true,
          listenMode: ListenMode.dictation,
          localeId: localeId,
          listenFor: listenFor,
          pauseFor: pauseFor,
        ),
      );
      return true;
    } catch (e) {
      debugPrint('STT listen error: $e');
      onError?.call(SttMessages.error);
      return false;
    }
  }

  /// [startListening] 의 기존 이름 별칭(호환용).
  Future<void> listen({
    required void Function(SttResult) onResult,
    String localeId = 'ko_KR',
  }) => startListening(onResult: onResult, localeId: localeId);

  /// 듣기를 정상 종료한다(부분 결과까지 최종 결과로 확정).
  Future<void> stopListening() async {
    try {
      await _speech.stop();
    } catch (e) {
      debugPrint('STT stop error: $e');
    }
  }

  /// [stopListening] 의 기존 이름 별칭(호환용).
  Future<void> stop() => stopListening();

  /// 듣기를 취소한다(결과 폐기). 화면 dispose 시 사용 권장.
  Future<void> cancelListening() async {
    try {
      await _speech.cancel();
    } catch (e) {
      debugPrint('STT cancel error: $e');
    }
  }

  /// [cancelListening] 의 기존 이름 별칭(호환용).
  Future<void> cancel() => cancelListening();

  /// 리소스 정리. 진행 중 세션을 취소한다.
  Future<void> dispose() async {
    await cancelListening();
  }
}
