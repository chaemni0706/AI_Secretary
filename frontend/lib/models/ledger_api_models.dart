/// AI 가계부(Ledger) 백엔드 API 응답 전용 DTO 모음.
///
/// 이 파일은 **백엔드 `/api/v1/ledger/...` 응답을 안전하게 파싱**하는 것만 담당한다.
/// 기존 `ledger_models.dart` 의 UI/Mock 모델(LedgerTx, PendingTx ...)은 그대로 두고,
/// 여기서는 절대 건드리지 않는다. DTO → UI 모델 변환은 다음 단계에서 수행한다.
///
/// 설계 원칙
/// - 서버 필드가 snake_case 여도, 일부 키가 없거나 타입이 흔들려도(예: amount 가
///   int/double/String) 절대 예외로 죽지 않도록 방어적으로 파싱한다.
/// - 모든 DTO 는 원본 맵을 [raw] 로 보존해 디버깅/후속 매핑에서 참조할 수 있게 한다.
/// - 외부 패키지 의존 없음(dart:core 만 사용).
library;

// ---------------------------------------------------------------------------
// 공용 파싱 헬퍼 (null / 타입 흔들림 방어)
// ---------------------------------------------------------------------------

/// 문자열로 안전 변환. 값이 없으면 null.
/// 빈 문자열/공백만 있는 값도 null 로 취급한다.
String? readString(dynamic value) {
  if (value == null) return null;
  final s = value.toString().trim();
  return s.isEmpty ? null : s;
}

/// 정수로 안전 변환. int / double / "1,234" / "1234.0" 등을 흡수한다.
int readInt(dynamic value, {int fallback = 0}) {
  if (value == null) return fallback;
  if (value is int) return value;
  if (value is double) return value.round();
  if (value is bool) return value ? 1 : 0;
  final cleaned = value.toString().replaceAll(',', '').trim();
  if (cleaned.isEmpty) return fallback;
  return int.tryParse(cleaned) ?? double.tryParse(cleaned)?.round() ?? fallback;
}

/// 실수로 안전 변환. int / double / "0.68" 등을 흡수한다.
double readDouble(dynamic value, {double fallback = 0}) {
  if (value == null) return fallback;
  if (value is double) return value;
  if (value is int) return value.toDouble();
  if (value is bool) return value ? 1 : 0;
  final cleaned = value.toString().replaceAll(',', '').trim();
  if (cleaned.isEmpty) return fallback;
  return double.tryParse(cleaned) ?? fallback;
}

/// 불리언으로 안전 변환. bool / 0·1 / "true"·"false"·"1"·"0" 를 흡수한다.
bool readBool(dynamic value, {bool fallback = false}) {
  if (value == null) return fallback;
  if (value is bool) return value;
  if (value is num) return value != 0;
  final s = value.toString().trim().toLowerCase();
  if (s.isEmpty) return fallback;
  if (s == 'true' || s == '1' || s == 'yes' || s == 'y') return true;
  if (s == 'false' || s == '0' || s == 'no' || s == 'n') return false;
  return fallback;
}

/// ISO datetime 문자열을 DateTime 으로 파싱. 실패하면 null.
DateTime? readDateTime(dynamic value) {
  final s = readString(value);
  if (s == null) return null;
  return DateTime.tryParse(s);
}

/// 여러 후보 키 중 처음으로 존재하는 값을 반환(snake_case/camelCase 동시 대응).
dynamic _pick(Map<String, dynamic> json, List<String> keys) {
  for (final k in keys) {
    if (json.containsKey(k) && json[k] != null) return json[k];
  }
  return null;
}

/// dynamic → `Map<String, dynamic>` 안전 변환(아니면 null).
Map<String, dynamic>? _asMap(dynamic value) {
  if (value is Map<String, dynamic>) return value;
  if (value is Map) return value.map((k, v) => MapEntry(k.toString(), v));
  return null;
}

/// dynamic → `List<dynamic>` 안전 변환(아니면 빈 리스트).
List<dynamic> _asList(dynamic value) {
  if (value is List) return value;
  return const <dynamic>[];
}

// ---------------------------------------------------------------------------
// 1) 거래 DTO
// ---------------------------------------------------------------------------

/// 백엔드 거래 한 건(`to_api_dict` 출력)에 대응하는 DTO.
///
/// enum 계열(transactionType/sourceType/status)은 서버 규약대로 **소문자 문자열**
/// 그대로 보존한다. amount 는 원화 정수(양수), 부호/카테고리 색 등 UI 변환은 하지 않는다.
class LedgerTransactionDto {
  /// 거래 ID. 서버 `transaction_id`. 미저장(ignore 등) 응답에서는 null 일 수 있다.
  final String? id;

  /// expense | income | cancel | ignore
  final String transactionType;

