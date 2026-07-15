import 'package:flutter/material.dart';
import '../models/schedule_model.dart';
import '../theme/app_constants.dart';
import '../theme/app_theme.dart';
import '../theme/schedule_styles.dart';
import 'schedule_card.dart';

class CategoryScheduleSection extends StatelessWidget {
  final String title;
  final List<ScheduleModel> schedules;
  final ValueChanged<ScheduleModel>? onScheduleTap;

  const CategoryScheduleSection({
    super.key,
    required this.title,
    required this.schedules,
    this.onScheduleTap,
  });

  @override
  Widget build(BuildContext context) {
    if (schedules.isEmpty) return const SizedBox.shrink();

    final color = ScheduleStyles.categoryColor(title);
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.cardGap),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 14, 20, 8),
            child: Row(
              children: [
                Container(
                  width: 9,
                  height: 9,
                  decoration: BoxDecoration(
                    color: color,
                    shape: BoxShape.circle,
                  ),
                ),
                const SizedBox(width: 8),
                Text(
                  title,
                  style: AppTextStyles.sectionTitle.copyWith(
                    color: AppTheme.textPrimary,
                  ),
                ),
                const SizedBox(width: 6),
                Text(
                  '${schedules.length}',
                  style: AppTextStyles.meta.copyWith(
                    color: AppTheme.textSecondary,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
          ),
          ...schedules.map(
            (schedule) => ScheduleCard(
              schedule: schedule,
              showDate: true,
              onTap: onScheduleTap == null
                  ? null
                  : () => onScheduleTap!(schedule),
            ),
          ),
        ],
      ),
    );
  }
}
