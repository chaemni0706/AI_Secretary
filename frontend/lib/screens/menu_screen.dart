import 'package:flutter/material.dart';
import '../theme/app_constants.dart';
import '../theme/app_theme.dart';
import '../widgets/glass_card.dart';
import 'briefing_screen.dart';
import 'booking_recommend_screen.dart';
import 'booking_message_screen.dart';
import 'voice_chat_screen.dart';
import 'voice_schedule_screen.dart';
import 'mock_call_alert_screen.dart';
import 'user_preference_screen.dart';

class MenuScreen extends StatelessWidget {
  final bool isDrawer;

  const MenuScreen({super.key, this.isDrawer = false});

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: Container(
        decoration: isDrawer
            ? const BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.horizontal(
                  left: Radius.circular(24),
                ),
              )
            : AppTheme.screenBackground,
        child: Scaffold(
          backgroundColor: Colors.transparent,
          body: SafeArea(
            child: CustomScrollView(
              physics: const BouncingScrollPhysics(),
              slivers: [
                SliverToBoxAdapter(child: _buildHeader(context)),
                SliverToBoxAdapter(child: _buildSearchBar()),
                SliverToBoxAdapter(child: _buildMvpSection(context)),
                SliverToBoxAdapter(child: _buildVoiceSection(context)),
                SliverToBoxAdapter(child: _buildExtendedSection()),
                SliverToBoxAdapter(child: _buildSettingsSection(context)),
                const SliverToBoxAdapter(child: SizedBox(height: 80)),
              ],
            ),
          ),
        ),
      ),
    );
  }

  void _openService(BuildContext context, Widget screen) {
    final rootNavigator = Navigator.of(context, rootNavigator: true);
    if (isDrawer) {
      Navigator.of(context).pop();
    }
    rootNavigator.push(MaterialPageRoute(builder: (_) => screen));
  }

  Widget _buildHeader(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 16, 4),
      child: Row(
        children: [
          const Expanded(
            child: Text(
              '전체',
              style: TextStyle(
                fontSize: 26,
                fontWeight: FontWeight.w700,
                color: AppTheme.textPrimary,
                letterSpacing: -0.5,
              ),
            ),
          ),
          if (isDrawer)
            IconButton(
              onPressed: () => Navigator.pop(context),
              icon: const Icon(Icons.close, color: AppTheme.textPrimary),
              tooltip: '닫기',
            ),
        ],
      ),
    );
  }

  Widget _buildSearchBar() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
      child: Container(
        decoration: BoxDecoration(
          color: const Color(0xFFEEEFF5),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: AppTheme.separator),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.04),
              blurRadius: 8,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: const TextField(
          style: TextStyle(fontSize: 14, color: AppTheme.textPrimary),
          decoration: InputDecoration(
            hintText: '기능 검색',
            hintStyle: TextStyle(fontSize: 14, color: AppTheme.textSecondary),
            prefixIcon: Icon(
              Icons.search,
              color: AppTheme.textSecondary,
              size: 20,
            ),
            border: InputBorder.none,
            contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 13),
          ),
        ),
      ),
    );
  }

  Widget _buildMvpSection(BuildContext context) {
    final items = [
      _MenuItem(
        icon: Icons.summarize_outlined,
        color: AppTheme.blue,
        title: '브리핑 상세',
        subtitle: '오늘 요약·주의사항',
        onTap: () => _openService(context, const BriefingScreen()),
      ),
      _MenuItem(
        icon: Icons.event_available_outlined,
        color: AppTheme.green,
        title: '예약 후보 추천',
        subtitle: '빈 시간 찾기',
        onTap: () => _openService(context, const BookingRecommendScreen()),
      ),
      _MenuItem(
        icon: Icons.forum_outlined,
        color: AppTheme.teal,
        title: '예약 메시지',
        subtitle: '정중한 문의 생성',
        onTap: () => _openService(context, const BookingMessageScreen()),
      ),
      _MenuItem(
        icon: Icons.backpack_outlined,
        color: AppTheme.orange,
        title: '준비물·출발 알림',
        subtitle: '설정',
        onTap: () {},
      ),
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SectionHeader(title: 'MVP 기능'),
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 0),
          child: _MenuList(items: items),
        ),
      ],
    );
  }

  Widget _buildVoiceSection(BuildContext context) {
    final items = [
      _MenuItem(
        icon: Icons.mic_external_on_outlined,
        color: AppTheme.blue,
        title: '음성으로 일정 만들기',
        subtitle: '말하면 일정 등록',
        onTap: () => _openService(context, const VoiceScheduleScreen()),
      ),
      _MenuItem(
        icon: Icons.wb_sunny_outlined,
        color: AppTheme.blue,
        title: '오늘의 브리핑',
        subtitle: '하루 요약·듣기',
        onTap: () => _openService(context, const BriefingScreen()),
      ),
      _MenuItem(
        icon: Icons.mic_none_outlined,
        color: AppTheme.purple,
        title: 'AI 음성 챗봇',
        subtitle: '감정 기반 코칭',
        onTap: () => _openService(context, const VoiceChatScreen()),
      ),
      _MenuItem(
        icon: Icons.phone_in_talk_outlined,
        color: AppTheme.teal,
        title: AppStrings.callAlertTitle(),
        subtitle: '일정 전 음성 알림',
        onTap: () => _openService(context, const MockCallAlertScreen()),
      ),
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SectionHeader(title: 'AI 음성 비서'),
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 0),
          child: _MenuList(items: items),
        ),
      ],
    );
  }

  Widget _buildExtendedSection() {
    final items = [
      (Icons.favorite_outline, AppTheme.red, '감정 기반 생활 코칭'),
      (Icons.photo_camera_outlined, AppTheme.purple, '이미지 기반 생활 관리'),
      (Icons.psychology_outlined, AppTheme.blue, '개인 맞춤 메모리'),
      (Icons.group_outlined, AppTheme.teal, '인간관계 관리'),
      (Icons.account_balance_wallet_outlined, AppTheme.orange, '소비·알림 관리'),
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SectionHeader(title: '확장 기능 · 곧 제공'),
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 0),
          child: GlassCard(
            padding: EdgeInsets.zero,
            child: Column(
              children: List.generate(items.length, (i) {
                final (icon, color, title) = items[i];
                return Column(
                  children: [
                    Padding(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 16,
                        vertical: 12,
                      ),
                      child: Row(
                        children: [
                          Container(
                            width: 36,
                            height: 36,
                            decoration: BoxDecoration(
                              color: color.withOpacity(0.12),
                              borderRadius: BorderRadius.circular(10),
                            ),
                            child: Icon(icon, color: color, size: 18),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Text(
                              title,
                              style: const TextStyle(
                                fontSize: 14,
                                fontWeight: FontWeight.w500,
                                color: AppTheme.textPrimary,
                              ),
                            ),
                          ),
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 8,
                              vertical: 3,
                            ),
                            decoration: BoxDecoration(
                              color: AppTheme.textSecondary.withOpacity(0.1),
                              borderRadius: BorderRadius.circular(6),
                            ),
                            child: const Text(
                              'SOON',
                              style: TextStyle(
                                fontSize: 10,
                                fontWeight: FontWeight.w700,
                                color: AppTheme.textSecondary,
                                letterSpacing: 0.5,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                    if (i < items.length - 1)
                      const Divider(
                        height: 1,
                        indent: 64,
                        endIndent: 16,
                        color: AppTheme.separator,
                      ),
                  ],
                );
              }),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildSettingsSection(BuildContext context) {
    final settings = [
      (
        Icons.record_voice_over_outlined,
        'AI 음성 스타일',
        AppTheme.blue,
        () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => const UserPreferenceScreen()),
            ),
      ),
      (Icons.notifications_outlined, '알림 설정', AppTheme.blue, null),
      (Icons.security_outlined, '개인정보 보호', AppTheme.textSecondary, null),
      (Icons.help_outline, '도움말', AppTheme.textSecondary, null),
      (Icons.info_outline, '앱 정보', AppTheme.textSecondary, null),
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SectionHeader(title: '설정'),
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 0),
          child: GlassCard(
            padding: EdgeInsets.zero,
            child: Column(
              children: List.generate(settings.length, (i) {
                final (icon, title, color, onTap) = settings[i];
                return Column(
                  children: [
                    InkWell(
                      onTap: onTap,
                      borderRadius: BorderRadius.circular(18),
                      child: Padding(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 16,
                          vertical: 14,
                        ),
                        child: Row(
                          children: [
                            Icon(icon, color: color, size: 22),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Text(
                                title,
                                style: const TextStyle(
                                  fontSize: 14,
                                  fontWeight: FontWeight.w500,
                                  color: AppTheme.textPrimary,
                                ),
                              ),
                            ),
                            const Icon(
                              Icons.chevron_right,
                              color: AppTheme.textSecondary,
                              size: 20,
                            ),
                          ],
                        ),
                      ),
                    ),
                    if (i < settings.length - 1)
                      const Divider(
                        height: 1,
                        indent: 50,
                        endIndent: 0,
                        color: AppTheme.separator,
                      ),
                  ],
                );
              }),
            ),
          ),
        ),
      ],
    );
  }
}

