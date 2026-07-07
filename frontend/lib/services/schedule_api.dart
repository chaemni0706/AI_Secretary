import '../models/schedule_model.dart';
import 'api_client.dart';
import 'local_schedule_parser.dart';
import 'schedule_draft_mapper.dart';

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

  /// 파싱 출처: "server"(기본) 또는 "on_device"(오프라인 로컬 파서 fallback).
  /// 화면/로그에서 신뢰 수준을 구분하는 용도. 기존 코드는 몰라도 무방하다.
  final String source;

  const ParseResult({
    required this.intent,
    required this.confidence,
    required this.scheduleDraft,
    this.missingFields = const [],
    this.ttsText,
    this.source = 'server',
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

    try {
      final data = await apiClient.postData(
        '$apiPrefix/ai/schedule/parse',
        body: body,
      );
      return ParseResult.fromJson(data as Map<String, dynamic>);
    } on ApiException catch (e) {
      // 서버 미도달(오프라인/타임아웃)일 때만 온디바이스 파서로 fallback 한다.
      // 4xx/5xx(서버가 응답한 경우)는 그대로 전달(잘못된 요청 등 원인 노출).
      if (e.isNetworkError) {
        return LocalScheduleParser.parse(input, inputType: inputType);
      }
      rethrow;
    }
  }

  /// 2) 일정 저장: `POST /api/v1/local/schedules/from-draft`
  ///
  /// 서버 draft 든 (향후) 온디바이스 parser draft 든 [ScheduleDraftMapper.normalize]
  /// 로 동일하게 정규화한 뒤 저장한다. 필드가 일부 비어도 기본값으로 안전 처리된다.
  ///
  /// [inputType] 은 source 추론용("voice"면 source="voice"). [preventDuplicate]
  /// 가 true 면 같은 날짜의 기존 일정을 조회해 (날짜+시작시간+제목) 중복이면
  /// [ApiException]("이미 같은 일정이 있어요.") 을 던진다(기본값 false = 기존 동작).
  Future<ScheduleModel> createFromDraft(
    Map<String, dynamic> scheduleDraft, {
    String? intent,
    String inputType = 'text',
    bool preventDuplicate = false,
  }) async {
    final normalized = ScheduleDraftMapper.normalize(
      scheduleDraft,
      intent: intent,
      inputType: inputType,
    );

    if (preventDuplicate) {
      final date = normalized['date'] as String?;
      if (date != null && date.isNotEmpty) {
        try {
          final existing = await list(date: date);
          if (ScheduleDraftMapper.isDuplicate(normalized, existing)) {
            throw ApiException('이미 같은 일정이 있어요.');
          }
        } on ApiException {
          rethrow; // 중복 경고는 그대로 전달
        } catch (_) {
          // 목록 조회 실패는 저장을 막지 않는다(중복 검사만 건너뜀).
        }
      }
    }

    final data = await apiClient.postData(
      '$apiPrefix/local/schedules/from-draft',
      body: {
        'schedule_draft': normalized,
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

  /// 수정: `PATCH /api/v1/local/schedules/{id}`
  ///
  /// 백엔드 `ScheduleUpdate` 스키마는 모든 필드가 optional(부분 수정) 이므로,
  /// [payload] 에는 바뀐 필드만 담아 보내면 된다. null 값은 "비우기"가 아니라
  /// 백엔드에서 무시되도록 호출부에서 걸러 담는 것을 권장한다.
  /// 응답은 수정된 일정 전체(`ScheduleModel`)다.
  Future<ScheduleModel> update(String id, Map<String, dynamic> payload) async {
    final data = await apiClient.patchData(
      '$apiPrefix/local/schedules/$id',
      body: payload,
    );
    return ScheduleModel.fromJson(data as Map<String, dynamic>);
  }

  /// 삭제: `DELETE /api/v1/local/schedules/{id}`
  Future<void> delete(String id) async {
    await apiClient.deleteData('$apiPrefix/local/schedules/$id');
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
