import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../core/theme/app_colors.dart';
import '../../core/theme/app_dimens.dart';
import '../../core/utils/responsive_utils.dart';

// ─────────────────────────────────────────────────────────────
//  임시 mock 모델 (다음 단계에서 data/models 로 분리 예정)
// ─────────────────────────────────────────────────────────────

class _DayMarker {
  const _DayMarker({this.hasSchedule = false, this.hasTodo = false});
  final bool hasSchedule; // 파란 점
  final bool hasTodo; // 초록 점
}

class _ScheduleItem {
  const _ScheduleItem({
    required this.time,
    required this.title,
    required this.color,
  });
  final String time;
  final String title;
  final Color color;
}

class CalendarScreen extends StatefulWidget {
  const CalendarScreen({super.key});

  @override
  State<CalendarScreen> createState() => _CalendarScreenState();
}

class _CalendarScreenState extends State<CalendarScreen> {
  // 2026년 6월 고정
  static const int _year = 2026;
  static const int _month = 6;

  int _selectedDay = 17;

  // ── mock: 날짜별 점 표시 ──
  static const Map<int, _DayMarker> _markers = {
    1: _DayMarker(hasSchedule: true),
    2: _DayMarker(hasTodo: true),
    3: _DayMarker(hasSchedule: true, hasTodo: true),
    4: _DayMarker(hasSchedule: true),
    6: _DayMarker(hasSchedule: true),
    8: _DayMarker(hasTodo: true),
    9: _DayMarker(hasSchedule: true),
    10: _DayMarker(hasTodo: true),
    11: _DayMarker(hasSchedule: true, hasTodo: true),
    12: _DayMarker(hasSchedule: true),
    14: _DayMarker(hasSchedule: true),
    15: _DayMarker(hasTodo: true),
    16: _DayMarker(hasSchedule: true),
    17: _DayMarker(hasSchedule: true, hasTodo: true),
    18: _DayMarker(hasTodo: true),
    19: _DayMarker(hasSchedule: true),
    20: _DayMarker(hasSchedule: true),
    21: _DayMarker(hasTodo: true),
    22: _DayMarker(hasSchedule: true),
    23: _DayMarker(hasTodo: true),
    24: _DayMarker(hasSchedule: true, hasTodo: true),
    25: _DayMarker(hasTodo: true),
    26: _DayMarker(hasSchedule: true),
    27: _DayMarker(hasSchedule: true),
    28: _DayMarker(hasTodo: true),
    29: _DayMarker(hasTodo: true),
    30: _DayMarker(hasSchedule: true),
  };

  // ── mock: 날짜별 일정 리스트 (17일만 채움) ──
  static const Map<int, List<_ScheduleItem>> _schedules = {
    17: [
      _ScheduleItem(
        time: '09:30',
        title: '팀 주간 회의',
        color: AppColors.categoryMeeting,
      ),
      _ScheduleItem(
        time: '11:00',
        title: '병원 진료 예약',
        color: AppColors.categoryMedical,
      ),
      _ScheduleItem(
        time: '14:00',
        title: 'AI 스터디 세션',
        color: AppColors.categoryMeeting,
      ),
    ],
  };

  List<_ScheduleItem> get _selectedSchedules =>
      _schedules[_selectedDay] ?? const [];