  /// notification | receipt_scan | manual | seed
  final String sourceType;

  /// pending | confirmed | duplicate | deleted | needs_review | ignored
  final String status;

  /// 원화 정수(양수). 지출/수입 부호는 UI 변환 단계에서 처리한다.
  final int amount;

  final String merchant;

  /// 내부 카테고리 한글 라벨(예: '카페', '식비', '구독_콘텐츠').
  final String category;

  /// 사용자 자유 메모(백엔드 memo 컬럼). 없으면 null.
  final String? memo;

  /// 'YYYY-MM-DD' (없을 수 있음).
  final String date;

  /// 'HH:MM' (없을 수 있음).
  final String time;

  final DateTime? occurredAt;

  final bool needsUserConfirmation;

  /// 0.0 ~ 1.0 신뢰도. 서버 값이 없으면 0.
  final double confidence;

  /// 중복 판정 여부(응답 최상위 또는 상세에 포함될 수 있음).
  final bool? duplicate;

  /// 분류 근거(rule_based / mock_place_search / user_override ...). UI 변환에 사용.
  final String? categorySource;

  final bool isRecurring;

  /// 디버그/후속 매핑용 원본 맵.
  final Map<String, dynamic> raw;

  const LedgerTransactionDto({
    required this.id,
    required this.transactionType,
    required this.sourceType,
    required this.status,
    required this.amount,
    required this.merchant,
    required this.category,
    required this.memo,
    required this.date,
    required this.time,
    required this.occurredAt,
    required this.needsUserConfirmation,
    required this.confidence,
    required this.duplicate,
    required this.categorySource,
    required this.isRecurring,
    required this.raw,
  });

  factory LedgerTransactionDto.fromJson(Map<String, dynamic> json) {
    return LedgerTransactionDto(
      id: readString(_pick(json, ['transaction_id', 'transactionId', 'id'])),
      transactionType:
          readString(_pick(json, ['transaction_type', 'transactionType'])) ??
          '',
      sourceType: readString(_pick(json, ['source_type', 'sourceType'])) ?? '',
      status: readString(json['status']) ?? '',
      amount: readInt(json['amount']),
      merchant: readString(json['merchant']) ?? '',
      category: readString(json['category']) ?? '',
      memo: readString(json['memo']),
      date: readString(json['date']) ?? '',
      time: readString(json['time']) ?? '',
      occurredAt: readDateTime(_pick(json, ['occurred_at', 'occurredAt'])),
      needsUserConfirmation: readBool(
        _pick(json, ['needs_user_confirmation', 'needsUserConfirmation']),
      ),
      confidence: readDouble(json['confidence']),
      duplicate: json.containsKey('duplicate')
          ? readBool(json['duplicate'])
          : null,
      categorySource: readString(
        _pick(json, ['category_source', 'categorySource']),
      ),
      isRecurring: readBool(_pick(json, ['is_recurring', 'isRecurring'])),
      raw: json,
    );
  }

  /// 실제로 DB 에 저장된(=유효 ID 를 가진) 거래인지.
  bool get hasId => id != null && id!.isNotEmpty;

  bool get isExpense => transactionType == 'expense';
  bool get isIncome => transactionType == 'income';

  /// 결제취소/환불. 앞선 지출을 되돌리는 유입성 거래로 취급한다.
  bool get isCancel => transactionType == 'cancel';

  /// 지출은 음수, 수입·결제취소(환불)는 양수로 부호를 붙인 금액(UI 편의용).
  int get signedAmount => (isIncome || isCancel) ? amount : -amount;

  @override
  String toString() =>
      'LedgerTransactionDto(id: $id, type: $transactionType, status: $status, '
      'amount: $amount, merchant: $merchant, category: $category, '
      'date: $date $time, needsReview: $needsUserConfirmation, '
      'confidence: $confidence)';
}

// ---------------------------------------------------------------------------
// 2) 대시보드 DTO
// ---------------------------------------------------------------------------

/// `GET /ledger/dashboard` 응답 data 에 대응.
///
/// summary / calendar / budget_alerts / recurring_preview 는 형태 변화 가능성이
/// 있어 원형(Map/List)으로 유연하게 보관하고, pending_transactions 만 DTO 화한다.
class LedgerDashboardDto {
  final Map<String, dynamic> summary;
  final List<dynamic> calendar;
  final Map<String, dynamic>? selectedDate;
  final List<LedgerTransactionDto> pendingTransactions;
  final List<dynamic> budgetAlerts;
  final List<dynamic> recurringPreview;
  final Map<String, dynamic> raw;

  const LedgerDashboardDto({
    required this.summary,
    required this.calendar,
    required this.selectedDate,
    required this.pendingTransactions,
    required this.budgetAlerts,
    required this.recurringPreview,
    required this.raw,
  });

