import '../services/voice_router_api.dart';

/// 음성 라우터 화면(voice_chat_screen)에서 사용하는 채팅 메시지 모델.
///
/// AI 메시지는 `POST /api/v1/voice/route` 의 결과([VoiceRouteResult])를 그대로
/// 들고 있어서, 화면이 intent 별로 카드를 다르게 그릴 수 있다.

enum ChatRole { user, assistant }

/// 채팅 말풍선 1개를 나타낸다.
class VoiceChatMessage {
  final ChatRole role;
  final String text;

  /// AI 메시지에 한해 라우팅 결과 전체를 담는다(사용자 메시지는 null).
  final VoiceRouteResult? route;

  const VoiceChatMessage({
    required this.role,
    required this.text,
    this.route,
  });

  bool get isUser => role == ChatRole.user;
}
