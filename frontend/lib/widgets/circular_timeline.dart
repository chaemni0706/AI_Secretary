import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

class TimelineEvent {
  final String title;
  final double startHour;
  final double endHour;
  final Color color;

  const TimelineEvent({
    required this.title,
    required this.startHour,
    required this.endHour,
    required this.color,
  });
}

// ─────────────────────────────────────────
//  도넛 타임라인
// ─────────────────────────────────────────
class CircularTimeline extends StatelessWidget {
  final List<TimelineEvent> events;
  final double currentHour;
  final double size;
  final double? progressPercent;

  const CircularTimeline({
    super.key,
    required this.events,
    required this.currentHour,
    this.size = 220,
    this.progressPercent,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: size,
      height: size,
      child: Stack(
        alignment: Alignment.center,
        children: [
          CustomPaint(
            size: Size(size, size),
            painter: _DonutPainter(events: events, currentHour: currentHour),
          ),
          _buildCenter(),
        ],
      ),
    );
  }

  Widget _buildCenter() {
    if (progressPercent != null) {
      return Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            '${(progressPercent! * 100).round()}%',
            style: const TextStyle(
              fontSize: 30,
              fontWeight: FontWeight.w800,
              color: AppTheme.blue,
              letterSpacing: -1.2,
            ),
          ),
          const SizedBox(height: 2),
          const Text(
            '오늘의 진행률',
            style: TextStyle(
              fontSize: 11,
              color: AppTheme.textSecondary,
              fontWeight: FontWeight.w500,
            ),
          ),
          const SizedBox(height: 8),
          Row(
            mainAxisSize: MainAxisSize.min,
            children: events
                .map(
                  (e) => Container(
                    width: 7,
                    height: 7,
                    margin: const EdgeInsets.symmetric(horizontal: 2),
                    decoration: BoxDecoration(
                      color: e.color,
                      shape: BoxShape.circle,
                    ),
                  ),
                )
                .toList(),
          ),
        ],
      );
    }
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          _fmt(currentHour),
          style: const TextStyle(
            fontSize: 22,
            fontWeight: FontWeight.w700,
            color: AppTheme.textPrimary,
            letterSpacing: -0.5,
          ),
        ),
        const Text(
          '현재 시간',
          style: TextStyle(fontSize: 11, color: AppTheme.textSecondary),
        ),
      ],
    );
  }

  String _fmt(double h) {
    final hh = h.floor();
    final mm = ((h - hh) * 60).round();
    return '${hh.toString().padLeft(2, '0')}:${mm.toString().padLeft(2, '0')}';
  }
}

class _DonutPainter extends CustomPainter {
  final List<TimelineEvent> events;
  final double currentHour;

  const _DonutPainter({required this.events, required this.currentHour});

  double _angle(double h) => (h / 24.0) * 2 * math.pi - math.pi / 2;

  @override
  void paint(Canvas canvas, Size size) {
    final c = Offset(size.width / 2, size.height / 2);
    const pad = 38.0; // 중앙 빈 공간 축소
    final r = size.width / 2 - pad;
    const tw = 44.0; // 도넛 두께

    // 배경 트랙
    canvas.drawCircle(
      c,
      r,
      Paint()
        ..color = AppTheme.separator
        ..style = PaintingStyle.stroke
        ..strokeWidth = tw,
    );

    // 이벤트 호
    for (final e in events) {
      final start = _angle(e.startHour);
      final sweep = ((e.endHour - e.startHour) / 24) * 2 * math.pi;
      canvas.drawArc(
        Rect.fromCircle(center: c, radius: r),
        start,
        sweep,
        false,
        Paint()
          ..color = e.color
          ..style = PaintingStyle.stroke
          ..strokeWidth = tw
          ..strokeCap = StrokeCap.round,
      );
    }

    // 현재시각 점
    final da = _angle(currentHour);
    final dx = c.dx + r * math.cos(da);
    final dy = c.dy + r * math.sin(da);
    canvas.drawCircle(Offset(dx, dy), 9, Paint()..color = Colors.white);
    canvas.drawCircle(
      Offset(dx, dy),
      9,
      Paint()
        ..color = AppTheme.blue
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.5,
    );

    // 레이블 0, 6, 12, 18
    for (final h in [0, 6, 12, 18]) {
      final a = _angle(h.toDouble());
      final lr = r + pad - 4;
      final lx = c.dx + lr * math.cos(a);
      final ly = c.dy + lr * math.sin(a);
      final tp = TextPainter(
        text: TextSpan(
          text: '$h',
          style: const TextStyle(
            fontSize: 10,
            color: AppTheme.textSecondary,
            fontWeight: FontWeight.w500,
          ),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      tp.paint(canvas, Offset(lx - tp.width / 2, ly - tp.height / 2));
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter old) => false;
}

// ─────────────────────────────────────────
//  크로노덱스 타임라인
// ─────────────────────────────────────────
class ChronodexTimeline extends StatelessWidget {
  final List<TimelineEvent> events;
  final double size;

  const ChronodexTimeline({super.key, required this.events, this.size = 220});

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: size,
      height: size,
      child: CustomPaint(
        size: Size(size, size),
        painter: _ChronodexPainter(events: events),
      ),
    );
  }
}

class _ChronodexPainter extends CustomPainter {
  final List<TimelineEvent> events;
  const _ChronodexPainter({required this.events});

