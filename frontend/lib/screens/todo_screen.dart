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
import '../widgets/todo_progress_card.dart';
import '../widgets/todo_ring_chart.dart';
import 'todo_add_screen.dart';

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
  final Set<String> _expandedDoneCategories = {};

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _loadTodos();
    dashboardRefresh.addListener(_loadTodos);
  }

  @override
  void dispose() {
    dashboardRefresh.removeListener(_loadTodos);
    _tabController.dispose();
    super.dispose();
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

  double _completionRate(List<TodoModel> todos) {
    if (todos.isEmpty) return 0;
    return todos.where((todo) => todo.completed).length / todos.length;
  }

  List<TodoRingCardData> _ringCardsByDate() {
    final byDate = <String, List<TodoModel>>{};
    for (final todo in _all) {
      final key = todo.dueDate?.trim().isNotEmpty == true
          ? todo.dueDate!
          : '날짜 미정';
      byDate.putIfAbsent(key, () => []).add(todo);
    }

    final keys = byDate.keys.toList()
      ..sort((a, b) {
        if (a == _today) return -1;
        if (b == _today) return 1;
        if (a == '날짜 미정') return 1;
        if (b == '날짜 미정') return -1;
        return a.compareTo(b);
      });

    return keys.take(8).map((date) {
      final todos = byDate[date]!;
      final grouped = _groupByCategory(todos);
      final rings = TodoStyles.categoryOrder
          .where((category) => (grouped[category] ?? const []).isNotEmpty)
          .map(
            (category) => TodoRingData(
              label: category,
              color: TodoStyles.categoryColor(category),
              progress: _completionRate(grouped[category] ?? const []),
            ),
          )
          .toList();
      final done = todos.where((todo) => todo.completed).length;
      return TodoRingCardData(
        title: date == _today ? '오늘' : date,
        subtitle: '완료 $done / 전체 ${todos.length}',
        overallProgress: _completionRate(todos),
        rings: rings,
      );
    }).toList();
  }

  Future<void> _openAddTodo() async {
    final saved = await Navigator.push<TodoModel>(
      context,
      MaterialPageRoute(builder: (_) => const TodoAddScreen()),
    );
    if (saved == null || !mounted) return;
    setState(() {
      _all = [saved, ..._all.where((todo) => todo.id != saved.id)];
    });
    triggerDashboardRefresh();
    await _loadTodos();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: AppTheme.screenBackground,
      child: SafeArea(
        child: Stack(
          children: [
            Column(
              children: [
                _buildHeader(),
                _buildTabBar(),
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
            Positioned(
              left: 20,
              bottom: 18,
              child: FloatingActionButton(
                heroTag: 'todo-add-fab',
                shape: const CircleBorder(),
                backgroundColor: AppTheme.blue,
                foregroundColor: Colors.white,
                onPressed: _openAddTodo,
                child: const Icon(Icons.add),
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

  Widget _buildTabBar() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
      child: Container(
        decoration: BoxDecoration(
          color: Colors.white.withValues(alpha: 0.55),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: AppTheme.separator.withValues(alpha: 0.6)),
        ),
        child: TabBar(
          controller: _tabController,
          indicator: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(12),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.07),
                blurRadius: 6,
                offset: const Offset(0, 2),
              ),
            ],
          ),
          indicatorPadding: const EdgeInsets.all(3),
          dividerColor: Colors.transparent,
          labelColor: AppTheme.textPrimary,
          unselectedLabelColor: AppTheme.textSecondary,
          labelStyle: const TextStyle(
            fontSize: 13,
            fontWeight: FontWeight.w600,
          ),
          unselectedLabelStyle: const TextStyle(fontSize: 13),
          tabs: [
            Tab(text: '오늘 ${_todayTodos.length}'),
            Tab(text: '예정 ${_upcomingTodos.length}'),
            Tab(text: '완료 ${_doneTodos.length}'),
          ],
        ),
      ),
    );
  }

  Widget _buildTodayTab() {
    final todayAll = _todayAll;
    final done = todayAll.where((todo) => todo.completed).length;
    final grouped = _groupByCategory(_todayTodos);

    return RefreshIndicator(
      onRefresh: _loadTodos,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(0, 0, 0, 92),
        physics: const AlwaysScrollableScrollPhysics(
          parent: BouncingScrollPhysics(),
        ),
        children: [
          TodoProgressCard(done: done, total: todayAll.length),
          if (_todayTodos.isEmpty)
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
          else
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 4, 16, 0),
              child: Column(
                children: TodoStyles.categoryOrder
                    .map(
                      (category) => TodoCategorySection(
                        title: category,
                        todos: grouped[category] ?? const [],
                        onToggle: _toggle,
                      ),
                    )
                    .toList(),
              ),
            ),
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
              itemBuilder: (context, i) =>
                  TodoCard(todo: todos[i], onToggle: () => _toggle(todos[i])),
            ),
    );
  }

  Widget _buildDoneTab() {
    final groupedDone = _groupByCategory(_doneTodos);

    return RefreshIndicator(
      onRefresh: _loadTodos,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(0, 0, 0, 92),
        physics: const AlwaysScrollableScrollPhysics(
          parent: BouncingScrollPhysics(),
        ),
        children: [
          TodoRingChart(cards: _ringCardsByDate()),
          if (_doneTodos.isEmpty)
            const Padding(
              padding: EdgeInsets.fromLTRB(16, 16, 16, 0),
              child: GlassCard(
                padding: EdgeInsets.symmetric(horizontal: 16, vertical: 18),
                child: Text(
                  '완료한 할 일이 없습니다.',
                  style: TextStyle(fontSize: 13, color: AppTheme.textSecondary),
                ),
              ),
            )
          else
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 4, 16, 0),
              child: Column(
                children: TodoStyles.categoryOrder
                    .map(
                      (category) => TodoCategorySection(
                        title: category,
                        todos: groupedDone[category] ?? const [],
                        onToggle: _toggle,
                        compactCards: true,
                        visibleLimit: 3,
                        expanded: _expandedDoneCategories.contains(category),
                        onToggleExpanded: () {
                          setState(() {
                            if (_expandedDoneCategories.contains(category)) {
                              _expandedDoneCategories.remove(category);
                            } else {
                              _expandedDoneCategories.add(category);
                            }
                          });
                        },
                      ),
                    )
                    .toList(),
              ),
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
              FilledButton(
                onPressed: _loadTodos,
                style: FilledButton.styleFrom(backgroundColor: AppTheme.blue),
                child: const Text('다시 시도'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
