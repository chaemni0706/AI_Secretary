import 'api_client.dart';

/// `POST /api/v1/voice/route` 결과.
///
/// 음성 입력(STT 텍스트) 하나를 백엔드가 의도별로 분류해 알맞은 기능(예약/장소
/// 추천, 감정 기반 일정 코칭, 오늘 브리핑, 일정 조회/등록, 알림 설정, 일반 대화)
/// 으로 위임한 뒤 돌려주는 공통 응답이다. `context` 는 다음 발화 요청에 그대로
/// 실어 보내야 하는 "직전 턴" 정보(예: 방금 등록한 일정 id)다.
class ScreenAction {
  final String type; // navigate | show_card | show_bottom_sheet | none
  final String? target;
  final Map<String, dynamic> payload;

  const ScreenAction({
    required this.type,
    this.target,
    this.payload = const {},
  });

  factory ScreenAction.fromJson(Map<String, dynamic>? json) {
    if (json == null) return const ScreenAction(type: 'none');
    return ScreenAction(
      type: (json['type'] ?? 'none').toString(),
      target: json['target']?.toString(),
      payload: Map<String, dynamic>.from(json['payload'] as Map? ?? const {}),
    );
  }
}

class VoiceRouteResult {
  final String intent;
  final String ttsText;
  final ScreenAction screenAction;
  final Map<String, dynamic> data;

  /// 다음 턴 요청에 그대로 되돌려 보내야 하는 pending context (없으면 null).
  final Map<String, dynamic>? context;

  const VoiceRouteResult({
    required this.intent,
    required this.ttsText,
    required this.screenAction,
    required this.data,
    this.context,
  });

  factory VoiceRouteResult.fromJson(Map<String, dynamic> json) {
    return VoiceRouteResult(
      intent: (json['intent'] ?? 'fallback_chat').toString(),
      ttsText: (json['tts_text'] ?? '').toString(),
      screenAction: ScreenAction.fromJson(
        json['screen_action'] as Map<String, dynamic>?,
      ),
      data: Map<String, dynamic>.from(json['data'] as Map? ?? const {}),
      context: json['context'] == null
          ? null
          : Map<String, dynamic>.from(json['context'] as Map),
    );
  }
}

/// 음성 입력 통합 라우팅 API 클라이언트.
///
/// Flutter STT 로 얻은 텍스트를 이 API 하나로 보내면, 일정 등록 전용이 아니라
/// AI 비서의 모든 기능(예약/장소 추천 포함) 중 알맞은 곳으로 서버가 분기해준다.
class VoiceRouterApi {
  Future<VoiceRouteResult> route(
    String text, {
    String userId = 'local-user',
    String? currentDatetime,
    String timezone = 'Asia/Seoul',
    Map<String, dynamic>? context,
    Map<String, dynamic>? location,
    String? assistantTone,
    String? responseLength,
    String? reminderStrength,
  }) async {
    final body = <String, dynamic>{
      'text': text,
      'user_id': userId,
      'timezone': timezone,
    };
    if (currentDatetime != null) body['current_datetime'] = currentDatetime;
    if (context != null) body['context'] = context;
    if (location != null) body['location'] = location;
    if (assistantTone != null) body['assistant_tone'] = assistantTone;
    if (responseLength != null) body['response_length'] = responseLength;
    if (reminderStrength != null) body['reminder_strength'] = reminderStrength;

    final data = await apiClient.postData('$apiPrefix/voice/route', body: body);
    return VoiceRouteResult.fromJson(data as Map<String, dynamic>);
  }

  /// 의도 분류만(부수효과 없음): `POST /api/v1/voice/classify`.
  /// 반환 intent: schedule_create | fallback_chat | emotion_schedule_coaching |
  /// reservation_recommendation | daily_briefing | schedule_query | reminder_setting.
  /// 챗 화면이 '일정 등록'과 '상담/대화'를 분리하는 게이트로 쓴다.
  Future<String> classifyIntent(
    String text, {
    String userId = 'local-user',
    String? currentDatetime,
    String timezone = 'Asia/Seoul',
    Map<String, dynamic>? context,
  }) async {
    final body = <String, dynamic>{
      'text': text,
      'user_id': userId,
      'timezone': timezone,
    };
    if (currentDatetime != null) body['current_datetime'] = currentDatetime;
    if (context != null) body['context'] = context;

    final data = await apiClient.postData(
      '$apiPrefix/voice/classify',
      body: body,
    );
    final m = (data as Map).cast<String, dynamic>();
    return (m['intent'] ?? 'fallback_chat').toString();
  }
}

final voiceRouterApi = VoiceRouterApi();
