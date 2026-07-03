import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../widgets/glass_card.dart';
import 'briefing_screen.dart';
import 'booking_recommend_screen.dart';
import 'booking_message_screen.dart';
import 'daily_briefing_screen.dart';
import 'voice_chat_screen.dart';
import 'voice_schedule_screen.dart';
import 'mock_call_alert_screen.dart';

class MenuScreen extends StatelessWidget {
  const MenuScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: AppTheme.screenBackground,
      child: SafeArea(
        child: CustomScrollView(
          physics: const BouncingScrollPhysics(),
          slivers: [
            SliverToBoxAdapter(child: _buildHeader()),
            SliverToBoxAdapter(child: _buildSearchBar()),
            SliverToBoxAdapter(child: _buildMvpSection(context)),
            SliverToBoxAdapter(child: _buildVoiceSection(context)),
            SliverToBoxAdapter(child: _buildExtendedSection()),
            SliverToBoxAdapter(child: _buildSettingsSection()),
            const SliverToBoxAdapter(child: SizedBox(height: 80)),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return const Padding(
      padding: EdgeInsets.fromLTRB(20, 16, 20, 4),
      child: Text(
        '전체',
        style: TextStyle(
          fontSize: 26,
          fontWeight: FontWeight.w700,
          color: AppTheme.textPrimary,
          letterSpacing: -0.5,
        ),
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
            hintStyle:
                TextStyle(fontSize: 14, color: AppTheme.textSecondary),
            prefixIcon:
                Icon(Icons.search, color: AppTheme.textSecondary, size: 20),
            border: InputBorder.none,
            contentPadding:
                EdgeInsets.symmetric(horizontal: 16, vertical: 13),
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
        onTap: () => Navigator.push(
          context,
          MaterialPageRoute(builder: (_) => const BriefingScreen()),
        ),
      ),
      _MenuItem(
        icon: Icons.event_available_outlined,
        color: AppTheme.green,
        title: '예약 후보 추천',
        subtitle: '빈 시간 찾기',
        onTap: () => Navigator.push(
          context,
          MaterialPageRoute(builder: (_) => const BookingRecommendScreen()),
        ),
      ),
      _MenuItem(
        icon: Icons.forum_outlined,
        color: AppTheme.teal,
        title: '예약 메시지',
        subtitle: '정중한 문의 생성',
        onTap: () => Navigator.push(
          context,
          MaterialPageRoute(builder: (_) => const BookingMessageScreen()),
        ),
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
          child: GridView.count(
            crossAxisCount: 2,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            crossAxisSpacing: 10,
            mainAxisSpacing: 10,
            childAspectRatio: 2.2,
            children: items
                .map((item) => _MenuCard(item: item))
                .toList(),
          ),
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
        onTap: () => Navigator.push(
          context,
          MaterialPageRoute(builder: (_) => const VoiceScheduleScreen()),
        ),
      ),
      _MenuItem(
        icon: Icons.wb_sunny_outlined,
        color: AppTheme.blue,
        title: '오늘의 브리핑',
        subtitle: '하루 요약·듣기',
        onTap: () => Navigator.push(
          context,
          MaterialPageRoute(builder: (_) => const DailyBriefingScreen()),
        ),
      ),
      _MenuItem(
        icon: Icons.mic_none_outlined,
        color: AppTheme.purple,
        title: 'AI 음성 챗봇',
        subtitle: '감정 기반 코칭',
        onTap: () => Navigator.push(
          context,
          MaterialPageRoute(builder: (_) => const VoiceChatScreen()),
        ),
      ),
      _MenuItem(
        icon: Icons.phone_in_talk_outlined,
        color: AppTheme.teal,
        title: '챔니 전화 알림',
        subtitle: '일정 전 음성 알림',
        onTap: () => Navigator.push(
          context,
          MaterialPageRoute(builder: (_) => const MockCallAlertScreen()),
        ),
      ),
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SectionHeader(title: 'AI 음성 비서'),
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 0),
          child: GridView.count(
            crossAxisCount: 2,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            crossAxisSpacing: 10,
            mainAxisSpacing: 10,
            childAspectRatio: 1.5,
            children: items.map((item) => _MenuCard(item: item)).toList(),
          ),
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
                          horizontal: 16, vertical: 12),
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
                                horizontal: 8, vertical: 3),
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

  Widget _buildSettingsSection() {
    final settings = [
      (Icons.notifications_outlined, '알림 설정', AppTheme.blue),
      (Icons.security_outlined, '개인정보 보호', AppTheme.textSecondary),
      (Icons.help_outline, '도움말', AppTheme.textSecondary),
      (Icons.info_outline, '앱 정보', AppTheme.textSecondary),
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
                final (icon, title, color) = settings[i];
                return Column(
                  children: [
                    Padding(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 16, vertical: 14),
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
                          const Icon(Icons.chevron_right,
                              color: AppTheme.textSecondary, size: 20),
                        ],
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

class _MenuCard extends StatelessWidget {
  final _MenuItem item;

  const _MenuCard({required this.item});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: item.onTap,
      child: GlassCard(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        child: Row(
          children: [
            Container(
              width: 32,
              height: 32,
              decoration: BoxDecoration(
                color: item.color.withOpacity(0.14),
                borderRadius: BorderRadius.circular(9),
              ),
              child: Icon(item.icon, color: item.color, size: 18),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(item.title, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: AppTheme.textPrimary), maxLines: 1, overflow: TextOverflow.ellipsis),
                  const SizedBox(height: 2),
                  Text(item.subtitle, style: const TextStyle(fontSize: 10, color: AppTheme.textSecondary)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