class _MenuItem {
  final IconData icon;
  final Color color;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  const _MenuItem({
    required this.icon,
    required this.color,
    required this.title,
    required this.subtitle,
    required this.onTap,
  });
}

class _MenuList extends StatelessWidget {
  final List<_MenuItem> items;

  const _MenuList({required this.items});

  @override
  Widget build(BuildContext context) {
    return GlassCard(
      padding: EdgeInsets.zero,
      child: Column(
        children: List.generate(items.length, (i) {
          final item = items[i];
          return Column(
            children: [
              InkWell(
                onTap: item.onTap,
                borderRadius: BorderRadius.circular(18),
                child: Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 16,
                    vertical: 13,
                  ),
                  child: Row(
                    children: [
                      Container(
                        width: 38,
                        height: 38,
                        decoration: BoxDecoration(
                          color: item.color.withValues(alpha: 0.14),
                          borderRadius: BorderRadius.circular(10),
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
                              style: const TextStyle(
                                fontSize: 14,
                                fontWeight: FontWeight.w700,
                                color: AppTheme.textPrimary,
                              ),
                            ),
                            const SizedBox(height: 2),
                            Text(
                              item.subtitle,
                              style: const TextStyle(
                                fontSize: 12,
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
                ),
              ),
              if (i < items.length - 1)
                const Divider(
                  height: 1,
                  indent: 66,
                  endIndent: 0,
                  color: AppTheme.separator,
                ),
            ],
          );
        }),
      ),
    );
  }
}
