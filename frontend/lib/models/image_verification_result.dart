/// VLM 기반 이미지 인증 통합 결과 모델 (local-first + server fallback).
///
/// 실제 backend 엔드포인트(`POST /api/v1/verification/image/{type}`,
/// `backend/services/image_verification_service.py::verify_image_upload`)의 응답 schema를
/// 앱 측에서 mirror 한 것.
///
/// 최종 판정(`finalResult`)은 항상 **Rule Engine + backend FP guard 또는 fail-safe** 에서 나온다.
/// Smol(서버사이드 1차)과 Qwen2.5-VL-7B(서버 fallback)는 evidence extractor 일 뿐이며, 어느 쪽도
/// 단독으로 verified 를 만들지 않는다.
///
/// water 의 `verified` 는 서버가 evidence/uncertainty 기반으로 판단해 `reviewRequired` 를 결정한다
/// (모델이 낮은 uncertainty 로 명확한 positive evidence 를 보고하면 review 없이 그대로 확정 가능).
class ImageVerificationResult {
  final String task; // water | study | exercise

  /// verified | rejected | retake_required
  final String finalResult;

  /// smol | server_fallback | fail_safe
  final String engineUsed;

  final bool fallbackUsed;

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
      reviewReason: (m['review_reason'] ?? '').toString(),
      localResult: (m['local_result'] ?? 'unknown').toString(),
      fallbackResult: m['fallback_result']?.toString(),
      ruleReason: (m['rule_reason'] ?? '').toString(),
      raw: m,
    );
  }

  /// secondary_review(자동 확정 불가 → 재촬영) 필요 여부.
  ///
  /// 오늘 production patch: "water verified 는 항상 review" 블랭킷 정책은 백엔드에서
  /// 제거되었다(backend/services/image_verification_service.py::apply_secondary_review_policy).
  /// 이제 서버가 evidence/uncertainty 기반으로 review_required 를 판단해 응답에 담아 보낸다 --
  /// 명확한 positive water evidence(모델이 uncertainty="low" 로 보고)는 review 없이 그대로
  /// verified 로 확정될 수 있다(클라이언트에서 강제로 덮어쓰지 않는다). 서버 값을 그대로 신뢰한다.
  bool get reviewRequired => raw['review_required'] == true;

  bool get isVerified => finalResult == 'verified' && !reviewRequired;
  bool get isRejected => finalResult == 'rejected';
  bool get isRetakeRequired => finalResult == 'retake_required';

  /// verified 이지만 자동 인증 확정이 어려운 상태(자동 성공 처리 금지 → 재촬영 안내).
  /// review_required 는 "관리자 검수 대기"가 아니라 "자동 확정 불가 → 다른 사진으로 재촬영" 을 의미한다.
  bool get needsRetake => (finalResult == 'verified' && reviewRequired) || smolBlockerDetected;

  /// (하위호환) 이전 이름. needsRetake 와 동일 의미.
  bool get needsSecondaryReview => needsRetake;

  /// Smol 온디바이스가 **명백한 blocker**(주스/커피/소파 등)를 감지해 로컬에서 재촬영으로 보낸 경우.
  /// Smol 은 positive verifier 가 아니라 보수적 blocker extractor 이며, 최종 accept 는 하지 않는다.
  bool get smolBlockerDetected => raw['smol_blocker_detected'] == true;

  /// 서버 응답의 점수(raw 에서 추출; Smol blocker 로컬 경로엔 없음).
  int? get score => raw['score'] is num ? (raw['score'] as num).toInt() : null;

  /// 사용자에게 보여줄 근거 목록(서버 rule_evidence[].message 우선, 없으면 ruleReason).
  List<String> get reasons {
    final ev = raw['rule_evidence'];
    if (ev is List) {
      final out = <String>[];
      for (final e in ev) {
        if (e is Map && e['message'] != null) out.add(e['message'].toString());
      }
      if (out.isNotEmpty) return out;
    }
    return ruleReason.isNotEmpty ? [ruleReason] : const [];
  }

  String get displayMessage {
    if (smolBlockerDetected) {
      switch (task) {
        case 'water':
          return '물이 아닌 음료로 보이는 단서가 감지됐어요. 물이 잘 보이도록 다시 촬영해 주세요 📷';
        case 'exercise':
          return '운동 중인 장면으로 보기 어려운 단서가 감지됐어요. 운동 동작·공간이 잘 보이도록 다시 촬영해 주세요 📷';
        case 'study':
          return '공부 장면으로 보기 어려운 단서가 감지됐어요. 책·노트·학습 화면이 잘 보이도록 다시 촬영해 주세요 📷';
        default:
          return '사진이 인증 조건과 맞지 않아 보여요. 다시 촬영해 주세요 📷';
      }
    }
    if (needsRetake) return '자동 인증이 어렵습니다. 다른 사진으로 다시 촬영해 주세요 📷';
    if (task == 'wake_up') {
      switch (finalResult) {
        case 'verified':
          return '기상 인증이 완료되었습니다 👍';
        case 'retake_required':
          return '기상 상태를 확인하기 어려워요. 밝은 곳에서 다시 촬영해 주세요 📷';
        case 'rejected':
          return '기상 인증 조건과 맞지 않는 사진으로 보여요. 다시 촬영해 주세요 📷';
        default:
          return '알 수 없는 결과입니다: $finalResult';
      }
    }
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
