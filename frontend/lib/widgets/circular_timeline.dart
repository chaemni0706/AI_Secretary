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

class CircularTimeline extends StatelessWidget {
  final List<TimelineEvent> events;
  final double currentHour;
  final double size;

  const CircularTimeline({
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
      child: Stack(
        alignment: Alignment.center,
        children: [
          CustomPaint(
            size: Size(size, size),
            painter: _TimelinePainter(
              events: events,
              currentHour: currentHour,
            ),
          ),
          Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                _formatHour(currentHour),
                style: const TextStyle(
                  fontSize: 22,
                  fontWeight: FontWeight.w700,
                  color: AppTheme.textPrimary,
                  letterSpacing: -0.5,
                ),
              ),
              const Text(
                '현재 시간',
                style: TextStyle(
                  fontSize: 11,
                  color: AppTheme.textSecondary,
                ),
              ),
              const SizedBox(height: 6),
              Row(
                mainAxisSize: MainAxisSize.min,
                children: events
                    .map((e) => Container(
                          width: 8,
                          height: 8,
                          margin: const EdgeInsets.symmetric(horizontal: 2),
                          decoration: BoxDecoration(
                            color: e.color,
                            shape: BoxShape.circle,
                          ),
                        ))
                    .toList(),
              ),
            ],
          ),
        ],
      ),
    );
  }

  String _formatHour(double hour) {
    final h = hour.floor();
    final m = ((hour - h) * 60).round();
    return '${h.toString().padLeft(2, '0')}:${m.toString().padLeft(2, '0')}';
  }
}

class _TimelinePainter extends CustomPainter {
  final List<TimelineEvent> events;
  final double currentHour;

  const _TimelinePainter({required this.events, required this.currentHour});

  double _toAngle(double hour) =>
      (hour / 24.0) * 2 * math.pi - math.pi / 2;

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    const labelPad = 20.0;
    final outerR = size.width / 2 - labelPad;
    const trackW = 16.0;

    // Background track
    canvas.drawCircle(
      center,
      outerR,
      Paint()
        ..color = AppTheme.separator
        ..style = PaintingStyle.stroke
        ..strokeWidth = trackW,
    );

    // Event arcs
    for (final event in events) {
      final startAngle = _toAngle(event.startHour);
      final sweepAngle =
          ((event.endHour - event.startHour) / 24.0) * 2 * math.pi;
      canvas.drawArc(
        Rect.fromCircle(center: center, radius: outerR),
        startAngle,
        sweepAngle,
        false,
        Paint()
          ..color = event.color
          ..style = PaintingStyle.stroke
          ..strokeWidth = trackW
          ..strokeCap = StrokeCap.round,
      );
    }

    // Current time dot
    final dotAngle = _toAngle(currentHour);
    final dotX = center.dx + outerR * math.cos(dotAngle);
    final dotY = center.dy + outerR * math.sin(dotAngle);
    canvas.drawCircle(Offset(dotX, dotY), 8, Paint()..color = Colors.white);
    canvas.drawCircle(
      Offset(dotX, dotY),
      8,
      Paint()
        ..color = AppTheme.blue
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.5,
    );

    // Hour labels 0, 6, 12, 18
    for (final h in [0, 6, 12, 18]) {
      final angle = _toAngle(h.toDouble());
      final labelR = outerR + labelPad - 4;
      final lx = center.dx + labelR * math.cos(angle);
      final ly = center.dy + labelR * math.sin(angle);

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
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
