import 'package:flutter/material.dart';
import '../../data/widget_catalog.dart';
import '../../models/dashboard_model.dart';
import '../../models/dashboard_widget_model.dart';
import '../../theme/app_theme.dart';
import '../../theme/illustrations.dart';
import 'dashboard_widget_card.dart';

/// 오늘 요약 / 하루 브리핑 (Medium).
/// 실데이터: dashboardApi.getTodayDashboard() 결과([DashboardData]).
class BriefingWidget extends StatelessWidget {
  final DashboardData? data;
  final bool loading;

  const BriefingWidget({super.key, this.data, this.loading = false});

  @override
  Widget build(BuildContext context) {
    final spec = WidgetCatalog.of(DashboardWidgetType.briefing);
    final d = data;
    final scheduleCount = d?.stats.scheduleCount ?? 0;
    final todoCount = d?.stats.todoCount ?? 0;
    final doneCount = d?.stats.completedTodoCount ?? 0;
    final message = (d?.summaryMessage.isNotEmpty ?? false)
        ? d!.summaryMessage
        : (loading ? '오늘 브리핑을 불러오는 중…' : '오늘도 좋은 하루 보내세요 :)');

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
            _MiniStat(
              icon: Icons.event_outlined,
              label: '일정',
              value: '$scheduleCount건',
              color: AppTheme.blue,
            ),
            const SizedBox(width: 8),
            _MiniStat(
              icon: Icons.checklist,
              label: '할 일',
              value: '$doneCount/$todoCount',
              color: AppTheme.green,
            ),
          ],
        ),
        const Spacer(),
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Image.asset(AppIllustrations.wave, width: 16, height: 16),
            const SizedBox(width: 6),
            Expanded(
              child: Text(
                message,
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

class _MiniStat extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  final Color color;

  const _MiniStat({
    required this.icon,
    required this.label,
    required this.value,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: color),
          const SizedBox(width: 5),
          Text(
            label,
            style: const TextStyle(
              fontSize: 11.5,
              fontWeight: FontWeight.w500,
              color: AppTheme.textSecondary,
            ),
          ),
          const SizedBox(width: 4),
          Text(
            value,
            style: TextStyle(
              fontSize: 12.5,
              fontWeight: FontWeight.w700,
              color: color,
            ),
          ),
        ],
      ),
    );
  }
}
