import 'package:flutter/material.dart';
import 'app_theme.dart';

class ScheduleStyles {
  static const List<String> categoryOrder = [
    '직장',
    '개인',
    '공부',
    '건강',
    '약속',
    '기타',
  ];

  static String categoryLabel(String? category) {
    final value = category?.trim();
    if (value == null || value.isEmpty) return '기타';

    switch (value) {
      case 'work':
        return '직장';
      case 'personal':
        return '개인';
      case 'study':
        return '공부';
      case 'exercise':
      case 'hospital':
      case 'health':
        return '건강';
      case 'meeting':
      case 'appointment':
      case 'reservation':
      case 'meal':
      case 'beauty':
        return '약속';
      case '직장':
      case '개인':
      case '공부':
      case '건강':
      case '약속':
      case '기타':
        return value;
      default:
        return value;
    }
  }

  static Color categoryColor(String? category) {
    switch (categoryLabel(category)) {
      case '직장':
        return AppTheme.blue;
      case '개인':
        return AppTheme.orange;
      case '공부':
        return AppTheme.purple;
      case '건강':
        return AppTheme.green;
      case '약속':
        return AppTheme.teal;
      default:
        return AppTheme.textSecondary;
    }
  }

  static IconData categoryIcon(String? category) {
    switch (categoryLabel(category)) {
      case '직장':
        return Icons.work_outline;
      case '개인':
        return Icons.person_outline;
      case '공부':
        return Icons.book_outlined;
      case '건강':
        return Icons.favorite_border;
      case '약속':
        return Icons.event_available_outlined;
      default:
        return Icons.event_outlined;
    }
  }

  static String timeText(String? startTime, String? endTime) {
    if (startTime == null || startTime.isEmpty) return '시간 미정';
    if (endTime != null && endTime.isNotEmpty) return '$startTime - $endTime';
    return startTime;
  }
}
