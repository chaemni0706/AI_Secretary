import 'dart:math' as math;
import 'package:flutter/material.dart';

class WidgetEditJiggleWrapper extends StatefulWidget {
  final bool isEditing;
  final int index;
  final Widget child;

  const WidgetEditJiggleWrapper({
    super.key,
    required this.isEditing,
    required this.index,
    required this.child,
  });

  @override
  State<WidgetEditJiggleWrapper> createState() =>
      _WidgetEditJiggleWrapperState();
}

class _WidgetEditJiggleWrapperState extends State<WidgetEditJiggleWrapper>
    with SingleTickerProviderStateMixin {
  static const _duration = Duration(milliseconds: 420);
  static const _maxAngle = 0.012;
  static const _maxOffset = 1.1;

  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(vsync: this, duration: _duration);
    if (widget.isEditing) _startJiggle();
  }

  @override
  void didUpdateWidget(covariant WidgetEditJiggleWrapper oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.isEditing == oldWidget.isEditing) return;
    if (widget.isEditing) {
      _startJiggle();
    } else {
      _controller
        ..stop()
        ..reset();
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _startJiggle() {
    final delay = Duration(milliseconds: (widget.index % 5) * 34);
    Future<void>.delayed(delay, () {
      if (!mounted || !widget.isEditing) return;
      _controller.repeat(reverse: true);
    });
  }

  @override
  Widget build(BuildContext context) {
    final disableMotion =
        MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    if (!widget.isEditing || disableMotion) return widget.child;

    return AnimatedBuilder(
      animation: _controller,
      child: widget.child,
      builder: (context, child) {
        final phase = (widget.index % 7) * 0.37;
        final wave = math.sin((_controller.value * math.pi * 2) + phase);
        final angle = wave * _maxAngle;
        final offsetY =
            math.cos((_controller.value * math.pi * 2) + phase) * _maxOffset;
        return Transform.translate(
          offset: Offset(0, offsetY),
          child: Transform.rotate(angle: angle, child: child),
        );
      },
    );
  }
}