  static const _pad = 22.0;
  static const _startAngle = -math.pi / 2;

  @override
  void paint(Canvas canvas, Size size) {
    final c = Offset(size.width / 2, size.height / 2);
    final maxR = size.width / 2 - _pad;
    final midR = maxR * 0.54;
    final minR = maxR * 0.16;

    const n = 24;
    final step = 2 * math.pi / n;
    const gap = 0.04;

    // 배경 조각
    for (int h = 0; h < n; h++) {
      final sa = _startAngle + h * step;
      final sw = step - gap;
      final ir = h < 12 ? minR : midR;
      final or = h < 12 ? midR : maxR;
      canvas.drawPath(
        _wedge(c, ir, or, sa, sw),
        Paint()
          ..color = const Color(0xFFE9EDF8)
          ..style = PaintingStyle.fill,
      );
    }

    // 이벤트
    for (final ev in events) {
      final sh = ev.startHour;
      final eh = ev.endHour;
      for (int h = sh.floor(); h < eh.ceil() && h < n; h++) {
        final slotS = math.max(sh, h.toDouble());
        final slotE = math.min(eh, h + 1.0);
        final frac = slotE - slotS;
        if (frac <= 0) continue;

        final sa = _startAngle + slotS * step;
        final sw = (frac * step) - gap;
        if (sw <= 0) continue;

        final ir = h < 12 ? minR : midR;
        final or = h < 12 ? midR : maxR;

        canvas.drawPath(
          _wedge(c, ir, or, sa, sw),
          Paint()
            ..color = ev.color.withValues(alpha: 0.88)
            ..style = PaintingStyle.fill,
        );
      }
    }

    // 구분선
    for (int h = 0; h < n; h++) {
      final a = _startAngle + h * step;
      final ir = h < 12 ? minR : midR;
      final or = h < 12 ? midR : maxR;
      canvas.drawLine(
        Offset(c.dx + ir * math.cos(a), c.dy + ir * math.sin(a)),
        Offset(c.dx + or * math.cos(a), c.dy + or * math.sin(a)),
        Paint()
          ..color = Colors.white
          ..strokeWidth = 1.4,
      );
    }

    // AM/PM 경계 링
    canvas.drawCircle(
      c,
      midR,
      Paint()
        ..color = Colors.white
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.2,
    );

    // 외부 링
    canvas.drawCircle(
      c,
      maxR,
      Paint()
        ..color = const Color(0xFFD0D5E8)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 0.8,
    );

    // 내부 원
    canvas.drawCircle(
      c,
      minR,
      Paint()
        ..color = const Color(0xFFF0F3FC)
        ..style = PaintingStyle.fill,
    );
    canvas.drawCircle(
      c,
      minR,
      Paint()
        ..color = Colors.white
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.5,
    );

    // AM/PM 레이블
    final amA = _startAngle + 6 * step; // 6h 위치
    final pmA = _startAngle + 18 * step; // 18h 위치
    for (final pair in [
      (amA, 'AM', (minR + midR) / 2),
      (pmA, 'PM', (midR + maxR) / 2),
    ]) {
      final (angle, label, radius) = pair;
      final lx = c.dx + radius * math.cos(angle);
      final ly = c.dy + radius * math.sin(angle);
      final tp = TextPainter(
        text: TextSpan(
          text: label,
          style: const TextStyle(
            fontSize: 9,
            color: AppTheme.textSecondary,
            fontWeight: FontWeight.w700,
          ),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      tp.paint(canvas, Offset(lx - tp.width / 2, ly - tp.height / 2));
    }

    // 외부 레이블 0, 6, 12, 18
    for (final h in [0, 6, 12, 18]) {
      final a = _startAngle + h * step;
      final lr = maxR + _pad - 6;
      final lx = c.dx + lr * math.cos(a);
      final ly = c.dy + lr * math.sin(a);
      final tp = TextPainter(
        text: TextSpan(
          text: '$h',
          style: const TextStyle(
            fontSize: 10,
            color: AppTheme.textSecondary,
            fontWeight: FontWeight.w600,
          ),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      tp.paint(canvas, Offset(lx - tp.width / 2, ly - tp.height / 2));
    }
  }

  Path _wedge(Offset c, double ir, double or, double sa, double sw) {
    return Path()
      ..moveTo(c.dx + or * math.cos(sa), c.dy + or * math.sin(sa))
      ..arcTo(Rect.fromCircle(center: c, radius: or), sa, sw, false)
      ..arcTo(Rect.fromCircle(center: c, radius: ir), sa + sw, -sw, false)
      ..close();
  }

  @override
  bool shouldRepaint(covariant CustomPainter old) => false;
}

// ─────────────────────────────────────────
//  피자 슬라이스형 24시간 일정표 (3번째 슬라이드)
// ─────────────────────────────────────────
class ClockTimeline extends StatelessWidget {
  final List<TimelineEvent> events;
  final double currentHour;
  final double size;

  const ClockTimeline({
    super.key,
    required this.events,
    required this.currentHour,
    this.size = 220,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: size,
      height: size,
      child: CustomPaint(
        size: Size(size, size),
        painter: _PizzaPainter(events: events, currentHour: currentHour),
      ),
    );
  }
}

class _PizzaPainter extends CustomPainter {
  final List<TimelineEvent> events;
  final double currentHour;

  const _PizzaPainter({required this.events, required this.currentHour});

  static const _startAngle = -math.pi / 2;
  static const _step = 2 * math.pi / 24; // 1시간 = 15°

  @override
  void paint(Canvas canvas, Size size) {
    final c = Offset(size.width / 2, size.height / 2);
    const outerPad = 26.0;
    final maxR = size.width / 2 - outerPad;
    final minR = maxR * 0.18; // 중앙 구멍

    // ── 1. 배경 원 (전체 24시간) ──
    canvas.drawCircle(
      c,
      maxR,
      Paint()
        ..color = const Color(0xFFECEFF8)
        ..style = PaintingStyle.fill,
    );

    // ── 2. 이벤트 섹터 (시간 비례, 1시간 경계선 없음) ──
    for (final ev in events) {
      final sa = _startAngle + ev.startHour * _step;
      final sw = (ev.endHour - ev.startHour) * _step;
      if (sw <= 0) continue;
      canvas.drawPath(
        _sector(c, minR, maxR, sa, sw),
        Paint()
          ..color = ev.color.withValues(alpha: 0.9)
          ..style = PaintingStyle.fill,
      );
    }

    // ── 3. 외부 링 (얇은 흰 테두리) ──
    canvas.drawCircle(
      c,
      maxR,
      Paint()
        ..color = Colors.white.withValues(alpha: 0.6)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.0,
    );

    // ── 4. 3시간마다 주요 눈금선 (외부 링 위에만) ──
    for (int h = 0; h < 24; h += 3) {
      final isMajor = h % 6 == 0;
      final a = _startAngle + h * _step;
      final tickLen = isMajor ? 9.0 : 5.0;
      canvas.drawLine(
        Offset(
          c.dx + (maxR - tickLen) * math.cos(a),
          c.dy + (maxR - tickLen) * math.sin(a),
        ),
        Offset(c.dx + maxR * math.cos(a), c.dy + maxR * math.sin(a)),
        Paint()
          ..color = Colors.white.withValues(alpha: isMajor ? 0.95 : 0.6)
          ..strokeWidth = isMajor ? 2.5 : 1.5,
      );
    }

    // ── 5. 이벤트 레이블 ──
    for (final ev in events) {
      final dur = ev.endHour - ev.startHour;
      final midH = (ev.startHour + ev.endHour) / 2;
      final midAngle = _startAngle + midH * _step;

      if (dur >= 1.5) {
        // 넓은 섹터: 텍스트 안에 (방사방향 회전)
        final textR = (minR + maxR) * 0.57;
        final tx = c.dx + textR * math.cos(midAngle);
        final ty = c.dy + textR * math.sin(midAngle);

        final raw = ev.title;
        final title = raw.length > 6 ? raw.substring(0, 6) : raw;

        // 왼쪽 반구는 뒤집어서 읽기 쉽게
        double rot = midAngle;
        if (math.cos(midAngle) < 0) rot += math.pi;

        final tp = TextPainter(
          text: TextSpan(
            text: title,
            style: const TextStyle(
              fontSize: 10,
              color: Colors.white,
              fontWeight: FontWeight.w800,
              letterSpacing: -0.2,
            ),
          ),
          textDirection: TextDirection.ltr,
        )..layout();

        canvas.save();
        canvas.translate(tx, ty);
        canvas.rotate(rot);
        tp.paint(canvas, Offset(-tp.width / 2, -tp.height / 2));
        canvas.restore();
      } else {
        // 좁은 섹터: 외부 리더선 + 레이블
        final edgePt = Offset(
          c.dx + (maxR + 1) * math.cos(midAngle),
          c.dy + (maxR + 1) * math.sin(midAngle),
        );
        final linePt = Offset(
          c.dx + (maxR + 11) * math.cos(midAngle),
          c.dy + (maxR + 11) * math.sin(midAngle),
        );
        canvas.drawLine(
          edgePt,
          linePt,
          Paint()
            ..color = ev.color
            ..strokeWidth = 1.5
            ..strokeCap = StrokeCap.round,
        );

        final short = ev.title.length > 4 ? ev.title.substring(0, 4) : ev.title;
        final tp = TextPainter(
          text: TextSpan(
            text: short,
            style: TextStyle(
              fontSize: 9,
              color: ev.color,
              fontWeight: FontWeight.w700,
            ),
          ),
          textDirection: TextDirection.ltr,
        )..layout();

        final textPt = Offset(
          c.dx + (maxR + 15) * math.cos(midAngle) - tp.width / 2,
          c.dy + (maxR + 15) * math.sin(midAngle) - tp.height / 2,
        );
        tp.paint(canvas, textPt);
      }
    }

    // ── 6. 외부 시간 숫자 (0, 6, 12, 18) ──
    for (final h in [0, 6, 12, 18]) {
      final a = _startAngle + h * _step;
      final lr = maxR + outerPad - 4;
      final lx = c.dx + lr * math.cos(a);
      final ly = c.dy + lr * math.sin(a);
      final tp = TextPainter(
        text: TextSpan(
          text: '$h',
          style: const TextStyle(
            fontSize: 10,
            color: AppTheme.textSecondary,
            fontWeight: FontWeight.w700,
          ),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      tp.paint(canvas, Offset(lx - tp.width / 2, ly - tp.height / 2));
    }

    // ── 7. 현재 시각 마커 (링 위의 점) ──
    final nowA = _startAngle + currentHour * _step;
    final nx = c.dx + maxR * math.cos(nowA);
    final ny = c.dy + maxR * math.sin(nowA);
    canvas.drawCircle(Offset(nx, ny), 7, Paint()..color = Colors.white);
    canvas.drawCircle(
      Offset(nx, ny),
      7,
      Paint()
        ..color = AppTheme.blue
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.2,
    );

    // ── 8. 중앙 원 ──
    canvas.drawCircle(
      c,
      minR,
      Paint()
        ..color = const Color(0xFFF2F4FC)
        ..style = PaintingStyle.fill,
    );
    canvas.drawCircle(
      c,
      minR,
      Paint()
        ..color = Colors.white
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.8,
    );
    canvas.drawCircle(
      c,
      4,
      Paint()..color = AppTheme.blue.withValues(alpha: 0.45),
    );
  }

  Path _sector(Offset c, double ir, double or, double sa, double sw) {
    return Path()
      ..moveTo(c.dx + or * math.cos(sa), c.dy + or * math.sin(sa))
      ..arcTo(Rect.fromCircle(center: c, radius: or), sa, sw, false)
      ..arcTo(Rect.fromCircle(center: c, radius: ir), sa + sw, -sw, false)
      ..close();
  }

  @override
  bool shouldRepaint(covariant CustomPainter old) => false;
}
