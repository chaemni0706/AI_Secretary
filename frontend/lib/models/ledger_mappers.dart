/// 백엔드 Ledger DTO → 기존 UI 모델(LedgerTx / PendingTx / DayInfo ...) 어댑터.
///
/// 화면 위젯을 갈아엎지 않고 재사용하기 위해, API 응답을 기존 UI 모델로 변환한다.
/// 서버 응답 필드명이 조금 달라도 깨지지 않도록 여러 후보 키를 확인한다.
/// Mock fallback 데이터와 동일한 모델 타입을 만들어 같은 화면에서 함께 렌더된다.
library;

import 'ledger_api_models.dart';
import 'ledger_models.dart';

// ---------------------------------------------------------------------------
// 카테고리 라벨 → 색 키(catKey) / 분류 근거 → 표시 라벨(method)
// ---------------------------------------------------------------------------

/// 백엔드 내부 카테고리(한글 라벨) → ledger_styles 색 키.
/// 대응 색이 없는 카테고리는 '' 로 두어 기본색(green) fallback 되게 한다.
const Map<String, String> _catKeyByLabel = {
  '식비': 'food',
  '카페': 'cafe',
  '편의점': 'cvs',
  '마트_장보기': 'shop',
  '교통': 'trans',
  '쇼핑': 'shop',
  '구독_콘텐츠': 'sub',
  '통신_공과금': 'tel',
  '수입': 'income',
};

String _catKeyOf(String label) => _catKeyByLabel[label] ?? '';

/// category_source → 사용자에게 보여줄 분류 방식 라벨.
const Map<String, String> _methodBySource = {
  'rule_based': '룰베이스',
  'mock_place_search': '장소 검색',
  'category_mapping': '매핑 규칙',
  'notification_rule': '입금 알림',
  'user_override': '직접 수정',
  'llm': 'AI 판단',
  'fallback': 'AI 판단',
};

String _methodOf(LedgerTransactionDto d) {
  if (d.needsUserConfirmation) return 'AI 판단';
  final src = d.categorySource;
  if (src == null) return '자동 기록';
  return _methodBySource[src] ?? '자동 기록';
}

String _initialOf(String merchant) {
  final m = merchant.trim();
  if (m.isEmpty) return '?';
  return m.substring(0, 1);
}

String _p2(int n) => n.toString().padLeft(2, '0');

String _timeLabelOf(LedgerTransactionDto d) {
  if (d.time.isNotEmpty) return d.time;
  final o = d.occurredAt;
  if (o != null) return '${_p2(o.hour)}:${_p2(o.minute)}';
  return '';
}

/// 여러 후보 키 중 처음 존재하는(non-null) 값을 그대로 반환.
dynamic _pick(Map<String, dynamic> map, List<String> keys) {
  for (final k in keys) {
    if (map.containsKey(k) && map[k] != null) return map[k];
  }
  return null;
}

/// 여러 후보 키 중 처음 존재하는 값을 int 로 읽는다.
int _readIntKeys(Map<String, dynamic> map, List<String> keys) {
  for (final k in keys) {
    if (map.containsKey(k) && map[k] != null) return readInt(map[k]);
  }
  return 0;
}

/// 'YYYY-MM-DD' 또는 int day → 월중 일(day) 숫자. 실패하면 null.
int? _dayOf(dynamic value) {
  if (value == null) return null;
  if (value is int) return value;
  final s = value.toString().trim();
  if (s.isEmpty) return null;
  // 'YYYY-MM-DD'
  final parts = s.split('-');
  if (parts.length == 3) return int.tryParse(parts[2]);
  return int.tryParse(s);
}

// ---------------------------------------------------------------------------
// 거래 DTO → UI 모델
// ---------------------------------------------------------------------------

extension LedgerTransactionMapper on LedgerTransactionDto {
  /// 대기(확정 필요) 성격의 거래인지. (pending / needs_review / 확인 필요)
  bool get isPendingLike =>
      status == 'pending' ||
      status == 'needs_review' ||
      needsUserConfirmation;

