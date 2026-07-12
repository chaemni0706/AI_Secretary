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
/// - water 의 `verified` 는 비시각 맥락 리스크로 `reviewRequired` → 앱은 자동 성공이 아니라 **재촬영 안내**.
/// - Smol 온디바이스 추론은 아직 미구현(네이티브는 세션 로드까지) → 현재는 항상 서버 fallback. 준비 시 자동 활성.
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
    // 0) Smol **blocker-only** local-first: 명백한 blocker(주스/커피/소파 등)면 서버 없이 로컬 재촬영 안내.
    //    positive/약함/모호/모델없음/오류는 모두 null → 아래 서버 fallback. **local accept 는 절대 없음.**
    final blocker = await smol.inferBlocker(imageFile: imageFile, task: task);
    if (blocker != null) {
      return ImageVerificationResult.fromMap({
        'task': task,
        'final_result': 'retake_required', // 보수적: rejected 보다 재촬영 우선
        'engine_used': 'smol_ondevice',
        'fallback_used': false,
        'review_required': false,
        'review_reason': '',
        'local_result': 'blocker',
        'smol_blocker_detected': true,
        'blockers': blocker['blockers'],
        'evidence_codes': blocker['evidence_codes'],
        'rule_reason': blocker['reason'],
        'generated_text': blocker['generated_text'],
      });
    }

    // 1) Smol 온디바이스 positive accept (현재 미개방 → inferEvidence stub → null)
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
      ...data, // 서버 원본(score/rule_evidence 등) 먼저 — 아래 계산값이 우선하도록 덮어씀
      'task': task,
      'final_result': finalResult,
      'engine_used': 'server_fallback',
      'fallback_used': true,
      'review_required': reviewRequired,
      'review_reason': reviewRequired ? 'water_non_visual_context_risk' : '',
      'local_result': local == null ? 'unknown' : (local['final_result'] ?? 'unknown'),
      'fallback_result': finalResult,
      'rule_reason': server.reasons.isNotEmpty ? server.reasons.first : '',
    });
  }
}

const imageVerificationService = ImageVerificationService();
