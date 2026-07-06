import 'package:flutter/material.dart';
import '../../data/widget_catalog.dart';
import '../../models/dashboard_widget_model.dart';
import '../../models/todo_model.dart';
import '../../theme/app_theme.dart';
import '../../theme/todo_styles.dart';
import 'dashboard_widget_card.dart';

/// 할 일 위젯 (Medium / Large).
/// 실데이터: todoApi.list() 결과([TodoModel]).
/// Medium: 오늘 할 일 목록(카테고리 색 원형). Large: 카테고리별 구분 + 완료 상태.
class TodoDashboardWidget extends StatelessWidget {
  final List<TodoModel> todos;
  final WidgetSize size;
  final bool loading;

  const TodoDashboardWidget({
    super.key,
    this.todos = const [],
    required this.size,
    this.loading = false,
  });

  static String _today() {
    final n = DateTime.now();
    return '${n.year.toString().padLeft(4, '0')}-${n.month.toString().padLeft(2, '0')}-${n.day.toString().padLeft(2, '0')}';
  }

  List<TodoModel> get _todayTodos {
    final t = _today();
    return todos.where((x) => x.dueDate == t).toList();
  }

  @override
  Widget build(BuildContext context) {
    final spec = WidgetCatalog.of(DashboardWidgetType.todo);
    final today = _todayTodos;
    final done = today.where((x) => x.completed).length;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        WidgetCardHeader(
          icon: spec.icon,
          accent: spec.accent,
          title: '오늘 할 일',
          trailing: Text(
            '$done/${today.length}',
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w700,
              color: spec.accent,
            ),
          ),
        ),
        const SizedBox(height: 8),
        Expanded(
          child: today.isEmpty
              ? _EmptyState(loading: loading)
              : (size == WidgetSize.large
                  ? _buildGrouped(today)
                  : _buildFlat(today, max: 3)),
        ),
      ],
    );
  }

  Widget _buildFlat(List<TodoModel> list, {required int max}) {
    final shown = list.take(max).toList();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final todo in shown) _TodoRow(todo: todo),
        if (list.length > max)
          Padding(
            padding: const EdgeInsets.only(top: 2, left: 2),
            child: Text(
              '+${list.length - max}개 더',
              style: const TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w600,
                color: AppTheme.textSecondary,
              ),
            ),
          ),
      ],
    );
  }

  Widget _buildGrouped(List<TodoModel> list) {
    final grouped = <String, List<TodoModel>>{};
    for (final todo in list) {
      final category = TodoStyles.categoryLabel(todo.category);
      grouped.putIfAbsent(category, () => []).add(todo);
    }
    final categories = TodoStyles.categoryOrder
        .where((c) => (grouped[c] ?? const []).isNotEmpty)
        .toList();

    return SingleChildScrollView(
      physics: const NeverScrollableScrollPhysics(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (final category in categories) ...[
            Padding(
              padding: const EdgeInsets.only(bottom: 4, top: 2),
              child: Row(
                children: [
                  Container(
                    width: 8,
                    height: 8,
                    decoration: BoxDecoration(
                      color: TodoStyles.categoryColor(category),
                      shape: BoxShape.circle,
                    ),
                  ),
                  const SizedBox(width: 6),
                  Text(
                    category,
                    style: const TextStyle(
                      fontSize: 11.5,
                      fontWeight: FontWeight.w700,
                      color: AppTheme.textSecondary,
                    ),
                  ),
                ],
              ),
            ),
            for (final todo in grouped[category]!)
              _TodoRow(todo: todo, indent: true),
            const SizedBox(height: 4),
          ],
        ],
      ),
    );
  }
}

class _TodoRow extends StatelessWidget {
  final TodoModel todo;
  final bool indent;

  const _TodoRow({required this.todo, this.indent = false});

  @override
  Widget build(BuildContext context) {
    final color = TodoStyles.categoryColor(todo.category);
    return Padding(
      padding: EdgeInsets.only(bottom: 6, left: indent ? 14 : 0),
      child: Row(
        children: [
          if (todo.completed)
            Icon(Icons.check_circle, size: 14, color: color)
          else
            Container(
              width: 8,
              height: 8,
              decoration: BoxDecoration(color: color, shape: BoxShape.circle),
            ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              todo.title,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                fontSize: 12.5,
                fontWeight: FontWeight.w600,
                color: todo.completed
                    ? AppTheme.textSecondary
                    : AppTheme.textPrimary,
                decoration:
                    todo.completed ? TextDecoration.lineThrough : null,
                decorationColor: AppTheme.textSecondary,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  final bool loading;
  const _EmptyState({required this.loading});

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.centerLeft,
      child: Text(
        loading ? '불러오는 중…' : '오늘 할 일이 없어요 👍',
        style: const TextStyle(
          fontSize: 12.5,
          fontWeight: FontWeight.w500,
          color: AppTheme.textSecondary,
        ),
      ),
    );
  }
}