  @override
  Widget build(BuildContext context) {
    final bottomPadding = ResponsiveUtils.tabBottomPadding(context);

    return Scaffold(
      body: SafeArea(
        bottom: false, // 하단 인셋은 스크롤 padding 으로 직접 처리
        child: SingleChildScrollView(
          padding: EdgeInsets.fromLTRB(
            AppDimens.screenPadding,
            AppDimens.screenPadding,
            AppDimens.screenPadding,
            bottomPadding,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _buildHeader(context),
              const SizedBox(height: AppDimens.lg),
              _buildCalendarCard(context),
              const SizedBox(height: AppDimens.lg),
              _buildScheduleCard(context),
            ],
          ),
        ),
      ),
    );
  }

  // ── 상단 타이틀 ──
  Widget _buildHeader(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('캘린더', style: textTheme.headlineLarge),
        const SizedBox(height: AppDimens.xs),
        Text(
          '$_year년 $_month월',
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: textTheme.titleMedium?.copyWith(
            color: AppColors.textSecondary,
          ),
        ),
      ],
    );
  }

  // ── 월간 캘린더 카드 ──
  Widget _buildCalendarCard(BuildContext context) {
    return _SoftCard(
      child: Column(
        children: [
          _buildWeekdayRow(),
          const SizedBox(height: AppDimens.sm),
          _buildDayGrid(context),
          const SizedBox(height: AppDimens.md),
          _buildLegend(context),
        ],
      ),
    );
  }

  // 요일 헤더 (일~토)
  Widget _buildWeekdayRow() {
    const labels = ['일', '월', '화', '수', '목', '금', '토'];
    return Row(
      children: List.generate(7, (i) {
        final color = i == 0
            ? AppColors.priorityHigh // 일요일 빨강
            : (i == 6 ? AppColors.primary : AppColors.textSecondary); // 토요일 파랑
        return Expanded(
          child: Center(
            child: Text(
              labels[i],
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w600,
                color: color,
              ),
            ),
          ),
        );
      }),
    );
  }

  // 날짜 그리드 — LayoutBuilder 로 한 칸 폭을 구해 모든 치수를 비례 계산
  Widget _buildDayGrid(BuildContext context) {
    // 2026-06-01 의 요일 (DateTime.weekday: 월=1 ... 일=7)
    final firstWeekday = DateTime(_year, _month, 1).weekday;
    final leadingEmpty = firstWeekday % 7; // 일요일 시작 그리드로 변환
    final daysInMonth = DateTime(_year, _month + 1, 0).day; // 6월 = 30

    final totalCells = leadingEmpty + daysInMonth;
    final rows = (totalCells / 7).ceil(); // 5주 또는 6주

    return LayoutBuilder(
      builder: (context, constraints) {
        final cellWidth = constraints.maxWidth / 7;
        // 한 칸 높이는 폭에 비례(살짝 세로로 여유). 6주 달도 안전한 비율.
        final cellHeight = cellWidth * 1.15;

        // 숫자 원/점 크기를 셀 폭 기반으로 계산 (320px 에서도 겹치지 않게 상한)
        final circleSize = math.min(cellWidth * 0.78, 40.0);
        final numberFont = math.min(cellWidth * 0.34, 16.0);
        final dotSize = math.min(cellWidth * 0.11, 5.0);
        final dotGap = dotSize * 0.6;

        return Column(
          children: List.generate(rows, (row) {
            return Row(
              children: List.generate(7, (col) {
                final cellIndex = row * 7 + col;
                final day = cellIndex - leadingEmpty + 1;
                if (day < 1 || day > daysInMonth) {
                  return SizedBox(width: cellWidth, height: cellHeight);
                }
                return _DayCell(
                  width: cellWidth,
                  height: cellHeight,
                  circleSize: circleSize,
                  numberFont: numberFont,
                  dotSize: dotSize,
                  dotGap: dotGap,
                  day: day,
                  isSunday: col == 0,
                  isSelected: day == _selectedDay,
                  marker: _markers[day] ?? const _DayMarker(),
                  onTap: () => setState(() => _selectedDay = day),
                );
              }),
            );
          }),
        );
      },
    );
  }

  // 범례 (일정 / 할 일)
  Widget _buildLegend(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    Widget item(Color color, String label) {
      return Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          ),
          const SizedBox(width: AppDimens.xs),
          Text(
            label,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: textTheme.bodyMedium,
          ),
        ],
      );
    }

    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        item(AppColors.primary, '일정'),
        const SizedBox(width: AppDimens.lg),
        item(AppColors.priorityLow, '할 일'),
      ],
    );
  }

  // ── 선택 날짜 일정 카드 ──
  Widget _buildScheduleCard(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    final schedules = _selectedSchedules;

    return _SoftCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(
                Icons.calendar_today_outlined,
                size: 20,
                color: AppColors.primary,
              ),
              const SizedBox(width: AppDimens.sm),
              Expanded(
                child: Text(
                  '선택한 날짜 일정',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: textTheme.titleMedium,
                ),
              ),
              Text(
                '${schedules.length}개 일정',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: textTheme.bodyMedium?.copyWith(
                  color: AppColors.textSecondary,
                ),
              ),
              const SizedBox(width: AppDimens.xs),
              const Icon(
                Icons.chevron_right,
                size: 20,
                color: AppColors.textSecondary,
              ),
            ],
          ),
          const SizedBox(height: AppDimens.md),
          if (schedules.isEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: AppDimens.lg),
              child: Center(
                child: Text(
                  '선택한 날짜에 일정이 없어요.',
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: textTheme.bodyMedium,
                ),
              ),
            )
          else
            ...List.generate(schedules.length, (i) {
              final isLast = i == schedules.length - 1;
              return Padding(
                padding: EdgeInsets.only(
                  bottom: isLast ? 0 : AppDimens.md,
                ),
                child: _ScheduleRow(item: schedules[i]),
              );
            }),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────
