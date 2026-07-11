/// VLM 기반 이미지 인증 통합 결과 모델 (local-first + server fallback).
///
/// Python 파이프라인 `local_eval/vlm_baseline/vlm_fallback_verifier.py`
/// (`verify_image_with_vlm_fallback`) 의 반환 schema 를 앱 측에서 mirror 한 것.
///
/// 최종 판정(`finalResult`)은 항상 **기존 Rule Engine 또는 fail-safe/guard** 에서 나온다.
/// Smol 온디바이스와 Qwen2.5-VL-7B 서버 fallback 은 evidence extractor 일 뿐이다.
///
/// water 의 `verified` 는 비시각 맥락(수질/장소/음료 종류)을 외관만으로 확정할 수 없어
/// `reviewRequired == true` 로 표시된다 → 앱은 secondary_review(사람/맥락 rule) 로 라우팅한다.
class ImageVerificationResult {
  final String task; // water | study | exercise

  /// verified | rejected | retake_required
  final String finalResult;

  /// smol | server_fallback | fail_safe
  final String engineUsed;

  final bool fallbackUsed;

  /// secondary_review 필요 여부(현재: verified(water)).
  final bool reviewRequired;

  /// review 사유 (예: water_non_visual_context_risk).
  final String reviewReason;

  final String localResult; // verified | rejected | retake_required | error | unknown
  final String? fallbackResult;

  final String ruleReason;
  final Map<String, dynamic> raw;

  const ImageVerificationResult({
    required this.task,
    required this.finalResult,
    required this.engineUsed,
    required this.fallbackUsed,
    required this.reviewRequired,
    required this.reviewReason,
    required this.localResult,
    required this.ruleReason,
    required this.raw,
    this.fallbackResult,
  });

  factory ImageVerificationResult.fromMap(Map<String, dynamic> m) {
    return ImageVerificationResult(
      task: (m['task'] ?? '').toString(),
      finalResult: (m['final_result'] ?? '').toString(),
      engineUsed: (m['engine_used'] ?? '').toString(),
      fallbackUsed: m['fallback_used'] == true,
      reviewRequired: m['review_required'] == true,
      reviewReason: (m['review_reason'] ?? '').toString(),
      localResult: (m['local_result'] ?? 'unknown').toString(),
      fallbackResult: m['fallback_result']?.toString(),
      ruleReason: (m['rule_reason'] ?? '').toString(),
      raw: m,
    );
  }

  bool get isVerified => finalResult == 'verified' && !reviewRequired;
  bool get isRejected => finalResult == 'rejected';
  bool get isRetakeRequired => finalResult == 'retake_required';

  /// verified 이지만 비시각 맥락 확인이 필요한 상태(앱은 자동 확정하지 말 것).
  bool get needsSecondaryReview => finalResult == 'verified' && reviewRequired;

  String get displayMessage {
    if (needsSecondaryReview) return '거의 다 됐어요. 추가 확인이 필요해요 🔎';
    switch (finalResult) {
      case 'verified':
        return '인증 성공! 잘 하셨어요 👍';
      case 'retake_required':
        return '근거가 불확실해요. 다시 촬영해 주세요 📷';
      case 'rejected':
        return '인증에 실패했어요. 조건을 확인하고 다시 시도해 주세요.';
      default:
        return '알 수 없는 결과입니다: $finalResult';
    }
  }
}
