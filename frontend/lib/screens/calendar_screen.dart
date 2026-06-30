import 'package:flutter/material.dart';
import 'package:table_calendar/table_calendar.dart';
import '../theme/app_theme.dart';
import '../widgets/glass_card.dart';

class CalendarScreen extends StatefulWidget {
  const CalendarScreen({super.key});

  @override
  State<CalendarScreen> createState() => _CalendarScreenState();
}

class _CalendarScreenState extends State<CalendarScreen> {
  DateTime _focusedDay = DateTime(2026, 6, 29);
  DateTime _selectedDay = DateTime(2026, 6, 29);
  int _viewIndex = 0; // 0=월간, 1=주간, 2=타임라인

  static final _eventDays = {
    DateTime(2026, 6, 23),
    DateTime(2026, 6, 24),
    DateTime(2026, 6, 25),
    DateTime(2026, 6, 26),
    DateTime(2026, 6, 29),
    DateTime(2026, 6, 30),
    DateTime(2026, 7, 1),
    DateTime(2026, 7, 3),
  };

  static const _scheduleForDay = [
    _CalEvent('09:30 – 10:30', '발표 자료 최종 확인', '업무', AppTheme.blue,
        Icons.work_outline),
    _CalEvent('11:00 – 11:30', '병원 예약 확인 전화', '병원', AppTheme.teal,
        Icons.local_hospital_outlined),
    _CalEvent('19:00 – 21:00', '저녁 약속', '약속', AppTheme.orange,
        Icons.restaurant_outlined),
  ];

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
              child: SingleChildScrollView(
                physics: const BouncingScrollPhysics(),
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
                _focusedDay = DateTime(
                    _focusedDay.year, _focusedDay.month - 1);
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
                _focusedDay = DateTime(
                    _focusedDay.year, _focusedDay.month + 1);
              });
            },
            child: const Icon(Icons.chevron_right,
                color: AppTheme.textPrimary, size: 26),
          ),
          const SizedBox(width: 8),
          GestureDetector(
            onTap: () {},
            child: Container(
              width: 36,
              height: 36,
              decoration: BoxDecoration(
                color: AppTheme.blue.withOpacity(0.12),
                borderRadius: BorderRadius.circular(10),
              ),
              child: const Icon(Icons.add, color: AppTheme.blue, size: 20),
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
                      fontWeight: isActive
                          ? FontWeight.w600
                          : FontWeight.w400,
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
          eventLoader: (day) =>
              _eventDays.any((d) => isSameDay(d, day)) ? [true] : [],
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
            final hasEvent =
                _eventDays.any((d) => isSameDay(d, day));
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
                      color: hasEvent
                          ? AppTheme.blue
                          : Colors.transparent,
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
              final hasEvent = _scheduleForDay
                  .any((e) => int.parse(e.time.split(':')[0]) == hour);
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
                        Container(
                          height: 1,
                          color: AppTheme.separator,
                        ),
                        if (hasEvent)
                          Container(
                            margin: const EdgeInsets.only(top: 2, bottom: 2),
                            padding: const EdgeInsets.symmetric(
                                horizontal: 8, vertical: 4),
                            decoration: BoxDecoration(
                              color: AppTheme.blue.withOpacity(0.15),
                              borderRadius: BorderRadius.circular(6),
                            ),
                            child: Text(
                              _scheduleForDay
                                  .firstWhere((e) =>
                                      int.parse(e.time.split(':')[0]) ==
                                      hour)
                                  .title,
                              style: const TextStyle(
                                fontSize: 12,
                                color: AppTheme.blue,
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
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 8),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                '$dateStr 일정 ${_scheduleForDay.length}',
                style: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w700,
                  color: AppTheme.textPrimary,
                ),
              ),
              const Icon(Icons.umbrella_outlined,
                  color: AppTheme.blue, size: 20),
            ],
          ),
        ),
        ...List.generate(_scheduleForDay.length, (i) {
          final ev = _scheduleForDay[i];
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
                      color: ev.color,
                      borderRadius: BorderRadius.circular(4),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(ev.title,
                            style: const TextStyle(
                              fontSize: 14,
                              fontWeight: FontWeight.w600,
                              color: AppTheme.textPrimary,
                            )),
                        const SizedBox(height: 3),
                        Row(
                          children: [
                            Text(ev.time,
                                style: const TextStyle(
                                  fontSize: 12,
                                  color: AppTheme.textSecondary,
                                )),
                            const Text(' · ',
                                style: TextStyle(
                                    color: AppTheme.textSecondary,
                                    fontSize: 12)),
                            PillBadge(
                                label: ev.category, color: ev.color),
                          ],
                        ),
                      ],
                    ),
                  ),
                  Icon(ev.icon, color: ev.color.withOpacity(0.6), size: 20),
                ],
              ),
            ),
          );
        }),
      ],
    );
  }

  String _weekdayStr(int weekday) {
    const days = ['', '월', '화', '수', '목', '금', '토', '일'];
    return '${days[weekday]}요일';
  }
}

class _CalEvent {
  final String time;
  final String title;
  final String category;
  final Color color;
  final IconData icon;

  const _CalEvent(
      this.time, this.title, this.category, this.color, this.icon);
}
