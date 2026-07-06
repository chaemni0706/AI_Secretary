import 'package:flutter/foundation.dart';

import '../models/voice_chat_message.dart';

/// 서버 `/emotion/analyze` 실패 시 사용하는 온디바이스 공감 fallback.
///
/// 원칙(안전 최우선):
///  - 의학적 진단처럼 보이는 표현을 절대 쓰지 않는다(우울증/장애/진단/처방 등 금지).
///  - 위기 신호(자해/극단적 표현)가 감지되면 분석을 생략하고 **고정 안전 문구**를
///    사용한다.
///  - 서버와 동일한 [EmotionAnalysis] 형태로 돌려주어 화면 코드를 그대로 재사용한다.
///  - schedule_suggestions 는 로컬에서 만들지 않는다(빈 리스트).
class LocalEmotion {
  /// 위기 신호 키워드(고정 안전 문구로 대응).
  static const _crisis = [
    '죽고 싶', '죽고싶', '자해', '사라지고 싶', '사라지고싶', '살기 싫', '살기싫',
    '없어지고 싶', '없어지고싶',
  ];

  /// 감정 키워드(라벨만; 출력 문구는 비진단적으로 유지).
  static const Map<String, List<String>> _emotionKeywords = {
    'fatigue': ['피곤', '지쳐', '지친', '힘들', '졸려', '기운 없'],
    'anxiety': ['불안', '걱정', '초조', '긴장'],
    'sadness': ['슬프', '슬퍼', '눈물', '외로', '허전'],
    'anger': ['화가', '짜증', '화나', '분노', '억울'],
    'stress': ['스트레스', '부담', '벅차', '압박', '바빠'],
    'positive': ['좋아', '행복', '기뻐', '설레', '뿌듯', '즐거'],
  };

  static const Map<String, String> _labelKo = {
    'fatigue': '피로',
    'anxiety': '불안',
    'sadness': '슬픔',
    'anger': '화남',
    'stress': '스트레스',
    'positive': '긍정',
    'neutral': '평온',
  };

  /// 비진단적 공감 문구 템플릿.
  static const Map<String, String> _reply = {
    'fatigue': '많이 지치셨겠어요. 잠깐이라도 숨 고르는 시간을 가져보는 건 어떨까요?',
    'anxiety': '마음이 불안하셨겠어요. 지금 느끼는 감정을 천천히 살펴봐도 괜찮아요.',
    'sadness': '많이 속상하셨겠어요. 그런 마음이 드는 건 자연스러운 일이에요.',
    'anger': '화가 날 만한 일이 있으셨군요. 잠시 마음을 가라앉힐 여유를 가져보세요.',
    'stress': '할 일이 많아 부담되셨겠어요. 하나씩 나눠서 가볍게 시작해봐요.',
    'positive': '좋은 기분이 느껴져요. 그 기분을 오늘 하루 이어가시길 바라요.',
    'neutral': '이야기해 주셔서 고마워요. 지금 마음을 편하게 나눠주세요.',
  };

  /// 위기 상황용 고정 안전 문구(진단/단정 없이 지지 + 도움 안내).
  static const String _crisisReply =
      '지금 많이 힘드신 것 같아요. 혼자 견디지 않으셔도 괜찮아요. '
      '가까운 사람에게 마음을 나누거나, 24시간 상담이 필요하면 자살예방상담전화 109 로 '
      '연락해 이야기해 보시면 좋겠어요.';

  static EmotionAnalysis analyze(String text) {
    final t = text.trim();
    try {
      // 1) 위기 신호 우선 처리(고정 안전 문구).
      if (_crisis.any(t.contains)) {
        return _build(
          label: 'sadness',
          intensity: 'high',
          burdenLevel: 'high',
          reply: _crisisReply,
          safetyNote: '위기 신호가 감지되어 안전 안내를 우선 표시했어요. '
              '전문 상담(자살예방상담전화 109)의 도움을 받아보세요.',
        );
      }

      // 2) 키워드 감정 분류(첫 매칭).
      String label = 'neutral';
      for (final e in _emotionKeywords.entries) {
        if (e.value.any(t.contains)) {
          label = e.key;
          break;
        }
      }
      final intensity = label == 'neutral' ? 'low' : 'medium';
      return _build(
        label: label,
        intensity: intensity,
        burdenLevel: intensity,
        reply: _reply[label] ?? _reply['neutral']!,
        safetyNote: '',
      );
    } catch (e) {
      debugPrint('LocalEmotion error: $e');
      return _build(
        label: 'neutral',
        intensity: 'low',
        burdenLevel: 'low',
        reply: _reply['neutral']!,
        safetyNote: '',
      );
    }
  }

  static EmotionAnalysis _build({
    required String label,
    required String intensity,
    required String burdenLevel,
    required String reply,
    required String safetyNote,
  }) {
    return EmotionAnalysis(
      emotion: Emotion(
        label: _labelKo[label] ?? label,
        intensity: intensity,
        confidence: 0.5,
      ),
      burden: Burden(level: burdenLevel, reason: '기기에서 임시로 분석한 결과예요.'),
      empathyStrategy:
          const EmpathyStrategy(type: 'support', description: '지지/공감'),
      coachingReply: reply,
      scheduleSuggestions: const [],
      ttsText: reply,
      safetyNote: safetyNote,
    );
  }
}
