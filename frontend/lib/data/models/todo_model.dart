import 'package:flutter/material.dart';

import '../../core/theme/app_colors.dart';

/// 할 일 우선순위
enum TodoPriority { high, normal, low }

extension TodoPriorityStyle on TodoPriority {
  String get label => switch (this) {
        TodoPriority.high => '높음',
        TodoPriority.normal => '보통',
        TodoPriority.low => '낮음',
      };

  Color get color => switch (this) {
        TodoPriority.high => AppColors.priorityHigh,
        TodoPriority.normal => AppColors.priorityNormal,
        TodoPriority.low => AppColors.priorityLow,
      };

  /// API 직렬화용 문자열 키
  String get apiValue => switch (this) {
        TodoPriority.high => 'high',
        TodoPriority.normal => 'normal',
        TodoPriority.low => 'low',
      };

  static TodoPriority fromApi(String value) => switch (value) {
        'high' => TodoPriority.high,
        'low' => TodoPriority.low,
        _ => TodoPriority.normal,
      };
}

/// 할 일 항목
class TodoItem {
  const TodoItem({
    required this.id,
    required this.title,
    required this.priority,
    required this.reminder,
    this.isDone = false,
  });

  final String id;
  final String title;
  final TodoPriority priority;
  final String reminder;
  final bool isDone;

  TodoItem copyWith({
    String? id,
    String? title,
    TodoPriority? priority,
    String? reminder,
    bool? isDone,
  }) {
    return TodoItem(
      id: id ?? this.id,
      title: title ?? this.title,
      priority: priority ?? this.priority,
      reminder: reminder ?? this.reminder,
      isDone: isDone ?? this.isDone,
    );
  }

  factory TodoItem.fromJson(Map<String, dynamic> json) {
    return TodoItem(
      id: json['id'] as String,
      title: json['title'] as String,
      priority: TodoPriorityStyle.fromApi(
        json['priority'] as String? ?? 'normal',
      ),
      reminder: json['reminder'] as String? ?? '',
      isDone: json['is_done'] as bool? ?? false,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'title': title,
      'priority': priority.apiValue,
      'reminder': reminder,
      'is_done': isDone,
    };
  }
}

/// 할 일 요약
class TodoSummary {
  const TodoSummary({
    required this.progressPercent,
    required this.completedCount,
    required this.remainingCount,
  });

  final int progressPercent;
  final int completedCount;
  final int remainingCount;

  factory TodoSummary.from({
    required int baseCompleted,
    required int totalCount,
  }) {
    final remaining = (totalCount - baseCompleted).clamp(0, totalCount);
    final percent =
        totalCount == 0 ? 0 : ((baseCompleted / totalCount) * 100).round();

    return TodoSummary(
      progressPercent: percent,
      completedCount: baseCompleted,
      remainingCount: remaining,
    );
  }
}