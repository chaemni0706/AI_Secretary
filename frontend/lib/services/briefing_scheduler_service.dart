import 'package:flutter/material.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:timezone/data/latest_all.dart' as tzdata;
import 'package:timezone/timezone.dart' as tz;

import '../screens/mock_call_alert_screen.dart';
import 'briefing_api.dart';

/// 사용자가 설정한 시각에 "오늘 브리핑"을 전화형 알림으로 띄우는 스케줄러.
///
/// MVP 정책: 실제 전화/푸시 서버 없이 `flutter_local_notifications` 로 매일
/// 같은 시각에 로컬 알림만 예약한다. 알림을 탭하면 [MockCallAlertScreen]을
/// 브리핑 데이터로 채워 열고, 그 화면이 자동으로 TTS를 재생한다(스펙 C-2).
///
/// 날씨 연동은 아직 없어 브리핑 문장 자체에 안내 문구가 포함된다
/// (`voice_route_orchestrator._handle_daily_briefing` 참고).
class BriefingSchedulerService {
  BriefingSchedulerService._();
  static final BriefingSchedulerService instance = BriefingSchedulerService._();

  static const int _notificationId = 9001;
  static const String _channelId = 'daily_briefing';
  static const String _channelName = '자동 브리핑';
  static const String _channelDesc = '설정한 시각에 오늘 일정과 브리핑을 알려드려요.';

  final FlutterLocalNotificationsPlugin _plugin = FlutterLocalNotificationsPlugin();
  GlobalKey<NavigatorState>? _navigatorKey;
  bool _initialized = false;

  /// 앱 시작 시 1회 호출. 알림 탭 시 이동할 화면을 위해 rootNavigatorKey 를 받는다.
  Future<void> init(GlobalKey<NavigatorState> navigatorKey) async {
    if (_initialized) return;
    _navigatorKey = navigatorKey;
    try {
      tzdata.initializeTimeZones();
      // 서버/데이터는 모두 Asia/Seoul 기준(스펙 전반의 timezone 기본값)이라
      // 로컬 알림도 동일 기준으로 맞춘다.
      tz.setLocalLocation(tz.getLocation('Asia/Seoul'));

      const androidInit = AndroidInitializationSettings('@mipmap/ic_launcher');
      const iosInit = DarwinInitializationSettings();
      await _plugin.initialize(
        const InitializationSettings(android: androidInit, iOS: iosInit),
        onDidReceiveNotificationResponse: _onNotificationTapped,
      );

      const channel = AndroidNotificationChannel(
        _channelId, _channelName,
        description: _channelDesc,
        importance: Importance.max,
      );
      await _plugin
          .resolvePlatformSpecificImplementation<
              AndroidFlutterLocalNotificationsPlugin>()
          ?.createNotificationChannel(channel);

      _initialized = true;
      debugPrint('[BriefingScheduler] initialized');
    } catch (e) {
      debugPrint('[BriefingScheduler] init error: $e');
    }
  }

  /// 알림 권한 확인/요청 (Android 13+ POST_NOTIFICATIONS).
  Future<bool> ensureNotificationPermission() async {
    try {
      final status = await Permission.notification.status;
      if (status.isGranted) return true;
      final result = await Permission.notification.request();
      return result.isGranted;
    } catch (e) {
      debugPrint('[BriefingScheduler] permission error: $e');
      return false;
    }
  }

  /// [hhmm] 이 'HH:mm' 형식이면 매일 그 시각에 반복 알림을 예약한다.
  /// 빈 문자열/형식 오류면 예약을 취소한다(비활성화).
  Future<void> scheduleDailyBriefing(String hhmm) async {
    if (!_initialized) return;
    final parsed = _parseHhmm(hhmm);
    if (parsed == null) {
      await cancel();
      return;
    }
    final granted = await ensureNotificationPermission();
    if (!granted) {
      debugPrint('[BriefingScheduler] notification permission denied — 예약 건너뜀');
      return;
    }

    final (hour, minute) = parsed;
    try {
      await _plugin.zonedSchedule(
        _notificationId,
        '오늘의 브리핑',
        '챔니가 오늘 일정과 브리핑을 알려드려요. 눌러서 들어보세요.',
        _nextInstance(hour, minute),
        const NotificationDetails(
          android: AndroidNotificationDetails(
            _channelId, _channelName,
            channelDescription: _channelDesc,
            importance: Importance.max,
            priority: Priority.high,
            fullScreenIntent: true, // 전화 수신처럼 화면을 깨우는 느낌
          ),
          iOS: DarwinNotificationDetails(),
        ),
        androidScheduleMode: AndroidScheduleMode.exactAllowWhileIdle,
        uiLocalNotificationDateInterpretation:
            UILocalNotificationDateInterpretation.absoluteTime,
        matchDateTimeComponents: DateTimeComponents.time, // 매일 반복
        payload: 'daily_briefing',
      );
      debugPrint('[BriefingScheduler] scheduled daily briefing at $hhmm');
    } catch (e) {
      debugPrint('[BriefingScheduler] schedule error: $e');
    }
  }

  Future<void> cancel() async {
    if (!_initialized) return;
    try {
      await _plugin.cancel(_notificationId);
      debugPrint('[BriefingScheduler] cancelled');
    } catch (e) {
      debugPrint('[BriefingScheduler] cancel error: $e');
    }
  }

  (int, int)? _parseHhmm(String value) {
    final m = RegExp(r'^([01]\d|2[0-3]):([0-5]\d)$').firstMatch(value.trim());
    if (m == null) return null;
    return (int.parse(m.group(1)!), int.parse(m.group(2)!));
  }

  tz.TZDateTime _nextInstance(int hour, int minute) {
    final now = tz.TZDateTime.now(tz.local);
    var scheduled = tz.TZDateTime(tz.local, now.year, now.month, now.day, hour, minute);
    if (!scheduled.isAfter(now)) {
      scheduled = scheduled.add(const Duration(days: 1));
    }
    return scheduled;
  }

  /// 알림을 탭했을 때: 오늘 브리핑을 불러와 전화형 알림 화면을 자동 재생으로 연다.
  void _onNotificationTapped(NotificationResponse response) {
    if (response.payload != 'daily_briefing') return;
    final navigator = _navigatorKey?.currentState;
    if (navigator == null) return;

    () async {
      String title = '오늘의 브리핑';
      String message = '오늘 브리핑을 불러오지 못했어요.';
      String ttsText = message;
      try {
        final briefing = await briefingApi.getDailyBriefing();
        message = briefing.summary.isNotEmpty ? briefing.summary : message;
        ttsText = (briefing.ttsText != null && briefing.ttsText!.trim().isNotEmpty)
            ? briefing.ttsText!
            : message;
      } catch (e) {
        debugPrint('[BriefingScheduler] briefing fetch failed: $e');
      }

      navigator.push(MaterialPageRoute(
        builder: (_) => MockCallAlertScreen(
          overrideTitle: title,
          overrideMessage: message,
          overrideTtsText: ttsText,
          autoPlay: true,
        ),
      ));
    }();
  }
}

final briefingSchedulerService = BriefingSchedulerService.instance;