  /// 자동 감지 카드에 보여줄 대기 거래로 변환.
  /// 백엔드 String id 는 [PendingTx.transactionId] 로 보존한다.
  PendingTx toPendingTx() {
    return PendingTx(
      id?.hashCode ?? merchant.hashCode, // 로컬 리스트 key용 int
      merchant,
      _initialOf(merchant),
      signedAmount, // 지출 음수 / 수입 양수
      category,
      _catKeyOf(category),
      _methodOf(this),
      needsUserConfirmation || status == 'needs_review', // review
      (confidence * 100).round(), // 0.0~1.0 → %
      transactionId: id,
      date: date,
      time: _timeLabelOf(this),
      status: status, // pending | needs_review
      memo: memo,
    );
  }

  /// 확정/일자별 거래 리스트에 보여줄 거래로 변환.
  LedgerTx toLedgerTx() {
    return LedgerTx(
      _timeLabelOf(this),
      merchant,
      _initialOf(merchant),
      signedAmount, // 원 단위 int, 지출 음수 / 수입·결제취소 양수
      category,
      _catKeyOf(category),
      isCancel ? '결제취소' : _methodOf(this),
      transactionId: id,
    );
  }
}

// ---------------------------------------------------------------------------
// 대시보드 DTO → UI 모델/요약
// ---------------------------------------------------------------------------

extension LedgerDashboardMapper on LedgerDashboardDto {
  /// 이번 달 총 지출.
  int get monthExpense => _readIntKeys(
        summary,
        ['month_expense', 'total_expense', 'monthly_expense', 'expense'],
      );

  /// 이번 달 총 수입.
  int get monthIncome => _readIntKeys(
        summary,
        ['month_income', 'total_income', 'monthly_income', 'income'],
      );

  /// 잔액(수입-지출). summary 에 없으면 계산으로 보정.
  int get balance {
    for (final k in ['balance', 'remaining', 'net']) {
      if (summary.containsKey(k) && summary[k] != null) {
        return readInt(summary[k]);
      }
    }
    return monthIncome - monthExpense;
  }

  /// 선택 날짜의 오늘 지출(요약용).
  int get todayExpense =>
      _readIntKeys(summary, ['today_expense', 'selected_expense', 'expense']);

  /// 자동 감지 카드용 대기 거래 목록.
  List<PendingTx> pendingCards() =>
      pendingTransactions.map((d) => d.toPendingTx()).toList();

  /// 예산 경고 배너에 표시할 문구. budget_alerts 데이터 기반으로만 생성하며,
  /// 데이터가 없으면 null(배너 숨김). 하드코딩 문구를 만들지 않는다.
  ///
  /// 표시 정책(백엔드가 usage_rate 내림차순으로 정렬하므로 첫 항목=최상위):
  /// - message 있으면 그대로
  /// - category + usage_rate 있으면 "{category} 예산의 {rate}%를 사용했어요"
  /// - category만 있으면 "{category} 예산 사용량을 확인해 주세요"
  /// - 그 외 "예산 사용량을 확인해 주세요"
  String? topBudgetAlertMessage() {
    for (final raw in budgetAlerts) {
      if (raw is! Map) continue;
      final m = raw.map((k, v) => MapEntry(k.toString(), v));
      final msg = readString(_pick(m, ['message', 'msg', 'text']));
      if (msg != null) return msg;
      final category = readString(_pick(m, ['category', 'name']));
      final rateRaw = _pick(m, ['usage_rate', 'percent', 'pct', 'rate']);
      if (category != null && rateRaw != null) {
        return '$category 예산의 ${readInt(rateRaw)}%를 사용했어요';
      }
      if (category != null) {
        return '$category 예산 사용량을 확인해 주세요';
      }
      return '예산 사용량을 확인해 주세요';
    }
    return null;
  }

