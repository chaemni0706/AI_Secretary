import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

/// 토스식 리스트 행 — 좌 아이콘 + 타이틀/서브텍스트 + 우측 값·화살표.
///
/// 구분선 대신 여백으로 분리하고, 누르면 배경이 그레이로 살짝 눌린다.
/// 터치 타깃 최소 높이 56 확보.
class TossListRow extends StatefulWidget {
  final Widget? leading;
  final String title;
  final String? subtitle;
  final Widget? trailing;
  final String? trailingText;
  final bool showChevron;
  final VoidCallback? onTap;
  final EdgeInsetsGeometry padding;

  const TossListRow({
    super.key,
    this.leading,
    required this.title,
    this.subtitle,
    this.trailing,
    this.trailingText,
    this.showChevron = false,
    this.onTap,
    this.padding = const EdgeInsets.symmetric(
      horizontal: TossSpacing.xl,
      vertical: TossSpacing.md,
    ),
  });

  @override
  State<TossListRow> createState() => _TossListRowState();
}

class _TossListRowState extends State<TossListRow> {
  bool _pressed = false;

  @override
  Widget build(BuildContext context) {
    final row = AnimatedContainer(
      duration: TossMotion.fast,
      constraints: const BoxConstraints(minHeight: 56),
      padding: widget.padding,
      color: _pressed ? TossColors.pressedGrey : Colors.transparent,
      child: Row(
        children: [
          if (widget.leading != null) ...[
            widget.leading!,
            const SizedBox(width: TossSpacing.md),
          ],
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(widget.title, style: TossTypography.label),
                if (widget.subtitle != null) ...[
                  const SizedBox(height: 2),
                  Text(widget.subtitle!, style: TossTypography.caption),
                ],
              ],
            ),
          ),
          if (widget.trailingText != null)
            Text(
              widget.trailingText!,
              style: TossTypography.label.copyWith(fontWeight: FontWeight.w600),
            ),
          if (widget.trailing != null) widget.trailing!,
          if (widget.showChevron) ...[
            const SizedBox(width: TossSpacing.xs),
            const Icon(
              Icons.chevron_right,
              size: 20,
              color: TossColors.grey400,
            ),
          ],
        ],
      ),
    );

    if (widget.onTap == null) return row;

    return GestureDetector(
      onTap: widget.onTap,
      onTapDown: (_) => setState(() => _pressed = true),
      onTapUp: (_) => setState(() => _pressed = false),
      onTapCancel: () => setState(() => _pressed = false),
      behavior: HitTestBehavior.opaque,
      child: row,
    );
  }
}
