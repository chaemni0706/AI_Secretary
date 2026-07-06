import 'package:flutter/material.dart';
import '../data/mock_profile_data.dart';
import '../theme/app_constants.dart';
import '../theme/app_theme.dart';
import '../widgets/glass_card.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  String _assistantTone = mockUserProfile.assistantTone;

  static const _toneOptions = ['공손한', '친근한', '간결한', '사려 깊은', '전문적인'];

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: AppTheme.screenBackground,
      child: Scaffold(
        backgroundColor: Colors.transparent,
        appBar: AppBar(title: const Text('설정'), centerTitle: false),
        body: SafeArea(
          top: false,
          child: ListView(
            physics: const BouncingScrollPhysics(),
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
            children: [
              _SettingsSection(
                title: 'AI 비서 말투 설정',
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 10,
                      ),
                      decoration: BoxDecoration(
                        color: AppTheme.blue.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(AppRadii.control),
                      ),
                      child: Row(
                        children: [
                          const Icon(
                            Icons.record_voice_over_outlined,
                            color: AppTheme.blue,
                            size: 19,
                          ),
                          const SizedBox(width: 8),
                          Text(
                            '현재 말투: $_assistantTone',
                            style: AppTextStyles.cardTitle.copyWith(
                              color: AppTheme.blue,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 12),
                    ..._toneOptions.map(
                      (tone) => _ToneOptionCard(
                        label: tone,
                        selected: _assistantTone == tone,
                        onTap: () => setState(() => _assistantTone = tone),
                      ),
                    ),
                  ],
                ),
              ),
              _SettingsSection(
                title: '일반',
                child: Column(
                  children: const [
                    _SettingsRow(
                      icon: Icons.notifications_outlined,
                      title: '알림 설정',
                      subtitle: '일정과 할 일 알림 방식',
                    ),
                    _SettingsRow(
                      icon: Icons.dark_mode_outlined,
                      title: '화면/테마 설정',
                      subtitle: '밝기와 화면 표시 방식',
                    ),
                    _SettingsRow(
                      icon: Icons.privacy_tip_outlined,
                      title: '개인정보 관리',
                      subtitle: '개인 특성 정보와 권한',
                    ),
                    _SettingsRow(
                      icon: Icons.info_outline,
                      title: '앱 정보',
                      subtitle: '버전과 이용 안내',
                    ),
                    _SettingsRow(
                      icon: Icons.logout,
                      title: '로그아웃',
                      subtitle: '현재 계정에서 나가기',
                      destructive: true,
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _SettingsSection extends StatelessWidget {
  final String title;
  final Widget child;

  const _SettingsSection({required this.title, required this.child});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(4, 6, 4, 8),
            child: Text(
              title,
              style: AppTextStyles.sectionTitle.copyWith(
                color: AppTheme.textPrimary,
              ),
            ),
          ),
          GlassCard(padding: const EdgeInsets.all(14), child: child),
        ],
      ),
    );
  }
}

class _ToneOptionCard extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback onTap;

  const _ToneOptionCard({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(AppRadii.control),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 11),
          decoration: BoxDecoration(
            color: selected
                ? AppTheme.blue.withValues(alpha: 0.12)
                : Colors.white.withValues(alpha: 0.55),
            borderRadius: BorderRadius.circular(AppRadii.control),
            border: Border.all(
              color: selected ? AppTheme.blue : AppTheme.separator,
              width: selected ? 1.2 : 1,
            ),
          ),
          child: Row(
            children: [
              Icon(
                selected
                    ? Icons.radio_button_checked
                    : Icons.radio_button_unchecked,
                color: selected ? AppTheme.blue : AppTheme.textSecondary,
                size: 20,
              ),
              const SizedBox(width: 10),
              Text(
                label,
                style: AppTextStyles.cardTitle.copyWith(
                  color: selected ? AppTheme.blue : AppTheme.textPrimary,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _SettingsRow extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  final bool destructive;

  const _SettingsRow({
    required this.icon,
    required this.title,
    required this.subtitle,
    this.destructive = false,
  });

  @override
  Widget build(BuildContext context) {
    final color = destructive ? AppTheme.red : AppTheme.textPrimary;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 10),
      child: Row(
        children: [
          Icon(icon, color: color, size: 21),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: AppTextStyles.cardTitle.copyWith(color: color),
                ),
                const SizedBox(height: 2),
                Text(
                  subtitle,
                  style: AppTextStyles.meta.copyWith(
                    color: AppTheme.textSecondary,
                  ),
                ),
              ],
            ),
          ),
          const Icon(
            Icons.chevron_right,
            color: AppTheme.textSecondary,
            size: 20,
          ),
        ],
      ),
    );
  }
}
