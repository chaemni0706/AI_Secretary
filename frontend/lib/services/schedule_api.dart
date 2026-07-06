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

  /// 백엔드가 상태(성공/부분/실패)에 맞춰 내려주는 음성 안내 문장.
  /// 없을 수 있으므로(구버전 호환) 화면에서 fallback 을 마련한다.
  final String? ttsText;

  const ParseResult({
    required this.intent,
    required this.confidence,
    required this.scheduleDraft,
    this.missingFields = const [],
    this.ttsText,
  });

  bool get isTodo => intent == 'create_todo';

  /// 등록 가능한 유효 일정인지(제목 있고, 날짜·시간 누락 아님).
  bool get isRegisterable =>
      intent != 'unknown' &&
      !missingFields.contains('date') &&
      !missingFields.contains('time') &&
      (scheduleDraft['title']?.toString().trim().isNotEmpty ?? false);

  factory ParseResult.fromJson(Map<String, dynamic> json) {
    final draft = (json['schedule_draft'] as Map?)?.cast<String, dynamic>() ??
        <String, dynamic>{};
    final missing = (json['missing_fields'] as List?) ?? const [];
    final tts = json['tts_text'];
    return ParseResult(
      intent: (json['intent'] ?? 'unknown').toString(),
      confidence: ((json['confidence'] ?? 0) as num).toDouble(),
      scheduleDraft: draft,
      missingFields: missing.map((e) => e.toString()).toList(),
      ttsText: tts == null ? null : tts.toString(),
    );
  }
}

class ScheduleApi {
  /// 1) 자연어 파싱: `POST /api/v1/ai/schedule/parse`
  ///
  /// [inputType] 은 `"text"` 또는 `"voice"`. 음성 비서 화면에서는 `"voice"` 로
  /// 호출하며, 이 경우 백엔드가 draft.source 를 `"voice"` 로 표시하고
  /// 상태에 맞는 `tts_text` 를 함께 내려준다.
  Future<ParseResult> parse(
    String input, {
    String? currentDatetime,
    String timezone = 'Asia/Seoul',
    String inputType = 'text',
    String userId = 'local-user',
    String? assistantTone,
    String? responseLength,
    String? reminderStrength,
  }) async {
    final body = <String, dynamic>{
      'input': input,
      'input_type': inputType,
      'timezone': timezone,
      'user_id': userId,
    };
    if (currentDatetime != null) body['current_datetime'] = currentDatetime;
    // 음성 스타일 preference 를 함께 보내면 백엔드가 그 말투/길이로 tts_text 를
    // 생성한다. 값이 없으면 기존(무스타일) 응답을 그대로 받는다.
    if (assistantTone != null) body['assistant_tone'] = assistantTone;
    if (responseLength != null) body['response_length'] = responseLength;
    if (reminderStrength != null) body['reminder_strength'] = reminderStrength;

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
