import 'package:flutter/material.dart';
import '../data/mock_app_notifications.dart';
import '../theme/app_constants.dart';
import '../theme/app_theme.dart';
import '../widgets/glass_card.dart';

class NotificationListScreen extends StatelessWidget {
  const NotificationListScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: AppTheme.screenBackground,
      child: Scaffold(
        backgroundColor: Colors.transparent,
        appBar: AppBar(title: const Text('앱 알림'), centerTitle: false),
        body: SafeArea(
          top: false,
          child: ListView(
            physics: const BouncingScrollPhysics(),
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
            children: mockAppNotifications
                .map(
                  (item) => Padding(
                    padding: const EdgeInsets.only(bottom: AppSpacing.cardGap),
                    child: GlassCard(
                      padding: const EdgeInsets.all(14),
                      child: Row(
                        children: [
                          Container(
                            width: 38,
                            height: 38,
                            decoration: BoxDecoration(
                              color: item.color.withValues(alpha: 0.14),
                              borderRadius: BorderRadius.circular(
                                AppRadii.small,
                              ),
                            ),
                            child: Icon(item.icon, color: item.color, size: 20),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  item.title,
                                  style: AppTextStyles.cardTitle.copyWith(
                                    color: AppTheme.textPrimary,
                                  ),
                                ),
                                const SizedBox(height: 3),
                                Text(
                                  item.message,
                                  style: AppTextStyles.meta.copyWith(
                                    color: AppTheme.textSecondary,
                                  ),
                                ),
                              ],
                            ),
                          ),
                          Text(
                            item.time,
                            style: AppTextStyles.meta.copyWith(
                              color: AppTheme.textSecondary,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                )
                .toList(),
          ),
        ),
      ),
    );
  }
}
