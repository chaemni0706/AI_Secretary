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

  const DraggableAssistantFab({super.key, required this.actions});

  @override
  State<DraggableAssistantFab> createState() => _DraggableAssistantFabState();
}

class _DraggableAssistantFabState extends State<DraggableAssistantFab> {
  static const double _buttonSize = 58;
  static const double _menuButtonSize = 46;
  Offset? _position;
  bool _open = false;

  void _toggleOpen() => setState(() => _open = !_open);

  void _close() {
    if (_open) setState(() => _open = false);
  }

  Offset _clamp(Offset position, Size size) {
    return Offset(
      position.dx.clamp(12, size.width - _buttonSize - 12),
      position.dy.clamp(12, size.height - _buttonSize - 88),
    );
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
    return LayoutBuilder(
      builder: (context, constraints) {
        final size = Size(constraints.maxWidth, constraints.maxHeight);
        final position =
            _position ?? Offset(size.width - 82, size.height - 146);
        final safePosition = _clamp(position, size);
        if (_position == null || safePosition != position) {
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
            Positioned(
              left: safePosition.dx,
              top: safePosition.dy,
              child: GestureDetector(
                onTap: _toggleOpen,
                onPanUpdate: (details) {
                  setState(() {
                    _position = _clamp(safePosition + details.delta, size);
                  });
                },
                child: _AssistantMainButton(open: _open, size: _buttonSize),
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
                        boxShadow: [
                          BoxShadow(
                            color: action.color.withValues(alpha: 0.28),
                            blurRadius: 14,
                            offset: const Offset(0, 5),
                          ),
                        ],
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
        gradient: const LinearGradient(
          colors: [AppTheme.purple, AppTheme.blue],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        boxShadow: [
          BoxShadow(
            color: AppTheme.blue.withValues(alpha: open ? 0.32 : 0.22),
            blurRadius: open ? 22 : 16,
            offset: const Offset(0, 7),
          ),
        ],
      ),
      child: AnimatedRotation(
        turns: open ? 0.125 : 0,
        duration: const Duration(milliseconds: 180),
        child: Icon(
          open ? Icons.close : Icons.auto_awesome,
          color: Colors.white,
          size: 27,
        ),
      ),
    );
  }
}
