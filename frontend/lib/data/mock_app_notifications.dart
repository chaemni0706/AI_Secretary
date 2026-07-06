import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

class AppNotificationMock {
  final IconData icon;
  final Color color;
  final String title;
  final String message;
  final String time;

  const AppNotificationMock({
    required this.icon,
    required this.color,
    required this.title,
    required this.message,
    required this.time,
  });
}

const mockAppNotifications = [
  AppNotificationMock(
    icon: Icons.event_available_outlined,
    color: AppTheme.blue,
    title: '일정 알림',
    message: '오늘 오후 일정 2개가 예정되어 있어요.',
    time: '09:00',
  ),
  AppNotificationMock(
    icon: Icons.check_circle_outline,
    color: AppTheme.green,
    title: '할 일 알림',
    message: '오늘 마감인 할 일을 확인해 주세요.',
    time: '10:30',
  ),
  AppNotificationMock(
    icon: Icons.account_balance_wallet_outlined,
    color: AppTheme.orange,
    title: '가계부 알림',
    message: '이번 주 지출 흐름을 정리할 시간이에요.',
    time: '어제',
  ),
];
