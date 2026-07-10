import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

class AssistantMenuAction {
  final IconData icon;
  final String tooltip;
  final Color color;
  final VoidCallback onTap;

  const AssistantMenuAction({
    required this.icon,
    required this.tooltip,
    required this.color,
    required this.onTap,
  });
}

class DraggableAssistantFab extends StatefulWidget {
  final List<AssistantMenuAction> actions;

  /// 짧은 탭(onTap)과 별개로, 길게 누르면 호출된다.
  final VoidCallback? onLongPress;

  const DraggableAssistantFab({
    super.key,
    required this.actions,
    this.onLongPress,
  });

  @override
  State<DraggableAssistantFab> createState() => _DraggableAssistantFabState();
}

class _DraggableAssistantFabState extends State<DraggableAssistantFab> {
  static const double _buttonSize = 50;
  static const double _menuButtonSize = 46;

  /// 화면 좌/우 엣지와 버튼 사이 여백(AssistiveTouch 스타일 사이드 스냅 위치).
  static const double _edgeMargin = 10;
  static const Duration _snapDuration = Duration(milliseconds: 220);

  Offset? _position;
  bool _open = false;
  bool _isDragging = false;

  void _toggleOpen() => setState(() => _open = !_open);

  void _close() {
    if (_open) setState(() => _open = false);
  }

  /// 하단 여백(메뉴/탭바 회피)과 상단 최소 여백.
  static const double _bottomMargin = 88;
  static const double _topGap = 12;

  /// FAB 를 화면 안으로 보정한다(사이드 스냅 + 상단 인셋 고려).
  /// 초기 프레임처럼 크기가 0이거나 공간이 없으면(upper < lower) clamp 예외가
  /// 나므로, 안전한 기본 위치를 돌려준다.
  Offset _clamp(Offset position, Size size, double topInset) {
    final double minX = _edgeMargin;
    final double maxX = size.width - _buttonSize - _edgeMargin;
    final double minY = topInset + _topGap;
    final double maxY = size.height - _buttonSize - _bottomMargin;
    if (size.width <= 0 || size.height <= 0 || maxX < minX || maxY < minY) {
      return Offset(minX, minY);
    }
    return Offset(
      position.dx.clamp(minX, maxX).toDouble(),
      position.dy.clamp(minY, maxY).toDouble(),
    );
  }

  /// FAB 를 배치할 만큼 레이아웃 크기가 확보됐는지(초기 0크기 프레임 배제).
  bool _hasUsableBounds(Size size) =>
      size.width > _buttonSize + 2 * _edgeMargin &&
      size.height > _buttonSize + _bottomMargin + _topGap;

  void _snapToNearestSide(Size size) {
    final current = _position;
    if (current == null) return;
    final centerX = current.dx + _buttonSize / 2;
    final targetX = centerX < size.width / 2
        ? _edgeMargin
        : size.width - _buttonSize - _edgeMargin;
    setState(() {
      _isDragging = false;
      _position = Offset(targetX, current.dy);
    });
  }

  List<Offset> _menuOffsets(Size size) {
    final position = _position ?? Offset(size.width - 82, size.height - 146);
    final center = position + const Offset(_buttonSize / 2, _buttonSize / 2);
    final topZone = center.dy < size.height * 0.34;
    final leftSide = center.dx < size.width / 2;

    if (topZone) {
      return const [Offset(-58, 78), Offset(0, 92), Offset(58, 78)];
    }

    if (leftSide) {
      return const [Offset(72, -82), Offset(104, -22), Offset(40, -132)];
    }

    return const [Offset(-72, -82), Offset(-104, -22), Offset(-40, -132)];
  }

