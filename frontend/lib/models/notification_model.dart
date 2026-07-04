/// 알림 항목.
///
/// 백엔드 실제 계약 기준: `{ "time": "HH:mm", "message": "..." }`
/// ( `notify_at` / `type` 같은 필드는 없음 )
class NotificationItem {
  final String time;
  final String message;

  const NotificationItem({required this.time, required this.message});

  factory NotificationItem.fromJson(Map<String, dynamic> json) {
    return NotificationItem(
      time: (json['time'] ?? '').toString(),
      message: (json['message'] ?? '').toString(),
    );
  }
}

/// 준비물 체크리스트 항목.
class ChecklistItem {
  final String item;
  final String reason;

  const ChecklistItem({required this.item, required this.reason});

  factory ChecklistItem.fromJson(Map<String, dynamic> json) {
    return ChecklistItem(
      item: (json['item'] ?? '').toString(),
      reason: (json['reason'] ?? '').toString(),
    );
  }
}

/// 알림 계획 응답 (`POST/GET /api/v1/notifications/plan`).
class NotificationPlan {
  final String scheduleId;
  final String? leaveTime;
  final List<ChecklistItem> checklist;
  final List<NotificationItem> notifications;
  final String appliedPreference;
  final int persistedReminders;

  const NotificationPlan({
    required this.scheduleId,
    this.leaveTime,
    this.checklist = const [],
    this.notifications = const [],
    this.appliedPreference = 'normal',
    this.persistedReminders = 0,
  });

  factory NotificationPlan.fromJson(Map<String, dynamic> json) {
    final checklistRaw = (json['checklist'] as List?) ?? const [];
    final notiRaw = (json['notifications'] as List?) ?? const [];
    return NotificationPlan(
      scheduleId: json['schedule_id']?.toString() ?? '',
      leaveTime: json['leave_time'] as String?,
      checklist: checklistRaw
          .map((e) => ChecklistItem.fromJson(e as Map<String, dynamic>))
          .toList(),
      notifications: notiRaw
          .map((e) => NotificationItem.fromJson(e as Map<String, dynamic>))
          .toList(),
      appliedPreference: (json['applied_preference'] ?? 'normal').toString(),
      persistedReminders: (json['persisted_reminders'] ?? 0) as int,
    );
  }
}
