import 'package:flutter/material.dart';
import '../theme/app_constants.dart';
import '../theme/app_theme.dart';
import 'glass_card.dart';
import 'todo_progress_celebration.dart';

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
    final fillColor = Color.lerp(
      AppTheme.blue.withValues(alpha: 0.35),
      complete ? AppTheme.green : AppTheme.blue,
      rate,
    )!;
    final cardStart = complete
        ? AppTheme.green.withValues(alpha: 0.26)
        : fillColor.withValues(alpha: 0.24 + (0.26 * rate));
    final cardEnd = complete
        ? AppTheme.green.withValues(alpha: 0.12)
        : Colors.white.withValues(alpha: 0.72);

    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 10, 16, 0),
      child: GlassCard(
        padding: EdgeInsets.zero,
        child: ClipRRect(
          borderRadius: BorderRadius.circular(AppRadii.card),
          child: Container(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.centerLeft,
                end: Alignment.centerRight,
                colors: [cardStart, cardEnd],
                stops: [rate.clamp(0.18, 0.9), 1.0],
              ),
            ),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          '오늘 진행률',
                          style: AppTextStyles.sectionTitle.copyWith(
                            color: AppTheme.textPrimary,
                          ),
                        ),
                      ),
                      TodoProgressCelebration(
                        active: complete,
                        child: Text(
                          '$percent%',
                          style: TextStyle(
                            fontSize: 28,
                            fontWeight: FontWeight.w800,
                            color: complete
                                ? AppTheme.green
                                : AppTheme.textPrimary,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 14),
                  ClipRRect(
                    borderRadius: BorderRadius.circular(999),
                    child: Stack(
                      children: [
                        Container(
                          height: 12,
                          color: AppTheme.separator.withValues(alpha: 0.7),
                        ),
                        FractionallySizedBox(
                          widthFactor: rate.clamp(0.0, 1.0),
                          child: Container(
                            height: 12,
                            decoration: BoxDecoration(
                              gradient: LinearGradient(
                                colors: [
                                  fillColor.withValues(alpha: 0.72),
                                  fillColor,
                                ],
                              ),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      _Metric(label: '완료', value: '$done개', color: fillColor),
                      const SizedBox(width: 10),
                      _Metric(
                        label: '남은 할 일',
                        value: '${remaining < 0 ? 0 : remaining}개',
                        color: AppTheme.orange,
                      ),
                      const SizedBox(width: 10),
                      _Metric(
                        label: '전체',
                        value: '$total개',
                        color: AppTheme.textSecondary,
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
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
          color: Colors.white.withValues(alpha: 0.58),
          borderRadius: BorderRadius.circular(AppRadii.small),
          border: Border.all(color: AppTheme.separator.withValues(alpha: 0.65)),
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