  /// 선택 날짜의 거래 목록(여러 후보 키 대응).
  List<LedgerTx> selectedDayTransactions() {
    final sel = selectedDate;
    if (sel == null) return const [];
    const candidateKeys = [
      'transactions',
      'items',
      'daily_transactions',
      'selected_transactions',
    ];
    for (final key in candidateKeys) {
      final v = sel[key];
      if (v is List && v.isNotEmpty) {
        return v
            .whereType<Map>()
            .map((m) => LedgerTransactionDto.fromJson(
                  m.map((k, val) => MapEntry(k.toString(), val)),
                ).toLedgerTx())
            .toList();
      }
    }
    return const [];
  }

  /// 달력 셀용 일(day)별 합계.
  Map<int, DayInfo> dayInfos() {
    final out = <int, DayInfo>{};
    for (final raw in calendar) {
      if (raw is! Map) continue;
      final m = raw.map((k, v) => MapEntry(k.toString(), v));
      final day = _dayOf(m['day']) ?? _dayOf(m['date']);
      if (day == null) continue;
      final expense = _readIntKeys(m, ['expense_total', 'expense']);
      final income = _readIntKeys(m, ['income_total', 'income']);
      out[day] = DayInfo(spend: expense, income: income);
    }
    return out;
  }
}

// ---------------------------------------------------------------------------
// 월 전체 거래내역 DTO → UI 모델
// ---------------------------------------------------------------------------

/// 거래내역 탭에서 렌더할 '하루' 단위 그룹(날짜 헤더 + 거래 리스트).
class LedgerDayGroup {
  /// 'YYYY-MM-DD'.
  final String date;
  final int month;
  final int day;
  final int expenseTotal;
  final int incomeTotal;
  final List<LedgerTx> transactions;

  const LedgerDayGroup({
    required this.date,
    required this.month,
    required this.day,
    required this.expenseTotal,
    required this.incomeTotal,
    required this.transactions,
  });
}

extension LedgerMonthTransactionsMapper on LedgerMonthTransactionsDto {
  int get monthExpense => _readIntKeys(
        summary,
        ['month_expense', 'total_expense', 'monthly_expense', 'expense'],
      );

  int get monthIncome => _readIntKeys(
        summary,
        ['month_income', 'total_income', 'monthly_income', 'income'],
      );

  int get transactionCount {
    final n = _readIntKeys(summary, ['transaction_count', 'count']);
    return n > 0 ? n : transactions.length;
  }

  /// 일자별 그룹(최신 날짜 우선)으로 변환. 백엔드가 이미 by_date 를 내림차순으로
  /// 정렬해 주지만, 방어적으로 여기서도 날짜 내림차순 보장한다.
  List<LedgerDayGroup> dayGroups() {
    final groups = <LedgerDayGroup>[];
    for (final g in byDate) {
      final parts = g.date.split('-');
      final m = parts.length >= 2 ? int.tryParse(parts[1]) ?? 0 : 0;
      final d = parts.length >= 3 ? int.tryParse(parts[2]) ?? 0 : 0;
      groups.add(LedgerDayGroup(
        date: g.date,
        month: m,
        day: d,
        expenseTotal: g.expenseTotal,
        incomeTotal: g.incomeTotal,
        transactions: g.transactions.map((t) => t.toLedgerTx()).toList(),
      ));
    }
    groups.sort((a, b) => b.date.compareTo(a.date));
    return groups;
  }
}

// ---------------------------------------------------------------------------
// 리포트 DTO → UI 모델/요약
// ---------------------------------------------------------------------------

String _comma(int n) {
  final v = n.abs().toString();
  final b = StringBuffer();
  for (int i = 0; i < v.length; i++) {
    if (i > 0 && (v.length - i) % 3 == 0) b.write(',');
    b.write(v[i]);
  }
  return b.toString();
}

