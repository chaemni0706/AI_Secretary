import 'package:flutter/material.dart';
import '../core/utils/schedule_date_parser.dart';
import '../models/todo_model.dart';
import '../services/api_client.dart';
import '../services/dashboard_api.dart';
import '../services/todo_api.dart';
import '../theme/app_constants.dart';
import '../theme/app_theme.dart';
import '../theme/todo_styles.dart';
import '../widgets/todo_form_components.dart';

class TodoFormScreen extends StatefulWidget {
  final TodoModel? initialTodo;

  const TodoFormScreen({super.key, this.initialTodo});

  @override
  State<TodoFormScreen> createState() => _TodoFormScreenState();
}

class _TodoFormScreenState extends State<TodoFormScreen> {
  final _titleController = TextEditingController();
  final _dateController = TextEditingController();
  final _memoController = TextEditingController();

  String _category = TodoStyles.categoryOrder.first;
  String _priority = 'medium';
  bool _completed = false;
  bool _saving = false;
  bool _deleting = false;

  bool get _isEditMode => widget.initialTodo != null;

  @override
  void initState() {
    super.initState();
    final todo = widget.initialTodo;
    if (todo == null) return;
    _titleController.text = todo.title;
    _dateController.text = todo.dueDate ?? '';
    _memoController.text = todo.memo ?? '';
    _category = TodoStyles.categoryLabel(todo.category);
    _priority = todo.priority;
    _completed = todo.completed;
  }

  @override
  void dispose() {
    _titleController.dispose();
    _dateController.dispose();
    _memoController.dispose();
    super.dispose();
  }

  void _snack(String message) {
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }

  bool _normalizeDate({bool showError = false}) {
    final raw = _dateController.text.trim();
    if (raw.isEmpty) return true;
    final normalized = ScheduleDateParser.normalize(raw);
    if (normalized == null) {
      if (showError) _snack('날짜 형식을 확인해 주세요.');
      return false;
    }
    _dateController.text = normalized;
    return true;
  }

  Map<String, dynamic> _payload() {
    String? optional(String value) {
      final trimmed = value.trim();
      return trimmed.isEmpty ? null : trimmed;
    }

    return {
      'title': _titleController.text.trim(),
      'due_date': optional(_dateController.text),
      'priority': _priority,
      'completed': _completed,
      'category': _category,
      'memo': optional(_memoController.text),
      'source': widget.initialTodo?.source ?? 'user',
    };
  }

  Future<void> _submit() async {
    if (_titleController.text.trim().isEmpty) {
      _snack('제목을 입력해 주세요.');
      return;
    }
    if (!_normalizeDate(showError: true)) return;

    setState(() => _saving = true);
    try {
      final TodoModel saved;
      if (_isEditMode) {
        saved = await todoApi.update(widget.initialTodo!.id, _payload());
      } else {
        saved = await todoApi.create(_payload());
      }
      triggerDashboardRefresh();
      if (!mounted) return;
      Navigator.pop<TodoModel>(context, saved);
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _saving = false);
      _snack('저장 실패: ${e.message}');
    } catch (e) {
      if (!mounted) return;
      setState(() => _saving = false);
      _snack('저장 중 오류: $e');
    }
  }

  Future<void> _confirmDelete() async {
    final todo = widget.initialTodo;
    if (todo == null) return;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('할 일을 삭제할까요?'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(todo.title),
            const SizedBox(height: 8),
            Text('날짜: ${todo.dueDate ?? '마감일 미정'}'),
            Text('시간: ${_timeText(todo.memo)}'),
            Text('카테고리: ${TodoStyles.categoryLabel(todo.category)}'),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text('취소'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            style: FilledButton.styleFrom(
              backgroundColor: AppTheme.red,
              foregroundColor: Colors.white,
            ),
            child: const Text('삭제'),
          ),
        ],
      ),
    );
    if (confirmed == true) await _deleteTodo();
  }

  Future<void> _deleteTodo() async {
    final todo = widget.initialTodo;
    if (todo == null) return;

    setState(() => _deleting = true);
    try {
      await todoApi.delete(todo.id);
      triggerDashboardRefresh();
      if (!mounted) return;
      Navigator.pop<bool>(context, true);
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _deleting = false);
      _snack('삭제 실패: ${e.message}');
    } catch (e) {
      if (!mounted) return;
      setState(() => _deleting = false);
      _snack('삭제 중 오류: $e');
    }
  }

  String _timeText(String? memo) {
    final match = RegExp(r'시간:\s*([^\n]+)').firstMatch(memo ?? '');
    return match?.group(1)?.trim().isNotEmpty == true
        ? match!.group(1)!.trim()
        : '시간 필드 없음';
  }

  @override
  Widget build(BuildContext context) {
    final title = _isEditMode ? '할 일 수정' : '할 일 추가';

    return Container(
      decoration: AppTheme.screenBackground,
      child: Scaffold(
        backgroundColor: Colors.transparent,
        appBar: AppBar(
          title: Text(title),
          centerTitle: false,
          actions: [
            TextButton(
              onPressed: _saving || _deleting
                  ? null
                  : () => Navigator.pop(context),
              child: const Text('취소'),
            ),
          ],
        ),
        body: SafeArea(
          top: false,
          child: ListView(
            physics: const BouncingScrollPhysics(),
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 28),
            children: [
              Text(
                _isEditMode ? '기존 할 일을 수정합니다.' : '새 할 일을 입력합니다.',
                style: AppTextStyles.meta.copyWith(
                  color: AppTheme.textSecondary,
                ),
              ),
              const SizedBox(height: 12),
              TodoFormSection(
                children: [
                  TodoTextInputRow(
                    controller: _titleController,
                    label: '제목',
                    icon: Icons.title,
                    hint: '예: 자료 정리하기',
                  ),
                  TodoDateInputRow(
                    controller: _dateController,
                    onNormalize: _normalizeDate,
                  ),
                  TodoCategorySelector(
                    value: _category,
                    onChanged: (value) => setState(() => _category = value),
                  ),
                  TodoPrioritySelector(
                    value: _priority,
                    onChanged: (value) => setState(() => _priority = value),
                    showDivider: false,
                  ),
                ],
              ),
              TodoFormSection(
                children: [
                  TodoTextInputRow(
                    controller: _memoController,
                    label: '메모',
                    icon: Icons.notes_outlined,
                    hint: '메모 입력',
                    maxLines: 3,
                  ),
                  TodoCompletedRow(
                    value: _completed,
                    onChanged: (value) => setState(() => _completed = value),
                  ),
                  const TodoDisabledInfoRow(
                    icon: Icons.schedule_outlined,
                    label: '시간',
                    value: '추후 지원',
                  ),
                  const TodoDisabledInfoRow(
                    icon: Icons.notifications_outlined,
                    label: '알림',
                    value: '추후 지원',
                    showDivider: false,
                  ),
                ],
              ),
              SizedBox(
                width: double.infinity,
                child: FilledButton(
                  onPressed: _saving || _deleting ? null : _submit,
                  style: FilledButton.styleFrom(
                    backgroundColor: AppTheme.blue,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 15),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(AppRadii.control),
                    ),
                  ),
                  child: _saving
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white,
                          ),
                        )
                      : Text(_isEditMode ? '수정 저장' : '저장'),
                ),
              ),
              if (_isEditMode) ...[
                const SizedBox(height: 14),
                TodoDeleteActionSection(
                  deleting: _deleting,
                  onDelete: _confirmDelete,
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
