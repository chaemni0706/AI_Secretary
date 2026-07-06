import '../data/mock_voice_data.dart';

/// 음성/브리핑/알림 화면들이 공용으로 사용하는 Mock 서비스.
///
/// 실제 HTTP 통신은 하지 않고, `data/mock_voice_data.dart` 의 Mock 을
/// 약간의 지연과 함께 반환한다. 반환 타입은 백엔드 공통 응답
/// `{ success, message, data }` Map 이므로, 추후 실제 API 연결 시
/// 이 클래스 내부만 `apiClient.postData(...)` 호출로 바꾸면 되고
/// 화면 코드는 그대로 유지된다.
///
/// 대응 엔드포인트:
///   - getDailyBriefing   → POST /api/v1/briefings/daily
///   - getEmotionCoaching → POST /api/v1/emotion/analyze
///   - getMockCallAlert   → POST /api/v1/alerts/departure-plan
///   - requestTts         → POST /api/v1/voice/tts
class MockVoiceService {
  /// 네트워크 지연을 흉내내는 가짜 딜레이.
  static const Duration _fakeLatency = Duration(milliseconds: 600);

  /// 하루 브리핑 Mock 응답(`{success, message, data}`) 반환.
  Future<Map<String, dynamic>> getDailyBriefing({String? date}) async {
    await Future.delayed(_fakeLatency);
    // TODO(backend): apiClient.postData('$apiPrefix/briefings/daily', body: {...})
    return mockDailyBriefing;
  }

  /// 감정 기반 코칭 Mock 응답 반환.
  /// [text] 는 사용자의 발화/입력이며, 이번 단계에서는 응답에 영향을 주지 않는다.
  ///
  /// [userContext]/[voice] 는 말투/음성 설정 계약 필드다. 현재 Mock 은 무시하지만,
  /// 실제 `/emotion/analyze` 연결 시 아래 TODO 의 body 에 그대로 넣으면 된다.
  Future<Map<String, dynamic>> getEmotionCoaching(
    String text, {
    Map<String, dynamic>? userContext,
    Map<String, dynamic>? voice,
  }) async {
    await Future.delayed(_fakeLatency);
    // TODO(backend): apiClient.postData('$apiPrefix/emotion/analyze', body: {
    //   'input': text, 'user_context': userContext, 'voice': voice })
    return mockEmotionAnalyze;
  }

  /// 가짜 전화 알림 계획 Mock 응답 반환.
  Future<Map<String, dynamic>> getMockCallAlert({String? scheduleId}) async {
    await Future.delayed(_fakeLatency);
    // TODO(backend): apiClient.postData('$apiPrefix/alerts/departure-plan', body: {...})
    return mockCallAlert;
  }

  /// TTS Mock 응답 반환. 실제 음성 파일은 생성하지 않고 재생할 문장만 담는다.
  /// [source] 는 호출 맥락(예: chatbot_reply, briefing, call_alert) 구분용.
  Future<Map<String, dynamic>> requestTts(
    String text, {
    String source = "chatbot_reply",
  }) async {
    await Future.delayed(const Duration(milliseconds: 200));
    // TODO(backend): apiClient.postData('$apiPrefix/voice/tts', body: {'text': text, 'source': source})
    return mockTtsResponse(text);
  }
}

/// 간편 접근용 전역 인스턴스(기존 `*_api` 싱글턴 패턴과 동일).
final mockVoiceService = MockVoiceService();
