import 'package:flutter/material.dart';
import '../services/preference_store.dart';
import '../services/user_preferences_api.dart';
import '../theme/app_constants.dart';
import '../theme/app_theme.dart';
import '../widgets/glass_card.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  // 백엔드 assistant_tone 코드 ↔ 표시명(backend/data/tone_profiles.json 기준, 5종).
  // Map 리터럴은 삽입 순서를 보존하므로 그대로 옵션 순서로 쓴다.
  static const Map<String, String> _tones = {
    'polite': '정중한 비서',
    'friendly': '친근한 비서',
    'concise': '짧고 간결한 비서',
    'caring': '공감형 비서',
    'professional': '업무형 비서',
  };

  // 서버 동기화된 현재 말투 코드(preferenceStore 는 앱 시작 시 /user/preferences 로 로드됨).
  String _toneCode = preferenceStore.assistantTone;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    // 방어적으로 한 번 더 로드해 최신 서버 값 반영.
    preferenceStore.ensureLoaded().then((_) {
      if (mounted) setState(() => _toneCode = preferenceStore.assistantTone);
    });
  }

  String get _toneLabel => _tones[_toneCode] ?? _toneCode;

  Future<void> _selectTone(String code) async {
    if (code == _toneCode || _saving) return;
    // 즉시 반영(로컬/캐시) 후 서버 저장(best-effort).
    setState(() {
      _toneCode = code;
      _saving = true;
    });
    preferenceStore.updateLocal(assistantTone: code);
    try {
      await UserPreferencesApi.update(assistantTone: code);
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('말투를 서버에 저장하지 못했어요. 다음 접속 시 다시 시도됩니다.'),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

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
                            '현재 말투: $_toneLabel',
                            style: AppTextStyles.cardTitle.copyWith(
                              color: AppTheme.blue,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 12),
                    ..._tones.entries.map(
                      (e) => _ToneOptionCard(
                        label: e.value,
                        selected: _toneCode == e.key,
                        onTap: () => _selectTone(e.key),
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
