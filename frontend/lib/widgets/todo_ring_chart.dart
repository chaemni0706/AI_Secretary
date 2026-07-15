import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../theme/app_constants.dart';
import '../theme/app_theme.dart';
import 'glass_card.dart';

class TodoRingData {
  final String label;
  final Color color;
  final double progress;

  const TodoRingData({
    required this.label,
    required this.color,
    required this.progress,
  });
}

class TodoRingCardData {
  final String title;
  final String subtitle;
  final double overallProgress;
  final List<TodoRingData> rings;

  const TodoRingCardData({
    required this.title,
    required this.subtitle,
    required this.overallProgress,
    required this.rings,
  });
}

class TodoRingChart extends StatelessWidget {
  final List<TodoRingCardData> cards;

  const TodoRingChart({super.key, required this.cards});

  @override
  Widget build(BuildContext context) {
    final visibleCards = cards.isEmpty
        ? [
            const TodoRingCardData(
              title: '할 일 없음',
              subtitle: '완료 기록 없음',
              overallProgress: 0,
              rings: [],
            ),
          ]
        : cards;

    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 10, 16, 0),
      child: Wrap(
        spacing: 10,
        runSpacing: 10,
        children: visibleCards
            .map((card) => _MiniRingCard(data: card))
            .toList(growable: false),
      ),
    );
  }
}

class _MiniRingCard extends StatelessWidget {
  final TodoRingCardData data;

  const _MiniRingCard({required this.data});

  @override
  Widget build(BuildContext context) {
    final percent = (data.overallProgress * 100).round();

    return SizedBox(
      width: 158,
      child: GlassCard(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                SizedBox(
                  width: 72,
                  height: 72,
                  child: CustomPaint(
                    painter: _TodoRingPainter(rings: data.rings),
                    child: Center(
                      child: Text(
                        '$percent%',
                        style: const TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w800,
                          color: AppTheme.textPrimary,
                        ),
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        data.title,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: AppTextStyles.cardTitle.copyWith(
                          color: AppTheme.textPrimary,
                        ),
                      ),
                      const SizedBox(height: 3),
                      Text(
                        data.subtitle,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: AppTextStyles.meta.copyWith(
                          color: AppTheme.textSecondary,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Wrap(
              spacing: 5,
              runSpacing: 5,
              children: data.rings
                  .take(4)
                  .map(
                    (ring) => Container(
                      width: 8,
                      height: 8,
                      decoration: BoxDecoration(
                        color: ring.color,
                        shape: BoxShape.circle,
                      ),
                    ),
                  )
                  .toList(),
            ),
          ],
        ),
      ),
    );
  }
}

class _TodoRingPainter extends CustomPainter {
  final List<TodoRingData> rings;

  const _TodoRingPainter({required this.rings});

  @override
  void paint(Canvas canvas, Size size) {
    final center = size.center(Offset.zero);
    final ringList = rings.isEmpty
        ? [
            const TodoRingData(
              label: 'empty',
              color: AppTheme.textSecondary,
              progress: 0,
            ),
          ]
        : rings.take(4).toList();
    final baseRadius = size.shortestSide / 2 - 5;
    const strokeWidth = 5.0;
    const gap = 4.0;
    const startAngle = -math.pi / 2;

    for (var i = 0; i < ringList.length; i++) {
      final ring = ringList[i];
      final radius = baseRadius - (i * (strokeWidth + gap));
      if (radius <= strokeWidth) break;
      final rect = Rect.fromCircle(center: center, radius: radius);
      final backgroundPaint = Paint()
        ..color = ring.color.withValues(alpha: 0.12)
        ..style = PaintingStyle.stroke
        ..strokeWidth = strokeWidth
        ..strokeCap = StrokeCap.round;
      final progressPaint = Paint()
        ..color = ring.color
        ..style = PaintingStyle.stroke
        ..strokeWidth = strokeWidth
        ..strokeCap = StrokeCap.round;

      canvas.drawArc(rect, 0, math.pi * 2, false, backgroundPaint);
      canvas.drawArc(
        rect,
        startAngle,
        math.pi * 2 * ring.progress.clamp(0.0, 1.0),
        false,
        progressPaint,
      );
    }
  }

  @override
  bool shouldRepaint(covariant _TodoRingPainter oldDelegate) {
    return oldDelegate.rings != rings;
  }
}
