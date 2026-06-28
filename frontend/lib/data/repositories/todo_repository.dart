import '../mock/mock_todo_data.dart';
import '../models/todo_model.dart';

/// 할 일 데이터 진입점.
/// ViewModel은 이 인터페이스에만 의존한다.
/// 추후 FastAPI 연동 시 RemoteTodoRepository를 만들어 교체하면 된다.
abstract class TodoRepository {
  Future<TodoSummary> getSummary();

  Future<List<TodoItem>> getTodos();

  /// 사용자 이름 등 화면 부가 정보
  String getUserName();
}

/// Mock 구현체.
/// 현재 단계에서는 SampleData 역할을 하는 MockTodoData를 반환한다.
class MockTodoRepository implements TodoRepository {
  @override
  Future<TodoSummary> getSummary() async {
    return MockTodoData.summary();
  }

  @override
  Future<List<TodoItem>> getTodos() async {
    return MockTodoData.todos();
  }

  @override
  String getUserName() {
    return MockTodoData.userName;
  }
}