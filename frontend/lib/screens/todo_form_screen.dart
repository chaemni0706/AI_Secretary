import 'package:flutter/material.dart';
import '../core/utils/schedule_date_parser.dart';
import '../models/todo_model.dart';
import '../services/api_client.dart';
import '../services/dashboard_api.dart';
import '../services/todo_api.dart';
import '../theme/app_constants.dart';
import '../theme/app_theme.dart';
import '../theme/todo_styles.dart';
import '../widgets/schedule_form_components.dart' show DateTimePickerRow;
import '../widgets/todo_form_components.dart';

class TodoFormScreen extends StatefulWidget {
  final TodoModel? initialTodo;

  const TodoFormScreen({super.key, this.initialTodo});

  @override
  State<TodoFormScreen> createState() => _TodoFormScreenState();
}

class _TodoFormScreenState extends State<TodoFormScreen> {
  static final RegExp _timeLinePattern = RegExp(
    r'^\s*시간:\s*([^\n]+)\s*$',
    multiLine: true,
  );

  final _titleController = TextEditingController();
  final _startDateController = TextEditingController();
  final _startTimeController = TextEditingController();
  final _dueDateController = TextEditingController();
  final _dueTimeController = TextEditingController();
  final _memoController = TextEditingController();

  String _category = TodoStyles.categoryOrder.first;
  String _priority = 'medium';
  bool _completed = false;
  bool _saving = false;
  bool _deleting = false;
  bool _startDatePickerOpen = false;
  bool _startTimePickerOpen = false;
  bool _dueDatePickerOpen = false;
  bool _dueTimePickerOpen = false;
  DateTime _focusedDate = DateTime.now();

  bool get _isEditMode => widget.initialTodo != null;

  @override
  void initState() {
    super.initState();
    final todo = widget.initialTodo;
    if (todo != null) {
      _titleController.text = todo.title;
      _dueDateController.text = todo.dueDate ?? '';
      _startDateController.text = todo.startDate ?? '';
      _startTimeController.text = todo.startTime ?? '';
      _category = TodoStyles.categoryLabel(todo.category);
      _priority = todo.priority;
      _completed = todo.completed;

      final memo = todo.memo ?? '';
      if ((todo.dueTime ?? '').isNotEmpty) {
        _dueTimeController.text = todo.dueTime!;
        _memoController.text = memo;
      } else {
        // 하위 호환: 옛 데이터는 마감 시간이 memo 안에 "시간: HH:mm" 로 남아있을 수
        // 있다(이제 due_time 이 진짜 필드이므로 다음 저장부터는 여기로 안 온다).
        final timeMatch = _timeLinePattern.firstMatch(memo);
        if (timeMatch != null) {
          _dueTimeController.text = timeMatch.group(1)!.trim();
          _memoController.text = memo.replaceAll(_timeLinePattern, '').trim();
        } else {
          _memoController.text = memo;
        }
      }
    }
    _focusedDate =
        ScheduleDateParser.parse(_dueDateController.text) ?? DateTime.now();
  }

  @override
  void dispose() {
    _titleController.dispose();
    _startDateController.dispose();
    _startTimeController.dispose();
    _dueDateController.dispose();
    _dueTimeController.dispose();
    _memoController.dispose();
    super.dispose();
  }

  void _closePickersExcept(String target) {
    setState(() {
      final openingStartDate = target == 'startDate' ? !_startDatePickerOpen : false;
      final openingDueDate = target == 'dueDate' ? !_dueDatePickerOpen : false;
      _startDatePickerOpen = openingStartDate;
      _dueDatePickerOpen = openingDueDate;
      _startTimePickerOpen = target == 'startTime' ? !_startTimePickerOpen : false;
      _dueTimePickerOpen = target == 'dueTime' ? !_dueTimePickerOpen : false;
      if (openingStartDate) {
        _focusedDate =
            ScheduleDateParser.parse(_startDateController.text) ?? _focusedDate;
      } else if (openingDueDate) {
        _focusedDate =
            ScheduleDateParser.parse(_dueDateController.text) ?? _focusedDate;
      }
    });
  }

