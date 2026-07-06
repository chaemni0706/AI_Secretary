import 'package:flutter/material.dart';
import '../models/todo_model.dart';
import '../theme/app_constants.dart';
import '../theme/app_theme.dart';
import '../theme/todo_styles.dart';
import 'glass_card.dart';

class TodoCard extends StatelessWidget {
  final TodoModel todo;
  final VoidCallback onToggle;
  final bool compact;

  const TodoCard({
    super.key,
    required this.todo,
    required this.onToggle,
    this.compact = false,
  });

  @override
  Widget build(BuildContext context) {
    final done = todo.completed;
    final category = TodoStyles.categoryLabel(todo.category);
    final categoryColor = TodoStyles.categoryColor(todo.category);

    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.cardGap),
      child: GlassCard(
        padding: EdgeInsets.all(compact ? 12 : 14),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 4,
              height: compact ? 40 : 48,
              decoration: BoxDecoration(
                color: categoryColor,
                borderRadius: BorderRadius.circular(4),
              ),
            ),
            const SizedBox(width: 10),
            GestureDetector(
              onTap: onToggle,
              behavior: HitTestBehavior.opaque,
              child: Icon(
                done ? Icons.check_circle : Icons.radio_button_unchecked,
                color: done ? categoryColor : AppTheme.textSecondary,
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
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: AppTextStyles.cardTitle.copyWith(
                      color: done
                          ? AppTheme.textSecondary
                          : AppTheme.textPrimary,
                      decoration: done ? TextDecoration.lineThrough : null,
                    ),
                  ),
                  const SizedBox(height: 5),
                  Wrap(
                    spacing: 6,
                    runSpacing: 4,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      _MetaChip(
                        icon: Icons.event_outlined,
                        label: todo.dueDate ?? '마감일 미정',
                      ),
                      PillBadge(label: category, color: categoryColor),
                      PillBadge(
                        label: TodoStyles.priorityLabel(todo.priority),
                        color: TodoStyles.priorityColor(todo.priority),
                      ),
                    ],
                  ),
                  if (!compact &&
                      todo.memo != null &&
                      todo.memo!.isNotEmpty) ...[
                    const SizedBox(height: 6),
                    Text(
                      todo.memo!,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: AppTextStyles.meta.copyWith(
                        color: AppTheme.textSecondary,
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _MetaChip extends StatelessWidget {
  final IconData icon;
  final String label;

  const _MetaChip({required this.icon, required this.label});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 12, color: AppTheme.textSecondary),
        const SizedBox(width: 3),
        Text(
          label,
          style: AppTextStyles.meta.copyWith(color: AppTheme.textSecondary),
        ),
      ],
    );
  }
}
