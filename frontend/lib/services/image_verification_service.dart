import 'dart:io';

import '../models/image_verification_result.dart';
import 'smol_ondevice_verifier.dart';
import 'verification_api.dart';

/// 이미지 인증 오케스트레이터: **Smol 온디바이스 1차 → Qwen2.5-VL-7B 서버 fallback**.
///
///   image + task
///     → Smol on-device evidence(가능 시) → confident 하면 반환
///     → 아니면 서버 fallback API(POST /verification/image/{task}) → Rule Engine 판정
///     → 통합 [ImageVerificationResult] 반환
///
/// 원칙:
/// - 최종 판정은 항상 Rule Engine(서버) 또는 fail-safe. Smol/7B 는 evidence extractor.
/// - Smol `verified`(특히 water)는 로컬 단독 확정 금지 → 서버 fallback 으로 재확인.
/// - water 의 `verified` 는 비시각 맥락 리스크로 `reviewRequired` → 앱은 secondary_review 로.
/// - 현재 Smol 은 stub(`isAvailable=false`) → 항상 서버 fallback. 온디바이스 준비 시 자동 활성.
class ImageVerificationService {
  final SmolOndeviceVerifier smol;
  final VerificationApi api;

  const ImageVerificationService({
    this.smol = smolOndeviceVerifier,
    this.api = verificationApi,
  });

  /// exercise/study 만 로컬 accept 를 적극 허용. water 는 로컬 accept 금지(FP=9 이력).
  bool _canAcceptLocal(Map<String, dynamic> ev, String task) {
    if (task == 'water') return false; // water verified 로컬 채택 금지
    final fr = (ev['final_result'] ?? '').toString();
    final unc = (ev['uncertainty'] ?? 'high').toString();
    final engineError = (ev['engine_error'] ?? '').toString().isNotEmpty;
    final parseOk = {'clean', 'repaired'}.contains((ev['parse_status'] ?? '').toString());
    final ruleFallback = ev['rule_engine_fallback'] == true;
    if (engineError || ruleFallback || !parseOk) return false;
    if (fr == 'verified') {
      final blockers = (ev['blockers'] as List?) ?? const [];
      return unc == 'low' && blockers.isEmpty;
    }
    if (fr == 'rejected') {
      final blockers = (ev['blockers'] as List?) ?? const [];
      return blockers.isNotEmpty; // 명확한 blocker 기반 거절
    }
    return false;
  }

  Future<ImageVerificationResult> verify({
    required File imageFile,
    required String task,
    String? activityType,
  }) async {
    // 1) Smol 온디바이스 1차 (현재 stub → null)
    final local = await smol.inferEvidence(
      imageFile: imageFile, task: task, activityType: activityType);
    if (local != null && _canAcceptLocal(local, task)) {
      return ImageVerificationResult.fromMap({
        ...local,
        'engine_used': 'smol',
        'fallback_used': false,
        'local_result': local['final_result'],
      });
    }

    // 2) 서버 fallback (Qwen2.5-VL-7B + guard + Rule Engine)
    final server = await api.submitImageVerification(
      verificationType: task, imageFile: imageFile, activityType: activityType);
    final data = server.raw;
    final finalResult = (data['result'] ?? server.result).toString();
    // 서버가 review_required 를 주지 않으면 클라이언트 정책으로 보강(water verified → review).
    final reviewRequired = data['review_required'] == true ||
        (finalResult == 'verified' && task == 'water');
    return ImageVerificationResult.fromMap({
      'task': task,
      'final_result': finalResult,
      'engine_used': 'server_fallback',
      'fallback_used': true,
      'review_required': reviewRequired,
      'review_reason': reviewRequired ? 'water_non_visual_context_risk' : '',
      'local_result': local == null ? 'unknown' : (local['final_result'] ?? 'unknown'),
      'fallback_result': finalResult,
      'rule_reason': server.reasons.isNotEmpty ? server.reasons.first : '',
      ...data,
    });
  }
}

const imageVerificationService = ImageVerificationService();
