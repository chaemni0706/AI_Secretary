/// 가짜 전화 알림(Mock Call) 모델.
///
/// 백엔드 `POST /api/v1/alerts/departure-plan` 의 공통 응답
/// `{ success, message, data }` 중 `data` 구조에 맞춘 모델이다.
class MockCallAlert {
  final String scheduleId;
  final AlertPlan alertPlan;

  const MockCallAlert({required this.scheduleId, required this.alertPlan});

  factory MockCallAlert.fromJson(Map<String, dynamic> json) {
    return MockCallAlert(
      scheduleId: (json['schedule_id'] ?? '').toString(),
      alertPlan: AlertPlan.fromJson(
        (json['alert_plan'] as Map<String, dynamic>?) ?? const {},
      ),
    );
  }
}

class AlertPlan {
  final List<Reminder> reminders;
  final List<String> checklist;
  final String voiceAlertText;
  final bool saveRequiredOnFrontend;

  const AlertPlan({
    required this.reminders,
    required this.checklist,
    required this.voiceAlertText,
    required this.saveRequiredOnFrontend,
  });

  factory AlertPlan.fromJson(Map<String, dynamic> json) {
    final remindersJson = (json['reminders'] as List?) ?? const [];
    final checklistJson = (json['checklist'] as List?) ?? const [];
    return AlertPlan(
      reminders: remindersJson
          .map((e) => Reminder.fromJson(e as Map<String, dynamic>))
          .toList(),
      checklist: checklistJson.map((e) => e.toString()).toList(),
      voiceAlertText: (json['voice_alert_text'] ?? '').toString(),
      saveRequiredOnFrontend: json['save_required_on_frontend'] == true,
    );
  }

  /// 대표 리마인더(첫 번째). 없으면 null.
  Reminder? get primary => reminders.isNotEmpty ? reminders.first : null;
}

class Reminder {
  final String reminderId;
  final String type; // mock_call | ...
  final String triggerDatetime; // ISO8601
  final String title;
  final String message;
  final String screen;
  final String notificationChannel;

  const Reminder({
    required this.reminderId,
    required this.type,
    required this.triggerDatetime,
    required this.title,
    required this.message,
    required this.screen,
    required this.notificationChannel,
  });

  factory Reminder.fromJson(Map<String, dynamic> json) {
    return Reminder(
      reminderId: (json['reminder_id'] ?? '').toString(),
      type: (json['type'] ?? '').toString(),
      triggerDatetime: (json['trigger_datetime'] ?? '').toString(),
      title: (json['title'] ?? '').toString(),
      message: (json['message'] ?? '').toString(),
      screen: (json['screen'] ?? '').toString(),
      notificationChannel: (json['notification_channel'] ?? '').toString(),
    );
  }
}
