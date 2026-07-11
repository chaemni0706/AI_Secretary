import 'dart:io';

import 'package:flutter/services.dart';

/// 온디바이스 SmolVLM-500M 1차 evidence 추론 인터페이스 (**stub**).
///
/// 목표 구조:
///   image + task
///     → (이 클래스) Smol on-device ONNX 추론 → evidence JSON
///     → confident 하면 로컬 결과 사용, 아니면 서버 Qwen2.5-VL-7B fallback
///
/// **현재는 stub 이다.** 실디바이스 ONNX Runtime 추론은 아직 미구현이며 `isAvailable == false` 를 반환해
/// 오케스트레이터([ImageVerificationService])가 곧바로 서버 fallback 을 타도록 한다.
///
/// 온디바이스 자산(이미 준비됨, git 미포함 — release 시 asset 주입):
///   android/app/src/main/assets/models/smolvlm/
///     vision_encoder_q4f16.onnx (~57MB), embed_tokens_q4f16.onnx (~94MB),
///     decoder_model_merged_q4f16.onnx (~205MB), tokenizer/merges/chat_template/preprocessor
///
/// 연결 방법: [SmolVlmBridge.kt] (MethodChannel `ai_secretary/smolvlm`) 를 통해 네이티브 ONNX Runtime 호출.
/// 자세한 남은 작업은 루트 `SMOL_ONDEVICE_STATUS.md` 참조.
///
/// 주의: Smol 은 final verifier 가 아니다. Smol `verified`(특히 water)는 로컬 단독 확정 금지.
class SmolOndeviceVerifier {
  static const MethodChannel _channel = MethodChannel('ai_secretary/smolvlm');

  const SmolOndeviceVerifier();

  /// 온디바이스 Smol 런타임 사용 가능 여부. 현재 stub → 항상 false.
  /// (네이티브 브릿지가 모델 로드에 성공하면 true 로 전환.)
  Future<bool> isAvailable() async {
    try {
      final ok = await _channel.invokeMethod<bool>('isAvailable');
      return ok ?? false;
    } on MissingPluginException {
      // 네이티브 브릿지 미등록(현 stub 상태) → 온디바이스 불가.
      return false;
    } on PlatformException {
      return false;
    }
  }

  /// 온디바이스 Smol evidence 추론(→ 로컬 Rule Engine 매핑까지는 네이티브/후속 구현).
  ///
  /// 반환은 서버 fallback 과 **동일 schema**(`ImageVerificationResult.fromMap`) 여야 한다.
  /// 현재 stub: 항상 null 을 반환하여 오케스트레이터가 서버 fallback 을 타게 한다.
  Future<Map<String, dynamic>?> inferEvidence({
    required File imageFile,
    required String task,
    String? activityType,
  }) async {
    if (!await isAvailable()) return null; // stub: 서버 fallback 유도
    try {
      final res = await _channel.invokeMapMethod<String, dynamic>('inferEvidence', {
        'imagePath': imageFile.path,
        'task': task,
        if (activityType != null) 'activityType': activityType,
      });
      return res;
    } on PlatformException {
      return null; // 실패 시 서버 fallback
    }
  }
}

const smolOndeviceVerifier = SmolOndeviceVerifier();