extension LedgerReportMapper on LedgerReportDto {
  int get totalExpense => _readIntKeys(
        summary,
        ['month_expense', 'total_expense', 'monthly_expense', 'expense'],
      );

  int get totalIncome => _readIntKeys(
        summary,
        ['month_income', 'total_income', 'monthly_income', 'income'],
      );

  int get balance {
    for (final k in ['balance', 'remaining', 'net']) {
      if (summary.containsKey(k) && summary[k] != null) {
        return readInt(summary[k]);
      }
    }
    return totalIncome - totalExpense;
  }

  /// 저축률(%) — summary 에 있으면 사용, 없으면 (수입-지출)/수입 로 보정.
  int get savingRate {
    for (final k in ['saving_rate', 'savings_rate', 'saving']) {
      if (summary.containsKey(k) && summary[k] != null) {
        return readDouble(summary[k]).round();
      }
    }
    if (totalIncome <= 0) return 0;
    return ((totalIncome - totalExpense) / totalIncome * 100).round();
  }

  /// category_analysis → 기존 CategoryStat 목록.
  /// percent(ratio) 합이 100 이 아니어도 그대로 렌더된다.
  List<CategoryStat> categoryStats() {
    final out = <CategoryStat>[];
    for (final raw in categoryAnalysis) {
      if (raw is! Map) continue;
      final m = raw.map((k, v) => MapEntry(k.toString(), v));
      final name = readString(_pick(m, ['category', 'name'])) ?? '기타';
      final amount = _readIntKeys(m, ['amount', 'spent', 'total']);
      final pct = readInt(_pick(m, ['ratio', 'percent', 'pct']));
      out.add(CategoryStat(name, amount, pct, _catKeyOf(name)));
    }
    return out;
  }

  int get categoryTotal =>
      categoryStats().fold(0, (sum, c) => sum + c.amount);

  /// budget_usage → 기존 BudgetStat 목록.
  List<BudgetStat> budgetStats() {
    final out = <BudgetStat>[];
    for (final raw in budgetUsage) {
      if (raw is! Map) continue;
      final m = raw.map((k, v) => MapEntry(k.toString(), v));
      final name = readString(_pick(m, ['category', 'name'])) ?? '기타';
      final pct = readDouble(_pick(m, ['usage_rate', 'rate', 'pct'])).round();
      final spent = _readIntKeys(m, ['spent', 'used', 'amount']);
      final budget = _readIntKeys(m, ['budget', 'limit', 'total']);
      final status = readString(m['status']);
      final over = status == 'exceeded' || pct >= 100;
      out.add(BudgetStat(name, pct, '${_comma(spent)} / ${_comma(budget)}', over));
    }
    return out;
  }

  /// recurring_payments → 기존 RecurringPayment 목록.
  List<RecurringPayment> recurringItems() {
    final out = <RecurringPayment>[];
    for (final raw in recurringPayments) {
      if (raw is! Map) continue;
      final m = raw.map((k, v) => MapEntry(k.toString(), v));
      final name = readString(_pick(m, ['merchant', 'name'])) ?? '';
      final amount = _readIntKeys(m, ['amount', 'spent']);
      final cat = readString(m['category']) ?? '';
      final expectedDay = _pick(m, ['expected_day', 'day']);
      final cycle = expectedDay != null ? '매월 ${readInt(expectedDay)}일' : '매월';
      out.add(RecurringPayment(
          name, _initialOf(name), amount, cycle, cat, _catKeyOf(cat)));
    }
    return out;
  }

  int get recurringTotal =>
      recurringItems().fold(0, (sum, r) => sum + r.amount);

  /// briefing 이 {title,message} map 또는 문자열이어도 안전하게 본문 추출.
  String? get briefingBody {
    final b = briefing;
    if (b == null) return null;
    final msg = b['message'] ?? b['text'] ?? b['title'];
    final s = msg?.toString().trim();
    return (s == null || s.isEmpty) ? null : s;
  }
}
