import 'package:flutter/material.dart';
import '../models/schedule_model.dart';
import '../theme/app_theme.dart';
import '../theme/schedule_styles.dart';
import 'glass_card.dart';
import 'schedule_card.dart';

/// 하루 단위 시간표(00~23시, 1시간 간격) 위젯.
/// 시작 시각이 있는 일정은 시간대 위에 블록으로, 시작 시각이 없는 일정은
/// 상단 "시간 미정" 목록에 별도로 표시한다. 오늘 날짜인 경우에만 현재
/// 시각 표시선을 그린다.
class DayTimelineView extends StatelessWidget {
  final DateTime date;
  final List<ScheduleModel> schedules;
  final ValueChanged<ScheduleModel> onScheduleTap;

  const DayTimelineView({
    super.key,
    required this.date,
    required this.schedules,
    required this.onScheduleTap,
  });

  static const double hourHeight = 64;
  static const double _labelColumnWidth = 44;
  static const double _minBlockHeight = 22;

  /// 제목+시간 두 줄을 모두 표시해도 여유 있게 들어가는 최소 블록 높이.
  /// 이보다 낮으면 시간 텍스트를 숨기고 제목만 표시해 overflow를 피한다.
  static const double _twoLineThreshold = 44;

  bool get _isToday {
    final now = DateTime.now();
    return now.year == date.year &&
        now.month == date.month &&
        now.day == date.day;
  }

  int? _minutesOf(String? hhmm) {
    if (hhmm == null || hhmm.isEmpty) return null;
    final parts = hhmm.split(':');
    if (parts.length != 2) return null;
    final h = int.tryParse(parts[0]);
    final m = int.tryParse(parts[1]);
    if (h == null || m == null) return null;
    return h * 60 + m;
  }

  @override
  Widget build(BuildContext context) {
    final timed = <ScheduleModel>[];
    final untimed = <ScheduleModel>[];
    for (final schedule in schedules) {
      if (_minutesOf(schedule.startTime) != null) {
        timed.add(schedule);
      } else {
        untimed.add(schedule);
      }
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (untimed.isNotEmpty) ...[
          const Padding(
            padding: EdgeInsets.only(bottom: 4),
            child: Text(
              '시간 미정',
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: AppTheme.textSecondary,
              ),
            ),
          ),
          ...untimed.map(
            (schedule) => ScheduleCard(
              schedule: schedule,
              onTap: () => onScheduleTap(schedule),
            ),
          ),
          const SizedBox(height: 8),
        ],
        GlassCard(
          padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 4),
          child: SizedBox(
            height: hourHeight * 24,
            child: Stack(
              children: [
                Column(
                  children: List.generate(
                    24,
                    (hour) => SizedBox(
                      height: hourHeight,
                      child: _TimelineHourRow(hour: hour),
                    ),
                  ),
                ),
                ...timed.map(_buildScheduleBlock),
                if (_isToday) _buildNowIndicator(),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildScheduleBlock(ScheduleModel schedule) {
    final startMinutes = _minutesOf(schedule.startTime)!;
    final endMinutes = _minutesOf(schedule.endTime);
    final durationMinutes = (endMinutes != null && endMinutes > startMinutes)
        ? endMinutes - startMinutes
        : 30;
    final top = startMinutes / 60 * hourHeight;
    final height = (durationMinutes / 60 * hourHeight).clamp(
      _minBlockHeight,
      double.infinity,
    );
    final color = ScheduleStyles.categoryColor(schedule.category);
    final showTimeText = height >= _twoLineThreshold;

    return Positioned(
      left: _labelColumnWidth + 8,
      right: 8,
      top: top,
      height: height,
      child: GestureDetector(
        onTap: () => onScheduleTap(schedule),
        child: Container(
          padding: EdgeInsets.symmetric(
            horizontal: 8,
            vertical: showTimeText ? 4 : 2,
          ),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.16),
            borderRadius: BorderRadius.circular(8),
            border: Border(left: BorderSide(color: color, width: 3)),
          ),
          alignment: Alignment.topLeft,
          child: ClipRect(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  schedule.title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                    color: color,
                  ),
                ),
                if (showTimeText)
                  Text(
                    ScheduleStyles.timeText(
                      schedule.startTime,
                      schedule.endTime,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      fontSize: 10,
                      color: AppTheme.textSecondary,
                    ),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildNowIndicator() {
    final now = DateTime.now();
    final top = (now.hour * 60 + now.minute) / 60 * hourHeight;
    return Positioned(
      left: _labelColumnWidth - 4,
      right: 0,
      top: top - 4,
      child: Row(
        children: [
          Container(
            width: 8,
            height: 8,
            decoration: const BoxDecoration(
              color: AppTheme.red,
              shape: BoxShape.circle,
            ),
          ),
          Expanded(child: Container(height: 1.5, color: AppTheme.red)),
        ],
      ),
    );
  }
}

class _TimelineHourRow extends StatelessWidget {
  final int hour;

  const _TimelineHourRow({required this.hour});

  @override
  Widget build(BuildContext context) {
    return Stack(
      clipBehavior: Clip.none,
      children: [
        Positioned(
          top: 0,
          left: DayTimelineView._labelColumnWidth,
          right: 0,
          child: Container(height: 1, color: AppTheme.separator),
        ),
        Positioned(
          top: -7,
          left: 0,
          width: DayTimelineView._labelColumnWidth,
          child: Text(
            '${hour.toString().padLeft(2, '0')}:00',
            textAlign: TextAlign.center,
            style: const TextStyle(fontSize: 10, color: AppTheme.textSecondary),
          ),
        ),
      ],
    );
  }
}
