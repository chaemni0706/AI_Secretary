import 'package:flutter/material.dart';
import '../models/schedule_model.dart';
import '../services/api_client.dart';
import '../services/dashboard_api.dart';
import '../services/schedule_api.dart';
import '../theme/app_constants.dart';
import '../theme/app_theme.dart';
import '../theme/schedule_styles.dart';
import '../widgets/glass_card.dart';
import 'schedule_form_screen.dart';

class ScheduleDetailScreen extends StatefulWidget {
  final ScheduleModel schedule;

  const ScheduleDetailScreen({super.key, required this.schedule});

  @override
  State<ScheduleDetailScreen> createState() => _ScheduleDetailScreenState();
}

class _ScheduleDetailScreenState extends State<ScheduleDetailScreen> {
  bool _deleting = false;

  @override
  Widget build(BuildContext context) {
    final schedule = widget.schedule;
    final category = ScheduleStyles.categoryLabel(schedule.category);
    final color = ScheduleStyles.categoryColor(schedule.category);

    return Container(
      decoration: AppTheme.screenBackground,
      child: Scaffold(
        backgroundColor: Colors.transparent,
        appBar: AppBar(title: const Text('일정 상세'), centerTitle: false),
        body: SafeArea(
          top: false,
          child: ListView(
            physics: const BouncingScrollPhysics(),
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
            children: [
              GlassCard(
                padding: const EdgeInsets.all(18),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Container(
                          width: 40,
                          height: 40,
                          decoration: BoxDecoration(
                            color: color.withValues(alpha: 0.14),
                            borderRadius: BorderRadius.circular(AppRadii.small),
                          ),
                          child: Icon(
                            ScheduleStyles.categoryIcon(schedule.category),
                            color: color,
                            size: 21,
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Text(
                            schedule.title,
                            style: AppTextStyles.screenTitle.copyWith(
                              color: AppTheme.textPrimary,
                              fontSize: 22,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 18),
                    _DetailRow(label: '날짜', value: schedule.date ?? '날짜 미정'),
                    _DetailRow(
                      label: '시간',
                      value: ScheduleStyles.timeText(
                        schedule.startTime,
                        schedule.endTime,
                      ),
                    ),
                    _DetailRow(
                      label: '장소',
                      value: schedule.location?.isNotEmpty == true
                          ? schedule.location!
                          : '장소 미정',
                    ),
                    _DetailRow(label: '카테고리', value: category),
                    const SizedBox(height: 18),
                    SizedBox(
                      width: double.infinity,
                      child: FilledButton.icon(
                        onPressed: _deleting ? null : _openEdit,
                        icon: const Icon(Icons.edit_outlined, size: 18),
                        label: const Text('수정'),
                        style: FilledButton.styleFrom(
                          backgroundColor: AppTheme.blue,
                          foregroundColor: Colors.white,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 14),
              GlassCard(
                padding: const EdgeInsets.all(14),
                child: SizedBox(
                  width: double.infinity,
                  child: OutlinedButton.icon(
                    onPressed: _deleting ? null : _confirmDelete,
                    icon: _deleting
                        ? const SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.delete_outline, size: 18),
                    label: Text(_deleting ? '삭제 중...' : '일정 삭제'),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: AppTheme.red,
                      side: BorderSide(
                        color: AppTheme.red.withValues(alpha: 0.34),
                      ),
                      padding: const EdgeInsets.symmetric(vertical: 13),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(AppRadii.control),
                      ),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _openEdit() async {
    final saved = await Navigator.push<ScheduleModel>(
      context,
      MaterialPageRoute(
        builder: (_) => ScheduleFormScreen(initialSchedule: widget.schedule),
      ),
    );
    if (saved == null || !mounted) return;
    Navigator.pop<ScheduleModel>(context, saved);
  }

  Future<void> _confirmDelete() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('일정을 삭제할까요?'),
        content: Text('"${widget.schedule.title}" 일정이 캘린더에서 삭제됩니다.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text('취소'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            style: FilledButton.styleFrom(
              backgroundColor: AppTheme.red,
              foregroundColor: Colors.white,
            ),
            child: const Text('삭제'),
          ),
        ],
      ),
    );
    if (confirmed == true) await _deleteSchedule();
  }

  Future<void> _deleteSchedule() async {
    setState(() => _deleting = true);
    try {
      await scheduleApi.delete(widget.schedule.id);
      triggerDashboardRefresh();
      if (!mounted) return;
      Navigator.pop<bool>(context, true);
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _deleting = false);
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('삭제 실패: ${e.message}')));
    } catch (e) {
      if (!mounted) return;
      setState(() => _deleting = false);
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('삭제 중 오류: $e')));
    }
  }
}

class _DetailRow extends StatelessWidget {
  final String label;
  final String value;

  const _DetailRow({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 74,
            child: Text(
              label,
              style: AppTextStyles.meta.copyWith(
                color: AppTheme.textSecondary,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: AppTextStyles.cardTitle.copyWith(
                color: AppTheme.textPrimary,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
