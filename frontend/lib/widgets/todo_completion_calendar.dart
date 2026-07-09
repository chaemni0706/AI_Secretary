import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../models/todo_model.dart';
import '../theme/app_constants.dart';
import '../theme/app_theme.dart';
import '../theme/todo_styles.dart';
import 'glass_card.dart';
import 'todo_card.dart';

class CompletionCategoryRingTrack {
  final String category;
  final Color color;
  final int total;
  final int completed;

  const CompletionCategoryRingTrack({
    required this.category,
    required this.color,
    required this.total,
    required this.completed,
  });

  double get progress => total == 0 ? 0 : completed / total;
}

class CompletionDayStats {
  final DateTime date;
  final int total;
  final int completed;
  final List<CompletionCategoryRingTrack> rings;

  const CompletionDayStats({
    required this.date,
    required this.total,
    required this.completed,
    required this.rings,
  });

  bool get hasTodos => total > 0;
  bool get hasCompleted => completed > 0;
}

class TodoCompletionMonthlyCalendar extends StatelessWidget {
  final DateTime focusedMonth;
  final DateTime? selectedDate;
  final Map<String, CompletionDayStats> statsByDate;
  final List<TodoModel> selectedTodos;
  final ValueChanged<DateTime> onMonthChanged;
  final ValueChanged<DateTime> onDateSelected;
  final ValueChanged<TodoModel> onToggleTodo;
  final ValueChanged<TodoModel> onTodoTap;

  const TodoCompletionMonthlyCalendar({
    super.key,
    required this.focusedMonth,
    required this.selectedDate,
    required this.statsByDate,
    required this.selectedTodos,
    required this.onMonthChanged,
    required this.onDateSelected,
    required this.onToggleTodo,
    required this.onTodoTap,
  });

  @override
  Widget build(BuildContext context) {
    final normalizedMonth = DateTime(focusedMonth.year, focusedMonth.month);
    final selected = selectedDate;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        CompletionCalendarHeader(
          month: normalizedMonth,
          onPrevious: () => onMonthChanged(
            DateTime(normalizedMonth.year, normalizedMonth.month - 1),
          ),
          onNext: () => onMonthChanged(
            DateTime(normalizedMonth.year, normalizedMonth.month + 1),
          ),
        ),
        CompletionCategoryLegend(),
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 10, 16, 0),
          child: GlassCard(
            padding: const EdgeInsets.all(10),
            child: Column(
              children: [
                _WeekdayHeader(),
                const SizedBox(height: 6),
                _MonthGrid(
                  month: normalizedMonth,
                  selectedDate: selected,
                  statsByDate: statsByDate,
                  onDateSelected: onDateSelected,
                ),
              ],
            ),
          ),
        ),
        SelectedDateCompletedTodoList(
          date: selected,
          todos: selectedTodos,
          onToggleTodo: onToggleTodo,
          onTodoTap: onTodoTap,
        ),
      ],
    );
  }
}

class CompletionCalendarHeader extends StatelessWidget {
  final DateTime month;
  final VoidCallback onPrevious;
  final VoidCallback onNext;

  const CompletionCalendarHeader({
    super.key,
    required this.month,
    required this.onPrevious,
    required this.onNext,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 0),
      child: Row(
        children: [
          IconButton(
            onPressed: onPrevious,
            icon: const Icon(Icons.chevron_left),
            color: AppTheme.textPrimary,
            tooltip: '이전 달',
          ),
          Expanded(
            child: Text(
              '${month.year}년 ${month.month}월',
              textAlign: TextAlign.center,
              style: AppTextStyles.sectionTitle.copyWith(
                color: AppTheme.textPrimary,
              ),
            ),
          ),
          IconButton(
            onPressed: onNext,
            icon: const Icon(Icons.chevron_right),
            color: AppTheme.textPrimary,
            tooltip: '다음 달',
          ),
        ],
      ),
    );
  }
}

