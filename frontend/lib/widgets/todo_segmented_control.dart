import 'package:flutter/material.dart';
import '../theme/app_constants.dart';
import '../theme/app_theme.dart';

class TodoSegment {
  final String label;
  final int count;
  final bool showCount;

  const TodoSegment({
    required this.label,
    required this.count,
    this.showCount = true,
  });
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
          color: TossColors.grey200,
          borderRadius: BorderRadius.circular(AppRadii.control),
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
                  duration: TossMotion.fast,
                  curve: TossMotion.easeOut,
                  padding: const EdgeInsets.symmetric(vertical: 10),
                  decoration: BoxDecoration(
                    color: selected ? TossColors.bgWhite : Colors.transparent,
                    borderRadius: BorderRadius.circular(AppRadii.small),
                    boxShadow: selected ? TossShadow.tiny : null,
                  ),
                  child: Text(
                    segment.showCount
                        ? '${segment.label} ${segment.count}'
                        : segment.label,
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
