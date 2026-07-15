import 'package:flutter/material.dart';
import '../screens/menu_screen.dart';
import '../screens/notification_list_screen.dart';
import '../theme/app_constants.dart';
import '../theme/app_theme.dart';

class AppTopActions extends StatelessWidget {
  final VoidCallback? onMenuOpened;

  const AppTopActions({super.key, this.onMenuOpened});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        AppHeaderIconButton(
          icon: Icons.notifications_outlined,
          tooltip: '앱 알림',
          onTap: () {
            Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => const NotificationListScreen()),
            );
          },
        ),
        const SizedBox(width: 8),
        AppHeaderIconButton(
          icon: Icons.menu,
          tooltip: '전체 서비스',
          onTap: () {
            onMenuOpened?.call();
            showGeneralDialog<void>(
              context: context,
              barrierDismissible: true,
              barrierLabel: '전체 서비스 닫기',
              barrierColor: Colors.black.withValues(alpha: 0.24),
              transitionDuration: const Duration(milliseconds: 260),
              pageBuilder: (context, animation, secondaryAnimation) {
                return const Align(
                  alignment: Alignment.centerRight,
                  child: FractionallySizedBox(
                    widthFactor: 0.86,
                    heightFactor: 1,
                    child: MenuScreen(isDrawer: true),
                  ),
                );
              },
              transitionBuilder:
                  (context, animation, secondaryAnimation, child) {
                    final curved = CurvedAnimation(
                      parent: animation,
                      curve: Curves.easeOutCubic,
                      reverseCurve: Curves.easeInCubic,
                    );
                    return SlideTransition(
                      position: Tween<Offset>(
                        begin: const Offset(1, 0),
                        end: Offset.zero,
                      ).animate(curved),
                      child: child,
                    );
                  },
            );
          },
        ),
      ],
    );
  }
}

class AppHeaderIconButton extends StatelessWidget {
  final IconData icon;
  final String tooltip;
  final VoidCallback? onTap;

  const AppHeaderIconButton({
    super.key,
    required this.icon,
    required this.tooltip,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: tooltip,
      child: GestureDetector(
        onTap: onTap,
        behavior: HitTestBehavior.opaque,
        child: SizedBox(
          width: AppSpacing.iconButton,
          height: AppSpacing.iconButton,
          child: Icon(icon, color: TossColors.grey700, size: 22),
        ),
      ),
    );
  }
}
