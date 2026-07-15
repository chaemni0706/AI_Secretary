/// 시연용 "임의 금융 알림" 템플릿.
///
/// 카드/은행 결제 알림처럼 보이는 **원문 텍스트**만 담는다. 금액/상호/카테고리
/// 파싱은 전적으로 백엔드(ledger_notification_parser / ledger_service)가 담당하므로
/// 프론트는 이 원문을 그대로 `/ledger/notifications/simulate` 로 전달한다.
///
/// 파서가 안정적으로 인식하도록 "상호명 → 금액 → 결제/입금 키워드" 순서를 지킨다.
library;

class LedgerNotificationTemplate {
  /// 선택 칩에 보여줄 짧은 라벨.
  final String label;

  /// 백엔드로 전송할 알림 원문.
  final String text;

  const LedgerNotificationTemplate(this.label, this.text);
}

/// 빠른 선택용 알림 템플릿 목록.
const List<LedgerNotificationTemplate> ledgerNotificationTemplates = [
  LedgerNotificationTemplate('스타벅스', '[KB국민카드] 스타벅스 6,300원 승인'),
  LedgerNotificationTemplate('배달의민족', '[신한카드] 배달의민족 18,900원 결제'),
  LedgerNotificationTemplate('택시', '[카카오페이] 택시 12,400원 결제 완료'),
  LedgerNotificationTemplate('입금', '[토스뱅크] 홍길동님에게 50,000원 입금'),
  LedgerNotificationTemplate('넷플릭스', '[현대카드] 넷플릭스 17,000원 정기결제'),
  LedgerNotificationTemplate('결제취소', '[국민카드] 쿠팡 32,500원 승인취소'),
  LedgerNotificationTemplate('편의점', '[BC카드] CU 2,800원 승인'),
  LedgerNotificationTemplate('마트', '[삼성카드] 이마트 54,000원 승인'),
];
