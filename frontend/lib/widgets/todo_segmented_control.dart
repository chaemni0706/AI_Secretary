import 'package:flutter/material.dart';
import '../theme/app_constants.dart';
import '../theme/app_theme.dart';

class TodoSegment {
  final String label;
  final int count;

  const TodoSegment({required this.label, required this.count});
}

class TodoSegmentedControl extends StatelessWidget {
  final int selectedIndex;
  final List<TodoSegment> segments;
  final ValueChanged<int> onChanged;

  const TodoSegmentedControl({
    super.key,
    required this.selectedIndex,
    required this.segments,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
      child: Container(
        padding: const EdgeInsets.all(4),
        decoration: BoxDecoration(
          color: Colors.white.withValues(alpha: 0.55),
          borderRadius: BorderRadius.circular(AppRadii.control),
          border: Border.all(color: AppTheme.separator.withValues(alpha: 0.6)),
        ),
        child: Row(
          children: List.generate(segments.length, (index) {
            final segment = segments[index];
            final selected = index == selectedIndex;
            return Expanded(
              child: GestureDetector(
                onTap: () => onChanged(index),
                behavior: HitTestBehavior.opaque,
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 160),
                  curve: Curves.easeOut,
                  padding: const EdgeInsets.symmetric(vertical: 10),
                  decoration: BoxDecoration(
                    color: selected ? Colors.white : Colors.transparent,
                    borderRadius: BorderRadius.circular(AppRadii.small),
                    boxShadow: selected
                        ? [
                            BoxShadow(
                              color: Colors.black.withValues(alpha: 0.07),
                              blurRadius: 7,
                              offset: const Offset(0, 2),
                            ),
                          ]
                        : null,
                  ),
                  child: Text(
                    '${segment.label} ${segment.count}',
                    textAlign: TextAlign.center,
                    style: AppTextStyles.cardTitle.copyWith(
                      color: selected
                          ? AppTheme.textPrimary
                          : AppTheme.textSecondary,
                      fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
                    ),
                  ),
                ),
              ),
            );
          }),
        ),
      ),
    );
  }
}