  factory LedgerDashboardDto.fromJson(Map<String, dynamic> json) {
    return LedgerDashboardDto(
      summary: _asMap(json['summary']) ?? const {},
      calendar: _asList(json['calendar']),
      selectedDate: _asMap(_pick(json, ['selected_date', 'selectedDate'])),
      pendingTransactions:
          _asList(_pick(json, ['pending_transactions', 'pendingTransactions']))
              .map(_asMap)
              .where((m) => m != null)
              .map((m) => LedgerTransactionDto.fromJson(m!))
              .toList(),
      budgetAlerts: _asList(_pick(json, ['budget_alerts', 'budgetAlerts'])),
      recurringPreview: _asList(
        _pick(json, ['recurring_preview', 'recurringPreview']),
      ),
      raw: json,
    );
  }

  /// selected_date.transactions 를 DTO 리스트로 파싱(없으면 빈 리스트).
  List<LedgerTransactionDto> get selectedDateTransactions {
    final sel = selectedDate;
    if (sel == null) return const [];
    return _asList(sel['transactions'])
        .map(_asMap)
        .where((m) => m != null)
        .map((m) => LedgerTransactionDto.fromJson(m!))
        .toList();
  }

  @override
  String toString() =>
      'LedgerDashboardDto(summary: $summary, calendarDays: ${calendar.length}, '
      'pending: ${pendingTransactions.length}, '
      'budgetAlerts: ${budgetAlerts.length}, '
      'recurring: ${recurringPreview.length})';
}

// ---------------------------------------------------------------------------
// 2b) 월 전체 거래내역 DTO
// ---------------------------------------------------------------------------

/// `GET /ledger/transactions` 응답의 일자별 그룹 한 개(`by_date[i]`).
class LedgerDayGroupDto {
  /// 'YYYY-MM-DD'.
  final String date;
  final int expenseTotal;
  final int incomeTotal;
  final int netTotal;
  final int transactionCount;
  final List<LedgerTransactionDto> transactions;

  const LedgerDayGroupDto({
    required this.date,
    required this.expenseTotal,
    required this.incomeTotal,
    required this.netTotal,
    required this.transactionCount,
    required this.transactions,
  });

  factory LedgerDayGroupDto.fromJson(Map<String, dynamic> json) {
    return LedgerDayGroupDto(
      date: readString(json['date']) ?? '',
      expenseTotal: readInt(_pick(json, ['expense_total', 'expenseTotal'])),
      incomeTotal: readInt(_pick(json, ['income_total', 'incomeTotal'])),
      netTotal: readInt(_pick(json, ['net_total', 'netTotal'])),
      transactionCount: readInt(
        _pick(json, ['transaction_count', 'transactionCount']),
      ),
      transactions: _asList(json['transactions'])
          .map(_asMap)
          .where((m) => m != null)
          .map((m) => LedgerTransactionDto.fromJson(m!))
          .toList(),
    );
  }
}

/// `GET /ledger/transactions` 응답 data 에 대응.
///
/// 선택 날짜에 한정하지 않는 '월 전체' 거래내역. [byDate] 는 최신 날짜부터 정렬된
/// 일자별 그룹, [transactions] 는 동일 데이터의 평면(최신순) 목록이다.
class LedgerMonthTransactionsDto {
  final String? month;
  final Map<String, dynamic> summary;
  final List<LedgerTransactionDto> transactions;
  final List<LedgerDayGroupDto> byDate;
  final Map<String, dynamic> raw;

  const LedgerMonthTransactionsDto({
    required this.month,
    required this.summary,
    required this.transactions,
    required this.byDate,
    required this.raw,
  });

  factory LedgerMonthTransactionsDto.fromJson(Map<String, dynamic> json) {
    return LedgerMonthTransactionsDto(
      month: readString(json['month']),
      summary: _asMap(json['summary']) ?? const {},
      transactions: _asList(json['transactions'])
          .map(_asMap)
          .where((m) => m != null)
          .map((m) => LedgerTransactionDto.fromJson(m!))
          .toList(),
      byDate: _asList(_pick(json, ['by_date', 'byDate']))
          .map(_asMap)
          .where((m) => m != null)
          .map((m) => LedgerDayGroupDto.fromJson(m!))
          .toList(),
      raw: json,
    );
  }

  bool get isEmpty => transactions.isEmpty;

  @override
  String toString() =>
      'LedgerMonthTransactionsDto(month: $month, days: ${byDate.length}, '
      'transactions: ${transactions.length})';
}

// ---------------------------------------------------------------------------
// 3) 리포트 DTO
// ---------------------------------------------------------------------------

/// `GET /ledger/report` 응답 data 에 대응.
class LedgerReportDto {
  final Map<String, dynamic> summary;
  final List<dynamic> categoryAnalysis;
  final List<dynamic> budgetUsage;
  final List<dynamic> recurringPayments;

