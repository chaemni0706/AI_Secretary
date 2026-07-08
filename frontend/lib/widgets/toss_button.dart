import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

enum TossButtonSize { s, m, l, xl }

enum TossButtonStyle { primaryFill, primaryWeak, secondary }

/// 토스식 버튼 — 높이 S(32)/M(38)/L(48)/XL(56), 누름 시 스케일 피드백.
///
/// 화면 하단 고정 primary CTA는 [TossButton.cta] (XL, full-width) 사용.
class TossButton extends StatefulWidget {
  final String label;
  final VoidCallback? onPressed;
  final TossButtonSize size;
  final TossButtonStyle style;
  final bool expanded;
  final Widget? leading;

  const TossButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.size = TossButtonSize.l,
    this.style = TossButtonStyle.primaryFill,
    this.expanded = false,
    this.leading,
  });

  /// 화면 하단 고정 primary CTA (XL 56, full-width).
  const TossButton.cta({
    super.key,
    required this.label,
    required this.onPressed,
    this.leading,
  })  : size = TossButtonSize.xl,
        style = TossButtonStyle.primaryFill,
        expanded = true;

  @override
  State<TossButton> createState() => _TossButtonState();
}

class _TossButtonState extends State<TossButton> {
  bool _pressed = false;

  bool get _enabled => widget.onPressed != null;

  double get _height => switch (widget.size) {
        TossButtonSize.s => 32,
        TossButtonSize.m => 38,
        TossButtonSize.l => 48,
        TossButtonSize.xl => 56,
      };

  double get _fontSize => switch (widget.size) {
        TossButtonSize.s => 13,
        TossButtonSize.m => 14,
        TossButtonSize.l => 16,
        TossButtonSize.xl => 17,
      };

  double get _radius => switch (widget.size) {
        TossButtonSize.s => 8,
        TossButtonSize.m => 10,
        TossButtonSize.l => 12,
        TossButtonSize.xl => 14,
      };

  Color get _background {
    if (!_enabled) return TossColors.grey200;
    return switch (widget.style) {
      TossButtonStyle.primaryFill => TossColors.blue500,
      TossButtonStyle.primaryWeak => TossColors.blueWeak,
      TossButtonStyle.secondary => TossColors.grey100,
    };
  }

  Color get _foreground {
    if (!_enabled) return TossColors.textAssistive;
    return switch (widget.style) {
      TossButtonStyle.primaryFill => TossColors.textOnPrimary,
      TossButtonStyle.primaryWeak => TossColors.blue600,
      TossButtonStyle.secondary => TossColors.grey700,
    };
  }

  @override
  Widget build(BuildContext context) {
    final content = Row(
      mainAxisSize: widget.expanded ? MainAxisSize.max : MainAxisSize.min,
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        if (widget.leading != null) ...[
          IconTheme(
            data: IconThemeData(color: _foreground, size: _fontSize + 4),
            child: widget.leading!,
          ),
          const SizedBox(width: 6),
        ],
        Text(
          widget.label,
          style: TextStyle(
            fontFamily: TossTypography.fontFamily,
            fontSize: _fontSize,
            fontWeight: FontWeight.w600,
            color: _foreground,
          ),
        ),
      ],
    );

    return GestureDetector(
      onTap: widget.onPressed,
      onTapDown: _enabled ? (_) => setState(() => _pressed = true) : null,
      onTapUp: _enabled ? (_) => setState(() => _pressed = false) : null,
      onTapCancel: _enabled ? () => setState(() => _pressed = false) : null,
      child: AnimatedScale(
        scale: _pressed ? TossMotion.pressedScale : 1.0,
        duration: TossMotion.fast,
        curve: TossMotion.easeOut,
        child: AnimatedContainer(
          duration: TossMotion.fast,
          height: _height,
          padding: EdgeInsets.symmetric(
            horizontal: widget.size == TossButtonSize.s ? 12 : 20,
          ),
          decoration: BoxDecoration(
            color: _background,
            borderRadius: BorderRadius.circular(_radius),
          ),
          child: content,
        ),
      ),
    );
  }
}
