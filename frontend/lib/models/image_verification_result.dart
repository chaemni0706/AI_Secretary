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
  /// **water verified 는 항상 review**(비시각 맥락 리스크) — `raw` 의 값이 무엇이든 방어적으로 강제.
  /// 이는 화면이 서비스 결과의 `...data` 로 review_required 가 덮여도 water 자동 성공을 막는 안전장치.
  bool get reviewRequired =>
      raw['review_required'] == true || (finalResult == 'verified' && task == 'water');

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
