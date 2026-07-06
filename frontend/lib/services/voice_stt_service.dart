import 'package:flutter/foundation.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:speech_to_text/speech_to_text.dart';

/// 음성 인식 결과 1건.
class SttResult {
  final String text;
  final bool isFinal;
  const SttResult(this.text, this.isFinal);
}

/// `speech_to_text` 를 감싸는 온디바이스 STT 서비스.
///
/// MVP 정책: 서버 Whisper 등 서버 STT 를 쓰지 않고, 기기의 음성 인식을 사용해
/// 텍스트만 얻는다. 얻은 텍스트는 기존 일정 파싱 API 로 전달한다.
/// 모든 동작은 예외로 앱이 죽지 않도록 방어적으로 처리한다.
class VoiceSttService {
  final SpeechToText _speech = SpeechToText();
  bool _available = false;

  bool get isAvailable => _available;
  bool get isListening => _speech.isListening;

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

  /// 엔진 초기화. 최초 1회만 실제 초기화하고, 이후에는 캐시된 결과를 반환한다.
  Future<bool> init({
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

  /// 음성 인식 시작. 한국어(ko_KR) 우선. 결과는 [onResult] 로 스트리밍된다.
  Future<void> listen({
    required void Function(SttResult) onResult,
    String localeId = 'ko_KR',
  }) async {
    await _speech.listen(
      onResult: (r) => onResult(SttResult(r.recognizedWords, r.finalResult)),
      localeId: localeId,
      listenOptions: SpeechListenOptions(
        partialResults: true,
        cancelOnError: true,
        listenMode: ListenMode.dictation,
      ),
    );
  }

  Future<void> stop() async {
    try {
      await _speech.stop();
    } catch (e) {
      debugPrint('STT stop error: $e');
    }
  }

  Future<void> cancel() async {
    try {
      await _speech.cancel();
    } catch (e) {
      debugPrint('STT cancel error: $e');
    }
  }
}
