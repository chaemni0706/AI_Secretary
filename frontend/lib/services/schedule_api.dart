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

  /// 파싱 출처(예: 'on_device_rule' = 오프라인 기기 파서). 백엔드 응답에는
  /// 없을 수 있어 nullable. scheduleDraft['source'](저장용 source)와는 별개다.
  final String? source;

  const ParseResult({
    required this.intent,
    required this.confidence,
    required this.scheduleDraft,
    this.missingFields = const [],
    this.ttsText,
    this.source,
  });

  bool get isTodo => intent == 'create_todo';

  /// 등록 가능한 유효 일정인지(제목 있고, 날짜·시간 누락 아님).
  bool get isRegisterable =>
      intent != 'unknown' &&
      !missingFields.contains('date') &&
      !missingFields.contains('time') &&
      (scheduleDraft['title']?.toString().trim().isNotEmpty ?? false);

  factory ParseResult.fromJson(Map<String, dynamic> json) {
    final draft =
        (json['schedule_draft'] as Map?)?.cast<String, dynamic>() ??
        <String, dynamic>{};
    final missing = (json['missing_fields'] as List?) ?? const [];
    final tts = json['tts_text'];
    return ParseResult(
      intent: (json['intent'] ?? 'unknown').toString(),
      confidence: ((json['confidence'] ?? 0) as num).toDouble(),
      scheduleDraft: draft,
      missingFields: missing.map((e) => e.toString()).toList(),
      ttsText: tts == null ? null : tts.toString(),
      source: json['source']?.toString(),
    );
  }
}

class ScheduleApi {
  // --- 전체 목록(날짜 미지정) 캐시 -------------------------------------------
  // 콜드 스타트 시 main() 과 CalendarScreen 이 거의 동시에 list() 를 호출한다.
  // 진행 중 요청을 공유(in-flight dedup)해 중복 네트워크 호출을 없애고, 짧은
  // TTL 캐시로 연속 호출을 재사용한다. 캐시는 생성/수정/삭제 시 무효화한다.
  static const Duration _cacheTtl = Duration(seconds: 30);
  List<ScheduleModel>? _cachedAll;
  DateTime? _cachedAt;
  Future<List<ScheduleModel>>? _inFlightAll;

  /// 캐시된 전체 목록(있으면 즉시 반환, 없으면 null). UI 즉시 표시용.
  List<ScheduleModel>? get cachedAll => _cachedAll;

  /// 캐시 무효화(일정 변경 후 호출).
  void invalidateCache() {
    _cachedAll = null;
    _cachedAt = null;
  }

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
    invalidateCache();
    return ScheduleModel.fromJson(data as Map<String, dynamic>);
  }

  /// 직접 생성: `POST /api/v1/local/schedules`
  Future<ScheduleModel> create(Map<String, dynamic> payload) async {
    final data = await apiClient.postData(
      '$apiPrefix/local/schedules',
      body: payload,
    );
    invalidateCache();
    return ScheduleModel.fromJson(data as Map<String, dynamic>);
  }

  /// 일정 수정: `PATCH /api/v1/local/schedules/{id}`
  Future<ScheduleModel> update(
    String scheduleId,
    Map<String, dynamic> payload,
  ) async {
    final data = await apiClient.patchData(
      '$apiPrefix/local/schedules/$scheduleId',
      body: payload,
    );
    invalidateCache();
    return ScheduleModel.fromJson(data as Map<String, dynamic>);
  }

  /// 일정 삭제: `DELETE /api/v1/local/schedules/{id}`
  Future<void> delete(String scheduleId) async {
    await apiClient.deleteData('$apiPrefix/local/schedules/$scheduleId');
    invalidateCache();
  }

  /// 목록: `GET /api/v1/local/schedules`
  ///
  /// [date] 미지정(전체 목록)일 때만 캐시/dedup 을 적용한다. [forceRefresh] 로
  /// 캐시를 건너뛰고 서버를 다시 조회할 수 있다(당겨서 새로고침 등).
  Future<List<ScheduleModel>> list({String? date, bool forceRefresh = false}) {
    if (date != null) return _fetch(date: date);

    if (!forceRefresh) {
      final at = _cachedAt;
      if (_cachedAll != null &&
          at != null &&
          DateTime.now().difference(at) < _cacheTtl) {
        return Future.value(_cachedAll!);
      }
      // 이미 진행 중인 동일 요청이 있으면 그 Future 를 공유한다.
      final pending = _inFlightAll;
      if (pending != null) return pending;
    }

    final future = _fetch().then((schedules) {
      _cachedAll = schedules;
      _cachedAt = DateTime.now();
      return schedules;
    }).whenComplete(() => _inFlightAll = null);
    _inFlightAll = future;
    return future;
  }

  Future<List<ScheduleModel>> _fetch({String? date}) async {
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
