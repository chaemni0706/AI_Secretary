/// AI 가계부에서 사용하는 mock 기반 데이터 모델 모음.
/// 백엔드 연동 없이 로컬 상태로만 동작한다.
library;

/// 확정된 거래 한 건.
class LedgerTx {
  final String time; // 'HH:mm'
  final String merchant;
  final String initial; // 아바타 이니셜
  final int amount; // 음수=지출, 양수=수입
  final String category; // 표시용 라벨 (예: '카페')
  final String catKey; // 카테고리 키 (예: 'cafe')
  final String method; // 분류 방식 (예: '룰베이스')

  /// 백엔드 거래 ID(있으면). Mock 데이터는 null.
  /// 위치 인자 호환을 위해 선택적 named 로 추가한다.
  final String? transactionId;

  const LedgerTx(
    this.time,
    this.merchant,
    this.initial,
    this.amount,
    this.category,
    this.catKey,
    this.method, {
    this.transactionId,
  });

  bool get isExpense => amount < 0;
}

/// 결제 알림으로 자동 감지된 대기(pending) 거래.
class PendingTx {
  final int id;
  final String merchant;
  final String initial;
  final int amount;
  final String category;
  final String catKey;
  final String method;
  final bool review; // 확인 필요 여부
  final int confidence; // AI 신뢰도(%)

  /// 백엔드 거래 ID(있으면). Mock 데이터는 null.
  /// confirm/update/delete API 호출 시 이 값을 사용한다(위치 인자 호환 위해 named).
  final String? transactionId;

  /// 원본 거래 일자('YYYY-MM-DD')·시각('HH:MM'). 수정 다이얼로그 프리필용.
  final String? date;
  final String? time;

  /// 백엔드 status(소문자): pending | needs_review 등. 표시 문구 분기용.
  final String status;

  /// 사용자 자유 메모(있으면). 수정 다이얼로그 프리필용.
  final String? memo;

  const PendingTx(
    this.id,
    this.merchant,
    this.initial,
    this.amount,
    this.category,
    this.catKey,
    this.method,
    this.review,
    this.confidence, {
    this.transactionId,
    this.date,
    this.time,
    this.status = 'pending',
    this.memo,
  });

  /// 사용자 확인이 필요한(needs_review) 거래인지.
  bool get isNeedsReview => status == 'needs_review' || review;

  /// 백엔드 거래 ID 를 가진(=실제 처리 가능한) 항목인지.
  bool get hasTransactionId =>
      transactionId != null && transactionId!.isNotEmpty;

  PendingTx copyWith({
    String? method,
    bool? review,
    int? confidence,
    String? transactionId,
    String? date,
    String? time,
    String? status,
    String? memo,
  }) {
    return PendingTx(
      id,
      merchant,
      initial,
      amount,
      category,
      catKey,
      method ?? this.method,
      review ?? this.review,
      confidence ?? this.confidence,
      transactionId: transactionId ?? this.transactionId,
      date: date ?? this.date,
      time: time ?? this.time,
      status: status ?? this.status,
      memo: memo ?? this.memo,
    );
  }
}

/// 달력 셀 표시용 일별 합계.
class DayInfo {
  final int spend;
  final int income;

  const DayInfo({this.spend = 0, this.income = 0});
}

/// 반복 결제 · 고정지출 항목.
class RecurringPayment {
  final String name;
  final String initial;
  final int amount;
  final String cycle; // 예: '매월 1일'
  final String category;
  final String catKey;

  const RecurringPayment(
    this.name,
    this.initial,
    this.amount,
    this.cycle,
    this.category,
    this.catKey,
  );
}

/// 리포트: 카테고리별 소비 통계.
class CategoryStat {
  final String name;
  final int amount;
  final int pct; // 비율(%)
  final String catKey;

  const CategoryStat(this.name, this.amount, this.pct, this.catKey);
}

/// 리포트: 예산 사용률 항목.
class BudgetStat {
  final String name;
  final int pct; // 사용률(%)
  final String detail; // 예: '42,000 / 50,000'
  final bool over; // 초과(경고) 여부

  const BudgetStat(this.name, this.pct, this.detail, this.over);
}
