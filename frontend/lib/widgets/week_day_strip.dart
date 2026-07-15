import 'package:flutter/material.dart';
import 'package:table_calendar/table_calendar.dart' show isSameDay;
import '../theme/app_theme.dart';
import 'glass_card.dart';

/// 캘린더 주간 뷰의 7일 chip 행. PageView 등에서 주(week) 단위로 반복 사용된다.
class WeekDayStrip extends StatelessWidget {
  final DateTime weekStart;
  final DateTime selectedDay;
  final bool Function(DateTime day) hasEvent;
  final ValueChanged<DateTime> onDaySelected;

  /// true 면 카드/바깥 패딩 없이 7일 행만 그린다 — 주간 타임라인과 한 카드로
  /// 합쳐 쓸 때(칼렌더 주간 뷰) 카드 안에 카드가 겹치지 않도록.
  final bool bare;

  const WeekDayStrip({
    super.key,
    required this.weekStart,
    required this.selectedDay,
    required this.hasEvent,
    required this.onDaySelected,
    this.bare = false,
  });

  static const _dayNames = ['일', '월', '화', '수', '목', '금', '토'];

  /// 요일 라벨 줄높이를 고정해 기기별 폰트 메트릭 편차로 인한
  /// RenderFlex overflow를 방지한다.
  static const double _dayLabelHeight = 16;

  /// [bare] 모드의 콘텐츠 높이(요일라벨 + 간격 + 원형 배지 + 간격 + 점 + 버퍼).
  static const double bareHeight = _dayLabelHeight + 6 + 36 + 4 + 5 + 8;

  /// GlassCard 내부 콘텐츠 높이(패딩 12*2 포함) + 폰트 편차 여유 버퍼.
  static const double _cardHeight = 12 + bareHeight + 12;

  /// 바깥 Padding(top 10)까지 포함한, PageView에 사용할 고정 높이.
  static const double pageHeight = 10 + _cardHeight;

  @override
  Widget build(BuildContext context) {
    if (bare) return _buildRow();
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 10, 16, 0),
      child: GlassCard(padding: const EdgeInsets.all(12), child: _buildRow()),
    );
  }

  Widget _buildRow() {
    return Row(
          mainAxisAlignment: MainAxisAlignment.spaceAround,
          children: List.generate(7, (i) {
            final day = weekStart.add(Duration(days: i));
            final isSelected = isSameDay(day, selectedDay);
            final isToday = isSameDay(day, DateTime.now());
            final showDot = hasEvent(day);
            return GestureDetector(
              onTap: () => onDaySelected(day),
              child: Column(
                children: [
                  SizedBox(
                    height: _dayLabelHeight,
                    child: Text(
                      _dayNames[i],
                      style: TextStyle(
                        fontSize: 12,
                        height: 1,
                        fontWeight: FontWeight.w600,
                        color: i == 0
                            ? AppTheme.red
                            : (i == 6 ? AppTheme.blue : AppTheme.textSecondary),
                      ),
                    ),
                  ),
                  const SizedBox(height: 6),
                  Container(
                    width: 36,
                    height: 36,
                    decoration: BoxDecoration(
                      color: isSelected
                          ? TossColors.blue500
                          : isToday
                          ? TossColors.blueWeak
                          : Colors.transparent,
                      shape: BoxShape.circle,
                    ),
                    child: Center(
                      child: Text(
                        '${day.day}',
                        style: TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.w600,
                          color: isSelected
                              ? Colors.white
                              : isToday
                              ? TossColors.blue600
                              : TossColors.textPrimary,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 4),
                  Container(
                    width: 5,
                    height: 5,
                    decoration: BoxDecoration(
                      color: showDot ? AppTheme.blue : Colors.transparent,
                      shape: BoxShape.circle,
                    ),
                  ),
                ],
              ),
            );
          }),
    );
  }
}
