import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

import '../models/ledger_api_models.dart';
import 'ledger_notification_ingest_service.dart';

/// Android '알림 접근(NotificationListener)' 권한 제어 + 네이티브 알림 스트림 연결.
///
/// - 권한은 사용자가 시스템 설정 화면에서 직접 허용해야 한다([openPermissionSettings]).
/// - 네이티브에서 올라온 알림 원문은 [listenAndIngest] 로 구독해 그대로
///   [LedgerNotificationIngestService] 로 넘긴다(프론트 파싱 없음).
/// - Android 외 플랫폼(iOS/web/desktop)에서는 모든 메서드가 안전하게 no-op.
class LedgerNotificationPermissionService {
  const LedgerNotificationPermissionService();

  static const MethodChannel _control = MethodChannel(
    'ai_secretary/ledger_notifications/control',
  );
  static const EventChannel _events = EventChannel(
    'ai_secretary/ledger_notifications',
  );

  bool get _isAndroid =>
      !kIsWeb && defaultTargetPlatform == TargetPlatform.android;

  /// 알림 접근 권한이 켜져 있는지.
  Future<bool> isPermissionGranted() async {
    if (!_isAndroid) return false;
    try {
      final granted = await _control.invokeMethod<bool>('isPermissionGranted');
      return granted ?? false;
    } on PlatformException {
      return false;
    } on MissingPluginException {
      return false;
    }
  }

  /// 시스템 '알림 접근' 설정 화면을 연다.
  Future<void> openPermissionSettings() async {
    if (!_isAndroid) return;
    try {
      await _control.invokeMethod<void>('openSettings');
    } on PlatformException {
      // 무시 — 설정 화면을 열 수 없어도 앱은 계속 동작한다.
    } on MissingPluginException {
      // 무시
    }
  }

  /// 네이티브 알림 원문 스트림을 구독해 자동으로 백엔드에 등록한다.
  ///
  /// 반환한 [StreamSubscription] 을 화면 dispose 시 cancel 한다.
  /// Android 가 아니면 null 을 반환(no-op)한다.
  StreamSubscription<dynamic>? listenAndIngest({
    void Function(LedgerNotificationResultDto result)? onIngested,
    void Function(Object error)? onError,
    String userId = 'local-user',
  }) {
    if (!_isAndroid) return null;
    return _events.receiveBroadcastStream().listen(
      (dynamic event) async {
        try {
          if (event is! Map) return;
          final text = (event['text'] ?? '').toString();
          final pkg = event['packageName']?.toString();
          if (text.trim().isEmpty) return;
          final result = await ledgerNotificationIngest.ingestRawNotification(
            text: text,
            source: 'android_listener',
            packageName: pkg,
            receivedAt: DateTime.now(),
            userId: userId,
          );
          onIngested?.call(result);
        } catch (e) {
          onError?.call(e);
        }
      },
      onError: (Object e) => onError?.call(e),
      cancelOnError: false,
    );
  }
}

/// 간편 접근용 전역 인스턴스.
const LedgerNotificationPermissionService ledgerNotificationPermission =
    LedgerNotificationPermissionService();
