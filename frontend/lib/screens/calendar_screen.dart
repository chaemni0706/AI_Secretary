import 'dart:async';
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
import '../widgets/week_day_strip.dart';
import '../widgets/day_timeline_view.dart';
import '../widgets/year_month_picker_sheet.dart';
import '../models/schedule_model.dart';
import '../services/schedule_api.dart';
import '../services/dashboard_api.dart';
import '../services/api_client.dart';
import 'schedule_detail_screen.dart';
import 'schedule_form_screen.dart';

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

  // 주간 뷰 좌우 스와이프용 PageController. 기준 주(_weekAnchor)로부터의
  // 상대 주차를 큰 오프셋(_weekPageOffset)에서 시작해 양방향 스와이프를 흉내낸다.
  static const int _weekPageOffset = 6000;
  final PageController _weekPageController = PageController(
    initialPage: _weekPageOffset,
  );
  late final DateTime _weekAnchor;

  // 타임라인 탭이 보이는 동안에만 1분마다 현재 시각 표시선을 갱신한다.
  Timer? _nowTimer;

  @override
  void initState() {
    super.initState();
    _weekAnchor = _weekStart(DateTime.now());
    _loadSchedules();
    // 예약/AI챗 등에서 저장 후 triggerDashboardRefresh() 가 호출되면 캘린더도 갱신.
    dashboardRefresh.addListener(_loadSchedules);
  }

  @override
  void dispose() {
    dashboardRefresh.removeListener(_loadSchedules);
    _weekPageController.dispose();
    _nowTimer?.cancel();
    super.dispose();
  }

  void _setViewIndex(int index) {
    setState(() => _viewIndex = index);
    if (index == 2) {
      _nowTimer ??= Timer.periodic(const Duration(minutes: 1), (_) {
        if (mounted) setState(() {});
      });
    } else {
      _nowTimer?.cancel();
      _nowTimer = null;
    }
  }

  // 페이지 인덱스가 증가할수록 과거 주로 이동한다(부호 반전).
  // 표준 PageView 규약상 왼쪽 스와이프(오른쪽→왼쪽 드래그)가 다음 페이지(인덱스 증가)를
  // 보여주므로, 이 부호여야 "왼쪽 스와이프=저번 주, 오른쪽 스와이프=다음 주"가 된다.
  DateTime _weekStartForPage(int page) =>
      _weekAnchor.subtract(Duration(days: (page - _weekPageOffset) * 7));

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

  /// 선택 날짜와 schedule.date("YYYY-MM-DD") 문자열 비교로 필터링.
  List<ScheduleModel> _schedulesFor(DateTime day) {
    final key = _ymd(day);
    final list = _all.where((s) => s.date == key).toList();
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
    final memo = schedule.memo ?? '';
    final match = RegExp(
      r'(?:end_date|endDate|종료일)\s*[:=]\s*(\d{4}-\d{2}-\d{2})',
    ).firstMatch(memo);
    if (match == null) return startDate;
    try {
      final parsed = DateTime.parse(match.group(1)!);
      final end = DateTime(parsed.year, parsed.month, parsed.day);
      return end.isBefore(startDate) ? startDate : end;
    } catch (_) {
      return startDate;
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
        ),
      );
    }
    segments.sort((a, b) {
      final lengthCompare = b.daySpan.compareTo(a.daySpan);
      if (lengthCompare != 0) return lengthCompare;
      return (a.schedule.startTime ?? '').compareTo(b.schedule.startTime ?? '');
    });
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

  /// 주어진 주의 시작일(일요일)이 이번 주/지난 주/다음 주 중 무엇인지 라벨링.
  /// 스와이프로 다른 주를 볼 때도 "이번 주"로 고정 표시되던 문제를 해결한다.
  String _relativeWeekLabel(DateTime weekStart) {
    final thisWeekStart = _weekStart(DateTime.now());
    final diffWeeks = weekStart.difference(thisWeekStart).inDays ~/ 7;
    switch (diffWeeks) {
      case 0:
        return '이번 주';
      case -1:
        return '지난 주';
      case 1:
        return '다음 주';
      default:
        return '${weekStart.month}월 ${weekStart.day}일 주';
    }
  }

  List<ScheduleModel> _schedulesForSelectedWeek() {
    final start = _weekStart(_selectedDay);
    final end = start.add(const Duration(days: 7));
    final list = _all.where((schedule) {
      if (schedule.date == null) return false;
      try {
        final parsed = DateTime.parse(schedule.date!);
        final date = DateTime(parsed.year, parsed.month, parsed.day);
        return !date.isBefore(start) && date.isBefore(end);
      } catch (_) {
        return false;
      }
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

  void _openScheduleDetail(ScheduleModel schedule) {
    Navigator.push<Object>(
      context,
      MaterialPageRoute(
        builder: (_) => ScheduleDetailScreen(schedule: schedule),
      ),
    ).then((result) {
      if (result != null) _loadSchedules();
    });
  }

  Future<void> _openYearMonthPicker() async {
    final result = await showModalBottomSheet<DateTime>(
      context: context,
      backgroundColor: Colors.white,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(AppRadii.card)),
      ),
      builder: (_) => YearMonthPickerSheet(
        initialYear: _focusedDay.year,
        initialMonth: _focusedDay.month,
      ),
    );
    if (result == null || !mounted) return;
    final daysInMonth = DateUtils.getDaysInMonth(result.year, result.month);
    setState(() {
      _focusedDay = result;
      _selectedDay = DateTime(
        result.year,
        result.month,
        _selectedDay.day.clamp(1, daysInMonth),
      );
    });
  }

  Future<void> _openScheduleAdd() async {
    final saved = await Navigator.push<ScheduleModel>(
      context,
      MaterialPageRoute(
        builder: (_) => ScheduleFormScreen(initialDate: _ymd(_selectedDay)),
      ),
    );
    if (saved != null) _loadSchedules();
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
                        _buildWeekPager(),
                        _buildWeeklyCategoryList(),
                      ],
                      if (_viewIndex == 2) _buildDayTimeline(),
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
              onTap: _openYearMonthPicker,
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
    final labels = ['월간', '주간', '타임라인'];
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
                onTap: () => _setViewIndex(i),
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
    final segments = _monthEventSegmentsFor(day).take(2).toList();
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
          ...segments.map(
            (segment) => CalendarEventBar(
              title: segment.schedule.title,
              color: _monthEventColor(segment.schedule),
              startsOnThisDay: isSameDay(segment.start, segment.date),
              endsOnThisDay: isSameDay(segment.end, segment.date),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildWeekPager() {
    return SizedBox(
      height: WeekDayStrip.pageHeight,
      child: PageView.builder(
        controller: _weekPageController,
        onPageChanged: (page) {
          // 선택된 요일(오프셋)을 유지한 채 새 주로 이동한다.
          // (예: 수요일 선택 상태로 스와이프하면 다음 주도 수요일이 선택됨)
          final offset = _selectedDay.difference(_weekStart(_selectedDay)).inDays;
          setState(
            () => _selectedDay = _weekStartForPage(
              page,
            ).add(Duration(days: offset)),
          );
        },
        itemBuilder: (context, page) {
          final weekStart = _weekStartForPage(page);
          return WeekDayStrip(
            weekStart: weekStart,
            selectedDay: _selectedDay,
            hasEvent: _hasEvent,
            onDaySelected: (day) => setState(() => _selectedDay = day),
          );
        },
      ),
    );
  }

  Widget _buildDayTimeline() {
    final dateStr =
        '${_selectedDay.month}월 ${_selectedDay.day}일 ${_weekdayStr(_selectedDay.weekday)}';
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 8),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              GestureDetector(
                onTap: () => setState(
                  () => _selectedDay =
                      _selectedDay.subtract(const Duration(days: 1)),
                ),
                child: const Icon(
                  Icons.chevron_left,
                  color: AppTheme.textPrimary,
                  size: 24,
                ),
              ),
              Text(
                dateStr,
                style: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w700,
                  color: AppTheme.textPrimary,
                ),
              ),
              GestureDetector(
                onTap: () => setState(
                  () => _selectedDay = _selectedDay.add(const Duration(days: 1)),
                ),
                child: const Icon(
                  Icons.chevron_right,
                  color: AppTheme.textPrimary,
                  size: 24,
                ),
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
        else
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
            child: DayTimelineView(
              date: _selectedDay,
              schedules: _schedulesFor(_selectedDay),
              onScheduleTap: _openScheduleDetail,
            ),
          ),
      ],
    );
  }

  Widget _buildWeeklyCategoryList() {
    final grouped = _weekSchedulesByCategory();
    final total = grouped.values.fold<int>(0, (sum, list) => sum + list.length);
    final start = _weekStart(_selectedDay);
    final end = start.add(const Duration(days: 6));
    final rangeText = '${start.month}.${start.day} - ${end.month}.${end.day}';
    final weekLabel = _relativeWeekLabel(start);

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
                '$weekLabel 일정 $total',
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
              if (_loading)
                const SizedBox(
                  width: 18,
                  height: 18,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              else
                IconButton(
                  onPressed: _openScheduleAdd,
                  tooltip: '일정 추가',
                  icon: const Icon(Icons.add_circle_outline),
                  color: AppTheme.blue,
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

  const _MonthEventSegment({
    required this.schedule,
    required this.start,
    required this.end,
    required this.date,
  });

  int get daySpan => end.difference(start).inDays + 1;
}