//  내부 위젯
// ─────────────────────────────────────────────────────────────

class _SoftCard extends StatelessWidget {
  const _SoftCard({required this.child});
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppDimens.lg),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(AppDimens.radiusCard),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 16,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: child,
    );
  }
}

/// 날짜 한 칸 (숫자 원 + 점 표시 + 선택 강조) — 모든 치수 비례 주입
class _DayCell extends StatelessWidget {
  const _DayCell({
    required this.width,
    required this.height,
    required this.circleSize,
    required this.numberFont,
    required this.dotSize,
    required this.dotGap,
    required this.day,
    required this.isSunday,
    required this.isSelected,
    required this.marker,
    required this.onTap,
  });

  final double width;
  final double height;
  final double circleSize;
  final double numberFont;
  final double dotSize;
  final double dotGap;
  final int day;
  final bool isSunday;
  final bool isSelected;
  final _DayMarker marker;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final numberColor = isSelected
        ? AppColors.onPrimary
        : (isSunday ? AppColors.priorityHigh : AppColors.textPrimary);

    return SizedBox(
      width: width,
      height: height,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(AppDimens.radiusFull),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: circleSize,
              height: circleSize,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: isSelected ? AppColors.primary : Colors.transparent,
                shape: BoxShape.circle,
              ),
              child: Text(
                '$day',
                maxLines: 1,
                overflow: TextOverflow.clip,
                style: TextStyle(
                  fontSize: numberFont,
                  fontWeight: isSelected ? FontWeight.bold : FontWeight.w500,
                  color: numberColor,
                ),
              ),
            ),
            SizedBox(height: dotGap),
            _buildDots(),
          ],
        ),
      ),
    );
  }

  Widget _buildDots() {
    final dots = <Widget>[];
    if (marker.hasSchedule) dots.add(_dot(AppColors.primary));
    if (marker.hasTodo) dots.add(_dot(AppColors.priorityLow));

    if (dots.isEmpty) {
      return SizedBox(height: dotSize); // 점 없는 날도 높이 일관 유지
    }
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      mainAxisSize: MainAxisSize.min,
      children: [
        for (int i = 0; i < dots.length; i++) ...[
          if (i > 0) SizedBox(width: dotGap),
          dots[i],
        ],
      ],
    );
  }

  Widget _dot(Color color) {
    return Container(
      width: dotSize,
      height: dotSize,
      decoration: BoxDecoration(color: color, shape: BoxShape.circle),
    );
  }
}

/// 일정 카드의 한 줄 (컬러 점 + 시간 + 제목) — 시간 고정폭 제거
class _ScheduleRow extends StatelessWidget {
  const _ScheduleRow({required this.item});
  final _ScheduleItem item;

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        Container(
          width: 10,
          height: 10,
          decoration: BoxDecoration(color: item.color, shape: BoxShape.circle),
        ),
        const SizedBox(width: AppDimens.md),
        // 시간: 고정폭 대신 내용 크기 (짧고 일정한 "09:30")
        Text(
          item.time,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: textTheme.titleMedium?.copyWith(
            fontWeight: FontWeight.w600,
          ),
        ),
        const SizedBox(width: AppDimens.md),
        // 제목: 남는 폭 차지 + 길면 말줄임
        Expanded(
          child: Text(
            item.title,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: textTheme.bodyLarge,
          ),
        ),
      ],
    );
  }
}