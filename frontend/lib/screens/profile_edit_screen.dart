import 'package:flutter/material.dart';
import '../data/mock_profile_data.dart';
import '../theme/app_constants.dart';
import '../theme/app_theme.dart';
import '../widgets/glass_card.dart';

class ProfileEditScreen extends StatefulWidget {
  const ProfileEditScreen({super.key});

  @override
  State<ProfileEditScreen> createState() => _ProfileEditScreenState();
}

class _ProfileEditScreenState extends State<ProfileEditScreen> {
  late final TextEditingController _personalityController;
  late final TextEditingController _jobController;
  late final TextEditingController _ageController;
  late final TextEditingController _genderController;
  late final TextEditingController _lifePatternController;
  late final TextEditingController _notificationController;
  late final TextEditingController _interestsController;

  @override
  void initState() {
    super.initState();
    _personalityController = TextEditingController(
      text: mockUserProfile.personality,
    );
    _jobController = TextEditingController(text: mockUserProfile.job);
    _ageController = TextEditingController(text: mockUserProfile.age);
    _genderController = TextEditingController(text: mockUserProfile.gender);
    _lifePatternController = TextEditingController(
      text: mockUserProfile.lifePattern,
    );
    _notificationController = TextEditingController(
      text: mockUserProfile.notificationPreference,
    );
    _interestsController = TextEditingController(
      text: mockUserProfile.interests.join(', '),
    );
  }

  @override
  void dispose() {
    _personalityController.dispose();
    _jobController.dispose();
    _ageController.dispose();
    _genderController.dispose();
    _lifePatternController.dispose();
    _notificationController.dispose();
    _interestsController.dispose();
    super.dispose();
  }

  void _save() {
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(const SnackBar(content: Text('개인정보 저장 연동을 준비 중입니다.')));
    Navigator.pop(context);
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: AppTheme.screenBackground,
      child: Scaffold(
        backgroundColor: Colors.transparent,
        appBar: AppBar(title: const Text('개인정보 수정'), centerTitle: false),
        body: SafeArea(
          top: false,
          child: ListView(
            physics: const BouncingScrollPhysics(),
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
            children: [
              GlassCard(
                padding: const EdgeInsets.all(16),
                child: Column(
                  children: [
                    _ProfileField(
                      label: '성격',
                      controller: _personalityController,
                      icon: Icons.psychology_outlined,
                    ),
                    _ProfileField(
                      label: '직업',
                      controller: _jobController,
                      icon: Icons.work_outline,
                    ),
                    _ProfileField(
                      label: '나이',
                      controller: _ageController,
                      icon: Icons.cake_outlined,
                    ),
                    _ProfileField(
                      label: '성별',
                      controller: _genderController,
                      icon: Icons.person_outline,
                    ),
                    _ProfileField(
                      label: '생활 패턴',
                      controller: _lifePatternController,
                      icon: Icons.schedule_outlined,
                    ),
                    _ProfileField(
                      label: '선호 알림 방식',
                      controller: _notificationController,
                      icon: Icons.notifications_outlined,
                    ),
                    _ProfileField(
                      label: '주요 관심 카테고리',
                      controller: _interestsController,
                      icon: Icons.interests_outlined,
                      maxLines: 2,
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 14),
              FilledButton(
                onPressed: _save,
                style: FilledButton.styleFrom(
                  backgroundColor: AppTheme.blue,
                  foregroundColor: Colors.white,
                ),
                child: const Text('저장'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ProfileField extends StatelessWidget {
  final String label;
  final TextEditingController controller;
  final IconData icon;
  final int maxLines;

  const _ProfileField({
    required this.label,
    required this.controller,
    required this.icon,
    this.maxLines = 1,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: TextField(
        controller: controller,
        maxLines: maxLines,
        decoration: InputDecoration(
          labelText: label,
          prefixIcon: Icon(icon, size: 20),
          filled: true,
          fillColor: Colors.white.withValues(alpha: 0.7),
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(AppRadii.control),
            borderSide: const BorderSide(color: AppTheme.separator),
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(AppRadii.control),
            borderSide: const BorderSide(color: AppTheme.separator),
          ),
        ),
      ),
    );
  }
}
