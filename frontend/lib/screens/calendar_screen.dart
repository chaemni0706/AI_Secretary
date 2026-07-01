import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../widgets/glass_card.dart';

class CalendarScreen extends StatefulWidget {
  const CalendarScreen({super.key});

  @override
  State<CalendarScreen> createState() => _CalendarScreenState();
}

class _CalendarScreenState extends State<CalendarScreen> {
  DateTime _focusedDay = DateTime(2026, 6, 30);
  DateTime _selectedDay = DateTime(2026, 6, 30);
  int _viewIndex = 0; // 0=월간, 1=타임라인
  final Set<int> _checkedTodos = {};

  // ── Continuous Timeline ──
  static final _tlStart = DateTime(2026, 4, 30);
  static final _tlEnd   = DateTime(2026, 12, 28);
  static final _today   = DateTime(2026, 6, 30);
  static const _dayW    = 76.0;
  static const _tlH     = 340.0;
  static const _monthH  = 22.0;
  static const _dateH   = 50.0;
  static const _cardH   = 32.0;

  late final ScrollController _tlScroll;

  // ── 월간 달력 이벤트 막대 ──
  static final _monthEvents = [
    _MonthEvent('발표 자료 최종 확인',
        DateTime(2026, 6, 29), DateTime(2026, 6, 30), AppTheme.blue),
    _MonthEvent('병원 예약 확인 전화',
        DateTime(2026, 6, 30), DateTime(2026, 6, 30), AppTheme.teal),
    _MonthEvent('저녁 약속',
        DateTime(2026, 7, 1), DateTime(2026, 7, 1), AppTheme.orange),
    _MonthEvent('AI 스터디',
        DateTime(2026, 7, 2), DateTime(2026, 7, 3), AppTheme.purple),
    _MonthEvent('팀 회의',
        DateTime(2026, 7, 5), DateTime(2026, 7, 5), AppTheme.green),
  ];

  // ── 타임라인 일정 ──
  static final _tlItems = [
    _TLEvent('발표 자료 최종 확인',
        DateTime(2026, 6, 29), DateTime(2026, 6, 30), AppTheme.blue),
    _TLEvent('병원 예약 확인 전화',
        DateTime(2026, 6, 30), DateTime(2026, 6, 30), AppTheme.teal),
    _TLEvent('저녁 약속',
        DateTime(2026, 7, 1), DateTime(2026, 7, 1), AppTheme.orange),
    _TLEvent('AI 스터디',
        DateTime(2026, 7, 2), DateTime(2026, 7, 3), AppTheme.purple),
    _TLEvent('팀 회의',
        DateTime(2026, 7, 5), DateTime(2026, 7, 5), AppTheme.green),
  ];

  // ── 선택된 날 일정·할일 ──
  static const _dayEvents = [
    _CalEvent('09:30', '10:30', '발표 자료 최종 확인', '업무',
        AppTheme.blue, Icons.work_outline),
    _CalEvent('11:00', '11:30', '병원 예약 확인 전화', '병원',
        AppTheme.teal, Icons.local_hospital_outlined),
    _CalEvent('19:00', '21:00', '저녁 약속', '약속',
        AppTheme.orange, Icons.restaurant_outlined),
  ];
  static const _dayTodos = [
    '발표 자료 최종 확인', '병원 진료비 영수증 챙기기', 'AI 스터디 노트 준비'
  ];

  @override
  void initState() {
    super.initState();
    final daysToToday = _today.difference(_tlStart).inDays;
    final initialOffset =
        (daysToToday * _dayW - 100.0).clamp(0.0, double.infinity);
    _tlScroll = ScrollController(initialScrollOffset: initialOffset);
  }

  @override
  void dispose() {
    _tlScroll.dispose();
    super.dispose();
  }

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
                    if (_viewIndex == 1) _buildContinuousTimeline(),
                    _buildDayScheduleAndTodos(),
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

