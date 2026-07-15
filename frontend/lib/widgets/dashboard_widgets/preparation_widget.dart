import 'package:flutter/material.dart';
import '../../data/widget_catalog.dart';
import '../../data/widget_mock_data.dart';
import '../../models/dashboard_widget_model.dart';
import '../../models/schedule_model.dart';
import '../../services/notification_api.dart';
import '../../services/schedule_api.dart';
import '../../theme/app_theme.dart';

/// 준비물 위젯 (Small).
///
/// 오늘의 '다음 일정'을 찾아 `notificationApi.createPlan(persist:false)` 의
/// 체크리스트를 준비물로 보여준다. 일정이 없거나 실패/빈 체크리스트면 mock 으로
/// 폴백한다. persist:false 라 미리보기 목적의 알림을 실제로 만들지 않는다.
class PreparationWidget extends StatefulWidget {
  const PreparationWidget({super.key});

  @override
  State<PreparationWidget> createState() => _PreparationWidgetState();
}

class _PreparationWidgetState extends State<PreparationWidget> {
  List<PreparationItem> _items = WidgetMockData.preparationItems;
  String _context = WidgetMockData.preparationContext;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final schedules = await scheduleApi.list();
      final sched = _nextToday(schedules);
      if (sched == null) return; // 오늘 남은 일정 없음 → mock 유지
      final plan = await notificationApi.createPlan(
        scheduleId: sched.id,
        includeChecklist: true,
        persist: false,
      );
      if (!mounted) return;
      final items = plan.checklist
          .where((c) => c.item.trim().isNotEmpty)
          .map((c) => PreparationItem(c.item, _iconFor(c.item)))
          .toList();
      if (items.isEmpty) return; // 준비물 없음 → mock 유지
      setState(() {
        _items = items;
        _context = sched.title;
      });
    } catch (_) {
      // 실패 시 mock 유지.
    }
  }

  /// 오늘의 '다음(앞으로 올)' 일정. 없으면 null.
  ScheduleModel? _nextToday(List<ScheduleModel> all) {
    final today = _today();
    final nowHm = _nowHm();
    final todays =
        all
            .where((s) => s.date == today && (s.startTime ?? '').isNotEmpty)
            .toList()
          ..sort((a, b) => (a.startTime ?? '').compareTo(b.startTime ?? ''));
    for (final s in todays) {
      if ((s.startTime ?? '').compareTo(nowHm) >= 0) return s;
    }
    return null;
  }

  /// 준비물 이름 → 대표 아이콘(키워드 매칭, 없으면 체크 아이콘).
  IconData _iconFor(String item) {
    final t = item.toLowerCase();
    bool has(List<String> ks) => ks.any((k) => t.contains(k));
    if (has(['우산', '비', 'umbrella'])) return Icons.umbrella_outlined;
    if (has(['노트북', '랩탑', 'laptop'])) return Icons.laptop_mac_outlined;
    if (has(['지갑', '카드', 'wallet'])) {
      return Icons.account_balance_wallet_outlined;
    }
    if (has(['약', '처방', 'pill'])) return Icons.medication_outlined;
    if (has(['서류', '자료', '문서', '진료카드'])) return Icons.description_outlined;
    if (has(['충전', '배터리', 'charger'])) {
      return Icons.battery_charging_full_outlined;
    }
    return Icons.check_circle_outline;
  }

  static String _today() {
    final n = DateTime.now();
    return '${n.year}-${_two(n.month)}-${_two(n.day)}';
  }

  static String _nowHm() {
    final n = DateTime.now();
    return '${_two(n.hour)}:${_two(n.minute)}';
  }

  static String _two(int v) => v.toString().padLeft(2, '0');

  @override
  Widget build(BuildContext context) {
    final spec = WidgetCatalog.of(DashboardWidgetType.preparation);
    final items = _items;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(spec.icon, size: 18, color: spec.accent),
            const SizedBox(width: 6),
            const Text(
              '준비물',
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w700,
                color: AppTheme.textPrimary,
              ),
            ),
          ],
        ),
        const SizedBox(height: 4),
        Text(
          _context,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(
            fontSize: 10.5,
            fontWeight: FontWeight.w500,
            color: AppTheme.textSecondary,
          ),
        ),
        const Spacer(),
        for (final item in items.take(2))
          Padding(
            padding: const EdgeInsets.only(bottom: 6),
            child: Row(
              children: [
                Icon(item.icon, size: 15, color: spec.accent),
                const SizedBox(width: 7),
                Expanded(
                  child: Text(
                    item.label,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                      color: AppTheme.textPrimary,
                    ),
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }
}
