import 'package:flutter/material.dart';
import '../theme/app_constants.dart';
import '../theme/app_theme.dart';
import '../theme/illustrations.dart';
import 'glass_card.dart';
import 'todo_progress_celebration.dart';
import 'toss_motion_widgets.dart';

class TodoProgressCard extends StatelessWidget {
  final int done;
  final int total;

  const TodoProgressCard({super.key, required this.done, required this.total});

  @override
  Widget build(BuildContext context) {
    final remaining = total - done;
    final rate = total == 0 ? 0.0 : done / total;
    final complete = total > 0 && done >= total;
    final percent = (rate * 100).round();
    final fillColor = complete ? TossColors.green : TossColors.blue500;

    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 10, 16, 0),
      child: GlassCard(
        padding: const EdgeInsets.all(TossSpacing.xl),
        shadow: TossShadow.medium,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Expanded(
                  child: Row(
                    children: [
                      if (complete) ...[
                        Image.asset(
                          AppIllustrations.party,
                          width: 26,
                          height: 26,
                        ),
                        const SizedBox(width: 6),
                      ],
                      const Text('오늘 진행률', style: TossTypography.caption),
                    ],
                  ),
                ),
                TodoProgressCelebration(
                  active: complete,
                  child: TossCountUpText(
                    value: percent,
                    formatter: (v) => '${v.round()}%',
                    style: TossTypography.display.copyWith(
                      color: complete
                          ? TossColors.green
                          : TossColors.textPrimary,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 14),
            ClipRRect(
              borderRadius: BorderRadius.circular(TossRadius.full),
              child: Stack(
                children: [
                  Container(height: 10, color: TossColors.grey100),
                  AnimatedFractionallySizedBox(
                    duration: TossMotion.normal,
                    curve: TossMotion.easeOut,
                    widthFactor: rate.clamp(0.0, 1.0),
                    child: Container(height: 10, color: fillColor),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 14),
            Row(
              children: [
                _Metric(label: '완료', value: '$done개', color: fillColor),
                const SizedBox(width: 8),
                _Metric(
                  label: '남은 할 일',
                  value: '${remaining < 0 ? 0 : remaining}개',
                  color: TossColors.textPrimary,
                ),
                const SizedBox(width: 8),
                _Metric(
                  label: '전체',
                  value: '$total개',
                  color: TossColors.textSecondary,
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _Metric extends StatelessWidget {
  final String label;
  final String value;
  final Color color;

  const _Metric({
    required this.label,
    required this.value,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 9),
        decoration: BoxDecoration(
          color: TossColors.grey50,
          borderRadius: BorderRadius.circular(AppRadii.small),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(value, style: AppTextStyles.cardTitle.copyWith(color: color)),
            const SizedBox(height: 2),
            Text(
              label,
              style: AppTextStyles.meta.copyWith(color: AppTheme.textSecondary),
            ),
          ],
        ),
      ),
    );
  }
}
