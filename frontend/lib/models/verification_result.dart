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

  bool get isVerified => result == 'verified';
  bool get isRejected => result == 'rejected';
  bool get isRetakeRequired => result == 'retake_required';

  /// 사용자에게 보여줄 한 줄 메시지.
  String get displayMessage {
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
