import 'package:flutter/material.dart';
import '../models/schedule_model.dart';
import '../theme/app_constants.dart';
import '../theme/app_theme.dart';
import '../theme/schedule_styles.dart';
import 'glass_card.dart';

class ScheduleCard extends StatelessWidget {
  final ScheduleModel schedule;
  final VoidCallback? onTap;
  final bool showDate;

  const ScheduleCard({
    super.key,
    required this.schedule,
    this.onTap,
    this.showDate = false,
  });

  @override
  Widget build(BuildContext context) {
    final color = ScheduleStyles.categoryColor(schedule.category);
    final timeText = ScheduleStyles.timeText(
      schedule.startTime,
      schedule.endTime,
    );
    final category = ScheduleStyles.categoryLabel(schedule.category);

    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, AppSpacing.cardGap),
      child: GlassCard(
        onTap: onTap,
        padding: const EdgeInsets.all(14),
        child: Row(
          children: [
            Container(
              width: 4,
              height: 48,
              decoration: BoxDecoration(
                color: color,
                borderRadius: BorderRadius.circular(4),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    schedule.title,
                    style: AppTextStyles.cardTitle.copyWith(
                      color: AppTheme.textPrimary,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Wrap(
                    spacing: 6,
                    runSpacing: 4,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      if (showDate && schedule.date != null)
                        _MetaText(schedule.date!),
                      _MetaText(timeText),
                      PillBadge(label: category, color: color),
                    ],
                  ),
                  if (schedule.location != null &&
                      schedule.location!.isNotEmpty) ...[
                    const SizedBox(height: 5),
                    Row(
                      children: [
                        const Icon(
                          Icons.place_outlined,
                          size: 12,
                          color: AppTheme.textSecondary,
                        ),
                        const SizedBox(width: 3),
                        Expanded(
                          child: Text(
                            schedule.location!,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: AppTextStyles.meta.copyWith(
                              color: AppTheme.textSecondary,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                ],
              ),
            ),
            Icon(
              ScheduleStyles.categoryIcon(schedule.category),
              color: color.withValues(alpha: 0.62),
              size: 20,
            ),
          ],
        ),
      ),
    );
  }
}

class _MetaText extends StatelessWidget {
  final String value;

  const _MetaText(this.value);

  @override
  Widget build(BuildContext context) {
    return Text(
      value,
      style: AppTextStyles.meta.copyWith(color: AppTheme.textSecondary),
    );
  }
}
