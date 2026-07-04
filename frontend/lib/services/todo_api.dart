import '../models/todo_model.dart';
import 'api_client.dart';

class TodoApi {
  /// draft 로 To-do 저장: `POST /api/v1/local/todos/from-draft`
  ///
  /// draft 의 `date` 는 백엔드에서 To-do 의 `due_date` 로 매핑된다.
  Future<TodoModel> createFromDraft(
    Map<String, dynamic> scheduleDraft, {
    String intent = 'create_todo',
  }) async {
    final data = await apiClient.postData(
      '$apiPrefix/local/todos/from-draft',
      body: {
        'schedule_draft': scheduleDraft,
        'intent': intent,
      },
    );
    return TodoModel.fromJson(data as Map<String, dynamic>);
  }

  /// 직접 생성: `POST /api/v1/local/todos`
  Future<TodoModel> create(Map<String, dynamic> payload) async {
    final data = await apiClient.postData(
      '$apiPrefix/local/todos',
      body: payload,
    );
    return TodoModel.fromJson(data as Map<String, dynamic>);
  }

  /// 목록: `GET /api/v1/local/todos`
  Future<List<TodoModel>> list({String? dueDate, bool? completed}) async {
    final query = <String, dynamic>{};
    if (dueDate != null) query['due_date'] = dueDate;
    if (completed != null) query['completed'] = completed;
    final data = await apiClient.getData(
      '$apiPrefix/local/todos',
      query: query.isEmpty ? null : query,
    );
    final list = (data as List?) ?? const [];
    return list
        .map((e) => TodoModel.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// 완료 여부 변경: `PATCH /api/v1/local/todos/{id}`  (필드명은 `completed`)
  Future<TodoModel> setCompleted(String id, bool completed) async {
    final data = await apiClient.patchData(
      '$apiPrefix/local/todos/$id',
      body: {'completed': completed},
    );
    return TodoModel.fromJson(data as Map<String, dynamic>);
  }
}

final todoApi = TodoApi();
