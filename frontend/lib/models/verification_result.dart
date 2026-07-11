/// 이미지 인증 API 응답(`data`) 파싱 모델.
///
/// 백엔드 공통 envelope `{success, message, data}` 에서 `data` 부분만 담는다.
/// data 예: { "verification_type": "water", "result": "verified", "score": 65,
///           "mandatory_passed": true, "rule_evidence": [...], "vlm_analysis": {...} }
class VerificationResult {
  final String verificationType;

  /// verified | rejected | retake_required
  final String result;

  final int? score;
  final bool? mandatoryPassed;

  /// rule_evidence[].message 목록 (사용자에게 보여줄 근거).
  final List<String> reasons;

  /// 원본 data (필요 시 상세 접근용).
  final Map<String, dynamic> raw;

  const VerificationResult({
    required this.verificationType,
    required this.result,
    required this.reasons,
    required this.raw,
    this.score,
    this.mandatoryPassed,
  });

  factory VerificationResult.fromData(Map<String, dynamic> data) {
    final evidence = data['rule_evidence'];
    final reasons = <String>[];
    if (evidence is List) {
      for (final e in evidence) {
        if (e is Map && e['message'] != null) {
          reasons.add(e['message'].toString());
        }
      }
    }
    return VerificationResult(
      verificationType: (data['verification_type'] ?? '').toString(),
      result: (data['result'] ?? '').toString(),
      score: data['score'] is num ? (data['score'] as num).toInt() : null,
      mandatoryPassed: data['mandatory_passed'] is bool ? data['mandatory_passed'] as bool : null,
      reasons: reasons,
      raw: data,
    );
  }

  /// 자동 확정(verified) — 단, secondary_review 대상이면 자동 확정 아님.
  bool get isVerified => result == 'verified' && !reviewRequired;
  bool get isRejected => result == 'rejected';
  bool get isRetakeRequired => result == 'retake_required';

  /// VLM-eligible scope 밖(비시각 맥락)일 수 있어 secondary_review 가 필요한지.
  /// 백엔드 `data.review_required` 를 우선하고, 없으면 water verified 를 보수적으로 review 로 본다.
  bool get reviewRequired =>
      raw['review_required'] == true || (result == 'verified' && verificationType == 'water');

  /// review 사유 (예: water_non_visual_context_risk).
  String get reviewReason =>
      (raw['review_reason'] ?? (reviewRequired ? 'water_non_visual_context_risk' : '')).toString();

  /// 운영 상태: none | pending | approved | rejected | needs_retake.
  /// 백엔드 `data.review_status` 를 우선하고, 없으면 review_required 로 유추한다.
  String get reviewStatus {
    final s = raw['review_status'];
    if (s is String && s.isNotEmpty) return s;
    return reviewRequired ? 'pending' : 'none';
  }

  /// review queue record id(결정 조회/처리용). 없으면 null.
  String? get verificationId => raw['verification_id']?.toString();

  bool get isReviewPending => reviewStatus == 'pending';
  bool get isReviewApproved => reviewStatus == 'approved';
  bool get isReviewRejected => reviewStatus == 'rejected';
  bool get isReviewNeedsRetake => reviewStatus == 'needs_retake';

  /// verified 이지만 검수 대기(자동 확정하지 말 것).
  bool get needsSecondaryReview =>
      result == 'verified' && reviewRequired && reviewStatus == 'pending';

  /// 사용자에게 보여줄 한 줄 메시지.
  String get displayMessage {
    // review 대상은 review_status 를 우선한다(자동 확정 아님).
    if (reviewRequired) {
      switch (reviewStatus) {
        case 'pending':
          return '거의 다 됐어요. 추가 확인이 필요해요 🔎 (검수 대기)';
        case 'approved':
          return '검수 완료 — 인증이 승인되었어요 👍';
        case 'rejected':
          return '검수 완료 — 인증이 반려되었어요.';
        case 'needs_retake':
          return '재촬영이 필요해요. 다시 촬영해 주세요 📷';
      }
    }
    switch (result) {
      case 'verified':
        return '인증 성공! 잘 하셨어요 👍';
      case 'retake_required':
        return '근거가 불확실해요. 다시 촬영해 주세요 📷';
      case 'rejected':
        return '인증에 실패했어요. 조건을 확인하고 다시 시도해 주세요.';
      default:
        return '알 수 없는 결과입니다: $result';
    }
  }
}
