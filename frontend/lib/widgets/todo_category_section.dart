import 'package:flutter/material.dart';
import '../models/todo_model.dart';
import '../theme/app_constants.dart';
import '../theme/app_theme.dart';
import '../theme/illustrations.dart';
import '../theme/todo_styles.dart';
import 'todo_card.dart';

/// 카테고리 헤더에 작게 곁들이는 일러스트(있는 카테고리만).
const Map<String, String> _categoryIllustrations = {
  '공부': AppIllustrations.books,
  '건강': AppIllustrations.muscle,
};

class TodoCategorySection extends StatelessWidget {
  final String title;
  final List<TodoModel> todos;
  final ValueChanged<TodoModel> onToggle;
  final ValueChanged<TodoModel>? onTap;
  final bool compactCards;
  final int? visibleLimit;
  final bool expanded;
  final VoidCallback? onToggleExpanded;

  const TodoCategorySection({
    super.key,
    required this.title,
    required this.todos,
    required this.onToggle,
    this.onTap,
    this.compactCards = false,
    this.visibleLimit,
    this.expanded = true,
    this.onToggleExpanded,
  });

  @override
  Widget build(BuildContext context) {
    if (todos.isEmpty) return const SizedBox.shrink();

    final color = TodoStyles.categoryColor(title);
    final hasLimit = visibleLimit != null && todos.length > visibleLimit!;
    final visibleTodos = hasLimit && !expanded
        ? todos.take(visibleLimit!).toList()
        : todos;

    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.cardGap),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(4, 12, 4, 8),
            child: Row(
              children: [
                Container(
                  width: 10,
                  height: 10,
                  decoration: BoxDecoration(
                    color: color,
                    shape: BoxShape.circle,
                  ),
                ),
                const SizedBox(width: 8),
                if (_categoryIllustrations[title] != null) ...[
                  Image.asset(
                    _categoryIllustrations[title]!,
                    width: 22,
                    height: 22,
                  ),
                  const SizedBox(width: 6),
                ],
                Text(
                  title,
                  style: AppTextStyles.sectionTitle.copyWith(
                    color: AppTheme.textPrimary,
                  ),
                ),
                const SizedBox(width: 6),
                Text(
                  '${todos.length}',
                  style: AppTextStyles.meta.copyWith(
                    color: AppTheme.textSecondary,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const Spacer(),
                if (hasLimit && onToggleExpanded != null)
                  GestureDetector(
                    onTap: onToggleExpanded,
                    child: Text(
                      expanded ? '접기' : '더 보기',
                      style: AppTextStyles.meta.copyWith(
                        color: color,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
              ],
            ),
          ),
          ...visibleTodos.map(
            (todo) => TodoCard(
              todo: todo,
              compact: compactCards,
              onTap: onTap == null ? null : () => onTap!(todo),
              onToggle: () => onToggle(todo),
            ),
          ),
        ],
      ),
    );
  }
}
