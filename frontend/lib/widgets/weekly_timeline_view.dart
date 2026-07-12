import 'dart:async';

import 'package:flutter/material.dart';

import '../models/schedule_model.dart';
import '../theme/app_theme.dart';
import '../theme/schedule_styles.dart';

/// 주간 뷰용 Apple Watch 스타일 타임라인 본체(그리드만).
///
/// 요일/날짜 헤더는 그리지 않는다 — 바로 위 [WeekDayStrip](주간일정표)이 이미
/// 날짜를 보여주므로, 이 위젯은 시간축 + 7컬럼 색 블록 + 현재시각 선만 담당한다.
/// 접기/펼치기와 주(week) 스와이프는 호출한 화면(calendar_screen)이 관리하고,
/// 이 위젯은 한 주(weekStart 기준)의 그리드 하나를 그린다.
///
/// 시간→Y좌표 계산과 현재시각 선 스타일은 DayTimelineView 와 동일한 규칙,
/// 카테고리 색은 일정 입력 폼과 같은 [ScheduleStyles.categoryColor] 재사용.
class WeeklyTimelineBody extends StatefulWidget {
  /// 주 시작일(일요일, 자정 기준).
  final DateTime weekStart;

  /// 날짜별 일정 조회(다일치 일정 포함 — calendar_screen 의 `_schedulesFor`).
  final List<ScheduleModel> Function(DateTime day) schedulesFor;

  final ValueChanged<ScheduleModel>? onScheduleTap;

  const WeeklyTimelineBody({
    super.key,
    required this.weekStart,
    required this.schedulesFor,
    this.onScheduleTap,
  });

  /// 펼쳤을 때 차지할 뷰포트 높이(부모가 페이저 높이 계산에 사용).
  static const double preferredHeight = 300;

  static const double _hourHeight = 28;

  @override
  State<WeeklyTimelineBody> createState() => _WeeklyTimelineBodyState();
}