  /// 백엔드 briefing 은 `{title, message}` 객체. 문자열로 와도 안전하도록 nullable.
  final Map<String, dynamic>? briefing;

  /// 'YYYY-MM' (있으면).
  final String? month;

  final Map<String, dynamic> raw;

  const LedgerReportDto({
    required this.summary,
    required this.categoryAnalysis,
    required this.budgetUsage,
    required this.recurringPayments,
    required this.briefing,
    required this.month,
    required this.raw,
  });

  factory LedgerReportDto.fromJson(Map<String, dynamic> json) {
    // briefing 이 문자열로 올 경우에도 죽지 않도록 message 로 감싼다.
    final briefingRaw = json['briefing'];
    final Map<String, dynamic>? briefingMap =
        _asMap(briefingRaw) ??
        (readString(briefingRaw) != null
            ? <String, dynamic>{'message': readString(briefingRaw)}
            : null);

    return LedgerReportDto(
      summary: _asMap(json['summary']) ?? const {},
      categoryAnalysis: _asList(
        _pick(json, ['category_analysis', 'categoryAnalysis']),
      ),
      budgetUsage: _asList(_pick(json, ['budget_usage', 'budgetUsage'])),
      recurringPayments: _asList(
        _pick(json, ['recurring_payments', 'recurringPayments']),
      ),
      briefing: briefingMap,
      month: readString(json['month']),
      raw: json,
    );
  }

  @override
  String toString() =>
      'LedgerReportDto(month: $month, summary: $summary, '
      'categories: ${categoryAnalysis.length}, '
      'budgets: ${budgetUsage.length}, '
      'recurring: ${recurringPayments.length})';
}

// ---------------------------------------------------------------------------
// 4) 알림 시뮬레이트 결과 DTO
// ---------------------------------------------------------------------------

/// `POST /ledger/notifications/simulate` (및 영수증 스캔) 결과.
///
/// 응답 data 는 세 가지 형태로 올 수 있어 모두 흡수한다.
/// - 신규 저장: 거래 dict 자체(transaction_id/status/... 최상위)
/// - 중복: `{duplicate: true, duplicated_transaction_id, transaction: {...}}`
/// - 무시(ignore)/미저장: `{transaction_id: null, status: 'ignored', stored: false}`
class LedgerNotificationResultDto {
  /// 파싱된 거래(있으면). 중복이면 기존 거래, 신규면 새 거래, 무시면 null 일 수 있다.
  final LedgerTransactionDto? transaction;

  /// DB 저장 여부. 키가 없으면(=일반 신규 응답) 저장된 것으로 간주(true).
  final bool stored;

  /// 중복 판정 여부.
  final bool duplicate;

  /// 상태 문자열(pending / needs_review / ignored / duplicate ...).
  final String? status;

  /// 중복 시 기존 거래 ID.
  final String? duplicatedTransactionId;

  /// envelope message 가 data 안에 함께 실려오는 경우 대비(보통은 null).
  final String? message;

  final Map<String, dynamic> raw;

  const LedgerNotificationResultDto({
    required this.transaction,
    required this.stored,
    required this.duplicate,
    required this.status,
    required this.duplicatedTransactionId,
    required this.message,
    required this.raw,
  });

  factory LedgerNotificationResultDto.fromJson(Map<String, dynamic> json) {
    // 중첩된 transaction 우선, 없으면 응답 자체를 거래로 시도(유효 ID 있을 때만).
    LedgerTransactionDto? tx;
    final nested = _asMap(json['transaction']);
    if (nested != null) {
      tx = LedgerTransactionDto.fromJson(nested);
    } else {
      final selfHasTx =
          _pick(json, ['transaction_id', 'transactionId', 'id']) != null ||
          json.containsKey('transaction_type') ||
          json.containsKey('amount');
      if (selfHasTx) {
        final candidate = LedgerTransactionDto.fromJson(json);
        // ignore 응답처럼 ID 없고 저장 안 된 경우에도 정보 보존을 위해 담아둔다.
        tx = candidate;
      }
    }

    return LedgerNotificationResultDto(
      transaction: tx,
      stored: json.containsKey('stored') ? readBool(json['stored']) : true,
      duplicate: readBool(json['duplicate']),
      status: readString(json['status']) ?? tx?.status,
      duplicatedTransactionId: readString(
        _pick(json, ['duplicated_transaction_id', 'duplicatedTransactionId']),
      ),
      message: readString(json['message']),
      raw: json,
    );
  }

  bool get isIgnored => status == 'ignored' || (!stored && !duplicate);

  @override
  String toString() =>
      'LedgerNotificationResultDto(stored: $stored, duplicate: $duplicate, '
      'status: $status, tx: $transaction)';
}
