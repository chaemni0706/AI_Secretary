import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

/// 숫자가 굴러가듯 카운트업되는 텍스트 (토스 시그니처 모션).
///
/// [value]가 바뀌면 이전 값에서 새 값까지 부드럽게 굴러간다.
/// [formatter]로 천 단위 콤마 등 표시 형식을 제어한다.
class TossCountUpText extends StatelessWidget {
  final num value;
  final TextStyle? style;
  final String Function(num value) formatter;
  final Duration duration;

  const TossCountUpText({
    super.key,
    required this.value,
    this.style,
    this.formatter = _defaultFormat,
    this.duration = const Duration(milliseconds: 600),
  });

  static String _defaultFormat(num v) => v.round().toString();

  @override
  Widget build(BuildContext context) {
    // 접근성: 시스템이 애니메이션 축소를 요청하면 즉시 표시.
    if (MediaQuery.of(context).disableAnimations) {
      return Text(formatter(value), style: style);
    }
    return TweenAnimationBuilder<double>(
      tween: Tween(end: value.toDouble()),
      duration: duration,
      curve: TossMotion.easeOut,
      builder: (context, animated, _) =>
          Text(formatter(animated), style: style),
    );
  }
}

/// 아래에서 살짝 올라오며 fade-in 되는 등장 모션.
/// [index]를 주면 리스트에서 순차(stagger) 등장한다.
class TossFadeSlideIn extends StatefulWidget {
  final Widget child;
  final int index;
  final Duration staggerGap;

  const TossFadeSlideIn({
    super.key,
    required this.child,
    this.index = 0,
    this.staggerGap = const Duration(milliseconds: 50),
  });

  @override
  State<TossFadeSlideIn> createState() => _TossFadeSlideInState();
}

class _TossFadeSlideInState extends State<TossFadeSlideIn>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  late final Animation<double> _opacity;
  late final Animation<Offset> _offset;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(vsync: this, duration: TossMotion.slow);
    final curved = CurvedAnimation(
      parent: _controller,
      curve: TossMotion.easeOut,
    );
    _opacity = curved;
    _offset = Tween(
      begin: const Offset(0, 0.06),
      end: Offset.zero,
    ).animate(curved);

    Future.delayed(widget.staggerGap * widget.index.clamp(0, 12), () {
      if (mounted) _controller.forward();
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (MediaQuery.of(context).disableAnimations) return widget.child;
    return FadeTransition(
      opacity: _opacity,
      child: SlideTransition(position: _offset, child: widget.child),
    );
  }
}
