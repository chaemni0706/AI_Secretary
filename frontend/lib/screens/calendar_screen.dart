import 'package:flutter/material.dart';
import 'package:table_calendar/table_calendar.dart';
import '../theme/app_constants.dart';
import '../theme/app_theme.dart';
import '../theme/schedule_styles.dart';
import '../widgets/glass_card.dart';
import '../widgets/app_top_actions.dart';
import '../widgets/calendar_event_bar.dart';
import '../widgets/category_schedule_section.dart';
import '../widgets/schedule_card.dart';
import '../models/schedule_model.dart';
import '../services/schedule_api.dart';
import '../services/dashboard_api.dart';
import '../services/api_client.dart';
import 'schedule_detail_screen.dart';
import 'schedule_add_screen.dart';

class CalendarScreen extends StatefulWidget {
  const CalendarScreen({super.key});

  @override
  State<CalendarScreen> createState() => _CalendarScreenState();
}

class _CalendarScreenState extends State<CalendarScreen> {
  DateTime _focusedDay = DateTime.now();
  DateTime _selectedDay = DateTime.now();
  int _viewIndex = 0; // 0=월간, 1=주간

  bool _loading = true;
  String? _error;
  List<ScheduleModel> _all = [];

  /// schedule.id → 고정 행(lane) 인덱스. 기간 일정이 여러 날에 걸쳐도 같은 행에
  /// 놓이도록 월 전체 기준으로 한 번 배정한다(구간 스케줄링).
  final Map<String, int> _laneOf = {};

  @override
  void initState() {
    super.initState();
    _loadSchedules();
    // 예약/AI챗 등에서 저장 후 triggerDashboardRefresh() 가 호출되면 캘린더도 갱신.
    dashboardRefresh.addListener(_loadSchedules);
  }

  @override
  void dispose() {
    dashboardRefresh.removeListener(_loadSchedules);
    super.dispose();
  }

  Future<void> _loadSchedules() async {
    if (mounted) {
      setState(() {
        _loading = true;
        _error = null;
      });
    }
    try {
      // 전체 일정 조회 (프론트에서 날짜별 필터링).
      final schedules = await scheduleApi.list();
      if (!mounted) return;
      setState(() {
        _all = schedules;
        _assignLanes();
        _loading = false;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.message;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = '일정을 불러오지 못했습니다. ($e)';
        _loading = false;
      });
    }
  }

  // ---- 날짜 유틸 ------------------------------------------------------------

  static String _two(int n) => n.toString().padLeft(2, '0');

  String _ymd(DateTime d) => '${d.year}-${_two(d.month)}-${_two(d.day)}';

  /// 해당 날짜에 걸치는 일정. 기간 일정(시작~종료)은 중간·마지막 날에도 포함한다.
  List<ScheduleModel> _schedulesFor(DateTime day) {
    final date = DateTime(day.year, day.month, day.day);
    final list = _all.where((s) {
      final start = _dateFromSchedule(s);
      if (start == null) return false;
      final end = _endDateFor(s, start);
      return !date.isBefore(start) && !date.isAfter(end);
    }).toList();
    list.sort((a, b) => (a.startTime ?? '').compareTo(b.startTime ?? ''));
    return list;
  }

  bool _hasEvent(DateTime day) => _schedulesFor(day).isNotEmpty;

  DateTime? _dateFromSchedule(ScheduleModel schedule) {
    final raw = schedule.date;
    if (raw == null) return null;
    try {
      final parsed = DateTime.parse(raw);
      return DateTime(parsed.year, parsed.month, parsed.day);
    } catch (_) {
      return null;
    }
  }

  DateTime _endDateFor(ScheduleModel schedule, DateTime startDate) {
    // 종료일은 모델의 effectiveEndDate(서버 end_date → memo 규칙 순)로 통일한다.
    final raw = schedule.effectiveEndDate;
    if (raw == null) return startDate;
    try {
      final parsed = DateTime.parse(raw);
      final end = DateTime(parsed.year, parsed.month, parsed.day);
      return end.isBefore(startDate) ? startDate : end;
    } catch (_) {
      return startDate;
    }
  }

