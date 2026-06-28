import '../models/todo_model.dart';

/// TodoScreen 더미 데이터.
/// 추후 FastAPI 연동 시 remote repository 구현체로 교체할 예정.
class MockTodoData {
  MockTodoData._();

  static const String userName = '도경';

  /// 시안 기준 요약 수치
  /// 완료 8 / 남은 할 일 4 / 진행률 68% 유지
  static const int baseProgressPercent = 68;
  static const int baseCompleted = 8;
  static const int baseRemaining = 4;

  /// 오늘의 할 일 리스트
  static List<TodoItem> todos() => const [
        TodoItem(
          id: 'todo_1',
          title: 'AI 발표 자료 정리',
          priority: TodoPriority.high,
          reminder: '오늘 18:00 · 30분 전 알림',
        ),
        TodoItem(
          id: 'todo_2',
          title: '캘린더 일정 확인',
          priority: TodoPriority.normal,
          reminder: '내일 09:00 · 아침 알림',
        ),
        TodoItem(
          id: 'todo_3',
          title: '운동복 챙기기',
          priority: TodoPriority.low,
          reminder: '금요일 · 준비물 알림',
        ),
      ];

  /// 요약 데이터
  /// 현재는 시안 수치를 그대로 보존한다.
  static TodoSummary summary() => const TodoSummary(
        progressPercent: baseProgressPercent,
        completedCount: baseCompleted,
        remainingCount: baseRemaining,
      );
}