class _WeeklyTimelineBodyState extends State<WeeklyTimelineBody>
    with WidgetsBindingObserver {
  final _scrollController = ScrollController();
  Timer? _nowTimer;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    // 매 분 현재시각 선 위치 재계산(시간이 흐르며 자연스럽게 아래로 이동).
    _nowTimer = Timer.periodic(const Duration(minutes: 1), (_) {
      if (mounted) setState(() {});
    });
    _scrollToNow();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _nowTimer?.cancel();
    _scrollController.dispose();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // 백그라운드에 있다 돌아오면 현재시각 선을 즉시 재계산.
    if (state == AppLifecycleState.resumed && mounted) setState(() {});
  }

  /// 처음 보일 때 현재 시각이 뷰포트 중앙 부근에 오도록 초기 스크롤.
  void _scrollToNow() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted || !_scrollController.hasClients) return;
      final now = DateTime.now();
      final nowY =
          (now.hour * 60 + now.minute) / 60 * WeeklyTimelineBody._hourHeight;
      final viewport = _scrollController.position.viewportDimension;
      final target = (nowY - viewport / 2).clamp(
        0.0,
        _scrollController.position.maxScrollExtent,
      );
      _scrollController.jumpTo(target);
    });
  }

  bool get _weekContainsToday {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final diff = today.difference(widget.weekStart).inDays;
    return diff >= 0 && diff < 7;
  }

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      controller: _scrollController,
      physics: const BouncingScrollPhysics(),
      child: SizedBox(
        height: WeeklyTimelineBody._hourHeight * 24,
        child: Stack(
          children: [
            // 시간 라벨은 왼쪽 전용 컬럼이 아니라 구분선 아래 구석에 얹는다 —
            // 그래야 7개 요일 컬럼이 전체 폭을 써서 위 주간일정표의 요일
            // 위치와 정렬된다(일요일 일정이 일요일 밑에 오도록).
            _buildHourLines(),
            Positioned.fill(child: _buildDayColumns()),
            if (_weekContainsToday) _buildNowIndicator(),
          ],
        ),
      ),
    );
  }

  Widget _buildHourLines() {
    return Stack(
      children: [
        for (var hour = 0; hour < 24; hour++) ...[
          Positioned(
            top: hour * WeeklyTimelineBody._hourHeight,
            left: 0,
            right: 0,
            child: Container(
              height: 1,
              color: AppTheme.separator.withValues(alpha: 0.6),
            ),
          ),
          // 3시간 간격으로만, 해당 구분선 "아래" 왼쪽 구석에 라벨 표시.
          if (hour % 3 == 0)
            Positioned(
              top: hour * WeeklyTimelineBody._hourHeight + 2,
              left: 2,
              child: Text(
                '$hour',
                style: const TextStyle(
                  fontSize: 10,
                  color: AppTheme.textSecondary,
                ),
              ),
            ),
        ],
      ],
    );
  }

  Widget _buildDayColumns() {
    return Row(
      children: [
        for (var i = 0; i < 7; i++) ...[
          if (i > 0) const SizedBox(width: 1),
          Expanded(
            child: _DayColumn(
              schedules: widget.schedulesFor(
                widget.weekStart.add(Duration(days: i)),
              ),
              hourHeight: WeeklyTimelineBody._hourHeight,
              onScheduleTap: widget.onScheduleTap,
            ),
          ),
        ],
      ],
    );
  }

  Widget _buildNowIndicator() {
    final now = DateTime.now();
    final top =
        (now.hour * 60 + now.minute) / 60 * WeeklyTimelineBody._hourHeight;
    return Positioned(
      left: 0,
      right: 0,
      top: top - 3,
      child: Row(
        children: [
          Container(
            width: 6,
            height: 6,
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

/// 하루 컬럼 — 겹치는 일정은 레인으로 분할해 나란히 배치한다.
class _DayColumn extends StatelessWidget {
  final List<ScheduleModel> schedules;
  final double hourHeight;
  final ValueChanged<ScheduleModel>? onScheduleTap;

  const _DayColumn({
    required this.schedules,
    required this.hourHeight,
    this.onScheduleTap,
  });

  static int? _minutesOf(String? hhmm) {
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
    final entries = _layout();
    return LayoutBuilder(
      builder: (context, constraints) {
        final width = constraints.maxWidth;
        return Stack(
          children: [
            for (final entry in entries)
              Positioned(
                top: entry.start / 60 * hourHeight,
                height: ((entry.end - entry.start) / 60 * hourHeight).clamp(
                  6.0,
                  double.infinity,
                ),
                left: width * entry.leftFraction +
                    (entry.leftFraction > 0 ? 0.5 : 0),
                width: (width * entry.widthFraction -
                        (entry.widthFraction < 1 ? 1 : 0))
                    .clamp(2.0, width),
                child: GestureDetector(
                  onTap: onScheduleTap == null
                      ? null
                      : () => onScheduleTap!(entry.schedule),
                  child: Builder(
                    builder: (context) {
                      // 일간 타임라인(DayTimelineView) 블록과 동일한 톤:
                      // 옅은 배경 + 왼쪽 원색 바(원색 채움은 너무 진했음).
                      final color = ScheduleStyles.categoryColor(
                        entry.schedule.category,
                      );
                      return Container(
                        margin: const EdgeInsets.symmetric(vertical: 0.5),
                        decoration: BoxDecoration(
                          color: color.withValues(alpha: 0.16),
                          borderRadius: BorderRadius.circular(4),
                          border: Border(
                            left: BorderSide(color: color, width: 3),
                          ),
                        ),
                      );
                    },
                  ),
                ),
              ),
          ],
        );
      },
    );
  }

  /// 겹침 레인 배치: 시작시간 정렬 → 겹치는 일정끼리 클러스터로 묶고,
  /// 클러스터 안에서 빈 레인에 배정 → 레인 수만큼 가로 폭을 나눈다.
  List<_BlockEntry> _layout() {
    final timed = <({ScheduleModel s, int start, int end})>[];
    for (final s in schedules) {
      final start = _minutesOf(s.startTime);
      if (start == null) continue; // 시간 미정 일정은 표시하지 않음.
      final endRaw = _minutesOf(s.endTime);
      final end = (endRaw != null && endRaw > start) ? endRaw : start + 30;
      timed.add((s: s, start: start, end: end));
    }
    timed.sort((a, b) => a.start.compareTo(b.start));

    final entries = <_BlockEntry>[];
    var clusterStart = 0;
    var clusterEndMax = -1;
    var laneEnds = <int>[]; // 각 레인의 마지막 종료 시각.
    final laneOf = <int, int>{}; // timed 인덱스 → 레인 번호.

    void flushCluster(int from, int to) {
      final laneCount = laneEnds.length;
      if (laneCount == 0) return;
      for (var i = from; i < to; i++) {
        final lane = laneOf[i]!;
        entries.add(
          _BlockEntry(
            schedule: timed[i].s,
            start: timed[i].start,
            end: timed[i].end,
            leftFraction: lane / laneCount,
            widthFraction: 1 / laneCount,
          ),
        );
      }
    }

    for (var i = 0; i < timed.length; i++) {
      final item = timed[i];
      if (item.start >= clusterEndMax) {
        // 이전 클러스터와 겹치지 않음 → 클러스터 마감 후 새로 시작.
        flushCluster(clusterStart, i);
        clusterStart = i;
        laneEnds = [];
      }
      // 비어 있는 첫 레인에 배정(없으면 새 레인).
      var lane = laneEnds.indexWhere((end) => end <= item.start);
      if (lane == -1) {
        lane = laneEnds.length;
        laneEnds.add(item.end);
      } else {
        laneEnds[lane] = item.end;
      }
      laneOf[i] = lane;
      if (item.end > clusterEndMax) clusterEndMax = item.end;
    }
    flushCluster(clusterStart, timed.length);
    return entries;
  }
}

class _BlockEntry {
  final ScheduleModel schedule;
  final int start; // 분 단위.
  final int end;
  final double leftFraction;
  final double widthFraction;

  const _BlockEntry({
    required this.schedule,
    required this.start,
    required this.end,
    required this.leftFraction,
    required this.widthFraction,
  });
}
