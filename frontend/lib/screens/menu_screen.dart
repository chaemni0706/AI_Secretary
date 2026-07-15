import 'package:flutter/material.dart';
import '../theme/app_constants.dart';
import '../theme/app_theme.dart';
import '../widgets/glass_card.dart';
import 'briefing_screen.dart';
import 'hotword_control_screen.dart';
import 'booking_recommend_screen.dart';
import 'booking_message_screen.dart';
import 'voice_chat_screen.dart';
import 'voice_schedule_screen.dart';
import 'mock_call_alert_screen.dart';
import 'user_preference_screen.dart';
import 'image_verification_screen.dart';

class MenuScreen extends StatefulWidget {
  final bool isDrawer;

  const MenuScreen({super.key, this.isDrawer = false});

  @override
  State<MenuScreen> createState() => _MenuScreenState();
}

class _MenuScreenState extends State<MenuScreen> {
  final _searchController = TextEditingController();
  String _query = '';

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  bool _matches(String text) {
    if (_query.isEmpty) return true;
    return text.toLowerCase().contains(_query.toLowerCase());
  }

  @override
  Widget build(BuildContext context) {
    final mvpItems = _mvpItems(
      context,
    ).where((item) => _matches(item.title) || _matches(item.subtitle)).toList();
    final voiceItems = _voiceItems(
      context,
    ).where((item) => _matches(item.title) || _matches(item.subtitle)).toList();
    final extendedItems = _extendedItems
        .where((t) => _matches(t.$3))
        .toList();
    final settingsItems = _settingsItems(
      context,
    ).where((t) => _matches(t.$2)).toList();
    final noResults =
        _query.isNotEmpty &&
        mvpItems.isEmpty &&
        voiceItems.isEmpty &&
        extendedItems.isEmpty &&
        settingsItems.isEmpty;

    return Material(
      color: Colors.transparent,
      child: Container(
        decoration: widget.isDrawer
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
                if (noResults)
                  SliverToBoxAdapter(child: _buildNoResults())
                else ...[
                  if (mvpItems.isNotEmpty)
                    SliverToBoxAdapter(
                      child: _buildSection(title: 'MVP 기능', items: mvpItems),
                    ),
                  if (voiceItems.isNotEmpty)
                    SliverToBoxAdapter(
                      child: _buildSection(
                        title: 'AI 음성 비서',
                        items: voiceItems,
                      ),
                    ),
                  if (extendedItems.isNotEmpty)
                    SliverToBoxAdapter(
                      child: _buildExtendedSection(extendedItems),
                    ),
                  if (settingsItems.isNotEmpty)
                    SliverToBoxAdapter(
                      child: _buildSettingsSection(settingsItems),
                    ),
                ],
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
    if (widget.isDrawer) {
      Navigator.of(context).pop();
    }
    rootNavigator.push(MaterialPageRoute(builder: (_) => screen));
  }

  Widget _buildHeader(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 16, 4),
      child: Row(
        children: [
          Expanded(
            child: Text(
              '전체',
              style: AppTextStyles.screenTitle.copyWith(
                color: AppTheme.textPrimary,
              ),
            ),
          ),
          if (widget.isDrawer)
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
          boxShadow: TossShadow.tiny,
        ),
        child: TextField(
          controller: _searchController,
          onChanged: (value) => setState(() => _query = value.trim()),
          style: const TextStyle(fontSize: 14, color: AppTheme.textPrimary),
          decoration: InputDecoration(
            hintText: '기능 검색',
            hintStyle: const TextStyle(
              fontSize: 14,
              color: AppTheme.textSecondary,
            ),
            prefixIcon: const Icon(
              Icons.search,
              color: AppTheme.textSecondary,
              size: 20,
            ),
            suffixIcon: _query.isEmpty
                ? null
                : IconButton(
                    icon: const Icon(
                      Icons.close,
                      color: AppTheme.textSecondary,
                      size: 18,
                    ),
                    onPressed: () => setState(() {
                      _searchController.clear();
                      _query = '';
                    }),
                  ),
            border: InputBorder.none,
            contentPadding: const EdgeInsets.symmetric(
              horizontal: 16,
              vertical: 13,
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildNoResults() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 40, 16, 0),
      child: Center(
        child: Text(
          '"$_query" 에 대한 검색 결과가 없습니다.',
          style: const TextStyle(fontSize: 14, color: AppTheme.textSecondary),
        ),
      ),
    );
  }

  List<_MenuItem> _mvpItems(BuildContext context) => [
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
      icon: Icons.photo_camera_outlined,
      color: AppTheme.purple,
      title: '이미지 인증',
      subtitle: '물·운동·공부 사진 인증',
      onTap: () => _openService(context, const ImageVerificationScreen()),
    ),
    _MenuItem(
      icon: Icons.backpack_outlined,
      color: AppTheme.orange,
      title: '준비물·출발 알림',
      subtitle: '설정',
      onTap: () {},
    ),
  ];

  List<_MenuItem> _voiceItems(BuildContext context) => [
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
      icon: Icons.record_voice_over_outlined,
      color: AppTheme.green,
      title: '음성 비서 (포비)',
      subtitle: '"포비" 로 브리핑 호출',
      onTap: () => _openService(context, const HotwordControlScreen()),
    ),
    _MenuItem(
      icon: Icons.phone_in_talk_outlined,
      color: AppTheme.teal,
      title: AppStrings.callAlertTitle(),
      subtitle: '일정 전 음성 알림',
      onTap: () => _openService(context, const MockCallAlertScreen()),
    ),
  ];

  static final List<(IconData, Color, String)> _extendedItems = [
    (Icons.favorite_outline, AppTheme.red, '감정 기반 생활 코칭'),
    (Icons.photo_camera_outlined, AppTheme.purple, '이미지 기반 생활 관리'),
    (Icons.psychology_outlined, AppTheme.blue, '개인 맞춤 메모리'),
    (Icons.group_outlined, AppTheme.teal, '인간관계 관리'),
    (Icons.account_balance_wallet_outlined, AppTheme.orange, '소비·알림 관리'),
  ];

  List<(IconData, String, Color, VoidCallback?)> _settingsItems(
    BuildContext context,
  ) => [
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

  Widget _buildSection({
    required String title,
    required List<_MenuItem> items,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SectionHeader(title: title),
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 0),
          child: _MenuList(items: items),
        ),
      ],
    );
  }

  Widget _buildExtendedSection(List<(IconData, Color, String)> items) {
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
                              color: color.withValues(alpha: 0.12),
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
                              color: AppTheme.textSecondary.withValues(
                                alpha: 0.1,
                              ),
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

  Widget _buildSettingsSection(
    List<(IconData, String, Color, VoidCallback?)> settings,
  ) {
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
