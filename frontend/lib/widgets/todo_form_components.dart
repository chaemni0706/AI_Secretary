import 'package:flutter/material.dart';
import '../theme/app_constants.dart';
import '../theme/app_theme.dart';
import '../theme/todo_styles.dart';
import 'glass_card.dart';

class TodoFormSection extends StatelessWidget {
  final List<Widget> children;

  const TodoFormSection({super.key, required this.children});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.sectionGap),
      child: GlassCard(
        padding: EdgeInsets.zero,
        child: Column(children: children),
      ),
    );
  }
}

class TodoFormRow extends StatelessWidget {
  final IconData icon;
  final String label;
  final Widget child;
  final bool showDivider;

  const TodoFormRow({
    super.key,
    required this.icon,
    required this.label,
    required this.child,
    this.showDivider = true,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              Icon(icon, size: 20, color: AppTheme.textSecondary),
              const SizedBox(width: 12),
              SizedBox(
                width: 78,
                child: Text(
                  label,
                  style: AppTextStyles.cardTitle.copyWith(
                    color: AppTheme.textPrimary,
                  ),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(child: child),
            ],
          ),
        ),
        if (showDivider)
          Divider(
            height: 1,
            indent: 58,
            color: AppTheme.separator.withValues(alpha: 0.7),
          ),
      ],
    );
  }
}

class TodoTextInputRow extends StatelessWidget {
  final TextEditingController controller;
  final String label;
  final IconData icon;
  final String? hint;
  final int maxLines;
  final bool showDivider;

  const TodoTextInputRow({
    super.key,
    required this.controller,
    required this.label,
    required this.icon,
    this.hint,
    this.maxLines = 1,
    this.showDivider = true,
  });

  @override
  Widget build(BuildContext context) {
    return TodoFormRow(
      icon: icon,
      label: label,
      showDivider: showDivider,
      child: TextField(
        controller: controller,
        maxLines: maxLines,
        style: AppTextStyles.cardTitle.copyWith(color: AppTheme.textPrimary),
        decoration: InputDecoration(
          hintText: hint,
          isDense: true,
          border: InputBorder.none,
          hintStyle: AppTextStyles.cardTitle.copyWith(
            color: AppTheme.textSecondary.withValues(alpha: 0.7),
          ),
        ),
      ),
    );
  }
}

class TodoDateInputRow extends StatelessWidget {
  final TextEditingController controller;
  final VoidCallback onNormalize;
  final bool showDivider;

  const TodoDateInputRow({
    super.key,
    required this.controller,
    required this.onNormalize,
    this.showDivider = true,
  });

  @override
  Widget build(BuildContext context) {
    return TodoFormRow(
      icon: Icons.event_outlined,
      label: '날짜',
      showDivider: showDivider,
      child: Container(
        constraints: const BoxConstraints(minHeight: 34),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: AppTheme.blue.withValues(alpha: 0.08),
          borderRadius: BorderRadius.circular(999),
        ),
        child: TextField(
          controller: controller,
          onSubmitted: (_) => onNormalize(),
          onEditingComplete: onNormalize,
          style: AppTextStyles.cardTitle.copyWith(color: AppTheme.blue),
          decoration: InputDecoration(
            hintText: 'YYYY-MM-DD',
            isDense: true,
            border: InputBorder.none,
            hintStyle: AppTextStyles.cardTitle.copyWith(
              color: AppTheme.blue.withValues(alpha: 0.62),
            ),
          ),
        ),
      ),
    );
  }
}

class TodoCategorySelector extends StatelessWidget {
  final String value;
  final ValueChanged<String> onChanged;
  final bool showDivider;

  const TodoCategorySelector({
    super.key,
    required this.value,
    required this.onChanged,
    this.showDivider = true,
  });

  @override
  Widget build(BuildContext context) {
    return TodoFormRow(
      icon: Icons.category_outlined,
      label: '카테고리',
      showDivider: showDivider,
      child: Wrap(
        spacing: 8,
        runSpacing: 8,
        children: TodoStyles.categoryOrder.map((category) {
          final selected = category == value;
          final color = TodoStyles.categoryColor(category);
          return ChoiceChip(
            label: Text(category),
            selected: selected,
            showCheckmark: false,
            labelStyle: AppTextStyles.meta.copyWith(
              color: selected ? Colors.white : color,
              fontWeight: FontWeight.w700,
            ),
            selectedColor: color,
            backgroundColor: color.withValues(alpha: 0.1),
            side: BorderSide(color: color.withValues(alpha: 0.22)),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(999),
            ),
            onSelected: (_) => onChanged(category),
          );
        }).toList(),
      ),
    );
  }
}

class TodoPrioritySelector extends StatelessWidget {
  final String value;
  final ValueChanged<String> onChanged;
  final bool showDivider;

  const TodoPrioritySelector({
    super.key,
    required this.value,
    required this.onChanged,
    this.showDivider = true,
  });

  @override
  Widget build(BuildContext context) {
    return TodoFormRow(
      icon: Icons.flag_outlined,
      label: '우선순위',
      showDivider: showDivider,
      child: DropdownButtonHideUnderline(
        child: DropdownButton<String>(
          value: value,
          isExpanded: true,
          items: const ['high', 'medium', 'low']
              .map(
                (priority) => DropdownMenuItem(
                  value: priority,
                  child: Text(TodoStyles.priorityLabel(priority)),
                ),
              )
              .toList(),
          onChanged: (next) {
            if (next != null) onChanged(next);
          },
        ),
      ),
    );
  }
}

class TodoCompletedRow extends StatelessWidget {
  final bool value;
  final ValueChanged<bool> onChanged;
  final bool showDivider;

  const TodoCompletedRow({
    super.key,
    required this.value,
    required this.onChanged,
    this.showDivider = true,
  });

  @override
  Widget build(BuildContext context) {
    return TodoFormRow(
      icon: Icons.check_circle_outline,
      label: '완료',
      showDivider: showDivider,
      child: Switch.adaptive(value: value, onChanged: onChanged),
    );
  }
}

class TodoDisabledInfoRow extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  final bool showDivider;

  const TodoDisabledInfoRow({
    super.key,
    required this.icon,
    required this.label,
    required this.value,
    this.showDivider = true,
  });

  @override
  Widget build(BuildContext context) {
    return TodoFormRow(
      icon: icon,
      label: label,
      showDivider: showDivider,
      child: Text(
        value,
        textAlign: TextAlign.right,
        style: AppTextStyles.cardTitle.copyWith(
          color: AppTheme.textSecondary.withValues(alpha: 0.78),
        ),
      ),
    );
  }
}

class TodoDeleteActionSection extends StatelessWidget {
  final bool deleting;
  final VoidCallback onDelete;

  const TodoDeleteActionSection({
    super.key,
    required this.deleting,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 2),
      child: GlassCard(
        padding: const EdgeInsets.all(14),
        child: SizedBox(
          width: double.infinity,
          child: OutlinedButton.icon(
            onPressed: deleting ? null : onDelete,
            icon: deleting
                ? const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.delete_outline, size: 18),
            label: Text(deleting ? '삭제 중...' : '할 일 삭제'),
            style: OutlinedButton.styleFrom(
              foregroundColor: AppTheme.red,
              side: BorderSide(color: AppTheme.red.withValues(alpha: 0.34)),
              padding: const EdgeInsets.symmetric(vertical: 13),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(AppRadii.control),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
