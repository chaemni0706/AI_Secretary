import 'package:flutter/foundation.dart';

import '../../data/models/todo_model.dart';
import '../../data/repositories/todo_repository.dart';

/// TodoScreen 상태 관리 ViewModel.
/// Repository에서 요약/할 일 리스트를 가져오고,
/// 체크박스 토글 상태를 관리한다.
class TodoViewModel extends ChangeNotifier {
  TodoViewModel({
    required TodoRepository repository,
  }) : _repository = repository {
    load();
  }

  final TodoRepository _repository;

  bool _isLoading = true;
  bool get isLoading => _isLoading;

  String _userName = '';
  String get userName => _userName;

  TodoSummary? _summary;
  TodoSummary? get summary => _summary;

  List<TodoItem> _todos = const [];
  List<TodoItem> get todos => _todos;

  Future<void> load() async {
    _isLoading = true;
    notifyListeners();

    try {
      _userName = _repository.getUserName();
      _summary = await _repository.getSummary();
      _todos = await _repository.getTodos();
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  /// 체크박스 토글.
  /// 기존 TodoItem을 직접 수정하지 않고 copyWith로 새 리스트를 만든다.
  void toggleDone(String id) {
    _todos = _todos
        .map(
          (todo) => todo.id == id
              ? todo.copyWith(isDone: !todo.isDone)
              : todo,
        )
        .toList();

    notifyListeners();
  }
}