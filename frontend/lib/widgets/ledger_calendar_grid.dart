import 'package:flutter/material.dart';
import '../models/ledger_models.dart';
import '../models/mock_ledger_data.dart';
import '../theme/app_theme.dart';
import '../theme/ledger_styles.dart';

/// 월간 소비 달력. 요일 헤더 + 7열 그리드로 각 날짜의 지출/수입 합계를 보여준다.
class LedgerCalendarGrid extends StatelessWidget {
  final int selectedDay;
  final ValueChanged<int> onSelect;

  /// 표시할 연/월. null 이면 Mock 기준(하위호환).
  final int? year;
  final int? month;

  /// 일(day)별 합계. null 이면 Mock 데이터(하위호환).
  final Map<int, DayInfo>? dayData;

  const LedgerCalendarGrid({
    super.key,
    required this.selectedDay,
    required this.onSelect,
    this.year,
    this.month,
    this.dayData,
  });

  static const _dowLabels = ['일', '월', '화', '수', '목', '금', '토'];
  static const _saturday = TossColors.blue500;

  @override
  Widget build(BuildContext context) {
    final y = year ?? MockLedgerData.demoYear;
    final m = month ?? MockLedgerData.demoMonth;
    final data = dayData ?? MockLedgerData.dayData;

    final firstDow = DateTime(y, m, 1).weekday % 7; // 0=일
    final daysInMonth = DateTime(y, m + 1, 0).day;

    final cells = <Widget>[];
    for (int i = 0; i < firstDow; i++) {
      cells.add(const SizedBox.shrink());
    }
    for (int d = 1; d <= daysInMonth; d++) {
      cells.add(_DayCell(
        day: d,
        info: data[d],
        selected: d == selectedDay,
        weekday: (firstDow + d - 1) % 7,
        onTap: () => onSelect(d),
      ));
    }

    return Column(
      children: [
        Row(
          children: List.generate(7, (i) {
            Color color = AppTheme.textSecondary;
            if (i == 0) color = AppTheme.red;
            if (i == 6) color = _saturday;
            return Expanded(
              child: Text(
                _dowLabels[i],
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w500,
                  color: color,
                ),
              ),
            );
          }),
        ),
        const SizedBox(height: 8),
        GridView.count(
          crossAxisCount: 7,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          childAspectRatio: 0.72,
          mainAxisSpacing: 4,
          children: cells,
        ),
      ],
    );
  }
}

class _DayCell extends StatelessWidget {
  final int day;
  final DayInfo? info;
  final bool selected;
  final int weekday; // 0=일 ... 6=토
  final VoidCallback onTap;

  const _DayCell({
    required this.day,
    required this.info,
    required this.selected,
    required this.weekday,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    Color numberColor = AppTheme.textPrimary;
    if (weekday == 0) numberColor = AppTheme.red;
    if (selected) numberColor = AppTheme.blue;

    final spend = info?.spend ?? 0;
    final income = info?.income ?? 0;

    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 27,
            height: 27,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: selected
                  ? AppTheme.blue.withValues(alpha: 0.14)
                  : Colors.transparent,
              shape: BoxShape.circle,
            ),
            child: Text(
              '$day',
              style: TextStyle(
                fontSize: 13.5,
                fontWeight: FontWeight.w600,
                color: numberColor,
              ),
            ),
          ),
          const SizedBox(height: 2),
          SizedBox(
            height: 9,
            child: Text(
              spend > 0 ? '-${LedgerStyles.formatWon(spend)}' : '',
              style: const TextStyle(
                fontSize: 8,
                height: 1.15,
                fontWeight: FontWeight.w600,
                color: AppTheme.textSecondary,
              ),
            ),
          ),
          SizedBox(
            height: 9,
            child: Text(
              income > 0 ? '+${LedgerStyles.formatWon(income)}' : '',
              style: const TextStyle(
                fontSize: 8,
                height: 1.15,
                fontWeight: FontWeight.w600,
                color: AppTheme.blue,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
