import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:timezone/data/latest_all.dart' as tzdata;
import 'package:timezone/timezone.dart' as tz;

import '../models/schedule_model.dart';
import '../screens/mock_call_alert_screen.dart';
import '../theme/app_constants.dart';
import 'briefing_api.dart';
import 'preference_store.dart';

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

  // 일정 사전(리드타임) 알림용 별도 채널/ID 대역.
  static const String _scheduleChannelId = 'schedule_alert';
  static const String _scheduleChannelName = '일정 사전 알림';
  static const String _scheduleChannelDesc = '일정 시작 전에 전화형 알림으로 미리 알려드려요.';
  static const int _scheduleAlertBaseId = 20000; // per-일정 알림 ID 시작 대역
  static const int _testAlertId = 20999; // 데모용 테스트 알림 ID
  static const int _voiceReminderBaseId = 21000; // 음성으로 설정한 리마인더 ID 대역

  static const String _briefingPayload = 'daily_briefing';
  static const String _scheduleAlertPrefix = 'schedule_alert:';

  final FlutterLocalNotificationsPlugin _plugin =
      FlutterLocalNotificationsPlugin();
  AndroidFlutterLocalNotificationsPlugin? _androidImpl;
  GlobalKey<NavigatorState>? _navigatorKey;
  bool _initialized = false;

  /// 이번에 예약해 둔 일정 사전 알림 ID들(재동기화 시 취소용).
  final List<int> _scheduleAlertIds = [];

  /// 음성으로 설정한 리마인더 알림 ID들(재설정 시 취소용).
  final List<int> _voiceReminderIds = [];

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
        _channelId,
        _channelName,
        description: _channelDesc,
        importance: Importance.max,
      );
      const scheduleChannel = AndroidNotificationChannel(
        _scheduleChannelId,
        _scheduleChannelName,
        description: _scheduleChannelDesc,
        importance: Importance.max,
      );
      _androidImpl = _plugin
          .resolvePlatformSpecificImplementation<
            AndroidFlutterLocalNotificationsPlugin
          >();
      await _androidImpl?.createNotificationChannel(channel);
      await _androidImpl?.createNotificationChannel(scheduleChannel);

      // 알림 권한(Android 13+) + 정확한 알람 권한(Android 12+)을 미리 요청한다.
      // exact alarm 이 없으면 zonedSchedule 이 조용히 실패해 알림이 안 뜬다.
      try {
        await _androidImpl?.requestNotificationsPermission();
        await _androidImpl?.requestExactAlarmsPermission();
      } catch (e) {
        debugPrint('[BriefingScheduler] permission request error: $e');
      }

      _initialized = true;
      debugPrint('[BriefingScheduler] initialized');

      // 앱이 완전히 종료된 상태에서 알림을 탭해 실행된 경우: 그 payload 로
      // 화면 이동을 처리한다(네비게이터가 준비된 뒤 지연 실행).
      final launch = await _plugin.getNotificationAppLaunchDetails();
      final resp = launch?.notificationResponse;
      if (launch?.didNotificationLaunchApp == true && resp != null) {
        WidgetsBinding.instance.addPostFrameCallback((_) {
          Future.delayed(const Duration(milliseconds: 600), () {
            _onNotificationTapped(resp);
          });
        });
      }
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
        '${AppStrings.assistantName}가 오늘 일정과 브리핑을 알려드려요. 눌러서 들어보세요.',
        _nextInstance(hour, minute),
        const NotificationDetails(
          android: AndroidNotificationDetails(
            _channelId,
            _channelName,
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

  // ------------------------------------------------------------------- //
  // 일정 사전(리드타임) 알림
  // ------------------------------------------------------------------- //

  /// 앞으로의 일정들에 대해 "시작 [leadMinutes]분 전" 전화형 알림을 일괄 예약한다.
  /// 이전에 예약해 둔 일정 알림은 모두 취소하고 새로 예약한다(중복 방지).
  /// [leadMinutes] <= 0 이면 전부 취소(비활성화)한다.
  Future<void> syncScheduleAlerts(
    List<ScheduleModel> schedules, {
    required int leadMinutes,
  }) async {
    if (!_initialized) return;

    // 기존 일정 알림 모두 취소.
    for (final id in _scheduleAlertIds) {
      try {
        await _plugin.cancel(id);
      } catch (_) {}
    }
    _scheduleAlertIds.clear();

    if (leadMinutes <= 0) {
      debugPrint('[ScheduleAlert] leadMinutes<=0 → 비활성화');
      return;
    }

    final granted = await ensureNotificationPermission();
    if (!granted) {
      debugPrint('[ScheduleAlert] 알림 권한 없음 — 예약 건너뜀');
      return;
    }

    final now = tz.TZDateTime.now(tz.local);
    var idx = 0;
    var scheduledCount = 0;
    for (final s in schedules) {
      final start = _buildStart(s);
      if (start == null) continue;
      final alertAt = start.subtract(Duration(minutes: leadMinutes));
      if (!alertAt.isAfter(now)) continue; // 이미 지난 시각은 스킵

      final id = _scheduleAlertBaseId + idx;
      idx++;
      final title = s.title.isNotEmpty ? s.title : '일정';
      final timeText = s.startTime ?? '';
      final baseMsg = leadMinutes >= 60
          ? '${_leadLabel(leadMinutes)} 뒤 \'$title\' 일정이 있어요.'
          : '$leadMinutes분 뒤 \'$title\' 일정이 있어요.';
      final msg = timeText.isEmpty ? baseMsg : '$baseMsg ($timeText 시작)';
      final tts = preferenceStore.applyReminderStrength(msg);

      await _scheduleOneAlert(
        id: id,
        when: alertAt,
        title: title,
        message: msg,
        ttsText: tts,
      );
      _scheduleAlertIds.add(id);
      scheduledCount++;
    }
    debugPrint('[ScheduleAlert] 예약 완료: $scheduledCount건 (lead=$leadMinutes분)');
  }

  /// 데모용: [seconds]초 뒤에 일정 사전 알림을 한 번 띄운다(권한/동작 확인).
  Future<void> scheduleTestAlert({int seconds = 10}) async {
    if (!_initialized) return;
    final granted = await ensureNotificationPermission();
    if (!granted) return;
    final when = tz.TZDateTime.now(tz.local).add(Duration(seconds: seconds));
    const title = '테스트 일정';
    final msg = preferenceStore.applyReminderStrength("곧 '$title' 일정이 시작돼요.");
    await _scheduleOneAlert(
      id: _testAlertId,
      when: when,
      title: title,
      message: "곧 '$title' 일정이 시작돼요.",
      ttsText: msg,
    );
    debugPrint('[ScheduleAlert] 테스트 알림 $seconds초 뒤 예약');
  }

  /// 음성으로 설정한 리마인더(`/voice/route` intent=reminder_setting)의 서버
  /// `reminder_plan` 을 받아 실제 OS 알림으로 예약한다.
  /// data 구조: { reminder_plan: { reminders: [{ trigger_time, message, ... }] } }
  Future<void> scheduleFromVoiceReminderPlan(Map<String, dynamic> data) async {
    if (!_initialized) return;

    // 이전에 음성으로 잡아둔 리마인더는 모두 취소하고 새로 예약(중복 방지).
    for (final id in _voiceReminderIds) {
      try {
        await _plugin.cancel(id);
      } catch (_) {}
    }
    _voiceReminderIds.clear();

    final plan = data['reminder_plan'];
    if (plan is! Map) return;
    final reminders = plan['reminders'];
    if (reminders is! List || reminders.isEmpty) return;

    final granted = await ensureNotificationPermission();
    if (!granted) {
      debugPrint('[VoiceReminder] 알림 권한 없음 — 예약 건너뜀');
      return;
    }

    final now = tz.TZDateTime.now(tz.local);
    var idx = 0;
    var count = 0;
    for (final r in reminders) {
      if (r is! Map) continue;
      final trigger = r['trigger_time']?.toString();
      if (trigger == null || trigger.isEmpty) continue;
      final when = _parseLocalIso(trigger);
      if (when == null || !when.isAfter(now)) {
        debugPrint('[VoiceReminder] 과거/무효 시각 스킵: $trigger');
        continue;
      }
      final message = (r['message'] ?? '곧 일정이 시작돼요.').toString();
      final id = _voiceReminderBaseId + idx;
      idx++;
      await _scheduleOneAlert(
        id: id,
        when: when,
        title: '일정 알림',
        message: message,
        ttsText: preferenceStore.applyReminderStrength(message),
      );
      _voiceReminderIds.add(id);
      count++;
    }
    debugPrint('[VoiceReminder] 예약 완료: $count건');
  }

  /// 'YYYY-MM-DDTHH:mm:ss'(타임존 표기 없음)을 Asia/Seoul 기준 TZDateTime 으로.
  tz.TZDateTime? _parseLocalIso(String iso) {
    final dt = DateTime.tryParse(iso);
    if (dt == null) return null;
    return tz.TZDateTime(
      tz.local,
      dt.year,
      dt.month,
      dt.day,
      dt.hour,
      dt.minute,
      dt.second,
    );
  }

  Future<void> _scheduleOneAlert({
    required int id,
    required tz.TZDateTime when,
    required String title,
    required String message,
    required String ttsText,
  }) async {
    final payload =
        _scheduleAlertPrefix +
        jsonEncode({'title': title, 'message': message, 'tts': ttsText});
    const details = NotificationDetails(
      android: AndroidNotificationDetails(
        _scheduleChannelId,
        _scheduleChannelName,
        channelDescription: _scheduleChannelDesc,
        importance: Importance.max,
        priority: Priority.high,
        fullScreenIntent: true, // 전화 수신처럼 화면을 깨움
        category: AndroidNotificationCategory.call,
      ),
      iOS: DarwinNotificationDetails(),
    );
    // exact 알람이 권한 문제로 실패하면 inexact 로라도 예약(알림이 아예 안 뜨는 것 방지).
    for (final mode in const [
      AndroidScheduleMode.exactAllowWhileIdle,
      AndroidScheduleMode.inexactAllowWhileIdle,
    ]) {
      try {
        await _plugin.zonedSchedule(
          id,
          '📞 $title',
          message,
          when,
          details,
          androidScheduleMode: mode,
          uiLocalNotificationDateInterpretation:
              UILocalNotificationDateInterpretation.absoluteTime,
          payload: payload,
        );
        return; // 성공하면 종료
      } catch (e) {
        debugPrint('[ScheduleAlert] zonedSchedule($mode) 실패(id=$id): $e');
      }
    }
  }

  /// 일정의 date('YYYY-MM-DD') + start_time('HH:mm') → 로컬 TZ 시작 시각.
  tz.TZDateTime? _buildStart(ScheduleModel s) {
    final date = s.date;
    final time = s.startTime;
    if (date == null || date.isEmpty || time == null || time.isEmpty)
      return null;
    final d = RegExp(r'^(\d{4})-(\d{1,2})-(\d{1,2})$').firstMatch(date);
    final t = RegExp(r'^(\d{1,2}):(\d{2})$').firstMatch(time);
    if (d == null || t == null) return null;
    try {
      return tz.TZDateTime(
        tz.local,
        int.parse(d.group(1)!),
        int.parse(d.group(2)!),
        int.parse(d.group(3)!),
        int.parse(t.group(1)!),
        int.parse(t.group(2)!),
      );
    } catch (_) {
      return null;
    }
  }

  String _leadLabel(int minutes) {
    if (minutes % 60 == 0) return '${minutes ~/ 60}시간';
    return '${minutes ~/ 60}시간 ${minutes % 60}분';
  }

  /// 일정 사전 알림 탭 → payload(JSON)로 전화형 화면을 자동 재생으로 연다.
  void _openScheduleAlert(String jsonPart) {
    final navigator = _navigatorKey?.currentState;
    if (navigator == null) return;
    String title = '일정 알림';
    String message = '곧 일정이 시작돼요.';
    String tts = message;
    try {
      final m = jsonDecode(jsonPart) as Map<String, dynamic>;
      title = (m['title'] ?? title).toString();
      message = (m['message'] ?? message).toString();
      tts = (m['tts'] ?? message).toString();
    } catch (_) {}
    navigator.push(
      MaterialPageRoute(
        builder: (_) => MockCallAlertScreen(
          overrideTitle: title,
          overrideMessage: message,
          overrideTtsText: tts,
          autoPlay: true,
        ),
      ),
    );
  }

  (int, int)? _parseHhmm(String value) {
    final m = RegExp(r'^([01]\d|2[0-3]):([0-5]\d)$').firstMatch(value.trim());
    if (m == null) return null;
    return (int.parse(m.group(1)!), int.parse(m.group(2)!));
  }

  tz.TZDateTime _nextInstance(int hour, int minute) {
    final now = tz.TZDateTime.now(tz.local);
    var scheduled = tz.TZDateTime(
      tz.local,
      now.year,
      now.month,
      now.day,
      hour,
      minute,
    );
    if (!scheduled.isAfter(now)) {
      scheduled = scheduled.add(const Duration(days: 1));
    }
    return scheduled;
  }

  /// 알림을 탭했을 때: payload 로 분기해 전화형 알림 화면을 자동 재생으로 연다.
  void _onNotificationTapped(NotificationResponse response) {
    final payload = response.payload ?? '';
    if (payload.startsWith(_scheduleAlertPrefix)) {
      _openScheduleAlert(payload.substring(_scheduleAlertPrefix.length));
      return;
    }
    if (payload != _briefingPayload) return;
    final navigator = _navigatorKey?.currentState;
    if (navigator == null) return;

    () async {
      String title = '오늘의 브리핑';
      String message = '오늘 브리핑을 불러오지 못했어요.';
      String ttsText = message;
      try {
        final briefing = await briefingApi.getDailyBriefing();
        message = briefing.summary.isNotEmpty ? briefing.summary : message;
        ttsText =
            (briefing.ttsText != null && briefing.ttsText!.trim().isNotEmpty)
            ? briefing.ttsText!
            : message;
      } catch (e) {
        debugPrint('[BriefingScheduler] briefing fetch failed: $e');
      }

      navigator.push(
        MaterialPageRoute(
          builder: (_) => MockCallAlertScreen(
            overrideTitle: title,
            overrideMessage: message,
            overrideTtsText: ttsText,
            autoPlay: true,
          ),
        ),
      );
    }();
  }
}

final briefingSchedulerService = BriefingSchedulerService.instance;
