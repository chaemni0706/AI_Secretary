import '../models/ledger_api_models.dart';
import 'api_client.dart';

/// AI 가계부(Ledger) 백엔드 API 클라이언트.
///
/// 경로는 모두 `$apiPrefix/ledger/...` (= `/api/v1/ledger/...`).
/// envelope(`{success, message, data}`) 해제는 [apiClient] 가 처리하므로 여기서는
/// **data 만** 받아 DTO 로 파싱한다. 실패는 삼키지 않고 [ApiException] 이 그대로
/// 화면까지 올라간다. 응답 형태가 예상과 다르면 [FormatException] 을 던진다.
class LedgerApi {
  const LedgerApi();

  static const String _base = '$apiPrefix/ledger';

  // ------------------------------------------------------------------------
  // 조회
  // ------------------------------------------------------------------------

  /// 가계부 홈 대시보드: `GET /ledger/dashboard`
  ///
  /// [month] 는 1~12. [selectedDate] 가 있으면 'YYYY-MM-DD' 로 함께 전송한다.
  Future<LedgerDashboardDto> dashboard({
    String userId = 'local-user',
    required int year,
    required int month,
    DateTime? selectedDate,
  }) async {
    final query = <String, dynamic>{
      'user_id': userId,
      'month': _formatMonth(year, month),
    };
    if (selectedDate != null) {
      query['selected_date'] = _formatDate(selectedDate);
    }
    final data = await apiClient.getData('$_base/dashboard', query: query);
    return LedgerDashboardDto.fromJson(_expectMap(data, 'dashboard'));
  }

  /// 월간 소비 리포트: `GET /ledger/report`
  Future<LedgerReportDto> report({
    String userId = 'local-user',
    required int year,
    required int month,
  }) async {
    final data = await apiClient.getData(
      '$_base/report',
      query: {'user_id': userId, 'month': _formatMonth(year, month)},
    );
    return LedgerReportDto.fromJson(_expectMap(data, 'report'));
  }

  /// 월 전체 거래내역: `GET /ledger/transactions`
  ///
  /// 대시보드가 '선택 날짜'만 반환하는 것과 달리, 해당 월의 모든 거래를
  /// 일자별 그룹(`by_date`, 최신순)과 평면 목록(`transactions`)으로 함께 받는다.
  /// [status] 가 주어지면 쉼표구분 상태 필터로 전달한다(예: 'confirmed,pending').
  Future<LedgerMonthTransactionsDto> monthTransactions({
    String userId = 'local-user',
    required int year,
    required int month,
    String? status,
  }) async {
    final query = <String, dynamic>{
      'user_id': userId,
      'month': _formatMonth(year, month),
    };
    if (status != null && status.trim().isNotEmpty) {
      query['status'] = status.trim();
    }
    final data = await apiClient.getData('$_base/transactions', query: query);
    return LedgerMonthTransactionsDto.fromJson(
      _expectMap(data, 'transactions'),
    );
  }

  // ------------------------------------------------------------------------
  // 알림 → 거래 후보 생성
  // ------------------------------------------------------------------------

  /// mock 결제/입금 알림 파싱 & 거래 생성: `POST /ledger/notifications/simulate`
  ///
  /// [notificationText] 는 알림 본문(body)으로 전송된다. [packageName] 은 발신 앱
  /// (app_name), [receivedAt] 은 수신 시각(ISO)으로 매핑된다.
  Future<LedgerNotificationResultDto> simulateNotification({
    String userId = 'local-user',
    required String notificationText,
    String? packageName,
    DateTime? receivedAt,
  }) async {
    final body = <String, dynamic>{
      'user_id': userId,
      'app_name': packageName,
      'title': '',
      'body': notificationText,
      'received_at': _formatIso(receivedAt),
    };
    final data = await apiClient.postData(
      '$_base/notifications/simulate',
      body: body,
    );
    return LedgerNotificationResultDto.fromJson(
      _expectMap(data, 'notifications/simulate'),
    );
  }

  // ------------------------------------------------------------------------
  // 거래 확정 / 수정 / 삭제
  // ------------------------------------------------------------------------

