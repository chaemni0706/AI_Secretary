import 'package:flutter/material.dart';
import '../models/todo_model.dart';
import '../services/api_client.dart';
import '../services/dashboard_api.dart';
import '../services/todo_api.dart';
import '../theme/app_constants.dart';
import '../theme/app_theme.dart';
import '../theme/todo_styles.dart';
import '../widgets/app_top_actions.dart';
import '../widgets/glass_card.dart';
import '../widgets/todo_card.dart';
import '../widgets/todo_category_section.dart';
import '../widgets/todo_completion_calendar.dart';
import '../widgets/todo_progress_card.dart';
import '../widgets/todo_segmented_control.dart';
import '../widgets/toss_button.dart';
import 'todo_form_screen.dart';

class TodoScreen extends StatefulWidget {
  const TodoScreen({super.key});

  @override
  State<TodoScreen> createState() => _TodoScreenState();
}

class _TodoScreenState extends State<TodoScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;

  bool _loading = true;
  String? _error;
  List<TodoModel> _all = [];
  DateTime _completionMonth = DateTime(
    DateTime.now().year,
    DateTime.now().month,
  );
  DateTime? _selectedCompletionDate = DateTime.now();

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _tabController.addListener(_handleTabChange);
    _loadTodos();
    dashboardRefresh.addListener(_loadTodos);
  }

  @override
  void dispose() {
    dashboardRefresh.removeListener(_loadTodos);
    _tabController.removeListener(_handleTabChange);
    _tabController.dispose();
    super.dispose();
  }

  void _handleTabChange() {
    if (mounted) setState(() {});
  }

  Future<void> _loadTodos() async {
    if (mounted) {
      setState(() {
        _loading = true;
        _error = null;
      });
    }
    try {
      final todos = await todoApi.list();
      if (!mounted) return;
      setState(() {
        _all = todos;
        _loading = false;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.message;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = '할 일을 불러오지 못했습니다. ($e)';
        _loading = false;
      });
    }
  }

  Future<void> _toggle(TodoModel todo) async {
    try {
      await todoApi.setCompleted(todo.id, !todo.completed);
      triggerDashboardRefresh();
      await _loadTodos();
    } on ApiException catch (e) {
      _snack('변경 실패: ${e.message}');
    } catch (e) {
      _snack('변경 중 오류: $e');
    }
  }

  void _snack(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
  }

  static String _two(int n) => n.toString().padLeft(2, '0');
  String get _today {
    final n = DateTime.now();
    return '${n.year}-${_two(n.month)}-${_two(n.day)}';
  }

  static const _prioRank = {'high': 0, 'medium': 1, 'low': 2};

  int _cmp(TodoModel a, TodoModel b) {
    final pa = _prioRank[a.priority] ?? 1;
    final pb = _prioRank[b.priority] ?? 1;
    if (pa != pb) return pa.compareTo(pb);
    return (a.dueDate ?? '9999-99-99').compareTo(b.dueDate ?? '9999-99-99');
  }

  List<TodoModel> get _todayTodos {
    final t = _today;
    final list = _all.where((x) => !x.completed && x.dueDate == t).toList();
    list.sort(_cmp);
    return list;
  }

  List<TodoModel> get _todayDoneTodos {
    final t = _today;
    final list = _all.where((x) => x.completed && x.dueDate == t).toList();
    list.sort(_cmp);
    return list;
  }

  List<TodoModel> get _todayAll {
    final list = _all.where((x) => x.dueDate == _today).toList();
    list.sort(_cmp);
    return list;
  }

  List<TodoModel> get _upcomingTodos {
    final t = _today;
    final list = _all
        .where((x) => !x.completed && (x.dueDate == null || x.dueDate! != t))
        .where((x) => x.dueDate == null || x.dueDate!.compareTo(t) > 0)
        .toList();
    list.sort(_cmp);
    return list;
  }

  List<TodoModel> get _doneTodos {
    final list = _all.where((x) => x.completed).toList();
    list.sort(_cmp);
    return list;
  }

  Map<String, List<TodoModel>> _groupByCategory(List<TodoModel> todos) {
    final grouped = {
      for (final category in TodoStyles.categoryOrder) category: <TodoModel>[],
    };
    for (final todo in todos) {
      final category = TodoStyles.categoryLabel(todo.category);
      final key = grouped.containsKey(category) ? category : '기타';
      grouped[key]!.add(todo);
    }
    return grouped;
  }

  Map<String, CompletionDayStats> _completionStatsByDate(DateTime month) {
    final byDate = <String, List<TodoModel>>{};
    for (final todo in _all) {
      final dueDate = todo.dueDate;
      if (dueDate == null || dueDate.length < 10) continue;
      final parsed = DateTime.tryParse(dueDate);
      if (parsed == null ||
          parsed.year != month.year ||
          parsed.month != month.month) {
        continue;
      }
      final key = _dateKey(parsed);
      byDate.putIfAbsent(key, () => []).add(todo);
    }

    return byDate.map((key, todos) {
      final date = DateTime.parse(key);
      final grouped = _groupByCategory(todos);
      final done = todos.where((todo) => todo.completed).length;
      final rings = TodoStyles.categoryOrder
          .where((category) => (grouped[category] ?? const []).isNotEmpty)
          .map((category) {
            final items = grouped[category] ?? const <TodoModel>[];
            return CompletionCategoryRingTrack(
              category: category,
              color: TodoStyles.categoryColor(category),
              total: items.length,
              completed: items.where((todo) => todo.completed).length,
            );
          })
          .toList();
      return MapEntry(
        key,
        CompletionDayStats(
          date: date,
          total: todos.length,
          completed: done,
          rings: rings,
        ),
      );
    });
  }

  List<TodoModel> _todosForDate(DateTime? date) {
    if (date == null) return const [];
    final key = _dateKey(date);
    final list = _all.where((todo) => todo.dueDate == key).toList();
    list.sort(_cmp);
    return list;
  }

  String _dateKey(DateTime date) {
    return '${date.year}-${_two(date.month)}-${_two(date.day)}';
  }

  void _changeCompletionMonth(DateTime month) {
    setState(() {
      _completionMonth = DateTime(month.year, month.month);
      _selectedCompletionDate = DateTime(month.year, month.month, 1);
    });
  }

  void _selectCompletionDate(DateTime date) {
    setState(() {
      _selectedCompletionDate = DateTime(date.year, date.month, date.day);
    });
  }

  Future<void> _openEditTodo(TodoModel todo) async {
    final result = await Navigator.push<Object>(
      context,
      MaterialPageRoute(builder: (_) => TodoFormScreen(initialTodo: todo)),
    );
    if (result == null || !mounted) return;
    triggerDashboardRefresh();
    await _loadTodos();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: AppTheme.screenBackground,
      child: SafeArea(
        child: Column(
          children: [
            _buildHeader(),
            _buildFilterControl(),
            Expanded(
              child: _loading && _all.isEmpty
                  ? const Center(child: CircularProgressIndicator())
                  : _error != null
                  ? _buildError()
                  : TabBarView(
                      controller: _tabController,
                      children: [
                        _buildTodayTab(),
                        _buildTodoList(
                          _upcomingTodos,
                          emptyText: '예정된 할 일이 없습니다.',
                        ),
                        _buildDoneTab(),
                      ],
                    ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader() {
    final n = DateTime.now();
    const week = ['', '월', '화', '수', '목', '금', '토', '일'];
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '할 일',
                  style: AppTextStyles.screenTitle.copyWith(
                    color: AppTheme.textPrimary,
                  ),
                ),
                Text(
                  '${n.month}월 ${n.day}일 ${week[n.weekday]}요일',
                  style: AppTextStyles.meta.copyWith(
                    color: AppTheme.textSecondary,
                  ),
                ),
              ],
            ),
          ),
          const AppTopActions(),
        ],
      ),
    );
  }

  Widget _buildFilterControl() {
    return TodoSegmentedControl(
      selectedIndex: _tabController.index,
      segments: [
        TodoSegment(label: '오늘', count: _todayTodos.length),
        TodoSegment(label: '예정', count: _upcomingTodos.length),
        TodoSegment(label: '완료', count: _doneTodos.length),
      ],
      onChanged: (index) {
        setState(() => _tabController.index = index);
      },
    );
  }

  Widget _buildTodayTab() {
    final todayAll = _todayAll;
    final done = todayAll.where((todo) => todo.completed).length;
    final grouped = _groupByCategory(_todayTodos);
    final groupedDone = _groupByCategory(_todayDoneTodos);

    return RefreshIndicator(
      onRefresh: _loadTodos,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(0, 0, 0, 92),
        physics: const AlwaysScrollableScrollPhysics(
          parent: BouncingScrollPhysics(),
        ),
        children: [
          TodoProgressCard(done: done, total: todayAll.length),
          if (_todayTodos.isEmpty && _todayDoneTodos.isEmpty)
            const Padding(
              padding: EdgeInsets.fromLTRB(16, 16, 16, 0),
              child: GlassCard(
                padding: EdgeInsets.symmetric(horizontal: 16, vertical: 18),
                child: Text(
                  '오늘 마감인 할 일이 없습니다.',
                  style: TextStyle(fontSize: 13, color: AppTheme.textSecondary),
                ),
              ),
            )
          else ...[
            if (_todayTodos.isNotEmpty)
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 16, 20, 0),
                child: _TodoSectionTitle(
                  title: '오늘 할 일',
                  count: _todayTodos.length,
                ),
              ),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 4, 16, 0),
              child: Column(
                children: TodoStyles.categoryOrder
                    .map(
                      (category) => TodoCategorySection(
                        title: category,
                        todos: grouped[category] ?? const [],
                        onToggle: _toggle,
                        onTap: _openEditTodo,
                      ),
                    )
                    .toList(),
              ),
            ),
            if (_todayDoneTodos.isNotEmpty) ...[
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 16, 20, 0),
                child: _TodoSectionTitle(
                  title: '완료한 할 일',
                  count: _todayDoneTodos.length,
                  muted: true,
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 4, 16, 0),
                child: Column(
                  children: TodoStyles.categoryOrder
                      .map(
                        (category) => TodoCategorySection(
                          title: category,
                          todos: groupedDone[category] ?? const [],
                          onToggle: _toggle,
                          onTap: _openEditTodo,
                          compactCards: true,
                        ),
                      )
                      .toList(),
                ),
              ),
            ],
          ],
        ],
      ),
    );
  }

  Widget _buildTodoList(List<TodoModel> todos, {required String emptyText}) {
    return RefreshIndicator(
      onRefresh: _loadTodos,
      child: todos.isEmpty
          ? ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 40, 16, 0),
                  child: GlassCard(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 16,
                      vertical: 18,
                    ),
                    child: Text(
                      emptyText,
                      style: const TextStyle(
                        fontSize: 13,
                        color: AppTheme.textSecondary,
                      ),
                    ),
                  ),
                ),
              ],
            )
          : ListView.builder(
              padding: const EdgeInsets.fromLTRB(16, 10, 16, 92),
              physics: const AlwaysScrollableScrollPhysics(
                parent: BouncingScrollPhysics(),
              ),
              itemCount: todos.length,
              itemBuilder: (context, i) => TodoCard(
                todo: todos[i],
                onTap: () => _openEditTodo(todos[i]),
                onToggle: () => _toggle(todos[i]),
              ),
            ),
    );
  }

  Widget _buildDoneTab() {
    final monthlyStats = _completionStatsByDate(_completionMonth);
    final selectedTodos = _todosForDate(_selectedCompletionDate);

    return RefreshIndicator(
      onRefresh: _loadTodos,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(0, 0, 0, 92),
        physics: const AlwaysScrollableScrollPhysics(
          parent: BouncingScrollPhysics(),
        ),
        children: [
          TodoCompletionMonthlyCalendar(
            focusedMonth: _completionMonth,
            selectedDate: _selectedCompletionDate,
            statsByDate: monthlyStats,
            selectedTodos: selectedTodos,
            onMonthChanged: _changeCompletionMonth,
            onDateSelected: _selectCompletionDate,
            onToggleTodo: _toggle,
            onTodoTap: _openEditTodo,
          ),
        ],
      ),
    );
  }

  Widget _buildError() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: GlassCard(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(
                Icons.cloud_off,
                color: AppTheme.textSecondary,
                size: 34,
              ),
              const SizedBox(height: 10),
              Text(
                _error ?? '할 일을 불러오지 못했습니다.',
                textAlign: TextAlign.center,
                style: const TextStyle(
                  fontSize: 14,
                  color: AppTheme.textPrimary,
                ),
              ),
              const SizedBox(height: 4),
              const Text(
                '백엔드 서버가 실행 중인지 확인하세요.',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
              ),
              const SizedBox(height: 12),
              TossButton(
                label: '다시 시도',
                onPressed: _loadTodos,
                size: TossButtonSize.m,
                style: TossButtonStyle.primaryWeak,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _TodoSectionTitle extends StatelessWidget {
  final String title;
  final int count;
  final bool muted;

  const _TodoSectionTitle({
    required this.title,
    required this.count,
    this.muted = false,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Text(
          title,
          style: AppTextStyles.sectionTitle.copyWith(
            color: muted ? AppTheme.textSecondary : AppTheme.textPrimary,
          ),
        ),
        const SizedBox(width: 6),
        Text(
          '$count',
          style: AppTextStyles.meta.copyWith(
            color: AppTheme.textSecondary,
            fontWeight: FontWeight.w700,
          ),
        ),
      ],
    );
  }
}
