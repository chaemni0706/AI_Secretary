/// 예약 후보 모델.
///
/// 백엔드 실제 계약 기준:
/// - 사유 필드는 단일 **`reason`(string)** 이다. ( `reason_codes` 배열 아님 )
/// - **`conflict`** 는 bool.
/// - `start_time`/`end_time` 형식은 백엔드 구현 기준 `"HH:mm"`.
class ReservationCandidate {
  final String candidateId;
  final String startTime;
  final String endTime;
  final int score;
  final String reason;
  final bool conflict;

  const ReservationCandidate({
    required this.candidateId,
    required this.startTime,
    required this.endTime,
    required this.score,
    required this.reason,
    this.conflict = false,
  });

  factory ReservationCandidate.fromJson(Map<String, dynamic> json) {
    return ReservationCandidate(
      candidateId: json['candidate_id']?.toString() ?? '',
      startTime: (json['start_time'] ?? '').toString(),
      endTime: (json['end_time'] ?? '').toString(),
      score: (json['score'] ?? 0) as int,
      reason: (json['reason'] ?? '').toString(),
      conflict: json['conflict'] == true,
    );
  }
}

/// 후보에서 제외된 시간대.
class RejectedSlot {
  final String startTime;
  final String endTime;
  final String reason;

  const RejectedSlot({
    required this.startTime,
    required this.endTime,
    required this.reason,
  });

  factory RejectedSlot.fromJson(Map<String, dynamic> json) {
    return RejectedSlot(
      startTime: (json['start_time'] ?? '').toString(),
      endTime: (json['end_time'] ?? '').toString(),
      reason: (json['reason'] ?? '').toString(),
    );
  }
}

/// 예약 후보 응답 전체.
class ReservationResult {
  final String targetDate;
  final List<ReservationCandidate> recommendedCandidates;
  final List<RejectedSlot> rejectedSlots;

  const ReservationResult({
    required this.targetDate,
    this.recommendedCandidates = const [],
    this.rejectedSlots = const [],
  });

  factory ReservationResult.fromJson(Map<String, dynamic> json) {
    final rec = (json['recommended_candidates'] as List?) ?? const [];
    final rej = (json['rejected_slots'] as List?) ?? const [];
    return ReservationResult(
      targetDate: (json['target_date'] ?? '').toString(),
      recommendedCandidates: rec
          .map((e) => ReservationCandidate.fromJson(e as Map<String, dynamic>))
          .toList(),
      rejectedSlots: rej
          .map((e) => RejectedSlot.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }
}
