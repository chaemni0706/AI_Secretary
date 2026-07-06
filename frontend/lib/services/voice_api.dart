import 'package:flutter/foundation.dart';

import 'api_client.dart';
import 'preference_store.dart';
import 'voice_tts_service.dart';

/// `POST /api/v1/voice/tts` 응답을 정규화한 재생 명세.
///
/// 서버 응답 스키마(변경 금지): { mode, text, audio_url, ... }.
///  - mode == "server_tts" && audio_url 있음  → 서버가 만든 오디오 파일 재생
///  - mode == "flutter_tts" (또는 audio_url 없음) → text 를 기기 TTS 로 읽기
class TtsPlayback {
  final String mode;
  final String text;
  final String? audioUrl;

  const TtsPlayback({
    required this.mode,
    required this.text,
    this.audioUrl,
  });

  bool get hasServerAudio =>
      mode == 'server_tts' && (audioUrl != null && audioUrl!.trim().isNotEmpty);
}

/// `POST /api/v1/voice/tts` 클라이언트 + 재생 오케스트레이터.
///
/// MVP 정책: 서버는 오디오 파일을 만들지 않고 재생할 "문장"(mode=flutter_tts)만
/// 돌려준다. 실제 재생은 온디바이스 [VoiceTtsService](flutter_tts)가 담당한다.
/// 서버가 훗날 server_tts + audio_url 을 돌려주도록 확장되어도 응답 처리
/// 규칙은 여기 한 곳에서 통일해 둔다.
class VoiceApi {
  /// 서버에 재생 명세를 요청한다. 실패/형식 이상 시 flutter_tts + 원본 텍스트로
  /// 안전하게 fallback 한다(앱이 죽지 않는다).
  Future<TtsPlayback> requestPlayback(
    String text, {
    String source = 'voice_schedule',
  }) async {
    try {
      final data = await apiClient.postData(
        '$apiPrefix/voice/tts',
        body: {
          'text': text,
          'source': source,
          // 사용자 음성 옵션(style/speed/tone). 서버가 아직 미소비해도 무해하며,
          // 향후 server_tts 음색/속도 제어를 위한 계약 필드로 유지한다.
          'voice_options': preferenceStore.voice,
        },
      );
      if (data is Map) {
        final mode = (data['mode'] as String?) ?? 'flutter_tts';
        final serverText = (data['text'] as String?);
        final audioUrl = (data['audio_url'] as String?);
        return TtsPlayback(
          mode: mode,
          text: (serverText != null && serverText.trim().isNotEmpty)
              ? serverText
              : text,
          audioUrl: audioUrl,
        );
      }
    } catch (e) {
      debugPrint('VoiceApi.requestPlayback fallback (local text): $e');
    }
    // 서버 오류/이상 응답 → 원본 텍스트를 기기 TTS 로 읽도록.
    return TtsPlayback(mode: 'flutter_tts', text: text, audioUrl: null);
  }

  /// 기존 호출부 호환용: 재생할 문장(String)만 반환한다.
  Future<String> tts(String text, {String source = 'voice_schedule'}) async {
    final pb = await requestPlayback(text, source: source);
    return pb.text;
  }

  /// "듣기" 통합 진입점. 화면들은 이 메서드로 재생을 일원화한다.
  ///
  /// 규칙:
  ///  - 빈 텍스트 → 재생하지 않고 false 반환(안내는 호출부가 SnackBar 등으로).
  ///  - server_tts + audio_url → (MVP엔 오디오 플레이어 미도입) 안전하게 기기
  ///    TTS 로 text 를 읽는다. 실제 오디오 재생은 후속 단계에서 이 분기만 교체.
  ///  - flutter_tts / 서버 오류 → text 를 기기 TTS 로 읽는다.
  ///
  /// 반환값: 재생을 시작했으면 true.
  Future<bool> speak(
    VoiceTtsService engine,
    String text, {
    String source = 'voice_schedule',
    TtsOptions? options,
  }) async {
    if (text.trim().isEmpty) {
      debugPrint('VoiceApi.speak: empty text -> skip');
      return false;
    }

    final pb = await requestPlayback(text, source: source);

    if (pb.hasServerAudio) {
      // TODO(server_tts): audioplayers 등으로 pb.audioUrl 재생.
      // MVP 에서는 오디오 플레이어를 도입하지 않으므로 기기 TTS 로 대체한다.
      debugPrint('VoiceApi.speak: server_tts audio_url 감지(${pb.audioUrl}) '
          '-> MVP: flutter_tts 로 대체 재생');
      return engine.speak(pb.text, options: options);
    }

    // flutter_tts (기본) / 서버 오류 fallback.
    return engine.speak(pb.text, options: options);
  }
}

final voiceApi = VoiceApi();
