import '../models/schedule_model.dart';

/// 서버 `/ai/schedule/parse` 응답의 `schedule_draft`(또는 향후 온디바이스
/// parser 결과)를 로컬 저장(`/local/schedules/from-draft`) 요청용 Map 으로
/// 정규화하는 어댑터.
///
/// 설계 목표:
///  - 서버 draft 든 온디바이스 parser draft 든 **동일한 함수**([normalize])를
///    거쳐 같은 형태가 되게 한다(저장 함수 재사용).
///  - 일부 필드가 비어도 앱이 죽지 않도록 안전한 기본값을 채운다.
///  - 백엔드 스키마(`ScheduleDraftInput`)를 바꾸지 않고 그 필드명/기본값에 맞춘다.
///
/// 백엔드 계약(변경 금지):
///   title, category, date, start_time, end_time, location, memo,
///   priority(기본 "medium"), source(기본 "ai").
///   ※ id/status/created_at/updated_at 는 서버가 생성하므로 draft 에 넣지 않는다.
class ScheduleDraftMapper {
  static const Set<String> _priorities = {'low', 'medium', 'high'};

  /// draft(서버/온디바이스) → from-draft 요청용 정규화 Map.
  ///
  /// [intent] / [inputType] 은 source 추론에만 쓰인다(값이 이미 있으면 유지).
  ///  - draft.source 있으면 그대로 사용
  ///  - 없으면 inputType=="voice" → "voice", 그 외 → "ai"
  static Map<String, dynamic> normalize(
    Map<String, dynamic> draft, {
    String? intent,
    String inputType = 'text',
  }) {
    String? s(dynamic v) {
      final t = v?.toString().trim();
      return (t == null || t.isEmpty) ? null : t;
    }

    // priority: 소문자 정규화 후 화이트리스트 밖이면 medium.
    var priority = (draft['priority']?.toString().trim().toLowerCase()) ?? 'medium';
    if (!_priorities.contains(priority)) priority = 'medium';

    // source: draft 값 우선, 없으면 입력 경로로 추론.
    final rawSource = s(draft['source']);
    final source = rawSource ?? (inputType == 'voice' ? 'voice' : 'ai');

    // 기간 일정 종료일(end_date). 백엔드 스키마(ScheduleDraftInput)에는 end_date
    // 필드가 없어 그대로 보내면 버려지므로, 기존 캘린더가 이미 인식하는 memo 의
    // `end_date: YYYY-MM-DD` 규칙으로 인코딩해 저장한다(스키마 불변, 하위 호환).
    final date = s(draft['date']);
    final endDate = s(draft['end_date']);
    final userMemo = s(draft['memo']);
    final validEndDate =
        (endDate != null && date != null && endDate.compareTo(date) > 0)
            ? endDate
            : null;
    final memo = ScheduleModel.encodeMemoWithEndDate(userMemo, validEndDate);

    // 백엔드 ScheduleDraftInput 필드만 골라 담는다(알 수 없는 키는 버림).
    final result = <String, dynamic>{
      'title': s(draft['title']) ?? '',
      'category': s(draft['category']),
      'date': date,
      'start_time': s(draft['start_time']),
      'end_time': s(draft['end_time']),
      'location': s(draft['location']),
      'memo': memo,
      'priority': priority,
      'source': source,
    };
    return result;
  }

  /// 저장 전 필수 필드 검증. 반환 리스트가 비어 있으면 저장 가능.
  ///
  /// - 공통: title 필수.
  /// - 일정(EVENT): date 필수(시간은 없으면 종일 일정으로 저장 가능).
  /// - 할 일(TODO): 마감일 없이도 저장 가능하므로 date 는 필수 아님.
  ///
  /// 서버 응답의 `missing_fields` 와 함께 쓰면 이중 안전망이 된다.
  static List<String> missingRequiredFields(
    Map<String, dynamic> draft, {
    required bool isTodo,
  }) {
    final missing = <String>[];
    final title = draft['title']?.toString().trim() ?? '';
    if (title.isEmpty) missing.add('title');
    if (!isTodo) {
      final date = draft['date']?.toString().trim() ?? '';
      if (date.isEmpty) missing.add('date');
    }
    return missing;
  }

  /// 같은 날짜 + 시작시간 + 제목(대소문자/공백 무시)이면 중복으로 본다.
  /// [existing] 은 보통 같은 날짜의 기존 일정 목록.
  static bool isDuplicate(
    Map<String, dynamic> normalizedDraft,
    List<ScheduleModel> existing,
  ) {
    String norm(String? v) => (v ?? '').trim().toLowerCase();
    final d = norm(normalizedDraft['date'] as String?);
    final st = norm(normalizedDraft['start_time'] as String?);
    final ti = norm(normalizedDraft['title'] as String?);
    if (ti.isEmpty) return false;
    for (final e in existing) {
      if (norm(e.date) == d && norm(e.startTime) == st && norm(e.title) == ti) {
        return true;
      }
    }
    return false;
  }
}
