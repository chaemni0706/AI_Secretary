import 'package:flutter/material.dart';
import '../models/todo_model.dart';
import '../services/dashboard_api.dart';
import '../theme/app_constants.dart';
import '../theme/app_theme.dart';
import '../widgets/glass_card.dart';
import '../models/schedule_model.dart';
import 'schedule_form_screen.dart';
import 'todo_form_screen.dart';
import 'voice_schedule_screen.dart';

class AddItemChoiceScreen extends StatelessWidget {
  const AddItemChoiceScreen({super.key});

  Future<void> _openSchedule(BuildContext context) async {
    final saved = await Navigator.push<ScheduleModel>(
      context,
      MaterialPageRoute(builder: (_) => const ScheduleFormScreen()),
    );
    if (saved == null || !context.mounted) return;
    Navigator.pop(context);
  }

  void _openVoiceSchedule(BuildContext context) {
    Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => const VoiceScheduleScreen()),
    );
  }

  Future<void> _openTodo(BuildContext context) async {
    final saved = await Navigator.push<TodoModel>(
      context,
      MaterialPageRoute(builder: (_) => const TodoFormScreen()),
    );
    if (saved == null || !context.mounted) return;
    triggerDashboardRefresh();
    Navigator.pop(context);
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: AppTheme.screenBackground,
      child: Scaffold(
        backgroundColor: Colors.transparent,
        appBar: AppBar(title: const Text('추가하기'), centerTitle: false),
        body: SafeArea(
          top: false,
          child: ListView(
            physics: const BouncingScrollPhysics(),
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
            children: [
              _ChoiceCard(
                icon: Icons.event_available_outlined,
                color: AppTheme.blue,
                title: '일정 추가',
                subtitle: '제목, 날짜, 시간, 장소를 직접 입력해요',
                onTap: () => _openSchedule(context),
              ),
              _ChoiceCard(
                icon: Icons.mic_none_rounded,
                color: AppTheme.purple,
                title: '음성으로 일정 추가',
                subtitle: 'AI 음성 인식은 보조 옵션으로 유지해요',
                onTap: () => _openVoiceSchedule(context),
              ),
              _ChoiceCard(
                icon: Icons.checklist_outlined,
                color: AppTheme.green,
                title: '할 일 추가',
                subtitle: '제목, 날짜, 우선순위를 입력해요',
                onTap: () => _openTodo(context),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ChoiceCard extends StatelessWidget {
  final IconData icon;
  final Color color;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  const _ChoiceCard({
    required this.icon,
    required this.color,
    required this.title,
    required this.subtitle,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.cardGap),
      child: GlassCard(
        onTap: onTap,
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Container(
              width: 46,
              height: 46,
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.14),
                borderRadius: BorderRadius.circular(AppRadii.control),
              ),
              child: Icon(icon, color: color, size: 23),
            ),
            const SizedBox(width: 13),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: AppTextStyles.cardTitle.copyWith(
                      color: AppTheme.textPrimary,
                    ),
                  ),
                  const SizedBox(height: 3),
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
      ),
    );
  }
}