  void _selectStartDate(DateTime date) {
    setState(() {
      _startDateController.text = ScheduleDateParser.format(date);
      _focusedDate = date;
      _startDatePickerOpen = false;
    });
  }

  void _selectDueDate(DateTime date) {
    setState(() {
      _dueDateController.text = ScheduleDateParser.format(date);
      _focusedDate = date;
      _dueDatePickerOpen = false;
    });
  }

  void _selectStartTime(String time) {
    setState(() => _startTimeController.text = time);
  }

  void _selectDueTime(String time) {
    setState(() => _dueTimeController.text = time);
  }

  void _snack(String message) {
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }

  bool _normalizeStartDate({bool showError = false}) {
    final raw = _startDateController.text.trim();
    if (raw.isEmpty) return true;
    final normalized = ScheduleDateParser.normalize(raw);
    if (normalized == null) {
      if (showError) _snack('시작 날짜 형식을 확인해 주세요.');
      return false;
    }
    _startDateController.text = normalized;
    _focusedDate = ScheduleDateParser.parse(normalized) ?? _focusedDate;
    return true;
  }

  bool _normalizeDueDate({bool showError = false}) {
    final raw = _dueDateController.text.trim();
    if (raw.isEmpty) return true;
    final normalized = ScheduleDateParser.normalize(raw);
    if (normalized == null) {
      if (showError) _snack('종료 날짜 형식을 확인해 주세요.');
      return false;
    }
    _dueDateController.text = normalized;
    _focusedDate = ScheduleDateParser.parse(normalized) ?? _focusedDate;
    return true;
  }

  Map<String, dynamic> _payload() {
    String? optional(String value) {
      final trimmed = value.trim();
      return trimmed.isEmpty ? null : trimmed;
    }

    return {
      'title': _titleController.text.trim(),
      'due_date': optional(_dueDateController.text),
      'due_time': optional(_dueTimeController.text),
      'start_date': optional(_startDateController.text),
      'start_time': optional(_startTimeController.text),
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
    if (!_normalizeStartDate(showError: true)) return;
    if (!_normalizeDueDate(showError: true)) return;
    if (_startDateController.text.trim().isNotEmpty &&
        _dueDateController.text.trim().isNotEmpty &&
        _dueDateController.text.trim().compareTo(
              _startDateController.text.trim(),
            ) <
            0) {
      _snack('종료 날짜는 시작 날짜보다 빠를 수 없습니다.');
      return;
    }

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
            Text(
              '시간: ${(todo.dueTime ?? '').isNotEmpty ? todo.dueTime : '시간 미정'}',
            ),
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
                  DateTimePickerRow(
                    label: '시작날짜',
                    icon: Icons.event_outlined,
                    dateController: _startDateController,
                    timeController: _startTimeController,
                    dateExpanded: _startDatePickerOpen,
                    timeExpanded: _startTimePickerOpen,
                    focusedDay: _focusedDate,
                    onDateExpandedChanged: (_) => _closePickersExcept('startDate'),
                    onTimeExpandedChanged: (_) => _closePickersExcept('startTime'),
                    onFocusedDayChanged: (date) =>
                        setState(() => _focusedDate = date),
                    onDateSelected: _selectStartDate,
                    onTimeSelected: _selectStartTime,
                    onNormalizeDate: () => _normalizeStartDate(),
                  ),
                  DateTimePickerRow(
                    label: '종료날짜',
                    icon: Icons.event_available_outlined,
                    dateController: _dueDateController,
                    timeController: _dueTimeController,
                    dateExpanded: _dueDatePickerOpen,
                    timeExpanded: _dueTimePickerOpen,
                    focusedDay: _focusedDate,
                    onDateExpandedChanged: (_) => _closePickersExcept('dueDate'),
                    onTimeExpandedChanged: (_) => _closePickersExcept('dueTime'),
                    onFocusedDayChanged: (date) =>
                        setState(() => _focusedDate = date),
                    onDateSelected: _selectDueDate,
                    onTimeSelected: _selectDueTime,
                    onNormalizeDate: () => _normalizeDueDate(),
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
