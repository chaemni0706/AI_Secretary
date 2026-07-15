import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/services/local_emotion_classifier.dart';
import 'package:frontend/models/voice_chat_message.dart';

/// LocalEmotionClassifier 단위 테스트.
/// 실행: `flutter test test/local_emotion_classifier_test.dart`
void main() {
  EmotionAnalysis c(String s) => LocalEmotionClassifier.classify(s);

  // 진단성 표현이 코칭/안전 문구에 절대 없어야 한다.
  const forbidden = ['우울증', '불안장애', '장애', '진단', '처방', '질환', '환자'];
  void assertNoDiagnosis(EmotionAnalysis r) {
    for (final w in forbidden) {
      expect(r.coachingReply.contains(w), isFalse, reason: '코칭에 진단성 표현: $w');
      expect(r.safetyNote.contains(w), isFalse, reason: '안전문구에 진단성 표현: $w');
    }
  }

  group('감정 분류', () {
    test('피로(강조) → 피로/high', () {
      final r = c('요즘 너무 힘들고 지쳤어');
      expect(r.emotion.label, '피로');
      expect(r.emotion.intensity, 'high');
      expect(r.empathyStrategy.type, 'rest');
      expect(r.source, 'on_device_rule');
      expect(r.ttsText.isNotEmpty, isTrue);
      assertNoDiagnosis(r);
    });

    test('불안 → 불안/medium', () {
      final r = c('내일 발표 때문에 불안해');
      expect(r.emotion.label, '불안');
      expect(r.emotion.intensity, 'medium');
      expect(r.empathyStrategy.type, 'ground');
      assertNoDiagnosis(r);
    });

    test('짜증(강조) → 화남/high', () {
      final r = c('진짜 짜증나 답답해');
      expect(r.emotion.label, '화남');
      expect(r.emotion.intensity, 'high');
      expect(r.empathyStrategy.type, 'calm');
    });

    test('일정 부담 → 부담/burden high/pace', () {
      final r = c('할 일이 너무 많아 못 하겠어');
      expect(r.emotion.label, '부담');
      expect(r.burden.level, 'high');
      expect(r.empathyStrategy.type, 'pace');
      assertNoDiagnosis(r);
    });

    test('감정 없는 일반 문장 → 평온/low', () {
      final r = c('오늘 점심 뭐 먹지');
      expect(r.emotion.label, '평온');
      expect(r.emotion.intensity, 'low');
      expect(r.burden.level, 'low');
      expect(r.safetyNote, isEmpty);
    });

    test('피곤해 → 피로/medium', () {
      final r = c('피곤해');
      expect(r.emotion.label, '피로');
      expect(r.emotion.intensity, 'medium');
    });
  });

  group('위기 표현', () {
    test('"사라지고 싶어" → 고정 안전문구 + safetyNote', () {
      final r = c('그냥 다 사라지고 싶어');
      expect(r.safetyNote.isNotEmpty, isTrue);
      expect(r.empathyStrategy.type, 'safety');
      expect(r.coachingReply.contains('109'), isTrue); // 상담 안내 포함
      assertNoDiagnosis(r);
    });

    test('"죽고 싶어" → 위기 처리(일반 코칭 아님)', () {
      final r = c('죽고 싶어');
      expect(r.safetyNote.isNotEmpty, isTrue);
      expect(r.empathyStrategy.type, 'safety');
      assertNoDiagnosis(r);
    });
  });

  group('안전성', () {
    test('빈/이상 입력도 예외 없이 처리', () {
      expect(() => c(''), returnsNormally);
      expect(() => c('!!!###'), returnsNormally);
      expect(c('').source, 'on_device_rule');
    });
  });
}
