import 'package:flutter/material.dart';
import '../../models/dashboard_widget_model.dart';
import '../../theme/app_theme.dart';

/// 모든 대시보드 위젯이 공유하는 카드 컨테이너.
/// 토스식: 불투명 화이트 + 부드러운 무채색 그림자. 편집 모드에서만 액센트 보더.
class DashboardWidgetCard extends StatefulWidget {
  final Color accent;
  final Widget child;
  final bool editing;
  final VoidCallback? onTap;
  final VoidCallback? onDelete;
  final WidgetSize currentSize;
  final List<WidgetSize> supportedSizes;
  final ValueChanged<WidgetSize>? onResize;

  const DashboardWidgetCard({
    super.key,
    required this.accent,
    required this.child,
    this.editing = false,
    this.onTap,
    this.onDelete,
    required this.currentSize,
    this.supportedSizes = const [],
    this.onResize,
  });

  @override
  State<DashboardWidgetCard> createState() => _DashboardWidgetCardState();
}

class _DashboardWidgetCardState extends State<DashboardWidgetCard> {
  bool _pressed = false;

  @override
  Widget build(BuildContext context) {
    final editing = widget.editing;
    final card = AnimatedContainer(
      duration: TossMotion.fast,
      decoration: BoxDecoration(
        color: TossColors.bgWhite,
        borderRadius: BorderRadius.circular(TossRadius.xl),
        border: editing
            ? Border.all(
                color: widget.accent.withValues(alpha: 0.5),
                width: 1.2,
              )
            : null,
        boxShadow: TossShadow.weak,
      ),
      padding: const EdgeInsets.all(TossSpacing.lg),
      child: widget.child,
    );

    return Stack(
      clipBehavior: Clip.none,
      children: [
        Positioned.fill(
          child: GestureDetector(
            onTap: editing ? null : widget.onTap,
            onTapDown: editing ? null : (_) => setState(() => _pressed = true),
            onTapUp: editing ? null : (_) => setState(() => _pressed = false),
            onTapCancel:
                editing ? null : () => setState(() => _pressed = false),
            behavior: HitTestBehavior.opaque,
            child: AnimatedScale(
              scale: _pressed ? TossMotion.pressedScale : 1.0,
              duration: TossMotion.fast,
              curve: TossMotion.easeOut,
              child: card,
            ),
          ),
        ),
        // 편집 모드에서만 콘텐츠를 흐리게 눌러 편집 상태임을 표시.
        if (editing) ...[
          Positioned(
            top: -6,
            right: -6,
            child: _DeleteButton(onTap: widget.onDelete),
          ),
          if (widget.supportedSizes.length > 1)
            Positioned(
              left: 10,
              bottom: 10,
              child: _SizeSelector(
                accent: widget.accent,
                current: widget.currentSize,
                sizes: widget.supportedSizes,
                onResize: widget.onResize,
              ),
            ),
        ],
      ],
    );
  }
}

class _DeleteButton extends StatelessWidget {
  final VoidCallback? onTap;
  const _DeleteButton({this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: Container(
        width: 26,
        height: 26,
        decoration: BoxDecoration(
          color: AppTheme.red,
          shape: BoxShape.circle,
          border: Border.all(color: Colors.white, width: 2),
          boxShadow: TossShadow.tiny,
        ),
        child: const Icon(Icons.remove, size: 16, color: Colors.white),
      ),
    );
  }
}

class _SizeSelector extends StatelessWidget {
  final Color accent;
  final WidgetSize current;
  final List<WidgetSize> sizes;
  final ValueChanged<WidgetSize>? onResize;

  const _SizeSelector({
    required this.accent,
    required this.current,
    required this.sizes,
    this.onResize,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(3),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.92),
        borderRadius: BorderRadius.circular(10),
        boxShadow: TossShadow.tiny,
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          for (final s in sizes)
            GestureDetector(
              onTap: () => onResize?.call(s),
              behavior: HitTestBehavior.opaque,
              child: Container(
                margin: const EdgeInsets.symmetric(horizontal: 1),
                width: 22,
                height: 22,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: s == current ? accent : Colors.transparent,
                  borderRadius: BorderRadius.circular(7),
                ),
                child: Text(
                  s.label,
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                    color: s == current ? Colors.white : AppTheme.textSecondary,
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

/// 위젯 상단 공통 헤더 (아이콘 칩 + 제목 + 선택적 우측 요소).
class WidgetCardHeader extends StatelessWidget {
  final IconData icon;
  final Color accent;
  final String title;
  final Widget? trailing;
  final bool showChevron;

  const WidgetCardHeader({
    super.key,
    required this.icon,
    required this.accent,
    required this.title,
    this.trailing,
    this.showChevron = false,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 26,
          height: 26,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: accent.withValues(alpha: 0.14),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Icon(icon, size: 15, color: accent),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: Text(
            title,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              fontSize: 13.5,
              fontWeight: FontWeight.w700,
              color: AppTheme.textPrimary,
            ),
          ),
        ),
        ?trailing,
        if (showChevron && trailing == null)
          Icon(
            Icons.chevron_right,
            size: 18,
            color: AppTheme.textSecondary.withValues(alpha: 0.7),
          ),
      ],
    );
  }
}
