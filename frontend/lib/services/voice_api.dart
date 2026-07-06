import 'package:flutter/foundation.dart';

import 'api_client.dart';

/// `POST /api/v1/voice/tts` 호출용 얇은 클라이언트.
///
/// MVP 에서는 서버가 음성 파일을 만들지 않고 재생할 "문장"만 돌려주는
/// flutter_tts fallback 이다. 실제 재생은 [VoiceTtsService] (flutter_tts) 가 한다.
class VoiceApi {
  /// 서버에 재생 문장을 요청한다. 실패해도 앱이 죽지 않도록 입력 문장을
  /// 그대로 fallback 으로 돌려준다.
  Future<String> tts(String text, {String source = 'voice_schedule'}) async {
    try {
      final data = await apiClient.postData(
        '$apiPrefix/voice/tts',
        body: {'text': text, 'source': source},
      );
      if (data is Map && data['text'] is String) {
        return data['text'] as String;
      }
    } catch (e) {
      debugPrint('VoiceApi.tts fallback (local text): $e');
    }
    return text;
  }
}

final voiceApi = VoiceApi();
