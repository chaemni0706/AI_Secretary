import 'package:flutter/foundation.dart';

import '../models/voice_chat_message.dart';
import 'api_client.dart';
import 'local_emotion.dart';

/// 감정 코칭 API 클라이언트 (`POST /api/v1/emotion/analyze`).
///
/// 스키마 주의(문서화된 한계):
///   실제 백엔드 `/emotion/analyze` 응답은
///     { sentiment, emotion, emotion_score, risk_level, coaching, recommended_actions }
///   로, 화면이 쓰는 리치 모델([EmotionAnalysis]: burden/empathy_strategy/
///   coaching_reply/schedule_suggestions/tts_text/safety_note)과 다르다.
///   따라서 여기서 **어댑터**로 매핑한다. 서버가 제공하지 않는
///   schedule_suggestions 는 빈 리스트가 된다(화면은 비었을 때 카드를 숨김).
///
/// 안전: 이 메서드는 예외를 던지지 않는다. 어떤 실패든 온디바이스 공감
/// fallback([LocalEmotion])으로 대체해 앱이 죽지 않게 한다.
class EmotionApi {
  Future<EmotionAnalysis> analyze(
    String text, {
    String inputType = 'text',
    List<Map<String, dynamic>>? todaySchedule,
    Map<String, dynamic>? userContext,
    Map<String, dynamic>? voice,
    String? date,
  }) async {
    try {
      final data = await apiClient.postData(
        '$apiPrefix/emotion/analyze',
        body: {
          'input': text,
          // 아래는 계약/확장 필드. 서버가 미소비여도 무해(미지 필드 무시).
          'input_type': inputType,
          if (date != null) 'date': date,
          if (todaySchedule != null) 'today_schedule': todaySchedule,
          if (userContext != null) 'user_context': userContext,
          if (voice != null) 'voice': voice,
        },
      );
      if (data is Map<String, dynamic>) {
        return _adapt(data, fallbackText: text);
      }
      return LocalEmotion.analyze(text);
    } on ApiException catch (e) {
      // 오프라인이든 서버 오류든, 감정 흐름은 크래시 없이 공감 fallback 으로.
      debugPrint('EmotionApi.analyze fallback (${e.isNetworkError ? "network" : "server ${e.statusCode}"}): ${e.message}');
      return LocalEmotion.analyze(text);
    } catch (e) {
      debugPrint('EmotionApi.analyze unexpected fallback: $e');
      return LocalEmotion.analyze(text);
    }
  }

  /// 실제 응답(단순 스키마) → 화면용 리치 [EmotionAnalysis] 매핑.
  EmotionAnalysis _adapt(Map<String, dynamic> d, {required String fallbackText}) {
    final emotionRaw = (d['emotion'] ?? 'neutral').toString();
    final score = ((d['emotion_score'] ?? 0) as num).toDouble();
    final risk = (d['risk_level'] ?? 'low').toString();
    final coaching = (d['coaching'] ?? '').toString().trim();

    final intensity = score >= 0.66 ? 'high' : (score >= 0.33 ? 'medium' : 'low');
    final reply = coaching.isNotEmpty ? coaching : '이야기해 주셔서 고마워요.';

    // risk 가 high 일 때만 비진단적 안전 안내를 덧붙인다.
    final safety = risk == 'high'
        ? '많이 힘드시면 혼자 견디지 마시고, 자살예방상담전화 109 등 전문 상담의 도움을 받아보세요.'
        : '';

    return EmotionAnalysis(
      emotion: Emotion(label: _labelKo(emotionRaw), intensity: intensity, confidence: score),
      burden: Burden(level: risk, reason: ''),
      empathyStrategy: const EmpathyStrategy(type: 'support', description: ''),
      coachingReply: reply,
      // 실제 /emotion/analyze 는 일정 추천을 제공하지 않음 → 빈 리스트.
      scheduleSuggestions: const [],
      ttsText: reply,
      safetyNote: safety,
    );
  }

  String _labelKo(String raw) {
    const map = {
      'fatigue': '피로',
      'anxiety': '불안',
      'sadness': '슬픔',
      'anger': '화남',
      'stress': '스트레스',
      'positive': '긍정',
      'neutral': '평온',
    };
    return map[raw] ?? raw;
  }
}

final emotionApi = EmotionApi();
