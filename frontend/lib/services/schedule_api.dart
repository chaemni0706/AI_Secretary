import '../models/schedule_model.dart';
import 'api_client.dart';

/// `POST /api/v1/ai/schedule/parse` 결과.
///
/// 일정/할 일 구분은 **`intent`** 로 판단한다. ( `item_type` 필드는 없음 )
/// `scheduleDraft` 는 from-draft 요청에 그대로 넣을 수 있는 Map 이다.
class ParseResult {
  final String intent; // create_schedule | create_todo | ...
  final double confidence;
  final Map<String, dynamic> scheduleDraft;
  final List<String> missingFields;

  const ParseResult({
    required this.intent,
    required this.confidence,
    required this.scheduleDraft,
    this.missingFields = const [],
  });

  bool get isTodo => intent == 'create_todo';

  factory ParseResult.fromJson(Map<String, dynamic> json) {
    final draft = (json['schedule_draft'] as Map?)?.cast<String, dynamic>() ??
        <String, dynamic>{};
    final missing = (json['missing_fields'] as List?) ?? const [];
    return ParseResult(
      intent: (json['intent'] ?? 'unknown').toString(),
      confidence: ((json['confidence'] ?? 0) as num).toDouble(),
      scheduleDraft: draft,
      missingFields: missing.map((e) => e.toString()).toList(),
    );
  }
}

class ScheduleApi {
  /// 1) 자연어 파싱: `POST /api/v1/ai/schedule/parse`
  Future<ParseResult> parse(
    String input, {
    String? currentDatetime,
    String timezone = 'Asia/Seoul',
  }) async {
    final body = <String, dynamic>{
      'input': input,
      'input_type': 'text',
      'timezone': timezone,
    };
    if (currentDatetime != null) body['current_datetime'] = currentDatetime;

    final data = await apiClient.postData(
      '$apiPrefix/ai/schedule/parse',
      body: body,
    );
    return ParseResult.fromJson(data as Map<String, dynamic>);
  }

  /// 2) 일정 저장: `POST /api/v1/local/schedules/from-draft`
  Future<ScheduleModel> createFromDraft(
    Map<String, dynamic> scheduleDraft, {
    String? intent,
  }) async {
    final data = await apiClient.postData(
      '$apiPrefix/local/schedules/from-draft',
      body: {
        'schedule_draft': scheduleDraft,
        if (intent != null) 'intent': intent,
      },
    );
    return ScheduleModel.fromJson(data as Map<String, dynamic>);
  }

  /// 직접 생성: `POST /api/v1/local/schedules`
  Future<ScheduleModel> create(Map<String, dynamic> payload) async {
    final data = await apiClient.postData(
      '$apiPrefix/local/schedules',
      body: payload,
    );
    return ScheduleModel.fromJson(data as Map<String, dynamic>);
  }

  /// 목록: `GET /api/v1/local/schedules`
  Future<List<ScheduleModel>> list({String? date}) async {
    final data = await apiClient.getData(
      '$apiPrefix/local/schedules',
      query: date != null ? {'date': date} : null,
    );
    final list = (data as List?) ?? const [];
    return list
        .map((e) => ScheduleModel.fromJson(e as Map<String, dynamic>))
        .toList();
  }
}

final scheduleApi = ScheduleApi();
