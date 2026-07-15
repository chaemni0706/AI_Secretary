import 'package:flutter/material.dart';
import 'app_theme.dart';

class TodoStyles {
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
      case 'health':
      case 'exercise':
      case 'hospital':
        return '건강';
      case 'meeting':
      case 'appointment':
      case 'reservation':
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

  static String priorityLabel(String priority) {
    switch (priority) {
      case 'high':
        return '높음';
      case 'low':
        return '낮음';
      default:
        return '보통';
    }
  }

  static Color priorityColor(String priority) {
    switch (priority) {
      case 'high':
        return AppTheme.red;
      case 'low':
        return AppTheme.textSecondary;
      default:
        return AppTheme.orange;
    }
  }
}
