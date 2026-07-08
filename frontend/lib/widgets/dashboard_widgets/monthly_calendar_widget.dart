import 'package:flutter/material.dart';
import '../../data/widget_catalog.dart';
import '../../models/dashboard_widget_model.dart';
import '../../models/schedule_model.dart';
import '../../theme/app_theme.dart';
import 'dashboard_widget_card.dart';

/// 월간 캘린더 미리보기 (Large).
/// 실데이터: scheduleApi.list() 결과([ScheduleModel]). 일정 있는 날에 점 표시.
class MonthlyCalendarWidget extends StatelessWidget {
  final List<ScheduleModel> schedules;

  const MonthlyCalendarWidget({super.key, this.schedules = const []});

  static const _dow = ['일', '월', '화', '수', '목', '금', '토'];

  @override
  Widget build(BuildContext context) {
    final spec = WidgetCatalog.of(DashboardWidgetType.monthlyCalendar);
    final now = DateTime.now();
    final firstDow = DateTime(now.year, now.month, 1).weekday % 7; // 0=일
    final daysInMonth = DateTime(now.year, now.month + 1, 0).day;

    // 이번 달 일정이 있는 날짜 집합.
    final prefix =
        '${now.year.toString().padLeft(4, '0')}-${now.month.toString().padLeft(2, '0')}-';
    final busyDays = <int>{};
    for (final s in schedules) {
      final date = s.date;
      if (date != null && date.startsWith(prefix)) {
        final day = int.tryParse(date.substring(prefix.length));
        if (day != null) busyDays.add(day);
      }
    }

    final cells = <Widget>[];
    for (int i = 0; i < firstDow; i++) {
      cells.add(const SizedBox.shrink());
    }
    for (int d = 1; d <= daysInMonth; d++) {
      final weekday = (firstDow + d - 1) % 7;
      final isToday = d == now.day;
      final busy = busyDays.contains(d);
      Color numColor = AppTheme.textPrimary;
      if (weekday == 0) numColor = AppTheme.red;
      cells.add(_DayCell(
        day: d,
        isToday: isToday,
        busy: busy,
        numberColor: isToday ? Colors.white : numColor,
        accent: spec.accent,
      ));
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        WidgetCardHeader(
          icon: spec.icon,
          accent: spec.accent,
          title: '${now.month}월',
          showChevron: true,
        ),
        const SizedBox(height: 8),
        Row(
          children: List.generate(7, (i) {
            Color c = AppTheme.textSecondary;
            if (i == 0) c = AppTheme.red;
            if (i == 6) c = AppTheme.blue;
            return Expanded(
              child: Text(
                _dow[i],
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 10.5,
                  fontWeight: FontWeight.w600,
                  color: c,
                ),
              ),
            );
          }),
        ),
        const SizedBox(height: 4),
        Expanded(
          child: GridView.count(
            crossAxisCount: 7,
            physics: const NeverScrollableScrollPhysics(),
            padding: EdgeInsets.zero,
            children: cells,
          ),
        ),
      ],
    );
  }
}

class _DayCell extends StatelessWidget {
  final int day;
  final bool isToday;
  final bool busy;
  final Color numberColor;
  final Color accent;

  const _DayCell({
    required this.day,
    required this.isToday,
    required this.busy,
    required this.numberColor,
    required this.accent,
  });

  @override
  Widget build(BuildContext context) {
    // 정사각형 그리드 셀(GridView 비율 1.0)보다 내용이 살짝 커서 생기던
    // bottom overflow(수 px)를 방지: 셀 크기에 맞게 내용을 축소만(scaleDown) 한다.
    return FittedBox(
      fit: BoxFit.scaleDown,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            width: 22,
            height: 22,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: isToday ? accent : Colors.transparent,
            shape: BoxShape.circle,
          ),
          child: Text(
            '$day',
            style: TextStyle(
              fontSize: 11.5,
              fontWeight: isToday ? FontWeight.w700 : FontWeight.w500,
              color: numberColor,
            ),
          ),
        ),
        const SizedBox(height: 2),
        Container(
          width: 4,
          height: 4,
          decoration: BoxDecoration(
            color: busy && !isToday ? accent : Colors.transparent,
            shape: BoxShape.circle,
          ),
        ),
        ],
      ),
    );
  }
}
