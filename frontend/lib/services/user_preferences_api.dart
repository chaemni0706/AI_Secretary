import 'api_client.dart';

/// GET/PUT /api/v1/user/preferences — AI 음성 응답 스타일 설정
/// (assistant_tone / response_length / nudge_strength). Rule-based, LLM 없음.
///
/// 다른 *_api.dart(notification_api/dashboard_api/todo_api/schedule_api/
/// booking_message_api 등)와 동일하게, `apiClient.getData/postData/patchData/
/// putData` 는 path 에 접두사를 붙이지 않으므로 여기서 `$apiPrefix` 를 직접 포함한다.
class UserPreferencesApi {
  static const String _path = '$apiPrefix/user/preferences';

  /// 현재 설정값 + 화면에 표시할 옵션(code/display_name) 목록을 함께 반환한다.
  /// 반환 형태: { "user_id", "preferences": {...}, "options": {...} }
  static Future<Map<String, dynamic>> fetch({
    String userId = 'local-user',
  }) async {
    final data = await apiClient.getData(_path, query: {'user_id': userId});
    return Map<String, dynamic>.from(data as Map);
  }

  /// 일부 값만 보내도 나머지 값은 서버에 저장된 값을 유지한다.
  /// 반환 형태: { "user_id", "preferences": {...}, "tts_text": "..." }
  ///
  /// [briefingTime] 은 'HH:mm' 자동 브리핑 시각(additive). 빈 문자열("")을
  /// 보내면 비활성화된다 — null 이면(미지정) 기존 값이 그대로 유지된다.
  static Future<Map<String, dynamic>> update({
    String userId = 'local-user',
    String? assistantTone,
    String? responseLength,
    String? nudgeStrength,
    String? briefingTime,
  }) async {
    final body = <String, dynamic>{'user_id': userId};
    if (assistantTone != null) body['assistant_tone'] = assistantTone;
    if (responseLength != null) body['response_length'] = responseLength;
    if (nudgeStrength != null) body['nudge_strength'] = nudgeStrength;
    if (briefingTime != null) body['briefing_time'] = briefingTime;

    final data = await apiClient.putData(_path, body: body);
    return Map<String, dynamic>.from(data as Map);
  }
}
