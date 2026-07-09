import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

/// 토스식 카드 표면 — 불투명 화이트 + 부드러운 그림자.
///
/// (구 글래스모피즘 카드에서 전환. 파일명/클래스명은 참조 호환을 위해 유지)
/// 탭 가능하면 누름 시 살짝 눌리는 스케일 피드백을 준다.
class GlassCard extends StatefulWidget {
  final Widget child;
  final EdgeInsetsGeometry? padding;
  final double borderRadius;
  final Color? color;
  final VoidCallback? onTap;
  final List<BoxShadow>? shadow;

  const GlassCard({
    super.key,
    required this.child,
    this.padding,
    this.borderRadius = TossRadius.lg,
    this.color,
    this.onTap,
    this.shadow,
  });

  @override
  State<GlassCard> createState() => _GlassCardState();
}

class _GlassCardState extends State<GlassCard> {
  bool _pressed = false;

  @override
  Widget build(BuildContext context) {
    final card = Container(
      decoration: BoxDecoration(
        color: widget.color ?? TossColors.bgWhite,
        borderRadius: BorderRadius.circular(widget.borderRadius),
        boxShadow: widget.shadow ?? TossShadow.weak,
      ),
      padding: widget.padding ?? const EdgeInsets.all(TossSpacing.lg),
      child: widget.child,
    );

    if (widget.onTap == null) return card;

    return GestureDetector(
      onTap: widget.onTap,
      onTapDown: (_) => setState(() => _pressed = true),
      onTapUp: (_) => setState(() => _pressed = false),
      onTapCancel: () => setState(() => _pressed = false),
      child: AnimatedScale(
        scale: _pressed ? TossMotion.pressedScale : 1.0,
        duration: TossMotion.fast,
        curve: TossMotion.easeOut,
        child: card,
      ),
    );
  }
}

class PillBadge extends StatelessWidget {
  final String label;
  final Color color;
  final Color? textColor;

  const PillBadge({
    super.key,
    required this.label,
    required this.color,
    this.textColor,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(TossRadius.full),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w600,
          color: textColor ?? color,
        ),
      ),
    );
  }
}

class SectionHeader extends StatelessWidget {
  final String title;
  final String? trailing;
  final VoidCallback? onTrailingTap;

  const SectionHeader({
    super.key,
    required this.title,
    this.trailing,
    this.onTrailingTap,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(
        TossSpacing.screen, TossSpacing.xl, TossSpacing.screen, 10),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            title,
            style: const TextStyle(
              fontSize: 17,
              fontWeight: FontWeight.w700,
              color: TossColors.textPrimary,
            ),
          ),
          if (trailing != null)
            GestureDetector(
              onTap: onTrailingTap,
              child: Text(
                trailing!,
                style: const TextStyle(
                  fontSize: 14,
                  color: TossColors.blue500,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ),
        ],
      ),
    );
  }
}
