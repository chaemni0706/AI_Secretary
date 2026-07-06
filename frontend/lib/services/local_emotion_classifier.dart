import 'package:flutter/foundation.dart';

import '../models/voice_chat_message.dart';

/// 서버 `/emotion/analyze` 실패 시 사용하는 온디바이스 감정/부담 1차 분류기.
///
/// 안전 원칙(반드시 준수):
///  - 의학적/심리적 **진단이 아니다**. "우울증/불안장애" 같은 진단성 표현을
///    생성하지 않는다(감정 라벨은 '슬픔/불안' 같은 일상어만 사용).
///  - 위기 표현(자해/자살/사라지고 싶다 등) 감지 시 일반 코칭을 하지 않고
///    **고정 안전 문구**를 반환한다. 구체적 위험 방법은 절대 언급하지 않는다.
///  - 사용자를 겁주는 과한 표현을 쓰지 않는다.
///  - 서버 응답과 유사한 [EmotionAnalysis] 구조로 반환해 화면 코드를 재사용한다.
///  - 예외를 던지지 않는다(앱 크래시 방지).
///
/// 우선순위: 위기 > 일정 부담(burden_high) > 감정(tired/anxious/sad/angry) > 평온.
class LocalEmotionClassifier {
  static const String kSource = 'on_device_rule';

  // 위기 신호(자해/자살 등). 구체적 방법 언급 없이 신호 키워드만.
  static const _crisis = [
    '자해', '자살', '죽고 싶', '죽고싶', '사라지고 싶', '사라지고싶',
    '살기 싫', '살기싫', '없어지고 싶', '없어지고싶',
  ];

  // 강한 표현(강도 high 로 승격).
  static const _strong = ['너무', '진짜', '완전', '정말', '엄청', '매우', '못 하겠', '못하겠'];

  // 감정 키워드(라벨만; 출력 문구는 비진단적으로 유지).
  static const List<MapEntry<String, List<String>>> _emotionRules = [
    MapEntry('tired', ['힘들', '지쳤', '지쳐', '피곤', '기운 없', '기운없', '번아웃', '녹초']),
    MapEntry('anxious', ['불안', '걱정', '초조', '긴장']),
    MapEntry('sad', ['우울', '슬퍼', '슬프', '울고 싶', '울고싶', '눈물', '외로', '허전']),
    MapEntry('angry', ['짜증', '화나', '화가', '답답', '분노', '억울']),
  ];

  // 일정 부담 표현(burden.level = high).
  static const _burdenHigh = [
    '하기 싫', '하기싫', '미루고 싶', '미루고싶', '너무 많', '못 하겠', '못하겠',
    '시간이 없', '시간 없',
  ];

  static const Map<String, String> _labelKo = {
    'tired': '피로',
    'anxious': '불안',
    'sad': '슬픔',
    'angry': '화남',
    'stress': '부담',
    'neutral': '평온',
  };

  static const Map<String, String> _strategy = {
    'stress': 'pace',
    'tired': 'rest',
    'anxious': 'ground',
    'sad': 'validate',
    'angry': 'calm',
    'neutral': 'listen',
    'crisis': 'safety',
  };

  // 비진단 코칭 문구.
  static const Map<String, String> _coaching = {
    'stress':
        '할 일이 많아 마음이 무거우시죠. 지금은 한 번에 다 하려 하기보다, 20분 정도 쉬고 가장 작은 할 일 하나부터 시작해보는 걸 추천해요.',
    'tired':
        '많이 지친 상태처럼 느껴져요. 지금은 몰아붙이기보다 잠깐 쉬고, 가장 작은 할 일 하나부터 시작해보는 건 어떨까요?',
    'anxious':
        '마음이 불안하게 느껴지시는군요. 크게 숨을 한 번 고르고, 지금 할 수 있는 작은 일 하나에만 집중해보는 걸 추천해요.',
    'sad':
        '마음이 많이 가라앉은 것 같아요. 그런 기분이 드는 건 자연스러운 일이에요. 편한 사람과 잠깐 이야기 나눠보는 건 어떨까요?',
    'angry':
        '많이 답답하고 화가 나셨군요. 잠시 자리에서 벗어나 숨을 고르며 마음을 가라앉힐 시간을 가져보세요.',
    'neutral': '이야기해 주셔서 고마워요. 지금 어떤 마음인지 조금 더 편하게 들려주셔도 좋아요.',
  };

