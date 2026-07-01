import 'package:flutter/material.dart';
import 'package:table_calendar/table_calendar.dart';
import '../theme/app_theme.dart';
import '../widgets/glass_card.dart';
import '../models/schedule_model.dart';
import '../services/schedule_api.dart';
import '../services/dashboard_api.dart';
import '../services/api_client.dart';

class CalendarScreen extends StatefulWidget {
  const CalendarScreen({super.key});

  @override
  State<CalendarScreen> createState() => _CalendarScreenState();
}

class _CalendarScreenState extends State<CalendarScreen> {
  DateTime _focusedDay = DateTime.now();
  DateTime _selectedDay = DateTime.now();
  int _viewIndex = 0; // 0=월간, 1=주간, 2=타임라인

  bool _loading = true;
  String? _error;
  List<ScheduleModel> _all = [];

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

  int _hourOf(String? hhmm) {
    if (hhmm == null || !hhmm.contains(':')) return -1;
    return int.tryParse(hhmm.split(':')[0]) ?? -1;
  }

  Color _colorFor(String? category) {
    switch (category) {
      case 'hospital':
        return AppTheme.teal;
      case 'meeting':
      case 'work':
        return AppTheme.blue;
      case 'study':
        return AppTheme.purple;
      case 'meal':
      case 'beauty':
        return AppTheme.orange;
      case 'exercise':
        return AppTheme.green;
      default:
        return AppTheme.blue;
    }
  }

  IconData _iconFor(String? category) {
    switch (category) {
      case 'hospital':
        return Icons.local_hospital_outlined;
      case 'study':
        return Icons.book_outlined;
      case 'meeting':
      case 'work':
        return Icons.work_outline;
      case 'meal':
        return Icons.restaurant_outlined;
      case 'beauty':
        return Icons.content_cut_outlined;
      case 'exercise':
        return Icons.fitness_center_outlined;
      default:
        return Icons.event_outlined;
    }
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
                      if (_viewIndex == 1) _buildWeekView(),
                      if (_viewIndex == 2) _buildTimelineView(),
                      _buildDaySchedule(),
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
                _focusedDay =
                    DateTime(_focusedDay.year, _focusedDay.month - 1);
              });
            },
            child: const Icon(Icons.chevron_left,
                color: AppTheme.textPrimary, size: 26),
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
                  const Icon(Icons.expand_more,
                      color: AppTheme.textSecondary, size: 20),
                ],
              ),
            ),
          ),
          GestureDetector(
            onTap: () {
              setState(() {
                _focusedDay =
                    DateTime(_focusedDay.year, _focusedDay.month + 1);
              });
            },
            child: const Icon(Icons.chevron_right,
                color: AppTheme.textPrimary, size: 26),
          ),
          const SizedBox(width: 8),
          GestureDetector(
            onTap: _loading ? null : _loadSchedules,
            child: Container(
              width: 36,
              height: 36,
              decoration: BoxDecoration(
                color: AppTheme.blue.withOpacity(0.12),
                borderRadius: BorderRadius.circular(10),
              ),
              child: const Icon(Icons.refresh, color: AppTheme.blue, size: 20),
            ),
          ),
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
                            )
                          ]
                        : null,
                  ),
                  child: Text(
                    labels[i],
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      fontSize: 13,
                      fontWeight:
                          isActive ? FontWeight.w600 : FontWeight.w400,
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
          eventLoader: (day) => _hasEvent(day) ? [true] : [],
          headerVisible: false,
          daysOfWeekHeight: 28,
          rowHeight: 44,
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

  Widget _buildWeekView() {
    final weekStart =
        _selectedDay.subtract(Duration(days: _selectedDay.weekday % 7));
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

  Widget _buildTimelineView() {
    final daySchedules = _schedulesFor(_selectedDay);
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 10, 16, 0),
      child: GlassCard(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('타임라인',
                style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.textPrimary)),
            const SizedBox(height: 12),
            ...List.generate(12, (i) {
              final hour = 8 + i;
              ScheduleModel? ev;
              for (final s in daySchedules) {
                if (_hourOf(s.startTime) == hour) {
                  ev = s;
                  break;
                }
              }
              return Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  SizedBox(
                    width: 40,
                    child: Text(
                      '$hour:00',
                      style: const TextStyle(
                        fontSize: 11,
                        color: AppTheme.textSecondary,
                      ),
                    ),
                  ),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Container(height: 1, color: AppTheme.separator),
                        if (ev != null)
                          Container(
                            margin: const EdgeInsets.only(top: 2, bottom: 2),
                            padding: const EdgeInsets.symmetric(
                                horizontal: 8, vertical: 4),
                            decoration: BoxDecoration(
                              color: _colorFor(ev.category).withOpacity(0.15),
                              borderRadius: BorderRadius.circular(6),
                            ),
                            child: Text(
                              ev.title,
                              style: TextStyle(
                                fontSize: 12,
                                color: _colorFor(ev.category),
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          )
                        else
                          const SizedBox(height: 28),
                      ],
                    ),
                  ),
                ],
              );
            }),
          ],
        ),
      ),
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
          ...daySchedules.map(_scheduleCard),
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
            const Icon(Icons.cloud_off,
                color: AppTheme.textSecondary, size: 32),
            const SizedBox(height: 10),
            Text(
              _error ?? '일정을 불러오지 못했습니다.',
              textAlign: TextAlign.center,
              style:
                  const TextStyle(fontSize: 14, color: AppTheme.textPrimary),
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

  Widget _scheduleCard(ScheduleModel s) {
    final color = _colorFor(s.category);
    final timeText = s.startTime == null
        ? '시간 미정'
        : (s.endTime != null ? '${s.startTime} – ${s.endTime}' : s.startTime!);
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
      child: GlassCard(
        padding: const EdgeInsets.all(14),
        child: Row(
          children: [
            Container(
              width: 4,
              height: 44,
              decoration: BoxDecoration(
                color: color,
                borderRadius: BorderRadius.circular(4),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(s.title,
                      style: const TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                        color: AppTheme.textPrimary,
                      )),
                  const SizedBox(height: 3),
                  Row(
                    children: [
                      Text(timeText,
                          style: const TextStyle(
                            fontSize: 12,
                            color: AppTheme.textSecondary,
                          )),
                      if (s.category != null) ...[
                        const Text(' · ',
                            style: TextStyle(
                                color: AppTheme.textSecondary, fontSize: 12)),
                        PillBadge(label: s.category!, color: color),
                      ],
                    ],
                  ),
                  if (s.location != null && s.location!.isNotEmpty) ...[
                    const SizedBox(height: 3),
                    Row(
                      children: [
                        const Icon(Icons.place_outlined,
                            size: 12, color: AppTheme.textSecondary),
                        const SizedBox(width: 3),
                        Text(s.location!,
                            style: const TextStyle(
                              fontSize: 12,
                              color: AppTheme.textSecondary,
                            )),
                      ],
                    ),
                  ],
                ],
              ),
            ),
            Icon(_iconFor(s.category), color: color.withOpacity(0.6), size: 20),
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
