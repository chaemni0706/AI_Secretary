import 'schedule_model.dart';
import 'todo_model.dart';

/// 대시보드 집계 블록 (`data.stats`).
class DashboardStats {
  final int scheduleCount;
  final int todoCount;
  final int completedTodoCount;
  final double todoCompletionRate; // 0.0 ~ 1.0

  const DashboardStats({
    this.scheduleCount = 0,
    this.todoCount = 0,
    this.completedTodoCount = 0,
    this.todoCompletionRate = 0.0,
  });

  factory DashboardStats.fromJson(Map<String, dynamic>? json) {
    if (json == null) return const DashboardStats();
    return DashboardStats(
      scheduleCount: (json['schedule_count'] ?? 0) as int,
      todoCount: (json['todo_count'] ?? 0) as int,
      completedTodoCount: (json['completed_todo_count'] ?? 0) as int,
      todoCompletionRate: ((json['todo_completion_rate'] ?? 0) as num)
          .toDouble(),
    );
  }
}

/// `GET /api/v1/dashboard/today` 의 `data`.
class DashboardData {
  final String date;
  final List<ScheduleModel> schedules;
  final List<TodoModel> todos;
  final DashboardStats stats;
  final ScheduleModel? nextSchedule;
  final String summaryMessage;

  const DashboardData({
    required this.date,
    this.schedules = const [],
    this.todos = const [],
    this.stats = const DashboardStats(),
    this.nextSchedule,
    this.summaryMessage = '',
  });

  factory DashboardData.fromJson(Map<String, dynamic> json) {
    final schedulesRaw = (json['schedules'] as List?) ?? const [];
    final todosRaw = (json['todos'] as List?) ?? const [];
    final next = json['next_schedule'];

    // stats 가 없는 구버전 응답이면 평탄 필드로 대체.
    final statsJson = json['stats'] as Map<String, dynamic>?;
    final stats = statsJson != null
        ? DashboardStats.fromJson(statsJson)
        : DashboardStats(
            scheduleCount: (json['total_schedule_count'] ?? 0) as int,
            todoCount: (json['total_todo_count'] ?? 0) as int,
            completedTodoCount: (json['completed_todo_count'] ?? 0) as int,
            todoCompletionRate: ((json['todo_completion_rate'] ?? 0) as num)
                .toDouble(),
          );

    return DashboardData(
      date: (json['date'] ?? '').toString(),
      schedules: schedulesRaw
          .map((e) => ScheduleModel.fromJson(e as Map<String, dynamic>))
          .toList(),
      todos: todosRaw
          .map((e) => TodoModel.fromJson(e as Map<String, dynamic>))
          .toList(),
      stats: stats,
      nextSchedule: next is Map<String, dynamic>
          ? ScheduleModel.fromJson(next)
          : null,
      summaryMessage: (json['summary_message'] ?? '').toString(),
    );
  }
}
