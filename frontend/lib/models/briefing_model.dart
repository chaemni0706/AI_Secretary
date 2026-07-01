/// 하루 브리핑 모델.
///
/// 백엔드 실제 응답(`POST /api/v1/briefings/daily` → data) 기준:
///   { "summary": str, "key_points": [str],
///     "priority_order": [ {title, priority, reason} ] }
/// (프롬프트 예시의 priority_message/preparation_tip 필드는 실제로 없음)
class PriorityOrderItem {
  final String title;
  final String priority; // low | medium | high
  final String reason;

  const PriorityOrderItem({
    required this.title,
    required this.priority,
    required this.reason,
  });

  factory PriorityOrderItem.fromJson(Map<String, dynamic> json) {
    return PriorityOrderItem(
      title: (json['title'] ?? '').toString(),
      priority: (json['priority'] ?? 'medium').toString(),
      reason: (json['reason'] ?? '').toString(),
    );
  }
}

class BriefingModel {
  final String summary;
  final List<String> keyPoints;
  final List<PriorityOrderItem> priorityOrder;

  const BriefingModel({
    required this.summary,
    this.keyPoints = const [],
    this.priorityOrder = const [],
  });

  factory BriefingModel.fromJson(Map<String, dynamic> json) {
    final kp = (json['key_points'] as List?) ?? const [];
    final po = (json['priority_order'] as List?) ?? const [];
    return BriefingModel(
      summary: (json['summary'] ?? '').toString(),
      keyPoints: kp.map((e) => e.toString()).toList(),
      priorityOrder: po
          .map((e) => PriorityOrderItem.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }
}
