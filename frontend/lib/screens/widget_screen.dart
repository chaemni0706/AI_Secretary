import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../widgets/feature_placeholder_view.dart';

class WidgetScreen extends StatelessWidget {
  const WidgetScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const FeaturePlaceholderView(
      title: '위젯',
      subtitle: '자주 보는 정보를 한눈에',
      icon: Icons.dashboard_customize_outlined,
      color: AppTheme.purple,
      message: '일정, 할 일, 알림 위젯을 이곳에서 관리할 수 있도록 준비 중입니다.',
    );
  }
}
