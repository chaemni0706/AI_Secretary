import 'api_client.dart';

/// `/api/v1/chat/respond` 응답(감정·의도 기반 공감/상담 답변).
class ChatReply {
  /// 화면에 보여줄 상담/대화 답변.
  final String answer;

  /// TTS 재생용 문장(있으면). answer가 LLM 산출물인 경우 null일 수 있음.
  final String? ttsText;

  /// 백엔드가 고른 의도(참고용).
  final String intent;

  const ChatReply({
    required this.answer,
    this.ttsText,
    this.intent = 'fallback',
  });

  factory ChatReply.fromJson(Map<String, dynamic> j) => ChatReply(
        answer: (j['answer'] ?? '').toString(),
        ttsText: (j['tts_text']?.toString().trim().isNotEmpty ?? false)
            ? j['tts_text'].toString()
            : null,
        intent: (j['selected_intent'] ?? 'fallback').toString(),
      );
}

/// AI 상담/대화 API 클라이언트.
/// 일정 등록이 아닌 일반 대화·고민 상담은 이 엔드포인트로 처리한다.
class ChatApi {
  Future<ChatReply> respond(String message, {int? userId}) async {
    final body = <String, dynamic>{'message': message};
    if (userId != null) body['user_id'] = userId;
    final data = await apiClient.postData(
      '$apiPrefix/chat/respond',
      body: body,
    );
    return ChatReply.fromJson((data as Map).cast<String, dynamic>());
  }
}

final chatApi = ChatApi();
