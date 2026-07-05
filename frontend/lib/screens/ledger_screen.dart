import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../widgets/feature_placeholder_view.dart';

class LedgerScreen extends StatelessWidget {
  const LedgerScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const FeaturePlaceholderView(
      title: '가계부',
      subtitle: '소비와 예산 흐름 관리',
      icon: Icons.account_balance_wallet_outlined,
      color: AppTheme.orange,
      message: '지출 내역과 예산 알림을 확인하는 화면을 준비 중입니다.',
    );
  }
}