class CompletionCategoryLegend extends StatelessWidget {
  const CompletionCategoryLegend({super.key});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 0),
      child: Wrap(
        spacing: 10,
        runSpacing: 7,
        children: TodoStyles.categoryOrder.map((category) {
          final color = TodoStyles.categoryColor(category);
          return Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 8,
                height: 8,
                decoration: BoxDecoration(color: color, shape: BoxShape.circle),
              ),
              const SizedBox(width: 5),
              Text(
                category,
                style: AppTextStyles.meta.copyWith(
                  color: AppTheme.textSecondary,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          );
        }).toList(),
      ),
    );
  }
}

class _WeekdayHeader extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    const weekdays = ['일', '월', '화', '수', '목', '금', '토'];
    return Row(
      children: List.generate(7, (index) {
        return Expanded(
          child: Text(
            weekdays[index],
            textAlign: TextAlign.center,
            style: AppTextStyles.meta.copyWith(
              color: index == 0
                  ? AppTheme.red
                  : index == 6
                  ? AppTheme.blue
                  : AppTheme.textSecondary,
              fontWeight: FontWeight.w700,
            ),
          ),
        );
      }),
    );
  }
}

class _MonthGrid extends StatelessWidget {
  final DateTime month;
  final DateTime? selectedDate;
  final Map<String, CompletionDayStats> statsByDate;
  final ValueChanged<DateTime> onDateSelected;

  const _MonthGrid({
    required this.month,
    required this.selectedDate,
    required this.statsByDate,
    required this.onDateSelected,
  });

  @override
  Widget build(BuildContext context) {
    final first = DateTime(month.year, month.month, 1);
    final daysInMonth = DateTime(month.year, month.month + 1, 0).day;
    final leading = first.weekday % 7;
    final cellCount = ((leading + daysInMonth + 6) ~/ 7) * 7;

    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      itemCount: cellCount,
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 7,
        childAspectRatio: 0.76,
      ),
      itemBuilder: (context, index) {
        final dayNumber = index - leading + 1;
        if (dayNumber < 1 || dayNumber > daysInMonth) {
          return const SizedBox.shrink();
        }
        final date = DateTime(month.year, month.month, dayNumber);
        final key = _key(date);
        return CompletionDayActivityRingCell(
          date: date,
          stats: statsByDate[key],
          selected: _sameDay(date, selectedDate),
          today: _sameDay(date, DateTime.now()),
          onTap: () => onDateSelected(date),
        );
      },
    );
  }
}

class CompletionDayActivityRingCell extends StatelessWidget {
  final DateTime date;
  final CompletionDayStats? stats;
  final bool selected;
  final bool today;
  final VoidCallback onTap;

  const CompletionDayActivityRingCell({
    super.key,
    required this.date,
    required this.stats,
    required this.selected,
    required this.today,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final segments = stats?.rings ?? const <CompletionCategoryRingTrack>[];

    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 160),
        margin: const EdgeInsets.all(2),
        padding: const EdgeInsets.symmetric(vertical: 5, horizontal: 2),
        decoration: BoxDecoration(
          color: selected
              ? AppTheme.blue.withValues(alpha: 0.1)
              : Colors.transparent,
          borderRadius: BorderRadius.circular(AppRadii.small),
          border: selected
              ? Border.all(color: AppTheme.blue.withValues(alpha: 0.34))
              : today
              ? Border.all(color: AppTheme.green.withValues(alpha: 0.36))
              : null,
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              '${date.day}',
              style: AppTextStyles.meta.copyWith(
                color: today ? AppTheme.green : AppTheme.textPrimary,
                fontWeight: today || selected
                    ? FontWeight.w800
                    : FontWeight.w600,
              ),
            ),
            const SizedBox(height: 3),
            CompletionDayDonutChart(
              segments: segments,
              emphasized: stats?.hasCompleted == true,
            ),
          ],
        ),
      ),
    );
  }
}

class CompletionDayDonutChart extends StatelessWidget {
  final List<CompletionCategoryRingTrack> segments;
  final bool emphasized;

