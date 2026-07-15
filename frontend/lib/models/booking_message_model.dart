/// 예약 문의 메시지 모델.
///
/// 백엔드 실제 응답(`POST /api/v1/messages/reservation` → data) 기준:
///   { "generated_message": str, "alternatives": [str],
///     "style": {tone, length, channel} }
class BookingMessageModel {
  final String generatedMessage;
  final List<String> alternatives;

  const BookingMessageModel({
    required this.generatedMessage,
    this.alternatives = const [],
  });

  factory BookingMessageModel.fromJson(Map<String, dynamic> json) {
    final alts = (json['alternatives'] as List?) ?? const [];
    return BookingMessageModel(
      generatedMessage: (json['generated_message'] ?? '').toString(),
      alternatives: alts.map((e) => e.toString()).toList(),
    );
  }
}