  /// 월 전체 기준으로 각 일정에 고정 lane(행)을 배정한다. 시작일 오름차순 +
  /// 기간(긴 것) 우선으로 정렬한 뒤, 겹치지 않는 가장 낮은 행을 재사용한다.
  /// → 같은 일정은 모든 날에서 같은 행에 그려져 기간 바가 끊기지 않는다.
  void _assignLanes() {
    _laneOf.clear();
    final items = <List<Object>>[]; // [id, start, end, span]
    for (final s in _all) {
      final start = _dateFromSchedule(s);
      if (start == null) continue;
      final end = _endDateFor(s, start);
      items.add([s.id, start, end, end.difference(start).inDays]);
    }
    items.sort((a, b) {
      final c = (a[1] as DateTime).compareTo(b[1] as DateTime); // 시작일 asc
      if (c != 0) return c;
      return (b[3] as int).compareTo(a[3] as int); // 기간 긴 것 먼저
    });
    final laneEnd = <DateTime>[]; // lane → 마지막 점유 종료일
    for (final it in items) {
      final start = it[1] as DateTime;
      final end = it[2] as DateTime;
      int lane = -1;
      for (var i = 0; i < laneEnd.length; i++) {
        if (laneEnd[i].isBefore(start)) {
          lane = i;
          break;
        }
      }
      if (lane == -1) {
        lane = laneEnd.length;
        laneEnd.add(end);
      } else {
        laneEnd[lane] = end;
      }
      _laneOf[it[0] as String] = lane;
    }
  }

  List<_MonthEventSegment> _monthEventSegmentsFor(DateTime day) {
    final date = DateTime(day.year, day.month, day.day);
    final segments = <_MonthEventSegment>[];
    for (final schedule in _all) {
      final start = _dateFromSchedule(schedule);
      if (start == null) continue;
      final end = _endDateFor(schedule, start);
      if (date.isBefore(start) || date.isAfter(end)) continue;
      segments.add(
        _MonthEventSegment(
          schedule: schedule,
          start: start,
          end: end,
          date: date,
          lane: _laneOf[schedule.id] ?? 0,
        ),
      );
    }
    segments.sort((a, b) => a.lane.compareTo(b.lane));
    return segments;
  }

  Color _monthEventColor(ScheduleModel schedule) {
    final category = schedule.category?.trim();
    if (category == null || category.isEmpty) return AppTheme.blue;
    final color = ScheduleStyles.categoryColor(category);
    return color == AppTheme.textSecondary ? AppTheme.blue : color;
  }

  DateTime _weekStart(DateTime day) {
    return DateTime(
      day.year,
      day.month,
      day.day,
    ).subtract(Duration(days: day.weekday % 7));
  }

  List<ScheduleModel> _schedulesForSelectedWeek() {
    final start = _weekStart(_selectedDay);
    final end = start.add(const Duration(days: 7)); // 주의 끝(exclusive)
    final list = _all.where((schedule) {
      final sStart = _dateFromSchedule(schedule);
      if (sStart == null) return false;
      final sEnd = _endDateFor(schedule, sStart);
      // 기간이 이번 주와 겹치면 포함(시작이 주 이전이어도 걸치면 표시).
      return sStart.isBefore(end) && !sEnd.isBefore(start);
    }).toList();

    list.sort((a, b) {
      final dateCompare = (a.date ?? '').compareTo(b.date ?? '');
      if (dateCompare != 0) return dateCompare;
      return (a.startTime ?? '').compareTo(b.startTime ?? '');
    });
    return list;
  }

  Map<String, List<ScheduleModel>> _weekSchedulesByCategory() {
    final grouped = {
      for (final label in ScheduleStyles.categoryOrder)
        label: <ScheduleModel>[],
    };

    for (final schedule in _schedulesForSelectedWeek()) {
      final label = ScheduleStyles.categoryLabel(schedule.category);
      final key = grouped.containsKey(label) ? label : '기타';
      grouped[key]!.add(schedule);
    }
    return grouped;
  }

