/// 하루 브리핑 Mock 모델.
///
/// 백엔드 `POST /api/v1/briefings/daily` 의 공통 응답
/// `{ success, message, data }` 중 `data` 필드 구조에 맞춘 모델이다.
/// 추후 실제 API 연결 시 `DailyBriefingMock.fromJson(response['data'])`
/// 형태로 그대로 재사용할 수 있다.
class DailyBriefingMock {
  final String briefingId;
  final String date; // "YYYY-MM-DD"
  final BriefingSummary summary;
  final String briefingText;
  final List<BriefingSection> sections;
  final NextEvent? nextEvent;
  final String ttsText;
  final List<String> recommendedActions;

  const DailyBriefingMock({
    required this.briefingId,
    required this.date,
    required this.summary,
    required this.briefingText,
    required this.sections,
    required this.nextEvent,
    required this.ttsText,
    required this.recommendedActions,
  });

  factory DailyBriefingMock.fromJson(Map<String, dynamic> json) {
    final sectionsJson = (json['sections'] as List?) ?? const [];
    final actionsJson = (json['recommended_actions'] as List?) ?? const [];
    return DailyBriefingMock(
      briefingId: (json['briefing_id'] ?? '').toString(),
      date: (json['date'] ?? '').toString(),
      summary: BriefingSummary.fromJson(
        (json['summary'] as Map<String, dynamic>?) ?? const {},
      ),
      briefingText: (json['briefing_text'] ?? '').toString(),
      sections: sectionsJson
          .map((e) => BriefingSection.fromJson(e as Map<String, dynamic>))
          .toList(),
      nextEvent: json['next_event'] == null
          ? null
          : NextEvent.fromJson(json['next_event'] as Map<String, dynamic>),
      ttsText: (json['tts_text'] ?? '').toString(),
      recommendedActions: actionsJson.map((e) => e.toString()).toList(),
    );
  }
}

class BriefingSummary {
  final int scheduleCount;
  final int todoCount;
  final int highPriorityCount;

  const BriefingSummary({
    required this.scheduleCount,
    required this.todoCount,
    required this.highPriorityCount,
  });

  factory BriefingSummary.fromJson(Map<String, dynamic> json) {
    return BriefingSummary(
      scheduleCount: (json['schedule_count'] ?? 0) as int,
      todoCount: (json['todo_count'] ?? 0) as int,
      highPriorityCount: (json['high_priority_count'] ?? 0) as int,
    );
  }
}

class BriefingSection {
  final String type; // today_schedule | important_todo | recommendation
  final String title;
  final String content;

  const BriefingSection({
    required this.type,
    required this.title,
    required this.content,
  });

  factory BriefingSection.fromJson(Map<String, dynamic> json) {
    return BriefingSection(
      type: (json['type'] ?? '').toString(),
      title: (json['title'] ?? '').toString(),
      content: (json['content'] ?? '').toString(),
    );
  }
}

class NextEvent {
  final String id;
  final String title;
  final String startTime; // "HH:mm"
  final int minutesUntilStart;

  const NextEvent({
    required this.id,
    required this.title,
    required this.startTime,
    required this.minutesUntilStart,
  });

  factory NextEvent.fromJson(Map<String, dynamic> json) {
    return NextEvent(
      id: (json['id'] ?? '').toString(),
      title: (json['title'] ?? '').toString(),
      startTime: (json['start_time'] ?? '').toString(),
      minutesUntilStart: (json['minutes_until_start'] ?? 0) as int,
    );
  }
}
