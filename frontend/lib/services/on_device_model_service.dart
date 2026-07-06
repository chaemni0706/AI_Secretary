import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart' show rootBundle;

/// 온디바이스 TFLite/LiteRT 분류 모델 **실험용** 게이트 겸 스텁 로더.
///
/// 위치/역할:
///  - 이 단계는 MVP 필수 기능이 아니다. 실제 앱 동작은 계속 rule-based
///    (LocalScheduleParser / LocalEmotionClassifier)를 사용한다.
///  - 현재는 `tflite_flutter` 패키지를 pubspec 에 **추가하지 않았다**(빌드 무영향).
///    따라서 [tryLoadInterpreter] 는 항상 null 을 반환하고, 모든 분류 서비스는
///    rule-based fallback 으로 동작한다.
///  - 실제 도입 시: pubspec 에 tflite_flutter 추가 + assets 등록 후, 아래
///    TODO 위치에서 Interpreter.fromAsset(...) 를 반환하도록 교체하면 된다.
///
/// 안전 원칙:
///  - 모델 파일이 없거나/등록 안 됐거나/로드 실패해도 예외를 던지지 않는다.
///  - [enableOnDeviceModel] 가 false 면(기본값) 어떤 모델 코드도 실행되지 않는다.
///  - 감정 모델은 **진단이 아니라 UX 보조 분류**다(라벨 정교화 용도).
class OnDeviceModelService {
  OnDeviceModelService._();
  static final OnDeviceModelService instance = OnDeviceModelService._();

  /// 실험 플래그. 기본 false → release/일반 실행에서는 rule-based 만 사용.
  /// 활성화는 debug 빌드에서 이 값을 true 로 바꾸거나, 향후 개발자 설정으로 제어.
  static const bool enableOnDeviceModel = false;

  /// 모델 자산 경로(실제 파일이 없어도 됨 — 없으면 자동 fallback).
  static const String intentModelAsset = 'assets/models/intent_classifier.tflite';
  static const String emotionModelAsset = 'assets/models/emotion_classifier.tflite';

  /// 모델 결과를 신뢰하기 위한 최소 confidence. 미만이면 rule-based/서버로 fallback.
  static const double minConfidence = 0.60;

  bool get isEnabled => enableOnDeviceModel;

  /// 자산으로 등록된 모델 파일이 실제 존재하는지 확인(런타임). 미등록/부재면 false.
  Future<bool> assetExists(String assetPath) async {
    if (!isEnabled) return false;
    try {
      await rootBundle.load(assetPath);
      return true;
    } catch (_) {
      return false; // 미등록 자산은 예외 → 없음으로 처리.
    }
  }

  /// (실험) TFLite 인터프리터 로드 자리.
  ///
  /// 현재는 스텁: tflite 런타임을 도입하지 않았으므로 항상 null 을 반환한다.
  /// null == "모델 미사용" 이며, 호출부는 rule-based fallback 을 쓴다.
  ///
  /// 실제 도입 예시(tflite_flutter 추가 후):
  /// ```dart
  /// if (!await assetExists(assetPath)) return null;
  /// return await Interpreter.fromAsset(assetPath);
  /// ```
  Future<Object?> tryLoadInterpreter(String assetPath) async {
    if (!isEnabled) return null;
    try {
      final exists = await assetExists(assetPath);
      if (!exists) {
        debugPrint('[OnDeviceModel] asset 없음 → rule-based fallback: $assetPath');
        return null;
      }
      // TODO(tflite): 실제 Interpreter 반환으로 교체. 지금은 스텁.
      debugPrint('[OnDeviceModel] 스텁 로더: 런타임 미도입 → null 반환');
      return null;
    } catch (e) {
      debugPrint('[OnDeviceModel] 로드 실패 → rule-based fallback: $e');
      return null;
    }
  }
}

final onDeviceModelService = OnDeviceModelService.instance;

/// 분류 결과 공통 타입(label + confidence + 출처).
class ClassifierResult {
  final String label;
  final double confidence;

  /// "on_device_model" | "rule" | "server"
  final String source;

  const ClassifierResult({
    required this.label,
    required this.confidence,
    required this.source,
  });

  @override
  String toString() =>
      'ClassifierResult(label=$label, confidence=$confidence, source=$source)';
}