  const CompletionDayDonutChart({
    super.key,
    required this.segments,
    required this.emphasized,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 42,
      height: 42,
      child: CustomPaint(
        painter: CompletionDonutChartPainter(
          segments: segments,
          emphasized: emphasized,
        ),
      ),
    );
  }
}

class CompletionDonutChartPainter extends CustomPainter {
  final List<CompletionCategoryRingTrack> segments;
  final bool emphasized;

  const CompletionDonutChartPainter({
    required this.segments,
    required this.emphasized,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final center = size.center(Offset.zero);
    final radius = size.shortestSide / 2 - 5;
    const strokeWidth = 8.0;
    const startAngle = -math.pi / 2;
    const segmentGap = 0.045;
    final rect = Rect.fromCircle(center: center, radius: radius);
    final completedSegments = segments
        .where((segment) => segment.completed > 0)
        .toList(growable: false);
    final completedTotal = completedSegments.fold<int>(
      0,
      (sum, segment) => sum + segment.completed,
    );

    final trackPaint = Paint()
      ..color = AppTheme.separator.withValues(alpha: emphasized ? 0.9 : 0.62)
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth
      ..strokeCap = StrokeCap.round;

    canvas.drawArc(rect, 0, math.pi * 2, false, trackPaint);

    if (completedTotal == 0) return;

    var cursor = startAngle;
    for (var i = 0; i < completedSegments.length; i++) {
      final segment = completedSegments[i];
      final rawSweep = math.pi * 2 * (segment.completed / completedTotal);
      final gap = completedSegments.length == 1 ? 0.0 : segmentGap;
      final sweep = math.max(0.0, rawSweep - gap);
      final progressPaint = Paint()
        ..color = segment.color.withValues(alpha: emphasized ? 1.0 : 0.72)
        ..style = PaintingStyle.stroke
        ..strokeWidth = strokeWidth
        ..strokeCap = completedSegments.length == 1
            ? StrokeCap.round
            : StrokeCap.butt;
      if (sweep > 0) {
        canvas.drawArc(rect, cursor, sweep, false, progressPaint);
      }
      cursor += rawSweep;
    }
  }

  @override
  bool shouldRepaint(covariant CompletionDonutChartPainter oldDelegate) {
    return oldDelegate.segments != segments ||
        oldDelegate.emphasized != emphasized;
  }
}

class SelectedDateCompletedTodoList extends StatelessWidget {
  final DateTime? date;
  final List<TodoModel> todos;
  final ValueChanged<TodoModel> onToggleTodo;
  final ValueChanged<TodoModel> onTodoTap;

  const SelectedDateCompletedTodoList({
    super.key,
    required this.date,
    required this.todos,
    required this.onToggleTodo,
    required this.onTodoTap,
  });

  @override
  Widget build(BuildContext context) {
    if (date == null) return const SizedBox.shrink();
    final completed = todos.where((todo) => todo.completed).toList();
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(4, 0, 4, 8),
            child: Text(
              '${date!.month}월 ${date!.day}일 완료한 할 일',
              style: AppTextStyles.sectionTitle.copyWith(
                color: AppTheme.textPrimary,
              ),
            ),
          ),
          if (completed.isEmpty)
            const GlassCard(
              padding: EdgeInsets.symmetric(horizontal: 16, vertical: 18),
              child: Text(
                '이 날짜에 완료한 할 일이 없습니다.',
                style: TextStyle(fontSize: 13, color: AppTheme.textSecondary),
              ),
            )
          else
            ...completed.map(
              (todo) => TodoCard(
                todo: todo,
                compact: true,
                onToggle: () => onToggleTodo(todo),
                onTap: () => onTodoTap(todo),
              ),
            ),
        ],
      ),
    );
  }
}

String _key(DateTime date) {
  final month = date.month.toString().padLeft(2, '0');
  final day = date.day.toString().padLeft(2, '0');
  return '${date.year}-$month-$day';
}

bool _sameDay(DateTime a, DateTime? b) {
  return b != null && a.year == b.year && a.month == b.month && a.day == b.day;
}
