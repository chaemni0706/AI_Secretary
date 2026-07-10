import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import '../theme/app_constants.dart';
import '../theme/app_theme.dart';

/// 캘린더 상단 "YYYY년 M월" 탭 시 열리는 연/월 선택 바텀시트.
/// iOS 캘린더 스타일 휠 피커(CupertinoPicker) 두 개(연도/월)를 보여주고,
/// "완료"를 탭하면 DateTime(year, month)을 반환한다.
class YearMonthPickerSheet extends StatefulWidget {
  final int initialYear;
  final int initialMonth;

  const YearMonthPickerSheet({
    super.key,
    required this.initialYear,
    required this.initialMonth,
  });

  @override
  State<YearMonthPickerSheet> createState() => _YearMonthPickerSheetState();
}

class _YearMonthPickerSheetState extends State<YearMonthPickerSheet> {
  // 캘린더 화면의 TableCalendar(firstDay~lastDay) 범위와 동일하게 맞춘다.
  // 범위를 벗어나면 TableCalendar의 focusedDay 관련 assert에 걸려 크래시할 수 있다.
  static const int minYear = 2024;
  static const int maxYear = 2028;

  late int _year;
  late int _month;

  @override
  void initState() {
    super.initState();
    _year = widget.initialYear.clamp(minYear, maxYear);
    _month = widget.initialMonth;
  }

  @override
  Widget build(BuildContext context) {
    final years = List.generate(maxYear - minYear + 1, (i) => minYear + i);

    return SafeArea(
      top: false,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.cardGap),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                CupertinoButton(
                  padding: const EdgeInsets.symmetric(
                    horizontal: AppSpacing.cardGap,
                    vertical: 12,
                  ),
                  onPressed: () => Navigator.pop(context),
                  child: const Text(
                    '취소',
                    style: TextStyle(color: AppTheme.textSecondary),
                  ),
                ),
                const Text(
                  '연월 선택',
                  style: TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w700,
                    color: AppTheme.textPrimary,
                  ),
                ),
                CupertinoButton(
                  padding: const EdgeInsets.symmetric(
                    horizontal: AppSpacing.cardGap,
                    vertical: 12,
                  ),
                  onPressed: () =>
                      Navigator.pop(context, DateTime(_year, _month)),
                  child: const Text(
                    '완료',
                    style: TextStyle(
                      color: AppTheme.blue,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
              ],
            ),
          ),
          const Divider(height: 1, color: AppTheme.separator),
          SizedBox(
            height: 200,
            child: Row(
              children: [
                Expanded(
                  child: CupertinoPicker(
                    scrollController: FixedExtentScrollController(
                      initialItem: _year - minYear,
                    ),
                    itemExtent: 36,
                    onSelectedItemChanged: (index) =>
                        setState(() => _year = years[index]),
                    selectionOverlay: _pickerSelectionOverlay(),
                    children: years
                        .map(
                          (year) => Center(
                            child: Text(
                              '$year년',
                              style: const TextStyle(
                                fontSize: 18,
                                fontWeight: FontWeight.w600,
                                color: AppTheme.textPrimary,
                              ),
                            ),
                          ),
                        )
                        .toList(),
                  ),
                ),
                Expanded(
                  child: CupertinoPicker(
                    scrollController: FixedExtentScrollController(
                      initialItem: _month - 1,
                    ),
                    itemExtent: 36,
                    onSelectedItemChanged: (index) =>
                        setState(() => _month = index + 1),
                    selectionOverlay: _pickerSelectionOverlay(),
                    children: List.generate(
                      12,
                      (i) => Center(
                        child: Text(
                          '${i + 1}월',
                          style: const TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.w600,
                            color: AppTheme.textPrimary,
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _pickerSelectionOverlay() {
    return Container(
      decoration: BoxDecoration(
        color: AppTheme.blue.withValues(alpha: 0.08),
        border: const Border.symmetric(
          horizontal: BorderSide(color: AppTheme.separator),
        ),
      ),
    );
  }
}
