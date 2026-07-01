/// 일정(EVENT) 모델.
///
/// 백엔드 실제 계약 기준:
/// - `id` 는 **문자열(string)** 이다. (정수로 파싱하지 말 것)
/// - `priority` 는 소문자 `low | medium | high`.
/// - 시간은 `"HH:mm"`, 날짜는 `"YYYY-MM-DD"`.
class ScheduleModel {
  final String id;
  final String title;
  final String? date;
  final String? startTime;
  final String? endTime;
  final String? category;
  final String priority; // low | medium | high
  final String? location;
  final String? memo;
  final String status;
  final String source;
  final int? travelTimeMinutes;

  const ScheduleModel({
    required this.id,
    required this.title,
    this.date,
    this.startTime,
    this.endTime,
    this.category,
    this.priority = 'medium',
    this.location,
    this.memo,
    this.status = 'scheduled',
    this.source = 'user',
    this.travelTimeMinutes,
  });

  factory ScheduleModel.fromJson(Map<String, dynamic> json) {
    return ScheduleModel(
      // id 는 어떤 타입이 와도 문자열로 보존한다.
      id: json['id']?.toString() ?? '',
      title: (json['title'] ?? '').toString(),
      date: json['date'] as String?,
      startTime: json['start_time'] as String?,
      endTime: json['end_time'] as String?,
      category: json['category'] as String?,
      priority: (json['priority'] ?? 'medium').toString(),
      location: json['location'] as String?,
      memo: json['memo'] as String?,
      status: (json['status'] ?? 'scheduled').toString(),
      source: (json['source'] ?? 'user').toString(),
      travelTimeMinutes: json['travel_time_minutes'] as int?,
    );
  }
}