  @override
  Widget build(BuildContext context) {
    final topInset = MediaQuery.of(context).padding.top;
    return LayoutBuilder(
      builder: (context, constraints) {
        final size = Size(constraints.maxWidth, constraints.maxHeight);
        final position =
            _position ?? Offset(size.width - 82, size.height - 146);
        final safePosition = _clamp(position, size, topInset);
        // 유효한 레이아웃 프레임에서만 위치를 확정한다. 초기 0크기 프레임에서 확정하면
        // FAB 가 좌상단에 고정되어 기본 우하단 위치로 못 가기 때문.
        if (_hasUsableBounds(size) &&
            (_position == null || safePosition != position)) {
          WidgetsBinding.instance.addPostFrameCallback((_) {
            if (mounted) setState(() => _position = safePosition);
          });
        }

        return Stack(
          children: [
            if (_open)
              Positioned.fill(
                child: GestureDetector(
                  onTap: _close,
                  behavior: HitTestBehavior.translucent,
                  child: const SizedBox.expand(),
                ),
              ),
            AssistantSpeedDialMenu(
              open: _open,
              anchor: safePosition,
              buttonSize: _buttonSize,
              menuButtonSize: _menuButtonSize,
              offsets: _menuOffsets(size),
              actions: widget.actions,
              onActionSelected: _close,
            ),
            AnimatedPositioned(
              duration: _isDragging ? Duration.zero : _snapDuration,
              curve: Curves.easeOut,
              left: safePosition.dx,
              top: safePosition.dy,
              child: GestureDetector(
                onTap: _toggleOpen,
                onLongPress: widget.onLongPress,
                onPanStart: (_) => setState(() => _isDragging = true),
                onPanUpdate: (details) {
                  setState(() {
                    _position = _clamp(
                      safePosition + details.delta,
                      size,
                      topInset,
                    );
                  });
                },
                onPanEnd: (_) => _snapToNearestSide(size),
                child: AnimatedOpacity(
                  opacity: (_isDragging || _open) ? 1 : 0.85,
                  duration: const Duration(milliseconds: 180),
                  child: _AssistantMainButton(open: _open, size: _buttonSize),
                ),
              ),
            ),
          ],
        );
      },
    );
  }
}

class AssistantSpeedDialMenu extends StatelessWidget {
  final bool open;
  final Offset anchor;
  final double buttonSize;
  final double menuButtonSize;
  final List<Offset> offsets;
  final List<AssistantMenuAction> actions;
  final VoidCallback onActionSelected;

  const AssistantSpeedDialMenu({
    super.key,
    required this.open,
    required this.anchor,
    required this.buttonSize,
    required this.menuButtonSize,
    required this.offsets,
    required this.actions,
    required this.onActionSelected,
  });

  @override
  Widget build(BuildContext context) {
    final count = math.min(actions.length, offsets.length);
    return Stack(
      children: List.generate(count, (i) {
        final action = actions[i];
        final center =
            anchor +
            Offset(buttonSize / 2, buttonSize / 2) +
            (open ? offsets[i] : Offset.zero);
        return AnimatedPositioned(
          duration: const Duration(milliseconds: 210),
          curve: Curves.easeOutBack,
          left: center.dx - menuButtonSize / 2,
          top: center.dy - menuButtonSize / 2,
          child: AnimatedScale(
            scale: open ? 1 : 0.2,
            duration: const Duration(milliseconds: 180),
            child: AnimatedOpacity(
              opacity: open ? 1 : 0,
              duration: const Duration(milliseconds: 140),
              child: IgnorePointer(
                ignoring: !open,
                child: Tooltip(
                  message: action.tooltip,
                  child: GestureDetector(
                    onTap: () {
                      onActionSelected();
                      action.onTap();
                    },
                    child: Container(
                      width: menuButtonSize,
                      height: menuButtonSize,
                      decoration: BoxDecoration(
                        color: action.color,
                        shape: BoxShape.circle,
                        boxShadow: TossShadow.glow(action.color),
                      ),
                      child: Icon(action.icon, color: Colors.white, size: 22),
                    ),
                  ),
                ),
              ),
            ),
          ),
        );
      }),
    );
  }
}

class _AssistantMainButton extends StatelessWidget {
  final bool open;
  final double size;

  const _AssistantMainButton({required this.open, required this.size});

  @override
  Widget build(BuildContext context) {
    return AnimatedContainer(
      duration: const Duration(milliseconds: 180),
      width: size,
      height: size,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: TossColors.blue500,
        boxShadow: TossShadow.glow(
          TossColors.blue500,
          alpha: open ? 0.32 : 0.22,
          blur: open ? 18 : 12,
        ),
      ),
      child: AnimatedRotation(
        turns: open ? 0.125 : 0,
        duration: const Duration(milliseconds: 180),
        child: Icon(
          open ? Icons.close : Icons.auto_awesome,
          color: Colors.white,
          size: 23,
        ),
      ),
    );
  }
}
