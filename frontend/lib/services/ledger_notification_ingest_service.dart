import 'package:flutter/foundation.dart';

import '../models/ledger_api_models.dart';
import 'ledger_api.dart';

/// 알림 원문 → 백엔드 거래 등록의 **단일 진입점**.
///
/// 출처가 무엇이든(시연용 버튼, 향후 Android NotificationListenerService, 붙여넣기
/// 등) 알림 "원문 텍스트"만 이 서비스로 넘기면 동일하게 백엔드로 전달된다.
///
/// 설계 원칙
/// - 프론트는 금액/상호/카테고리를 **파싱하지 않는다**. 파싱·분류·중복판정은 전적으로
///   백엔드(ledger_notification_parser / ledger_service)가 담당한다(source of truth).
/// - 추후 네이티브 NotificationListenerService 에서 수신한 알림도, 원문을
///   [ingestRawNotification] 으로 그대로 연결하면 된다.
/// - 실제 금융 앱 패키지 필터링(어떤 앱의 알림만 받을지)은 이 프론트 서비스가 아니라
///   네이티브/설정 계층에서 처리할 예정이다. 여기서는 필터링하지 않는다.
class LedgerNotificationIngestService {
  const LedgerNotificationIngestService();

  /// 알림 원문 한 건을 백엔드로 보내 거래(후보)를 생성한다.
  ///
  /// [text]        : 알림 원문(예: '[KB국민카드] 스타벅스 6,300원 승인').
  /// [source]      : 논리적 출처 식별자('manual_demo' | 'android_listener' | ...).
  ///                 현재는 로깅/향후 라우팅용이며 백엔드 파싱에는 영향을 주지 않는다.
  /// [packageName] : 발신 앱 패키지/이름(백엔드 app_name 으로 매핑).
  /// [receivedAt]  : 수신 시각(백엔드 received_at, ISO).
  Future<LedgerNotificationResultDto> ingestRawNotification({
    required String text,
    String source = 'manual_demo',
    String? packageName,
    DateTime? receivedAt,
    String userId = 'local-user',
  }) async {
    final trimmed = text.trim();
    if (trimmed.isEmpty) {
      throw ArgumentError('알림 원문이 비어 있습니다.');
    }
    debugPrint('[LedgerIngest] source=$source pkg=$packageName len=${trimmed.length}');

    // 프론트는 원문만 전달한다. 파싱/분류/중복판정은 백엔드가 수행한다.
    return ledgerApi.simulateNotification(
      userId: userId,
      notificationText: trimmed,
      packageName: packageName,
      receivedAt: receivedAt,
    );
  }
}

/// 간편 접근용 전역 인스턴스(기존 서비스들과 동일 패턴).
const LedgerNotificationIngestService ledgerNotificationIngest =
    LedgerNotificationIngestService();