  Future<void> _openAddSchedule() async {
    final saved = await Navigator.push<ScheduleModel>(
      context,
      MaterialPageRoute(
        builder: (_) => ScheduleAddScreen(initialDate: _ymd(_selectedDay)),
      ),
    );
    if (saved != null) _loadSchedules(); // 새 일정 즉시 반영
  }

  void _openScheduleDetail(ScheduleModel schedule) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => ScheduleDetailScreen(schedule: schedule),
      ),
    );
  }

  // ---- build ---------------------------------------------------------------

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: AppTheme.screenBackground,
      child: SafeArea(
        child: Column(
          children: [
            _buildHeader(),
            _buildViewSwitcher(),
            Expanded(
              child: RefreshIndicator(
                onRefresh: _loadSchedules,
                child: SingleChildScrollView(
                  physics: const AlwaysScrollableScrollPhysics(
                    parent: BouncingScrollPhysics(),
                  ),
                  child: Column(
                    children: [
                      if (_viewIndex == 0) _buildMonthCalendar(),
                      if (_viewIndex == 0) _buildDaySchedule(),
                      if (_viewIndex == 1) ...[
                        _buildWeekView(),
                        _buildWeeklyCategoryList(),
                      ],
                      const SizedBox(height: 80),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 4),
      child: Row(
        children: [
          GestureDetector(
            onTap: () {
              setState(() {
                _focusedDay = DateTime(_focusedDay.year, _focusedDay.month - 1);
              });
            },
            child: const Icon(
              Icons.chevron_left,
              color: AppTheme.textPrimary,
              size: 26,
            ),
          ),
          const SizedBox(width: 4),
          Expanded(
            child: GestureDetector(
              onTap: () {},
              child: Row(
                children: [
                  Text(
                    '${_focusedDay.year}년 ${_focusedDay.month}월',
                    style: const TextStyle(
                      fontSize: 22,
                      fontWeight: FontWeight.w700,
                      color: AppTheme.textPrimary,
                      letterSpacing: -0.4,
                    ),
                  ),
                  const SizedBox(width: 4),
                  const Icon(
                    Icons.expand_more,
                    color: AppTheme.textSecondary,
                    size: 20,
                  ),
                ],
              ),
            ),
          ),
          GestureDetector(
            onTap: () {
              setState(() {
                _focusedDay = DateTime(_focusedDay.year, _focusedDay.month + 1);
              });
            },
            child: const Icon(
              Icons.chevron_right,
              color: AppTheme.textPrimary,
              size: 26,
            ),
          ),
          const SizedBox(width: 10),
          const AppTopActions(),
        ],
      ),
    );
  }

  Widget _buildViewSwitcher() {
    final labels = ['월간', '주간'];
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
      child: Container(
        decoration: BoxDecoration(
          color: Colors.white.withOpacity(0.55),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppTheme.separator.withOpacity(0.6)),
        ),
        padding: const EdgeInsets.all(3),
        child: Row(
          children: List.generate(labels.length, (i) {
            final isActive = i == _viewIndex;
            return Expanded(
              child: GestureDetector(
                onTap: () => setState(() => _viewIndex = i),
                child: Container(
                  padding: const EdgeInsets.symmetric(vertical: 8),
                  decoration: BoxDecoration(
                    color: isActive ? Colors.white : Colors.transparent,
                    borderRadius: BorderRadius.circular(10),
                    boxShadow: isActive
                        ? [
                            BoxShadow(
                              color: Colors.black.withOpacity(0.06),
                              blurRadius: 6,
                              offset: const Offset(0, 2),
                            ),
                          ]
                        : null,
                  ),
                  child: Text(
                    labels[i],
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      fontSize: 13,
                      fontWeight: isActive ? FontWeight.w600 : FontWeight.w400,
                      color: isActive
                          ? AppTheme.textPrimary
                          : AppTheme.textSecondary,
                    ),
                  ),
                ),
              ),
            );
          }),
        ),
      ),
    );
  }

  Widget _buildMonthCalendar() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 10, 16, 0),
      child: GlassCard(
        padding: const EdgeInsets.all(8),
        child: TableCalendar(
          firstDay: DateTime.utc(2024, 1, 1),
          lastDay: DateTime.utc(2028, 12, 31),
          focusedDay: _focusedDay,
          calendarFormat: CalendarFormat.month,
          availableCalendarFormats: const {CalendarFormat.month: ''},
          selectedDayPredicate: (day) => isSameDay(_selectedDay, day),
          onDaySelected: (selected, focused) {
            setState(() {
              _selectedDay = selected;
              _focusedDay = focused;
            });
          },
          // 실제 API 일정이 있는 날짜에 marker 표시.
          eventLoader: (_) => const [],
          headerVisible: false,
          daysOfWeekHeight: 28,
          rowHeight: 68,
          calendarBuilders: CalendarBuilders(
            defaultBuilder: (context, day, focusedDay) =>
                _buildMonthDayCell(day),
            todayBuilder: (context, day, focusedDay) =>
                _buildMonthDayCell(day, isToday: true),
            selectedBuilder: (context, day, focusedDay) =>
                _buildMonthDayCell(day, isSelected: true),
            outsideBuilder: (context, day, focusedDay) =>
                _buildMonthDayCell(day, isOutside: true),
          ),
          calendarStyle: CalendarStyle(
            todayDecoration: BoxDecoration(
              color: AppTheme.blue.withOpacity(0.2),
              shape: BoxShape.circle,
            ),
            todayTextStyle: const TextStyle(
              color: AppTheme.blue,
              fontWeight: FontWeight.w700,
            ),
            selectedDecoration: const BoxDecoration(
              color: AppTheme.blue,
              shape: BoxShape.circle,
            ),
            selectedTextStyle: const TextStyle(
              color: Colors.white,
              fontWeight: FontWeight.w700,
            ),
            defaultTextStyle: const TextStyle(
              color: AppTheme.textPrimary,
              fontSize: 14,
              fontWeight: FontWeight.w500,
            ),
            weekendTextStyle: const TextStyle(
              color: AppTheme.red,
              fontSize: 14,
              fontWeight: FontWeight.w500,
            ),
            outsideTextStyle: TextStyle(
              color: AppTheme.textSecondary.withOpacity(0.5),
              fontSize: 14,
            ),
            markerDecoration: const BoxDecoration(
              color: AppTheme.blue,
              shape: BoxShape.circle,
            ),
            markerSize: 5,
            markersMaxCount: 1,
            cellMargin: const EdgeInsets.all(4),
          ),
          daysOfWeekStyle: const DaysOfWeekStyle(
            weekdayStyle: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: AppTheme.textSecondary,
            ),
            weekendStyle: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: AppTheme.red,
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildMonthDayCell(
    DateTime day, {
    bool isToday = false,
    bool isSelected = false,
    bool isOutside = false,
  }) {
    final segments = _monthEventSegmentsFor(day);
    const maxLanes = 2; // 셀에 표시할 최대 행 수(초과분은 +N)
    var maxLane = -1;
    var hidden = 0;
    for (final s in segments) {
      if (s.lane > maxLane) maxLane = s.lane;
      if (s.lane >= maxLanes) hidden++;
    }
    final visibleLanes = (maxLane + 1) > maxLanes ? maxLanes : (maxLane + 1);
    _MonthEventSegment? laneSeg(int r) {
      for (final s in segments) {
        if (s.lane == r) return s;
      }
      return null;
    }

    final textColor = isOutside
        ? AppTheme.textSecondary.withValues(alpha: 0.5)
        : isSelected
        ? Colors.white
        : isToday
        ? AppTheme.blue
        : AppTheme.textPrimary;

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 1, vertical: 2),
      padding: const EdgeInsets.fromLTRB(2, 2, 2, 1),
      decoration: BoxDecoration(
        color: isSelected ? AppTheme.blue : Colors.transparent,
        borderRadius: BorderRadius.circular(10),
        border: isToday && !isSelected
            ? Border.all(color: AppTheme.blue.withValues(alpha: 0.6))
            : null,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Align(
            alignment: Alignment.topCenter,
            child: Text(
              '${day.day}',
              style: TextStyle(
                color: textColor,
                fontSize: 12,
                fontWeight: isSelected || isToday
                    ? FontWeight.w800
                    : FontWeight.w600,
              ),
            ),
          ),
          const SizedBox(height: 1),
          // lane별 고정 배치: 해당 행에 일정이 있으면 바, 없으면 빈 자리(정렬 유지).
          for (int r = 0; r < visibleLanes; r++)
            laneSeg(r) != null
                ? CalendarEventBar(
                    title: laneSeg(r)!.schedule.title,
                    color: _monthEventColor(laneSeg(r)!.schedule),
                    startsOnThisDay:
                        isSameDay(laneSeg(r)!.start, laneSeg(r)!.date),
                    endsOnThisDay: isSameDay(laneSeg(r)!.end, laneSeg(r)!.date),
                  )
                : const SizedBox(height: 18),
          if (hidden > 0)
            Padding(
              padding: const EdgeInsets.only(top: 1),
              child: Text(
                '+$hidden',
                style: const TextStyle(
                    fontSize: 9,
                    fontWeight: FontWeight.w700,
                    color: AppTheme.textSecondary),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildWeekView() {
    final weekStart = _weekStart(_selectedDay);
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 10, 16, 0),
      child: GlassCard(
        padding: const EdgeInsets.all(12),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceAround,
          children: List.generate(7, (i) {
            final day = weekStart.add(Duration(days: i));
            final isSelected = isSameDay(day, _selectedDay);
            final isToday = isSameDay(day, DateTime.now());
            final hasEvent = _hasEvent(day);
            final dayNames = ['일', '월', '화', '수', '목', '금', '토'];
            return GestureDetector(
              onTap: () => setState(() => _selectedDay = day),
              child: Column(
                children: [
                  Text(
                    dayNames[i],
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color: i == 0
                          ? AppTheme.red
                          : (i == 6 ? AppTheme.blue : AppTheme.textSecondary),
                    ),
                  ),
                  const SizedBox(height: 6),
                  Container(
                    width: 36,
                    height: 36,
                    decoration: BoxDecoration(
                      color: isSelected ? AppTheme.blue : Colors.transparent,
                      shape: BoxShape.circle,
                      border: isToday && !isSelected
                          ? Border.all(color: AppTheme.blue, width: 1.5)
                          : null,
                    ),
                    child: Center(
                      child: Text(
                        '${day.day}',
                        style: TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.w600,
                          color: isSelected
                              ? Colors.white
                              : AppTheme.textPrimary,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 4),
                  Container(
                    width: 5,
                    height: 5,
                    decoration: BoxDecoration(
                      color: hasEvent ? AppTheme.blue : Colors.transparent,
                      shape: BoxShape.circle,
                    ),
                  ),
                ],
              ),
            );
          }),
        ),
      ),
    );
  }

  Widget _buildWeeklyCategoryList() {
    final grouped = _weekSchedulesByCategory();
    final total = grouped.values.fold<int>(0, (sum, list) => sum + list.length);
    final start = _weekStart(_selectedDay);
    final end = start.add(const Duration(days: 6));
    final rangeText = '${start.month}.${start.day} - ${end.month}.${end.day}';

    if (_loading && _all.isEmpty) {
      return const Padding(
        padding: EdgeInsets.only(top: 24),
        child: Center(child: CircularProgressIndicator()),
      );
    }

    if (_error != null) return _buildError();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 8),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                '이번 주 일정 $total',
                style: AppTextStyles.sectionTitle.copyWith(
                  color: AppTheme.textPrimary,
                ),
              ),
              Text(
                rangeText,
                style: AppTextStyles.meta.copyWith(
                  color: AppTheme.textSecondary,
                ),
              ),
            ],
          ),
        ),
        if (total == 0)
          const Padding(
            padding: EdgeInsets.fromLTRB(16, 0, 16, 8),
            child: GlassCard(
              padding: EdgeInsets.symmetric(horizontal: 16, vertical: 18),
              child: Text(
                '이번 주에 등록된 일정이 없습니다.',
                style: TextStyle(fontSize: 13, color: AppTheme.textSecondary),
              ),
            ),
          )
        else
          ...ScheduleStyles.categoryOrder.map(
            (category) => CategoryScheduleSection(
              title: category,
              schedules: grouped[category] ?? const [],
              onScheduleTap: _openScheduleDetail,
            ),
          ),
      ],
    );
  }

  Widget _buildDaySchedule() {
    final dateStr =
        '${_selectedDay.month}월 ${_selectedDay.day}일 ${_weekdayStr(_selectedDay.weekday)}';
    final daySchedules = _schedulesFor(_selectedDay);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 8),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                '$dateStr 일정 ${daySchedules.length}',
                style: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w700,
                  color: AppTheme.textPrimary,
                ),
              ),
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  if (_loading)
                    const Padding(
                      padding: EdgeInsets.only(right: 8),
                      child: SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      ),
                    ),
                  TextButton.icon(
                    onPressed: _openAddSchedule,
                    icon: const Icon(Icons.add, size: 18),
                    label: const Text('일정 추가'),
                    style: TextButton.styleFrom(
                      foregroundColor: AppTheme.blue,
                      padding: const EdgeInsets.symmetric(horizontal: 8),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
        if (_loading && _all.isEmpty)
          const Padding(
            padding: EdgeInsets.only(top: 24),
            child: Center(child: CircularProgressIndicator()),
          )
        else if (_error != null)
          _buildError()
        else if (daySchedules.isEmpty)
          const Padding(
            padding: EdgeInsets.fromLTRB(16, 0, 16, 8),
            child: GlassCard(
              padding: EdgeInsets.symmetric(horizontal: 16, vertical: 18),
              child: Text(
                '이 날짜에 등록된 일정이 없습니다.',
                style: TextStyle(fontSize: 13, color: AppTheme.textSecondary),
              ),
            ),
          )
        else
          ...daySchedules.map(
            (schedule) => ScheduleCard(
              schedule: schedule,
              onTap: () => _openScheduleDetail(schedule),
            ),
          ),
      ],
    );
  }

  Widget _buildError() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
      child: GlassCard(
        padding: const EdgeInsets.all(20),
        child: Column(
          children: [
            const Icon(
              Icons.cloud_off,
              color: AppTheme.textSecondary,
              size: 32,
            ),
            const SizedBox(height: 10),
            Text(
              _error ?? '일정을 불러오지 못했습니다.',
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 14, color: AppTheme.textPrimary),
            ),
            const SizedBox(height: 4),
            const Text(
              '백엔드 서버가 실행 중인지 확인하세요.',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
            ),
            const SizedBox(height: 12),
            FilledButton(
              onPressed: _loadSchedules,
              style: FilledButton.styleFrom(backgroundColor: AppTheme.blue),
              child: const Text('다시 시도'),
            ),
          ],
        ),
      ),
    );
  }

  String _weekdayStr(int weekday) {
    const days = ['', '월', '화', '수', '목', '금', '토', '일'];
    return '${days[weekday]}요일';
  }
}

class _MonthEventSegment {
  final ScheduleModel schedule;
  final DateTime start;
  final DateTime end;
  final DateTime date;

  /// 월 전체에서 고정된 행 인덱스(모든 날에서 동일 → 기간 바가 끊기지 않고 이어짐).
  final int lane;

  const _MonthEventSegment({
    required this.schedule,
    required this.start,
    required this.end,
    required this.date,
    this.lane = 0,
  });

  int get daySpan => end.difference(start).inDays + 1;
}
