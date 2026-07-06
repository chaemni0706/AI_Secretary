import 'package:flutter/material.dart';
import '../data/mock_profile_data.dart';
import '../theme/app_constants.dart';
import '../theme/app_theme.dart';
import '../widgets/app_top_actions.dart';
import '../widgets/glass_card.dart';
import '../widgets/my_page_menu_card.dart';
import 'profile_edit_screen.dart';
import 'settings_screen.dart';

class MyPageScreen extends StatelessWidget {
  const MyPageScreen({super.key});

  void _open(BuildContext context, Widget screen) {
    Navigator.push(context, MaterialPageRoute(builder: (_) => screen));
  }

  void _showProfileImageMessage(BuildContext context) {
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(const SnackBar(content: Text('프로필 이미지 변경 기능은 준비 중입니다.')));
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: AppTheme.screenBackground,
      child: SafeArea(
        child: ListView(
          physics: const BouncingScrollPhysics(),
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 96),
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(4, 16, 4, 8),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      '마이페이지',
                      style: AppTextStyles.screenTitle.copyWith(
                        color: AppTheme.textPrimary,
                      ),
                    ),
                  ),
                  const AppTopActions(),
                ],
              ),
            ),
            _ProfileCard(onEditImage: () => _showProfileImageMessage(context)),
            const SizedBox(height: 14),
            MyPageMenuCard(
              icon: Icons.edit_outlined,
              color: AppTheme.blue,
              title: '개인정보 수정',
              subtitle: '성격, 직업, 생활 패턴을 관리해요',
              onTap: () => _open(context, const ProfileEditScreen()),
            ),
            MyPageMenuCard(
              icon: Icons.photo_camera_outlined,
              color: AppTheme.purple,
              title: '프로필 이미지 변경',
              subtitle: '나를 나타내는 이미지를 바꿔요',
              onTap: () => _showProfileImageMessage(context),
            ),
            MyPageMenuCard(
              icon: Icons.settings_outlined,
              color: AppTheme.textTertiary,
              title: '설정',
              subtitle: '알림, 테마, AI 비서 말투 설정',
              onTap: () => _open(context, const SettingsScreen()),
            ),
            MyPageMenuCard(
              icon: Icons.notifications_outlined,
              color: AppTheme.orange,
              title: '알림 관리',
              subtitle: '중요 일정과 할 일 알림을 조정해요',
              onTap: () {},
            ),
            MyPageMenuCard(
              icon: Icons.storage_outlined,
              color: AppTheme.teal,
              title: '데이터 관리',
              subtitle: '앱 데이터와 연동 상태를 확인해요',
              onTap: () {},
            ),
            MyPageMenuCard(
              icon: Icons.info_outline,
              color: AppTheme.green,
              title: '앱 정보',
              subtitle: '버전과 이용 정보를 확인해요',
              onTap: () {},
            ),
          ],
        ),
      ),
    );
  }
}

class _ProfileCard extends StatelessWidget {
  final VoidCallback onEditImage;

  const _ProfileCard({required this.onEditImage});

  @override
  Widget build(BuildContext context) {
    return GlassCard(
      padding: const EdgeInsets.all(16),
      child: Row(
        children: [
          Stack(
            clipBehavior: Clip.none,
            children: [
              Container(
                width: 76,
                height: 76,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: const LinearGradient(
                    colors: [AppTheme.teal, AppTheme.blue],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                  boxShadow: [
                    BoxShadow(
                      color: AppTheme.blue.withValues(alpha: 0.16),
                      blurRadius: 12,
                      offset: const Offset(0, 4),
                    ),
                  ],
                ),
                child: const Icon(Icons.person, color: Colors.white, size: 38),
              ),
              Positioned(
                right: -2,
                bottom: -2,
                child: GestureDetector(
                  onTap: onEditImage,
                  child: Container(
                    width: 30,
                    height: 30,
                    decoration: BoxDecoration(
                      color: AppTheme.textPrimary,
                      shape: BoxShape.circle,
                      border: Border.all(color: Colors.white, width: 2),
                    ),
                    child: const Icon(
                      Icons.photo_camera_outlined,
                      color: Colors.white,
                      size: 15,
                    ),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '${mockUserProfile.name}님',
                  style: const TextStyle(
                    fontSize: 22,
                    fontWeight: FontWeight.w800,
                    color: AppTheme.textPrimary,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  mockUserProfile.greeting,
                  style: AppTextStyles.meta.copyWith(
                    color: AppTheme.textSecondary,
                    height: 1.35,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
