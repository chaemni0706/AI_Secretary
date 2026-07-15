import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

class TodoProgressCelebration extends StatefulWidget {
  final bool active;
  final Widget child;

  const TodoProgressCelebration({
    super.key,
    required this.active,
    required this.child,
  });

  @override
  State<TodoProgressCelebration> createState() =>
      _TodoProgressCelebrationState();
}

class _TodoProgressCelebrationState extends State<TodoProgressCelebration>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  bool _playedForCurrentCompletion = false;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1050),
    );
    _maybePlay();
  }

  @override
  void didUpdateWidget(covariant TodoProgressCelebration oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!widget.active) {
      _playedForCurrentCompletion = false;
      _controller.reset();
      return;
    }
    _maybePlay();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _maybePlay() {
    if (!widget.active || _playedForCurrentCompletion) return;
    _playedForCurrentCompletion = true;
    _controller.forward(from: 0);
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      child: widget.child,
      builder: (context, child) {
        final progress = Curves.easeOutBack.transform(
          math.min(_controller.value, 0.72) / 0.72,
        );
        final settle = Curves.easeOut.transform(_controller.value);
        final scale = widget.active ? 1.0 + (0.08 * (1 - settle)) : 1.0;
        return Stack(
          clipBehavior: Clip.none,
          alignment: Alignment.center,
          children: [
            Transform.scale(scale: scale, child: child),
            if (_controller.isAnimating || _controller.value > 0)
              Positioned.fill(
                child: IgnorePointer(
                  child: CustomPaint(
                    painter: _CelebrationPainter(progress: progress),
                  ),
                ),
              ),
          ],
        );
      },
    );
  }
}

class _CelebrationPainter extends CustomPainter {
  final double progress;

  const _CelebrationPainter({required this.progress});

  @override
  void paint(Canvas canvas, Size size) {
    if (progress <= 0) return;
    final center = size.center(Offset.zero);
    final colors = [AppTheme.green, AppTheme.blue, AppTheme.orange];
    final paint = Paint()..style = PaintingStyle.fill;
    for (var i = 0; i < 10; i++) {
      final angle = (math.pi * 2 / 10) * i - math.pi / 2;
      final distance = 18 + (22 * progress);
      final offset = Offset(math.cos(angle), math.sin(angle)) * distance;
      final opacity = (1 - progress).clamp(0.0, 1.0);
      paint.color = colors[i % colors.length].withValues(alpha: opacity);
      final radius = 2.2 + ((i % 2) * 1.2);
      canvas.drawCircle(center + offset, radius, paint);
    }
  }

  @override
  bool shouldRepaint(covariant _CelebrationPainter oldDelegate) {
    return oldDelegate.progress != progress;
  }
}
