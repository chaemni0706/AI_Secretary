import 'package:flutter/material.dart';
import '../models/schedule_model.dart';
import '../services/api_client.dart';
import '../services/dashboard_api.dart';
import '../services/schedule_api.dart';
import '../theme/app_constants.dart';
import '../theme/app_theme.dart';
import '../theme/schedule_styles.dart';
import '../widgets/glass_card.dart';
import 'schedule_edit_screen.dart';

class ScheduleDetailScreen extends StatefulWidget {
  final ScheduleModel schedule;

  const ScheduleDetailScreen({super.key, required this.schedule});

  @override
  State<ScheduleDetailScreen> createState() => _ScheduleDetailScreenState();
}

class _ScheduleDetailScreenState extends State<ScheduleDetailScreen> {
  /// 현재 표시 중인 일정. 수정 후 반환값으로 교체돼 화면이 즉시 갱신된다.
  late ScheduleModel schedule;

  @override
  void initState() {
    super.initState();
    schedule = widget.schedule;
  }

  /// 수정 화면으로 이동 → 저장 결과(ScheduleModel)를 받아 상세 갱신 + 캘린더 새로고침.
  Future<void> _openEdit() async {
    final updated = await Navigator.of(context).push<ScheduleModel>(
      MaterialPageRoute(
        builder: (_) => ScheduleEditScreen(schedule: schedule),
      ),
    );
    if (updated == null || !mounted) return;
    setState(() => schedule = updated);
    triggerDashboardRefresh(); // 홈/캘린더 즉시 반영
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('일정을 수정했어요.')),
    );
  }

  /// 날짜 표시: 기간 일정이면 "시작 ~ 종료", 아니면 시작일만.
  String _dateText() {
    final start = schedule.date;
    if (start == null || start.isEmpty) return '날짜 미정';
    final end = schedule.effectiveEndDate;
    if (end != null && end.compareTo(start) > 0) return '$start ~ $end';
    return start;
  }

  /// 기계용 end_date 토큰을 제외한 순수 메모.
  String _memoText() => ScheduleModel.stripEndDateToken(schedule.memo);

  /// 삭제 확인 다이얼로그 → DELETE /local/schedules/{id} → 대시보드 새로고침 → 뒤로.
  Future<void> _confirmDelete(BuildContext context) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('일정 삭제'),
        content: Text("'${schedule.title}' 일정을 삭제할까요?"),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('취소'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: TextButton.styleFrom(foregroundColor: AppTheme.red),
            child: const Text('삭제'),
          ),
        ],
      ),
    );
    if (ok != true) return;

    final messenger = ScaffoldMessenger.of(context);
    final navigator = Navigator.of(context);
    try {
      await scheduleApi.delete(schedule.id);
      triggerDashboardRefresh(); // 홈/캘린더 갱신
      messenger.showSnackBar(
        const SnackBar(content: Text('일정을 삭제했어요.')),
      );
      navigator.pop();
    } on ApiException catch (e) {
      messenger.showSnackBar(
        SnackBar(content: Text('삭제 실패: ${e.message}')),
      );
    } catch (e) {
      messenger.showSnackBar(
        SnackBar(content: Text('삭제 중 오류: $e')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final category = ScheduleStyles.categoryLabel(schedule.category);
    final color = ScheduleStyles.categoryColor(schedule.category);

    return Container(
      decoration: AppTheme.screenBackground,
      child: Scaffold(
        backgroundColor: Colors.transparent,
        appBar: AppBar(
          title: const Text('일정 상세'),
          centerTitle: false,
          actions: [
            IconButton(
              onPressed: () => _confirmDelete(context),
              icon: const Icon(Icons.delete_outline, color: AppTheme.red),
              tooltip: '삭제',
            ),
          ],
        ),
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
                    _DetailRow(label: '날짜', value: _dateText()),
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
                    if (_memoText().isNotEmpty)
                      _DetailRow(label: '메모', value: _memoText()),
                    const SizedBox(height: 18),
                    SizedBox(
                      width: double.infinity,
                      child: FilledButton.icon(
                        onPressed: _openEdit,
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
            ],
          ),
        ),
      ),
    );
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
