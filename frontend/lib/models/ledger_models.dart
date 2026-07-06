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

  const LedgerTx(
    this.time,
    this.merchant,
    this.initial,
    this.amount,
    this.category,
    this.catKey,
    this.method,
  );

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

  const PendingTx(
    this.id,
    this.merchant,
    this.initial,
    this.amount,
    this.category,
    this.catKey,
    this.method,
    this.review,
    this.confidence,
  );

  PendingTx copyWith({
    String? method,
    bool? review,
    int? confidence,
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