  /// 대기 거래 확정: `POST /ledger/transactions/{id}/confirm`
  Future<LedgerTransactionDto> confirmTransaction({
    required String transactionId,
    String userId = 'local-user',
  }) async {
    final data = await apiClient.postData(
      '$_base/transactions/$transactionId/confirm',
    );
    return LedgerTransactionDto.fromJson(_expectMap(data, 'confirm'));
  }

  /// 거래 수정: `PATCH /ledger/transactions/{id}`
  ///
  /// 백엔드는 category / merchant / amount / occurred_at / status / memo 를 받는다.
  /// [date]·[time] 이 주어지면 여기서 occurred_at(ISO)로 합쳐 전송한다.
  /// (백엔드가 occurred_at 으로부터 date/time 을 재계산한다.)
  /// [memo] 는 null 이면 미전송(변경 없음), 빈 문자열이면 메모 삭제로 전송한다.
  Future<LedgerTransactionDto> updateTransaction({
    required String transactionId,
    String userId = 'local-user',
    int? amount,
    String? merchant,
    String? category,
    String? date,
    String? time,
    String? memo,
  }) async {
    final body = <String, dynamic>{};
    if (amount != null) body['amount'] = amount;
    if (merchant != null) body['merchant'] = merchant;
    if (category != null) body['category'] = category;
    if (memo != null) body['memo'] = memo;

    final occurredAt = _composeOccurredAt(date, time);
    if (occurredAt != null) body['occurred_at'] = occurredAt;

    final data = await apiClient.patchData(
      '$_base/transactions/$transactionId',
      body: body,
    );
    return LedgerTransactionDto.fromJson(_expectMap(data, 'update'));
  }

  /// 거래 삭제(soft): `DELETE /ledger/transactions/{id}`
  Future<void> deleteTransaction({
    required String transactionId,
    String userId = 'local-user',
  }) async {
    await apiClient.deleteData('$_base/transactions/$transactionId');
  }

  // ------------------------------------------------------------------------
  // 시연용 시드
  // ------------------------------------------------------------------------

  /// mock 데이터 시드(idempotent): `POST /ledger/mock/seed`
  Future<void> seedMock({String userId = 'local-user'}) async {
    await apiClient.postData('$_base/mock/seed', query: {'user_id': userId});
  }

  // ------------------------------------------------------------------------
  // 내부 헬퍼
  // ------------------------------------------------------------------------

  /// 'YYYY-MM' 형식(백엔드 month 파라미터).
  String _formatMonth(int year, int month) => '${_pad4(year)}-${_pad2(month)}';

  /// 'YYYY-MM-DD' 형식(백엔드 selected_date 파라미터).
  String _formatDate(DateTime d) =>
      '${_pad4(d.year)}-${_pad2(d.month)}-${_pad2(d.day)}';

  /// ISO datetime('YYYY-MM-DDTHH:MM:SS'). null 이면 null.
  String? _formatIso(DateTime? d) {
    if (d == null) return null;
    return '${_formatDate(d)}T${_pad2(d.hour)}:${_pad2(d.minute)}:${_pad2(d.second)}';
  }

  /// date('YYYY-MM-DD') + time('HH:MM') → occurred_at(ISO). date 가 없으면 null.
  String? _composeOccurredAt(String? date, String? time) {
    final d = date?.trim();
    if (d == null || d.isEmpty) return null;
    final t = (time?.trim().isNotEmpty ?? false) ? time!.trim() : '00:00';
    final seconds = t.split(':').length >= 3 ? '' : ':00';
    return '${d}T$t$seconds';
  }

  String _pad2(int n) => n.toString().padLeft(2, '0');
  String _pad4(int n) => n.toString().padLeft(4, '0');

  /// data 가 Map 인지 검증하고 반환. 아니면 명확한 FormatException.
  Map<String, dynamic> _expectMap(dynamic data, String where) {
    if (data is Map<String, dynamic>) return data;
    if (data is Map) return data.map((k, v) => MapEntry(k.toString(), v));
    throw FormatException('ledger $where 응답이 Map 이 아닙니다: ${data.runtimeType}');
  }
}

/// 간편 접근용 전역 인스턴스(기존 서비스들과 동일한 패턴).
const LedgerApi ledgerApi = LedgerApi();
