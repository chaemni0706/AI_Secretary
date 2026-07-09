import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';

/// 시연용 로컬 알림 표시 서비스.
///
/// 공기계 데모에서 "진짜 금융 알림이 뜬 것처럼" 상단 알림을 띄우는 **보여주기용**이다.
/// 실제 거래 등록의 source of truth 는 백엔드 API 이며, 이 알림 표시가 실패해도
/// 거래 등록 흐름에는 영향을 주지 않는다(모든 실패는 삼켜 로그만 남긴다).
class LocalDemoNotificationService {
  LocalDemoNotificationService._();
  static final LocalDemoNotificationService instance =
      LocalDemoNotificationService._();

  static const String _channelId = 'ledger_demo_finance';
  static const String _channelName = '가계부 결제 알림(시연)';
  static const String _channelDesc = '시연용 금융 결제/입금 알림';

  final FlutterLocalNotificationsPlugin _plugin =
      FlutterLocalNotificationsPlugin();
  bool _initialized = false;
  int _id = 7100; // 데모 알림 ID 시퀀스(브리핑 등 다른 알림과 겹치지 않게).

  /// 지연 초기화. 채널 생성 + (Android 13+) 알림 권한 요청.
  /// 권한이 없어도 예외를 던지지 않는다.
  Future<void> _ensureInit() async {
    if (_initialized) return;
    try {
      const androidInit = AndroidInitializationSettings('@mipmap/ic_launcher');
      const iosInit = DarwinInitializationSettings();
      await _plugin.initialize(
        const InitializationSettings(android: androidInit, iOS: iosInit),
      );

      final android = _plugin.resolvePlatformSpecificImplementation<
          AndroidFlutterLocalNotificationsPlugin>();
      const channel = AndroidNotificationChannel(
        _channelId,
        _channelName,
        description: _channelDesc,
        importance: Importance.high,
      );
      await android?.createNotificationChannel(channel);
      // Android 13+ 알림 권한. 거부돼도 등록 흐름은 계속된다.
      try {
        await android?.requestNotificationsPermission();
      } catch (e) {
        debugPrint('[LocalDemoNotif] permission request error: $e');
      }
      _initialized = true;
    } catch (e) {
      debugPrint('[LocalDemoNotif] init error: $e');
    }
  }

  /// 금융 알림처럼 보이는 로컬 알림을 즉시 표시한다.
  /// 표시 실패는 삼킨다(거래 등록과 독립적).
  Future<void> showFinanceNotification({
    required String title,
    required String body,
  }) async {
    try {
      await _ensureInit();
      if (!_initialized) return;
      const details = NotificationDetails(
        android: AndroidNotificationDetails(
          _channelId,
          _channelName,
          channelDescription: _channelDesc,
          importance: Importance.high,
          priority: Priority.high,
          ticker: '결제 알림',
        ),
        iOS: DarwinNotificationDetails(),
      );
      await _plugin.show(_id++, title, body, details);
    } catch (e) {
      debugPrint('[LocalDemoNotif] show error: $e');
    }
  }
}

/// 간편 접근용 전역 인스턴스.
final localDemoNotifications = LocalDemoNotificationService.instance;
