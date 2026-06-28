import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../core/theme/app_colors.dart';
import '../../core/theme/app_dimens.dart';
import '../../core/utils/responsive_utils.dart';

// ─────────────────────────────────────────────────────────────
//  임시 mock 모델 (다음 단계에서 data/models 로 분리 예정)
// ─────────────────────────────────────────────────────────────

class _TodayEvent {
  const _TodayEvent({
    required this.time, // 표시용 "09:30"
    required this.title,
    required this.color,
    required this.startHour, // 그래프용 (소수 시간) 9.5
    required this.endHour, // 그래프용 10.5
  });

  final String time;
  final String title;
  final Color color;
  final double startHour;
  final double endHour;
}

class TodayScreen extends StatelessWidget {
  const TodayScreen({super.key});

  // ── mock: 오늘 일정 ──
  static const String _userName = '수진';

  static const List<_TodayEvent> _events = [
    _TodayEvent(
      time: '09:30',
      title: '팀 주간 회의',
      color: AppColors.categoryMeeting, // blue
      startHour: 9.5,
      endHour: 10.5,
    ),
    _TodayEvent(
      time: '11:00',
      title: '병원 진료 예약',
      color: AppColors.categoryMedical, // green
      startHour: 11.0,
      endHour: 12.0,
    ),
    _TodayEvent(
      time: '14:00',
      title: 'AI 스터디 세션',
      color: AppColors.categoryStudy, // orange
      startHour: 14.0,
      endHour: 15.5,
    ),
    _TodayEvent(
      time: '19:00',
      title: '저녁 식사 약속',
      color: AppColors.categoryDinner, // purple
      startHour: 19.0,
      endHour: 21.0,
    ),
  ];

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
              _buildTopBar(context),
              const SizedBox(height: AppDimens.lg),
              _buildBriefingCard(context),
              const SizedBox(height: AppDimens.lg),
              _buildClockCard(context),
              const SizedBox(height: AppDimens.lg),
              _buildScheduleCard(context),
              const SizedBox(height: AppDimens.lg),
              _buildAiSuggestButton(context),
            ],
          ),
        ),
      ),
    );
  }

  // ── 상단 인사 + 알림 ──
  Widget _buildTopBar(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        Expanded(
          child: RichText(
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            text: TextSpan(
              style: textTheme.titleLarge,
              children: [
                const TextSpan(text: '안녕하세요, '),
                TextSpan(
                  text: '$_userName님',
                  style: textTheme.titleLarge?.copyWith(
                    color: AppColors.primary,
                  ),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(width: AppDimens.sm),
        Stack(
          clipBehavior: Clip.none,
          children: [
            const Icon(
              Icons.notifications_none_rounded,
              size: 28,
              color: AppColors.textPrimary,
            ),
            Positioned(
              right: 0,
              top: 0,
              child: Container(
                width: 8,
                height: 8,
                decoration: const BoxDecoration(
                  color: AppColors.primary,
                  shape: BoxShape.circle,
                ),
              ),
            ),
          ],
        ),
      ],
    );
  }

  // ── 오늘 하루 브리핑 카드 ──
  Widget _buildBriefingCard(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    return _SoftCard(
      backgroundColor: AppColors.primarySoft,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '오늘 하루 브리핑',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: textTheme.titleMedium?.copyWith(
                        color: AppColors.primary,
                      ),
                    ),
                    const SizedBox(height: AppDimens.sm),
                    Text(
                      '오전에는 회의와 병원 예약이 있고,\n'
                      '오후에는 AI 스터디와 저녁 약속이 있어요.',
                      maxLines: 3,
                      overflow: TextOverflow.ellipsis,
                      style: textTheme.bodyLarge?.copyWith(
                        fontWeight: FontWeight.w600,
                        height: 1.4,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: AppDimens.sm),
              const Text('🌤️', style: TextStyle(fontSize: 40)),
            ],
          ),
          const SizedBox(height: AppDimens.md),
          Text(
            '이동 시간이 겹치지 않도록 10분 일찍 출발해요.',
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: textTheme.bodyMedium,
          ),
        ],
      ),
    );
  }

  // ── 24시간 원형 그래프 카드 ──
  Widget _buildClockCard(BuildContext context) {
    return _SoftCard(
      child: Column(
        children: [
          // AspectRatio 1 로 폭에 맞춰 정사각 영역 확보
          // LayoutBuilder 로 실제 변(side)을 넘겨 Painter 가 비율 계산
          AspectRatio(
            aspectRatio: 1,
            child: LayoutBuilder(
              builder: (context, constraints) {
                final side = math.min(
                  constraints.maxWidth,
                  constraints.maxHeight,
                );
                return CustomPaint(
                  size: Size.square(side),
                  painter: _ClockPainter(events: _events, side: side),
                );
              },
            ),
          ),
          const SizedBox(height: AppDimens.md),
          _buildClockLegend(context),
        ],
      ),
    );
  }

  Widget _buildClockLegend(BuildContext context) {
    return Wrap(
      alignment: WrapAlignment.center,
      spacing: AppDimens.md,
      runSpacing: AppDimens.sm,
      children: _events.map((e) {
        return Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 8,
              height: 8,
              decoration: BoxDecoration(color: e.color, shape: BoxShape.circle),
            ),
            const SizedBox(width: AppDimens.xs),
            Text(
              '${e.time} ${e.title}',
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.labelMedium,
            ),
          ],
        );
      }).toList(),
    );
  }

  // ── 오늘 일정 리스트 카드 ──
  Widget _buildScheduleCard(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    final sorted = [..._events]
      ..sort((a, b) => a.startHour.compareTo(b.startHour));

    return _SoftCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('오늘 일정', style: textTheme.titleLarge),
          const SizedBox(height: AppDimens.md),
          ...List.generate(sorted.length, (i) {
            final isLast = i == sorted.length - 1;
            return Column(
              children: [
                _ScheduleRow(event: sorted[i]),
                if (!isLast)
                  const Divider(
                    height: AppDimens.lg,
                    thickness: 1,
                    color: AppColors.divider,
                  ),
              ],
            );
          }),
        ],
      ),
    );
  }

  // ── AI 제안 받기 버튼 ──
  Widget _buildAiSuggestButton(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      height: 56,
      child: FilledButton.icon(
        onPressed: () {},
        icon: const Icon(Icons.auto_awesome, size: 20),
        label: const Text(
          'AI 제안 받기',
          style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────
//  24시간 원형 그래프 Painter (전부 비율 기반)
// ─────────────────────────────────────────────────────────────

class _ClockPainter extends CustomPainter {
  _ClockPainter({required this.events, required this.side});

  final List<_TodayEvent> events;

  /// 정사각 영역의 한 변 길이. 모든 치수의 기준값.
  final double side;

  // ── 비율 상수 (side 기준) ──
  static const double _strokeRatio = 0.085; // 호 두께
  static const double _labelFontRatio = 0.038; // 라벨 폰트
  static const double _labelGapRatio = 0.055; // 호 바깥쪽 ~ 라벨 중심 간격

  // 12시(정오)를 아래, 0/24시를 위에 두는 시계 배치.
  double _hourToAngle(double hour) => -90 + (hour / 24.0) * 360.0;

  @override
  void paint(Canvas canvas, Size size) {
    final s = math.min(size.width, size.height);
    final center = Offset(size.width / 2, size.height / 2);

    final strokeWidth = s * _strokeRatio;
    final labelFontSize = s * _labelFontRatio;
    final labelGap = s * _labelGapRatio;

    // 바깥 한계(=정사각 절반)에서 라벨 높이와 간격, 호 두께를 역산해
    // arcRadius 를 구한다 → 어떤 크기에서도 라벨이 잘리지 않음.
    final outerLimit = s / 2;
    final labelHalfHeight = labelFontSize; // 라벨 높이 여유(대략 1em)
    final arcRadius =
        outerLimit - strokeWidth / 2 - labelGap - labelHalfHeight;

    final safeArcRadius = math.max(arcRadius, s * 0.18); // 하한 보호
    final rect = Rect.fromCircle(center: center, radius: safeArcRadius);

    // 1) 배경 트랙
    final trackPaint = Paint()
      ..color = AppColors.primarySoft
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth
      ..strokeCap = StrokeCap.round;
    canvas.drawCircle(center, safeArcRadius, trackPaint);

    // 2) 일정 구간 호
    for (final e in events) {
      final startAngle = _hourToAngle(e.startHour);
      final sweep = ((e.endHour - e.startHour) / 24.0) * 360.0;
      final arcPaint = Paint()
        ..color = e.color
        ..style = PaintingStyle.stroke
        ..strokeWidth = strokeWidth
        ..strokeCap = StrokeCap.round;
      canvas.drawArc(
        rect,
        _degToRad(startAngle),
        _degToRad(sweep),
        false,
        arcPaint,
      );
    }

    // 3) 주요 시각 라벨 (호 바깥쪽)
    final labelRadius = safeArcRadius + strokeWidth / 2 + labelGap;
    _drawHourLabels(canvas, center, labelRadius, labelFontSize);

    // 4) 내부 점선 + 중앙 바늘 (장식, 비율 기반)
    _drawInnerDots(canvas, center, safeArcRadius - strokeWidth);
    _drawCenterHand(canvas, center, safeArcRadius - strokeWidth);
  }

  void _drawHourLabels(
    Canvas canvas,
    Offset center,
    double labelRadius,
    double fontSize,
  ) {
    const labels = {
      0: '24',
      2: '02',
      4: '04',
      6: '06',
      8: '08',
      10: '10',
      12: '12',
      14: '14',
      16: '16',
      18: '18',
      20: '20',
      22: '22',
    };
    labels.forEach((hour, text) {
      final angle = _degToRad(_hourToAngle(hour.toDouble()));
      final pos = Offset(
        center.dx + labelRadius * math.cos(angle),
        center.dy + labelRadius * math.sin(angle),
      );
      final tp = TextPainter(
        text: TextSpan(
          text: text,
          style: TextStyle(
            fontSize: fontSize,
            fontWeight: FontWeight.w500,
            color: AppColors.textSecondary,
          ),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      tp.paint(
        canvas,
        Offset(pos.dx - tp.width / 2, pos.dy - tp.height / 2),
      );
    });
  }

  void _drawInnerDots(Canvas canvas, Offset center, double dotRadius) {
    if (dotRadius <= 0) return;
    final dotPaint = Paint()..color = AppColors.divider;
    const count = 60;
    final dotSize = side * 0.004; // 비율 기반 점 크기
    for (int i = 0; i < count; i++) {
      final angle = _degToRad(-90 + (i / count) * 360);
      final pos = Offset(
        center.dx + dotRadius * math.cos(angle),
        center.dy + dotRadius * math.sin(angle),
      );
      canvas.drawCircle(pos, math.max(dotSize, 1.0), dotPaint);
    }
  }

  void _drawCenterHand(Canvas canvas, Offset center, double handRadius) {
    if (handRadius <= 0) return;
    final handPaint = Paint()
      ..color = AppColors.textPrimary
      ..strokeWidth = side * 0.013
      ..strokeCap = StrokeCap.round;
    final end = Offset(center.dx, center.dy - handRadius * 0.55);
    canvas.drawLine(center, end, handPaint);
    canvas.drawCircle(
      center,
      side * 0.02,
      Paint()..color = AppColors.textPrimary,
    );
  }

  double _degToRad(double deg) => deg * math.pi / 180.0;

  @override
  bool shouldRepaint(covariant _ClockPainter oldDelegate) {
    return oldDelegate.events != events || oldDelegate.side != side;
  }
}

// ─────────────────────────────────────────────────────────────
//  공용 내부 위젯
// ─────────────────────────────────────────────────────────────

/// 흰(또는 지정) 배경 + 둥근 모서리 + 부드러운 그림자 카드
class _SoftCard extends StatelessWidget {
  const _SoftCard({required this.child, this.backgroundColor});
  final Widget child;
  final Color? backgroundColor;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppDimens.lg),
      decoration: BoxDecoration(
        color: backgroundColor ?? AppColors.surface,
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

/// 오늘 일정 한 줄 (컬러 점 + 시간 + 제목 + chevron)
/// 시간 영역 고정폭 제거 → IntrinsicWidth 로 내용에 맞추되 제목이 우선 확장
class _ScheduleRow extends StatelessWidget {
  const _ScheduleRow({required this.event});
  final _TodayEvent event;

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        Container(
          width: 10,
          height: 10,
          decoration: BoxDecoration(color: event.color, shape: BoxShape.circle),
        ),
        const SizedBox(width: AppDimens.md),
        // 시간: 고정폭 대신 내용 크기. 짧고 일정한 "09:30" 이라 폭 차지가 적음
        Text(
          event.time,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600),
        ),
        const SizedBox(width: AppDimens.md),
        // 제목: 남는 폭을 모두 차지하고 길면 말줄임
        Expanded(
          child: Text(
            event.title,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: textTheme.bodyLarge,
          ),
        ),
        const SizedBox(width: AppDimens.sm),
        const Icon(
          Icons.chevron_right,
          size: 20,
          color: AppColors.textSecondary,
        ),
      ],
    );
  }
}