/// 할 일(TODO) 모델.
///
/// 백엔드 실제 계약 기준:
/// - `id` 는 **문자열(string)**.
/// - 마감일 필드명은 **`due_date`** ( `date`/`due_time` 아님 ).
/// - 완료 여부 필드명은 **`completed`** (bool) ( `is_completed` 아님 ).
/// - `priority` 는 소문자 `low | medium | high`.
class TodoModel {
  final String id;
  final String title;
  final String? dueDate;
  final String priority; // low | medium | high
  final bool completed;
  final String? category;
  final String? memo;
  final String status;
  final String source;

  const TodoModel({
    required this.id,
    required this.title,
    this.dueDate,
    this.priority = 'medium',
    this.completed = false,
    this.category,
    this.memo,
    this.status = 'todo',
    this.source = 'user',
  });

  factory TodoModel.fromJson(Map<String, dynamic> json) {
    return TodoModel(
      id: json['id']?.toString() ?? '',
      title: (json['title'] ?? '').toString(),
      dueDate: json['due_date'] as String?,
      priority: (json['priority'] ?? 'medium').toString(),
      completed: json['completed'] == true,
      category: json['category'] as String?,
      memo: json['memo'] as String?,
      status: (json['status'] ?? 'todo').toString(),
      source: (json['source'] ?? 'user').toString(),
    );
  }
}
