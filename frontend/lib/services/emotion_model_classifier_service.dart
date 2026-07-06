import 'package:flutter/foundation.dart';

import '../models/voice_chat_message.dart';
import 'local_emotion_classifier.dart';
import 'on_device_model_service.dart';

/// 감정/부담 분류 실험 서비스 (TFLite 모델 → rule-based fallback).
///
/// ⚠️ 진단 아님: 이 분류는 **UX 보조용 감정 라벨링**이며 의학적/심리적 진단이
/// 아니다. 진단성 표현을 생성하지 않는다.
///
/// 라벨 후보(모델): neutral | tired | anxious | angry | sad | burden_high
///
/// 안전 설계(중요):
///  - 위기 감지·안전문구·코칭 문구는 **항상 rule-based**([LocalEmotionClassifier])가
///    담당한다. ML 모델은 감정 "라벨 정교화"만 보조하며, 위기 판단을 대신하지 않는다.
///  - 모델 비활성/부재/로드 실패/추론 실패/낮은 confidence → rule-based 결과를
///    그대로 사용한다. 예외를 던지지 않는다.
///
/// 현재는 스텁(모델 런타임 미도입)이라 항상 rule-based 결과를 반환한다.
class EmotionModelClassifierService {
  EmotionModelClassifierService._();
  static final EmotionModelClassifierService instance =
      EmotionModelClassifierService._();

  Future<EmotionAnalysis> classify(String text) async {
    // 1) 안전/코칭/위기는 언제나 rule-based 로 먼저 계산(모델과 무관하게 보장).
    final ruleResult = LocalEmotionClassifier.classify(text);

    // 2) (실험) 모델이 있고 신뢰도가 높으면 "감정 라벨"만 정교화.
    try {
      final interpreter = await onDeviceModelService
          .tryLoadInterpreter(OnDeviceModelService.emotionModelAsset);
      if (interpreter != null) {
        // TODO(tflite): 추론 → (label, confidence).
        //  - confidence < min 이면 ruleResult 유지.
        //  - 위기(ruleResult.safetyNote 있음)면 절대 override 하지 않음.
        //  - 그 외에는 라벨만 반영한 EmotionAnalysis 를 만들어 반환하되,
        //    coaching_reply/safety_note 는 rule-based 문구를 유지한다.
      }
    } catch (e) {
      debugPrint('[EmotionModelClassifier] model 추론 실패 → rule fallback: $e');
    }

    // 3) 스텁/미도입/실패/저신뢰 → rule-based 전체 결과 사용.
    return ruleResult;
  }
}

final emotionModelClassifierService = EmotionModelClassifierService.instance;