  // 위기 시 고정 안전 문구(생활 코칭 목적, 진단·방법 언급 없음).
  static const String _crisisReply =
      '지금 많이 힘드신 것 같아요. 혼자 견디지 않으셔도 괜찮아요. '
      '가까운 사람에게 지금 마음을 이야기하시거나, 도움이 필요하면 자살예방상담전화 109로 '
      '연락해 이야기 나눠보시길 권해요.';
  static const String _crisisSafetyNote =
      '위기 신호가 감지되어 안전 안내를 먼저 보여드렸어요. 급히 도움이 필요하면 '
      '주변 사람이나 자살예방상담전화 109에 바로 연락해 주세요.';

  /// 텍스트를 분류해 서버 유사 [EmotionAnalysis] 로 반환한다(예외 없음).
  static EmotionAnalysis classify(String text) {
    final t = text.trim();
    try {
      // 1) 위기 우선.
      if (_crisis.any(t.contains)) {
        return _build(
          labelKey: 'sad',
          intensity: 'high',
          confidence: 0.9,
          burdenLevel: 'high',
          strategyKey: 'crisis',
          reply: _crisisReply,
          safetyNote: _crisisSafetyNote,
        );
      }

      // 2) 감정 라벨(첫 매칭).
      String? emo;
      for (final rule in _emotionRules) {
        if (rule.value.any(t.contains)) {
          emo = rule.key;
          break;
        }
      }
      final hasBurden = _burdenHigh.any(t.contains);
      if (emo == null && hasBurden) emo = 'stress';
      emo ??= 'neutral';

      // 3) 강도.
      final strong = _strong.any(t.contains);
      final intensity =
          emo == 'neutral' ? 'low' : (strong ? 'high' : 'medium');

      // 4) 부담 수준.
      final burdenLevel =
          hasBurden ? 'high' : (emo == 'neutral' ? 'low' : 'medium');

      final confidence = strong ? 0.7 : (emo == 'neutral' ? 0.3 : 0.6);

      // 부담 표현이 있으면 pace 코칭을 우선(감정 라벨과 별개로).
      final coachingKey = hasBurden ? 'stress' : emo;

      return _build(
        labelKey: emo,
        intensity: intensity,
        confidence: confidence,
        burdenLevel: burdenLevel,
        strategyKey: hasBurden ? 'stress' : emo,
        reply: _coaching[coachingKey] ?? _coaching['neutral']!,
        safetyNote: '',
      );
    } catch (e) {
      debugPrint('LocalEmotionClassifier error: $e');
      return _build(
        labelKey: 'neutral',
        intensity: 'low',
        confidence: 0.3,
        burdenLevel: 'low',
        strategyKey: 'neutral',
        reply: _coaching['neutral']!,
        safetyNote: '',
      );
    }
  }

  static EmotionAnalysis _build({
    required String labelKey,
    required String intensity,
    required double confidence,
    required String burdenLevel,
    required String strategyKey,
    required String reply,
    required String safetyNote,
  }) {
    return EmotionAnalysis(
      emotion: Emotion(
        label: _labelKo[labelKey] ?? labelKey,
        intensity: intensity,
        confidence: confidence,
      ),
      burden: Burden(level: burdenLevel, reason: '기기에서 임시로 분석한 결과예요.'),
      empathyStrategy: EmpathyStrategy(
        type: _strategy[strategyKey] ?? 'listen',
        description: '',
      ),
      coachingReply: reply,
      // 로컬은 구체 일정 추천을 만들지 않는다(화면은 비었을 때 카드를 숨김).
      scheduleSuggestions: const [],
      ttsText: reply,
      safetyNote: safetyNote,
      source: kSource,
    );
  }
}
