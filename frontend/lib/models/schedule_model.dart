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

  /// 기간 일정의 종료일("YYYY-MM-DD"). 단일(하루) 일정이면 null.
  ///
  /// 백엔드가 아직 end_date 컬럼을 내려주지 않는 경우를 위해, [memo] 안의
  /// `end_date: YYYY-MM-DD` 규칙에서도 읽어올 수 있도록 [effectiveEndDate] 를
  /// 제공한다(기존 캘린더 렌더링이 쓰던 memo 규칙과 하위 호환).
  final String? endDate;

  final String? startTime;
  final String? endTime;
  final String? category;
  final String priority; // low | medium | high
  final String? location;
  final String? memo;
  final String status;
  final String source;
  final bool isAllDay;
  final int? travelTimeMinutes;

  const ScheduleModel({
    required this.id,
    required this.title,
    this.date,
    this.endDate,
    this.startTime,
    this.endTime,
    this.category,
    this.priority = 'medium',
    this.location,
    this.memo,
    this.status = 'scheduled',
    this.source = 'user',
    this.isAllDay = false,
    this.travelTimeMinutes,
  });

  factory ScheduleModel.fromJson(Map<String, dynamic> json) {
    return ScheduleModel(
      // id 는 어떤 타입이 와도 문자열로 보존한다.
      id: json['id']?.toString() ?? '',
      title: (json['title'] ?? '').toString(),
      date: json['date'] as String?,
      endDate: json['end_date'] as String?,
      startTime: json['start_time'] as String?,
      endTime: json['end_time'] as String?,
      category: json['category'] as String?,
      priority: (json['priority'] ?? 'medium').toString(),
      location: json['location'] as String?,
      memo: json['memo'] as String?,
      status: (json['status'] ?? 'scheduled').toString(),
      source: (json['source'] ?? 'user').toString(),
      isAllDay: json['is_all_day'] == true,
      travelTimeMinutes: json['travel_time_minutes'] as int?,
    );
  }

  /// memo 안의 `end_date: YYYY-MM-DD`(또는 endDate/종료일) 규칙에서 종료일을 읽는다.
  /// 기존 데이터(백엔드에 end_date 컬럼이 없던 일정)와의 하위 호환용.
  static final RegExp _memoEndDatePattern = RegExp(
    r'(?:end_date|endDate|종료일)\s*[:=]\s*(\d{4}-\d{2}-\d{2})',
  );

  /// 실제 사용할 종료일. 우선순위: 서버 [endDate] → memo 규칙 → null.
  String? get effectiveEndDate {
    if (endDate != null && endDate!.trim().isNotEmpty) return endDate;
    return endDateFromMemo(memo);
  }

  /// memo 문자열에서 `end_date: YYYY-MM-DD` 토큰의 날짜만 추출(없으면 null).
  static String? endDateFromMemo(String? memo) {
    final match = _memoEndDatePattern.firstMatch(memo ?? '');
    return match?.group(1);
  }

  /// memo 에서 종료일 토큰(및 주변 빈 줄)을 제거한 "사용자용 순수 메모"를 반환.
  /// 화면 표시·편집 시 기계용 토큰이 보이지 않도록 한다.
  static String stripEndDateToken(String? memo) {
    if (memo == null || memo.isEmpty) return '';
    final cleaned = memo
        .replaceAll(_memoEndDatePattern, '')
        .replaceAll(RegExp(r'\n{2,}'), '\n')
        .trim();
    return cleaned;
  }

  /// 사용자 메모와 종료일을 합쳐 저장용 memo 문자열을 만든다.
  /// [endDate] 가 비어 있으면 순수 메모만 반환(토큰 미부착).
  static String? encodeMemoWithEndDate(String? userMemo, String? endDate) {
    final base = (userMemo ?? '').trim();
    final end = (endDate ?? '').trim();
    if (end.isEmpty) return base.isEmpty ? null : base;
    final token = 'end_date: $end';
    return base.isEmpty ? token : '$base\n$token';
  }

  /// 여러 날에 걸친 기간 일정인지 여부(종료일이 시작일보다 뒤).
  bool get isMultiDay {
    final start = date;
    final end = effectiveEndDate;
    if (start == null || end == null) return false;
    return end.compareTo(start) > 0;
  }

  ScheduleModel copyWith({
    String? title,
    String? date,
    String? endDate,
    String? startTime,
    String? endTime,
    String? category,
    String? priority,
    String? location,
    String? memo,
    bool? isAllDay,
  }) {
    return ScheduleModel(
      id: id,
      title: title ?? this.title,
      date: date ?? this.date,
      endDate: endDate ?? this.endDate,
      startTime: startTime ?? this.startTime,
      endTime: endTime ?? this.endTime,
      category: category ?? this.category,
      priority: priority ?? this.priority,
      location: location ?? this.location,
      memo: memo ?? this.memo,
      status: status,
      source: source,
      isAllDay: isAllDay ?? this.isAllDay,
      travelTimeMinutes: travelTimeMinutes,
    );
  }
}
