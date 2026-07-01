import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../widgets/glass_card.dart';
import '../models/todo_model.dart';
import '../services/todo_api.dart';
import '../services/dashboard_api.dart';
import '../services/api_client.dart';

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

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _loadTodos();
    // 저장/변경 후 다른 화면에서 triggerDashboardRefresh() 호출 시 함께 갱신.
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
      // 완료율/집계도 갱신되도록 대시보드 트리거.
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
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(msg)));
  }

  // ---- 분류/유틸 ------------------------------------------------------------

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
    final list =
        _all.where((x) => !x.completed && x.dueDate == t).toList();
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

  String _prioKo(String p) {
    switch (p) {
      case 'high':
        return '높음';
      case 'low':
        return '낮음';
      default:
        return '보통';
    }
  }

  Color _prioColor(String p) {
    switch (p) {
      case 'high':
        return AppTheme.red;
      case 'low':
        return AppTheme.textSecondary;
      default:
        return AppTheme.orange;
    }
  }

  // ---- build ---------------------------------------------------------------

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: AppTheme.screenBackground,
      child: SafeArea(
        child: Column(
          children: [
            _buildHeader(),
            _buildTabBar(),
            _buildProgressCard(),
            Expanded(
              child: _loading && _all.isEmpty
                  ? const Center(child: CircularProgressIndicator())
                  : _error != null
                      ? _buildError()
                      : TabBarView(
                          controller: _tabController,
                          children: [
                            _buildTodoList(_todayTodos,
                                emptyText: '오늘 마감인 할 일이 없습니다.'),
                            _buildTodoList(_upcomingTodos,
                                emptyText: '예정된 할 일이 없습니다.'),
                            _buildTodoList(_doneTodos,
                                isDoneTab: true,
                                emptyText: '완료한 할 일이 없습니다.'),
                          ],
                        ),
            ),
          ],
        ),
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
              const Icon(Icons.cloud_off,
                  color: AppTheme.textSecondary, size: 34),
              const SizedBox(height: 10),
              Text(
                _error ?? '할 일을 불러오지 못했습니다.',
                textAlign: TextAlign.center,
                style: const TextStyle(
                    fontSize: 14, color: AppTheme.textPrimary),
              ),
              const SizedBox(height: 4),
              const Text(
                '백엔드 서버가 실행 중인지 확인하세요.',
                textAlign: TextAlign.center,
                style:
                    TextStyle(fontSize: 12, color: AppTheme.textSecondary),
              ),
              const SizedBox(height: 12),
              FilledButton(
                onPressed: _loadTodos,
                style:
                    FilledButton.styleFrom(backgroundColor: AppTheme.blue),
                child: const Text('다시 시도'),
              ),
            ],
          ),
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
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                '할 일',
                style: TextStyle(
                  fontSize: 26,
                  fontWeight: FontWeight.w700,
                  color: AppTheme.textPrimary,
                  letterSpacing: -0.5,
                ),
              ),
              Text(
                '${n.month}월 ${n.day}일 ${week[n.weekday]}요일',
                style: const TextStyle(
                    fontSize: 13, color: AppTheme.textSecondary),
              ),
            ],
          ),
          GestureDetector(
            onTap: _loading ? null : _loadTodos,
            child: Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: Colors.white.withOpacity(0.7),
                shape: BoxShape.circle,
                border: Border.all(color: AppTheme.separator),
              ),
              child: const Icon(Icons.refresh,
                  color: AppTheme.textPrimary, size: 20),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTabBar() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
      child: Container(
        decoration: BoxDecoration(
          color: Colors.white.withOpacity(0.55),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: AppTheme.separator.withOpacity(0.6)),
        ),
        child: TabBar(
          controller: _tabController,
          indicator: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(12),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withOpacity(0.07),
                blurRadius: 6,
                offset: const Offset(0, 2),
              ),
            ],
          ),
          indicatorPadding: const EdgeInsets.all(3),
          dividerColor: Colors.transparent,
          labelColor: AppTheme.textPrimary,
          unselectedLabelColor: AppTheme.textSecondary,
          labelStyle:
              const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
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

  Widget _buildProgressCard() {
    final today = _today;
    final todayAll =
        _all.where((x) => x.dueDate == today).toList();
    final done = todayAll.where((x) => x.completed).length;
    final total = todayAll.length;
    final rate = total == 0 ? 0.0 : done / total;
    final percent = (rate * 100).round();
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 10, 16, 0),
      child: GlassCard(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text(
                  '오늘 진행률',
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.textPrimary,
                  ),
                ),
                Text(
                  '$percent%',
                  style: const TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                    color: AppTheme.blue,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: rate,
                backgroundColor: AppTheme.separator,
                valueColor: const AlwaysStoppedAnimation(AppTheme.blue),
                minHeight: 6,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              '완료 $done개 · 남은 할 일 ${total - done}개',
              style: const TextStyle(
                  fontSize: 12, color: AppTheme.textSecondary),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTodoList(
    List<TodoModel> todos, {
    bool isDoneTab = false,
    required String emptyText,
  }) {
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
                        horizontal: 16, vertical: 18),
                    child: Text(
                      emptyText,
                      style: const TextStyle(
                          fontSize: 13, color: AppTheme.textSecondary),
                    ),
                  ),
                ),
              ],
            )
          : ListView.builder(
              padding: const EdgeInsets.fromLTRB(16, 10, 16, 80),
              physics: const AlwaysScrollableScrollPhysics(
                parent: BouncingScrollPhysics(),
              ),
              itemCount: todos.length,
              itemBuilder: (context, i) => _todoCard(todos[i], isDoneTab),
            ),
    );
  }

  Widget _todoCard(TodoModel todo, bool isDoneTab) {
    final done = todo.completed;
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: GlassCard(
        padding: const EdgeInsets.all(14),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // 체크 아이콘 = 완료 토글 (실제 PATCH 호출)
            GestureDetector(
              onTap: () => _toggle(todo),
              behavior: HitTestBehavior.opaque,
              child: Icon(
                done ? Icons.check_circle : Icons.radio_button_unchecked,
                color: done ? AppTheme.green : AppTheme.textSecondary,
                size: 22,
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    todo.title,
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      color: done
                          ? AppTheme.textSecondary
                          : AppTheme.textPrimary,
                      decoration:
                          done ? TextDecoration.lineThrough : null,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Row(
                    children: [
                      Icon(Icons.event_outlined,
                          size: 12, color: AppTheme.textSecondary),
                      const SizedBox(width: 4),
                      Text(
                        todo.dueDate ?? '마감일 미정',
                        style: const TextStyle(
                          fontSize: 12,
                          color: AppTheme.textSecondary,
                        ),
                      ),
                      if (todo.category != null) ...[
                        const Text(' · ',
                            style: TextStyle(
                                fontSize: 12,
                                color: AppTheme.textSecondary)),
                        Text(
                          todo.category!,
                          style: const TextStyle(
                            fontSize: 12,
                            color: AppTheme.textSecondary,
                          ),
                        ),
                      ],
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(width: 8),
            PillBadge(
              label: _prioKo(todo.priority),
              color: _prioColor(todo.priority),
            ),
          ],
        ),
      ),
    );
  }
}
