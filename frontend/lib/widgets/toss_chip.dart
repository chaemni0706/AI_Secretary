import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

/// 토스식 칩 — pill 형태, 선택 시 Blue-weak 배경 + Blue 텍스트.
class TossChip extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback? onTap;
  final Widget? leading;

  const TossChip({
    super.key,
    required this.label,
    this.selected = false,
    this.onTap,
    this.leading,
  });

  @override
  Widget build(BuildContext context) {
    final fg = selected ? TossColors.blue600 : TossColors.grey600;

    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: TossMotion.fast,
        curve: TossMotion.easeOut,
        constraints: const BoxConstraints(minHeight: 36),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        decoration: BoxDecoration(
          color: selected ? TossColors.blueWeak : TossColors.grey100,
          borderRadius: BorderRadius.circular(TossRadius.full),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (leading != null) ...[
              IconTheme(
                data: IconThemeData(color: fg, size: 16),
                child: leading!,
              ),
              const SizedBox(width: 4),
            ],
            Text(
              label,
              style: TextStyle(
                fontFamily: TossTypography.fontFamily,
                fontSize: 14,
                fontWeight: selected ? FontWeight.w600 : FontWeight.w500,
                color: fg,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