  // ─── 헤더 ───────────────────────────────
  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 4),
      child: Row(
        children: [
          GestureDetector(
            onTap: () => setState(() =>
                _focusedDay =
                    DateTime(_focusedDay.year, _focusedDay.month - 1)),
            child: const Icon(Icons.chevron_left,
                color: AppTheme.textPrimary, size: 26),
          ),
          const SizedBox(width: 4),
          Expanded(
            child: Row(
              children: [
                Text(
                  '${_focusedDay.year}년 ${_focusedDay.month}월',
                  style: const TextStyle(
                      fontSize: 22,
                      fontWeight: FontWeight.w700,
                      color: AppTheme.textPrimary,
                      letterSpacing: -0.4),
                ),
                const SizedBox(width: 4),
                const Icon(Icons.expand_more,
                    color: AppTheme.textSecondary, size: 20),
              ],
            ),
          ),
          GestureDetector(
            onTap: () => setState(() =>
                _focusedDay =
                    DateTime(_focusedDay.year, _focusedDay.month + 1)),
            child: const Icon(Icons.chevron_right,
                color: AppTheme.textPrimary, size: 26),
          ),
          const SizedBox(width: 8),
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              color: AppTheme.blue.withOpacity(0.12),
              borderRadius: BorderRadius.circular(10),
            ),
            child: const Icon(Icons.add, color: AppTheme.blue, size: 20),
          ),
        ],
      ),
    );
  }

  // ─── 뷰 전환기 ──────────────────────────
  Widget _buildViewSwitcher() {
    final labels = ['월간', '타임라인'];
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
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 200),
                  padding: const EdgeInsets.symmetric(vertical: 8),
                  decoration: BoxDecoration(
                    color: isActive ? Colors.white : Colors.transparent,
                    borderRadius: BorderRadius.circular(10),
                    boxShadow: isActive
                        ? [
                            BoxShadow(
                                color: Colors.black.withOpacity(0.06),
                                blurRadius: 6,
                                offset: const Offset(0, 2))
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

  // ─── 월간 달력 (커스텀 그리드 + 이벤트 막대) ──
  Widget _buildMonthCalendar() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 10, 16, 0),
      child: LayoutBuilder(
        builder: (context, constraints) {
          final cellW = constraints.maxWidth / 7;
          final weeks = _weeksOf(_focusedDay.year, _focusedDay.month);

          return GlassCard(
            padding: EdgeInsets.zero,
            child: Column(
              children: [
                // 요일 헤더
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 8),
                  child: Row(
                    children: ['일', '월', '화', '수', '목', '금', '토']
                        .asMap()
                        .entries
                        .map((e) => SizedBox(
                              width: cellW,
                              child: Center(
                                child: Text(
                                  e.value,
                                  style: TextStyle(
                                    fontSize: 12,
                                    fontWeight: FontWeight.w700,
                                    color: e.key == 0
                                        ? AppTheme.red
                                        : e.key == 6
                                            ? AppTheme.blue
                                            : AppTheme.textSecondary,
                                  ),
                                ),
                              ),
                            ))
                        .toList(),
                  ),
                ),
                Container(height: 1, color: AppTheme.separator),
                // 주 행들
                ...weeks
                    .map((week) => _buildWeekRow(week, cellW))
                    .toList(),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _buildWeekRow(List<DateTime> week, double cellW) {
    final weekStart = week.first;
    final weekEnd = week.last;
    final currentMonth = _focusedDay.month;

    final weekEvents = _monthEvents.where((ev) {
      return !(ev.end.isBefore(weekStart) || ev.start.isAfter(weekEnd));
    }).toList();

    final lanes = _assignLanes(weekEvents, weekStart, weekEnd);
    final numLanes =
        lanes.isEmpty ? 0 : lanes.values.reduce((a, b) => a > b ? a : b) + 1;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // 날짜 숫자 행
        Row(
          children: week.map((day) {
            final isCurrentMonth = day.month == currentMonth;
            final isToday = _sameDay(day, _today);
            final isSelected = _sameDay(day, _selectedDay);
            final isSun = day.weekday == 7;
            final isSat = day.weekday == 6;

            Color textColor;
            if (!isCurrentMonth) {
              textColor = AppTheme.textSecondary.withOpacity(0.3);
            } else if (isSun) {
              textColor = AppTheme.red;
            } else if (isSat) {
              textColor = AppTheme.blue;
            } else {
              textColor = AppTheme.textPrimary;
            }

            return GestureDetector(
              onTap: () => setState(() => _selectedDay = day),
              child: SizedBox(
                width: cellW,
                height: 36,
                child: Center(
                  child: Container(
                    width: 28,
                    height: 28,
                    decoration: BoxDecoration(
                      color: isToday
                          ? AppTheme.red
                          : isSelected
                              ? AppTheme.blue
                              : Colors.transparent,
                      shape: BoxShape.circle,
                    ),
                    child: Center(
                      child: Text(
                        '${day.day}',
                        style: TextStyle(
                          fontSize: 13,
                          fontWeight: (isToday || isSelected)
                              ? FontWeight.w700
                              : FontWeight.w500,
                          color: (isToday || isSelected)
                              ? Colors.white
                              : textColor,
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            );
          }).toList(),
        ),

        // 이벤트 막대 (최대 3개 lane)
        ...List.generate(numLanes.clamp(0, 3), (lane) {
          final laneEvs =
              weekEvents.where((ev) => lanes[ev] == lane).toList();
          if (laneEvs.isEmpty) return const SizedBox(height: 20);
          final ev = laneEvs.first;

          final barStart =
              ev.start.isBefore(weekStart) ? weekStart : ev.start;
          final barEnd = ev.end.isAfter(weekEnd) ? weekEnd : ev.end;
          final startCol = barStart.difference(weekStart).inDays;
          final endCol = barEnd.difference(weekStart).inDays;
          final barWidth = (endCol - startCol + 1) * cellW;

          final continuesLeft = ev.start.isBefore(weekStart);
          final continuesRight = ev.end.isAfter(weekEnd);

          return Padding(
            padding: const EdgeInsets.only(bottom: 2),
            child: Row(
              children: [
                SizedBox(width: startCol * cellW),
                SizedBox(
                  width: barWidth,
                  height: 18,
                  child: Container(
                    decoration: BoxDecoration(
                      color: ev.color,
                      borderRadius: BorderRadius.horizontal(
                        left: continuesLeft
                            ? Radius.zero
                            : const Radius.circular(4),
                        right: continuesRight
                            ? Radius.zero
                            : const Radius.circular(4),
                      ),
                    ),
                    padding: const EdgeInsets.only(left: 5),
                    alignment: Alignment.centerLeft,
                    child: Text(
                      ev.title,
                      style: const TextStyle(
                        fontSize: 10,
                        color: Colors.white,
                        fontWeight: FontWeight.w600,
                      ),
                      overflow: TextOverflow.ellipsis,
                      maxLines: 1,
                    ),
                  ),
                ),
              ],
            ),
          );
        }),

        // 빈 주간 최소 여백
        if (numLanes == 0) const SizedBox(height: 4),

        Container(height: 1, color: AppTheme.separator.withOpacity(0.4)),
      ],
    );
  }

  Map<_MonthEvent, int> _assignLanes(
      List<_MonthEvent> events, DateTime weekStart, DateTime weekEnd) {
    final lanes = <_MonthEvent, int>{};
    for (final ev in events) {
      final evStart = ev.start.isBefore(weekStart) ? weekStart : ev.start;
      final evEnd = ev.end.isAfter(weekEnd) ? weekEnd : ev.end;
      final startCol = evStart.difference(weekStart).inDays;
      final endCol = evEnd.difference(weekStart).inDays;

      int lane = 0;
      while (lane < 3) {
        final conflict =
            lanes.entries.where((e) => e.value == lane).any((e) {
          final eStart =
              e.key.start.isBefore(weekStart) ? weekStart : e.key.start;
          final eEnd = e.key.end.isAfter(weekEnd) ? weekEnd : e.key.end;
          final eStartCol = eStart.difference(weekStart).inDays;
          final eEndCol = eEnd.difference(weekStart).inDays;
          return !(endCol < eStartCol || startCol > eEndCol);
        });
        if (!conflict) break;
        lane++;
      }
      lanes[ev] = lane;
    }
    return lanes;
  }

  List<List<DateTime>> _weeksOf(int year, int month) {
    final firstDay = DateTime(year, month, 1);
    final lastDay = DateTime(year, month + 1, 0);
    // 일요일부터 시작하도록 오프셋 (Dart: 1=Mon..7=Sun)
    final startOffset = firstDay.weekday % 7; // 0=Sun, 1=Mon, ..., 6=Sat
    final gridStart = firstDay.subtract(Duration(days: startOffset));

    final weeks = <List<DateTime>>[];
    var current = gridStart;
    while (!current.isAfter(lastDay)) {
      weeks.add(List.generate(7, (i) => current.add(Duration(days: i))));
      current = current.add(const Duration(days: 7));
    }
    return weeks;
  }

  // ─── Continuous Horizontal Timeline ────
  Widget _buildContinuousTimeline() {
    final totalDays = _tlEnd.difference(_tlStart).inDays + 1;
    final totalWidth = totalDays * _dayW;
    const headerH = _monthH + _dateH;

    final placed = _placedEvents();

    return SizedBox(
      height: _tlH,
      child: SingleChildScrollView(
        controller: _tlScroll,
        scrollDirection: Axis.horizontal,
        physics: const BouncingScrollPhysics(),
        child: SizedBox(
          width: totalWidth,
          height: _tlH,
          child: Stack(
            clipBehavior: Clip.hardEdge,
            children: [
              // 주말 배경
              ...List.generate(totalDays, (i) {
                final date = _tlStart.add(Duration(days: i));
                if (date.weekday != 6 && date.weekday != 7) {
                  return const SizedBox.shrink();
                }
                return Positioned(
                  left: i * _dayW,
                  top: _monthH,
                  width: _dayW,
                  height: _tlH - _monthH,
                  child: Container(color: const Color(0xFFF3F3F8)),
                );
              }),
              // 오늘 빨간 세로선
              Positioned(
                left: _today.difference(_tlStart).inDays * _dayW + _dayW / 2,
                top: 0,
                width: 1.5,
                height: _tlH,
                child: Container(color: AppTheme.red.withOpacity(0.22)),
              ),
              // 날짜 구분선
              ...List.generate(totalDays, (i) {
                if (i == 0) return const SizedBox.shrink();
                return Positioned(
                  left: i * _dayW,
                  top: headerH,
                  width: 1,
                  height: _tlH - headerH,
                  child: Container(color: const Color(0xFFDDE0EA)),
                );
              }),
              // 월 레이블
              ..._buildMonthLabels(totalDays),
              // 날짜 헤더
              ...List.generate(totalDays, (i) {
                final date = _tlStart.add(Duration(days: i));
                final isToday = _sameDay(date, _today);
                final isSelected = _sameDay(date, _selectedDay);
                final isSun = date.weekday == 7;
                final isSat = date.weekday == 6;
                final Color textColor = isSun
                    ? AppTheme.red
                    : isSat
                        ? AppTheme.blue
                        : AppTheme.textPrimary;

                return Positioned(
                  left: i * _dayW,
                  top: _monthH,
                  width: _dayW,
                  height: _dateH,
                  child: GestureDetector(
                    onTap: () => setState(() => _selectedDay = date),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text(
                          _weekdayShort(date.weekday),
                          style: TextStyle(
                            fontSize: 10,
                            color: textColor.withOpacity(0.65),
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                        const SizedBox(height: 3),
                        Container(
                          width: 32,
                          height: 32,
                          decoration: BoxDecoration(
                            color: isToday
                                ? AppTheme.red
                                : isSelected
                                    ? AppTheme.blue
                                    : Colors.transparent,
                            shape: BoxShape.circle,
                          ),
                          child: Center(
                            child: Text(
                              '${date.day}',
                              style: TextStyle(
                                fontSize: 14,
                                fontWeight: (isToday || isSelected)
                                    ? FontWeight.w700
                                    : FontWeight.w500,
                                color: (isToday || isSelected)
                                    ? Colors.white
                                    : textColor,
                              ),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                );
              }),
              // 이벤트 카드
              ...placed.map((pe) {
                final startIdx =
                    pe.event.date.difference(_tlStart).inDays;
                final endIdx =
                    pe.event.endDate.difference(_tlStart).inDays;
                final cardWidth = (endIdx - startIdx + 1) * _dayW - 6;
                final top = headerH + 6 + pe.row * (_cardH + 4);
                final color = pe.event.color;

                return Positioned(
                  left: startIdx * _dayW + 3,
                  top: top,
                  width: cardWidth,
                  height: _cardH,
                  child: Container(
                    decoration: BoxDecoration(
                      color: color.withOpacity(0.12),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(
                          color: color.withOpacity(0.35), width: 1),
                      boxShadow: [
                        BoxShadow(
                          color: color.withOpacity(0.12),
                          blurRadius: 4,
                          offset: const Offset(0, 2),
                        )
                      ],
                    ),
                    padding: const EdgeInsets.symmetric(horizontal: 7),
                    child: Row(
                      children: [
                        Container(
                          width: 3,
                          height: 20,
                          decoration: BoxDecoration(
                            color: color,
                            borderRadius: BorderRadius.circular(2),
                          ),
                        ),
                        const SizedBox(width: 5),
                        Expanded(
                          child: Text(
                            pe.event.title,
                            style: TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.w600,
                              color: color,
                            ),
                            overflow: TextOverflow.ellipsis,
                            maxLines: 1,
                          ),
                        ),
                      ],
                    ),
                  ),
                );
              }),
            ],
          ),
        ),
      ),
    );
  }

  List<Widget> _buildMonthLabels(int totalDays) {
    final labels = <Widget>[];
    int? lastMonth;
    for (int i = 0; i < totalDays; i++) {
      final date = _tlStart.add(Duration(days: i));
      if (lastMonth == null || date.month != lastMonth) {
        lastMonth = date.month;
        labels.add(Positioned(
          left: i * _dayW + 10,
          top: 4,
          child: Text(
            '${date.year}년 ${date.month}월',
            style: const TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w700,
              color: AppTheme.textSecondary,
              letterSpacing: -0.2,
            ),
          ),
        ));
      }
    }
    return labels;
  }

  List<_PlacedEvent> _placedEvents() {
    final sorted = [..._tlItems]..sort((a, b) => a.date.compareTo(b.date));
    final placed = <_PlacedEvent>[];
    for (final ev in sorted) {
      final startIdx = ev.date.difference(_tlStart).inDays;
      final endIdx = ev.endDate.difference(_tlStart).inDays;
      int row = 0;
      while (true) {
        final conflict = placed.where((pe) => pe.row == row).any((pe) {
          final pStart = pe.event.date.difference(_tlStart).inDays;
          final pEnd = pe.event.endDate.difference(_tlStart).inDays;
          return !(endIdx < pStart || startIdx > pEnd);
        });
        if (!conflict) break;
        row++;
        if (row >= 5) break;
      }
      placed.add(_PlacedEvent(ev, row));
    }
    return placed;
  }

  bool _sameDay(DateTime a, DateTime b) =>
      a.year == b.year && a.month == b.month && a.day == b.day;

  // ─── 선택된 날 일정 + 할일 ───────────────
  Widget _buildDayScheduleAndTodos() {
    final dateStr =
        '${_selectedDay.month}월 ${_selectedDay.day}일 ${_weekdayStr(_selectedDay.weekday)}';

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 10),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(dateStr,
                  style: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w700,
                      color: AppTheme.textPrimary)),
              const Icon(Icons.umbrella_outlined,
                  color: AppTheme.blue, size: 20),
            ],
          ),
        ),
        _sectionLabel('일정', Icons.calendar_today_outlined),
        ...List.generate(_dayEvents.length, (i) {
          final ev = _dayEvents[i];
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
                        borderRadius: BorderRadius.circular(4)),
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
                                color: AppTheme.textPrimary)),
                        const SizedBox(height: 3),
                        Row(
                          children: [
                            Text('${ev.startTime} – ${ev.endTime}',
                                style: const TextStyle(
                                    fontSize: 12,
                                    color: AppTheme.textSecondary)),
                            const Text(' · ',
                                style: TextStyle(
                                    color: AppTheme.textSecondary,
                                    fontSize: 12)),
                            PillBadge(label: ev.category, color: ev.color),
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
        _sectionLabel('할일', Icons.check_circle_outline),
        ...List.generate(_dayTodos.length, (i) {
          final isDone = _checkedTodos.contains(i);
          return Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 6),
            child: GlassCard(
              padding: const EdgeInsets.symmetric(
                  horizontal: 14, vertical: 12),
              child: Row(
                children: [
                  GestureDetector(
                    onTap: () => setState(() {
                      if (isDone) {
                        _checkedTodos.remove(i);
                      } else {
                        _checkedTodos.add(i);
                      }
                    }),
                    child: AnimatedContainer(
                      duration: const Duration(milliseconds: 200),
                      width: 22,
                      height: 22,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: isDone
                            ? AppTheme.separator
                            : Colors.transparent,
                        border: Border.all(
                          color: isDone
                              ? AppTheme.separator
                              : AppTheme.textSecondary.withOpacity(0.4),
                          width: 1.8,
                        ),
                      ),
                      child: isDone
                          ? const Icon(Icons.check,
                              color: AppTheme.textSecondary, size: 13)
                          : null,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      _dayTodos[i],
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w500,
                        color: isDone
                            ? AppTheme.textSecondary
                            : AppTheme.textPrimary,
                        decoration: isDone
                            ? TextDecoration.lineThrough
                            : TextDecoration.none,
                        decorationColor: AppTheme.textSecondary,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          );
        }),
      ],
    );
  }

  Widget _sectionLabel(String text, IconData icon) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 4, 20, 8),
      child: Row(
        children: [
          Icon(icon, size: 14, color: AppTheme.textSecondary),
          const SizedBox(width: 5),
          Text(text,
              style: const TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w700,
                  color: AppTheme.textSecondary)),
        ],
      ),
    );
  }

  // ─── 헬퍼 ───────────────────────────────
  String _weekdayStr(int wd) {
    const d = ['', '월', '화', '수', '목', '금', '토', '일'];
    return '${d[wd]}요일';
  }

  String _weekdayShort(int wd) {
    const d = ['', '월', '화', '수', '목', '금', '토', '일'];
    return d[wd];
  }
}

// ─── 데이터 클래스 ───────────────────────
class _CalEvent {
  final String startTime, endTime, title, category;
  final Color color;
  final IconData icon;
  const _CalEvent(this.startTime, this.endTime, this.title, this.category,
      this.color, this.icon);
}

class _MonthEvent {
  final String title;
  final DateTime start, end;
  final Color color;
  _MonthEvent(this.title, this.start, this.end, this.color);
}

class _TLEvent {
  final String title;
  final DateTime date, endDate;
  final Color color;
  _TLEvent(this.title, this.date, this.endDate, this.color);
}

class _PlacedEvent {
  final _TLEvent event;
  final int row;
  const _PlacedEvent(this.event, this.row);
}
