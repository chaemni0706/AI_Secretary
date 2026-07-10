import 'package:flutter/material.dart';
import '../../data/widget_catalog.dart';
import '../../data/widget_mock_data.dart';
import '../../models/dashboard_widget_model.dart';
import '../../theme/app_theme.dart';
import 'dashboard_widget_card.dart';

/// 소비 분석 위젯 (Medium).
/// 현재 mock([WidgetMockData.spendingInsight]). 가계부 분석 API 준비 시 교체.
class SpendingAnalysisWidget extends StatelessWidget {
  const SpendingAnalysisWidget({super.key});

  @override
  Widget build(BuildContext context) {
    final spec = WidgetCatalog.of(DashboardWidgetType.spendingAnalysis);
    final insight = WidgetMockData.spendingInsight;
    final up = insight.changePercent >= 0;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        WidgetCardHeader(
          icon: spec.icon,
          accent: spec.accent,
          title: spec.title,
          showChevron: true,
        ),
        const SizedBox(height: 10),
        Row(
          children: [
            _Chip(label: '최다 ${insight.topCategory}', color: spec.accent),
            const SizedBox(width: 6),
            _Chip(
              label: '전월 대비 ${up ? '+' : '-'}${insight.changePercent.abs()}%',
              color: up ? AppTheme.red : AppTheme.green,
              icon: up ? Icons.trending_up : Icons.trending_down,
            ),
          ],
        ),
        const Spacer(),
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(Icons.auto_awesome, size: 14, color: spec.accent),
            const SizedBox(width: 6),
            Expanded(
              child: Text(
                insight.comment,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  fontSize: 12,
                  height: 1.35,
                  fontWeight: FontWeight.w500,
                  color: AppTheme.textTertiary,
                ),
              ),
            ),
          ],
        ),
      ],
    );
  }
}

class _Chip extends StatelessWidget {
  final String label;
  final Color color;
  final IconData? icon;

  const _Chip({required this.label, required this.color, this.icon});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(9),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, size: 13, color: color),
            const SizedBox(width: 4),
          ],
          Text(
            label,
            style: TextStyle(
              fontSize: 11.5,
              fontWeight: FontWeight.w700,
              color: color,
            ),
          ),
        ],
      ),
    );
  }
}
