import 'package:flutter/material.dart';
import '../../data/widget_catalog.dart';
import '../../models/dashboard_widget_model.dart';
import '../../models/schedule_model.dart';
import '../../theme/app_theme.dart';
import 'dashboard_widget_card.dart';

/// 주간 캘린더 (Medium).
/// 실데이터: scheduleApi.list() 결과. 이번 주 날짜별 일정 개수를 표시.
class WeeklyCalendarWidget extends StatelessWidget {
  final List<ScheduleModel> schedules;

  const WeeklyCalendarWidget({super.key, this.schedules = const []});

  static const _dow = ['월', '화', '수', '목', '금', '토', '일'];

  @override
  Widget build(BuildContext context) {
    final spec = WidgetCatalog.of(DashboardWidgetType.weeklyCalendar);
    final now = DateTime.now();
    final monday = now.subtract(Duration(days: now.weekday - 1));

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        WidgetCardHeader(
          icon: spec.icon,
          accent: spec.accent,
          title: spec.title,
          showChevron: true,
        ),
        const Spacer(),
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: List.generate(7, (i) {
            final date = DateTime(monday.year, monday.month, monday.day + i);
            final key =
                '${date.year.toString().padLeft(4, '0')}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}';
            final count = schedules.where((s) => s.date == key).length;
            final isToday = date.year == now.year &&
                date.month == now.month &&
                date.day == now.day;
            return _DayColumn(
              dow: _dow[i],
              day: date.day,
              count: count,
              isToday: isToday,
              accent: spec.accent,
              isSunday: i == 6,
            );
          }),
        ),
        const Spacer(),
      ],
    );
  }
}

class _DayColumn extends StatelessWidget {
  final String dow;
  final int day;
  final int count;
  final bool isToday;
  final bool isSunday;
  final Color accent;

  const _DayColumn({
    required this.dow,
    required this.day,
    required this.count,
    required this.isToday,
    required this.isSunday,
    required this.accent,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          dow,
          style: TextStyle(
            fontSize: 10.5,
            fontWeight: FontWeight.w600,
            color: isSunday ? AppTheme.red : AppTheme.textSecondary,
          ),
        ),
        const SizedBox(height: 6),
        Container(
          width: 30,
          height: 30,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: isToday ? accent : accent.withValues(alpha: 0.08),
            borderRadius: BorderRadius.circular(9),
          ),
          child: Text(
            '$day',
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w700,
              color: isToday ? Colors.white : AppTheme.textPrimary,
            ),
          ),
        ),
        const SizedBox(height: 5),
        if (count > 0)
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
            decoration: BoxDecoration(
              color: accent.withValues(alpha: 0.14),
              borderRadius: BorderRadius.circular(6),
            ),
            child: Text(
              '$count',
              style: TextStyle(
                fontSize: 10,
                fontWeight: FontWeight.w700,
                color: accent,
              ),
            ),
          )
        else
          const SizedBox(height: 14),
      ],
    );
  }
}
