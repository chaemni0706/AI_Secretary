import 'package:flutter/foundation.dart';

import 'on_device_model_service.dart';

/// intent 분류 실험 서비스 (TFLite 모델 → rule-based fallback).
///
/// 라벨: create_schedule | create_todo | ask_briefing | emotion_coaching |
///       reservation_request | unknown
///
/// 동작:
///  - [OnDeviceModelService.enableOnDeviceModel] 이 true 이고 모델이 로드/추론에
///    성공하며 confidence 가 임계값 이상이면 모델 결과를 사용한다.
///  - 그 외(비활성/모델 없음/로드 실패/추론 실패/낮은 confidence)에는 rule-based
///    분류로 fallback 한다. 절대 예외를 던지지 않는다.
///
/// 이 서비스는 **실험용**이며, 현재 앱 화면들은 이 서비스에 의존하지 않는다.
class IntentClassifierService {
  IntentClassifierService._();
  static final IntentClassifierService instance = IntentClassifierService._();

  static const List<String> labels = [
    'create_schedule',
    'create_todo',
    'ask_briefing',
    'emotion_coaching',
    'reservation_request',
    'unknown',
  ];

  Future<ClassifierResult> classify(String text) async {
    final input = _preprocess(text);

    // 1) 모델 경로(실험). 스텁이라 현재는 항상 null → rule fallback.
    try {
      final interpreter = await onDeviceModelService
          .tryLoadInterpreter(OnDeviceModelService.intentModelAsset);
      if (interpreter != null) {
        // TODO(tflite): 토크나이즈 → 추론 → argmax(label, confidence).
        // final r = _runModel(interpreter, input);
        // if (r.confidence >= OnDeviceModelService.minConfidence) return r;
        // (낮으면 아래 rule fallback 으로 진행)
      }
    } catch (e) {
      debugPrint('[IntentClassifier] model 추론 실패 → rule fallback: $e');
    }

    // 2) rule-based fallback.
    return _ruleClassify(input);
  }

  /// 전처리: trim + 소문자화(영문). 한국어는 형태소 분석 없이 키워드 매칭 기반.
  String _preprocess(String text) => text.trim().toLowerCase();

  ClassifierResult _ruleClassify(String t) {
    // 우선순위: 예약 > 브리핑 > 감정 > 할 일 > 일정 > unknown.
    if (_hasAny(t, const ['예약', '예약해', '예약 잡'])) {
      return const ClassifierResult(
          label: 'reservation_request', confidence: 0.6, source: 'rule');
    }
    if (_hasAny(t, const ['브리핑', '오늘 일정 알려', '오늘 뭐 있', '일정 요약'])) {
      return const ClassifierResult(
          label: 'ask_briefing', confidence: 0.6, source: 'rule');
    }
    if (_hasAny(t, const [
      '힘들', '지쳐', '지쳤', '피곤', '불안', '걱정', '우울', '슬퍼', '짜증', '화나', '번아웃', '스트레스'
    ])) {
      return const ClassifierResult(
          label: 'emotion_coaching', confidence: 0.55, source: 'rule');
    }
    if (_hasAny(t, const ['제출', '과제', '마감', '까지', '장보기', '사와', '작성']) &&
        !_hasAny(t, const ['회의', '약속', '병원', '수업', '예약'])) {
      return const ClassifierResult(
          label: 'create_todo', confidence: 0.55, source: 'rule');
    }
    // 시간/날짜/일정 단서가 있으면 일정 생성으로 본다.
    if (_hasAny(t, const [
      '시', '오늘', '내일', '모레', '요일', '회의', '미팅', '약속', '병원', '수업', '운동'
    ])) {
      return const ClassifierResult(
          label: 'create_schedule', confidence: 0.5, source: 'rule');
    }
    return const ClassifierResult(label: 'unknown', confidence: 0.3, source: 'rule');
  }

  bool _hasAny(String t, List<String> ks) => ks.any(t.contains);
}

final intentClassifierService = IntentClassifierService.instance;
