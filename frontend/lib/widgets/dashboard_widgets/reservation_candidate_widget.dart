import 'package:flutter/material.dart';
import '../../data/widget_catalog.dart';
import '../../data/widget_mock_data.dart';
import '../../models/dashboard_widget_model.dart';
import '../../models/reservation_model.dart';
import '../../services/reservation_api.dart';
import '../../theme/app_theme.dart';
import 'dashboard_widget_card.dart';

/// 예약 후보 추천 위젯 (Medium).
///
/// 저장된 일정을 기반으로 오늘 비어 있는 시간대를 `reservationApi.candidatesFromStore`
/// 로 추천한다. 충돌 없는 후보의 시작 시각을 최대 3개 노출하고, 실패/후보 없음이면
/// mock 으로 폴백해 항상 무언가를 보여준다.
class ReservationCandidateWidget extends StatefulWidget {
  const ReservationCandidateWidget({super.key});

  @override
  State<ReservationCandidateWidget> createState() =>
      _ReservationCandidateWidgetState();
}

class _ReservationCandidateWidgetState
    extends State<ReservationCandidateWidget> {
  List<String> _candidates = WidgetMockData.reservationCandidates;
  String _title = WidgetMockData.reservationTitle;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final result = await reservationApi.candidatesFromStore(
        targetDate: _today(),
      );
      _apply(result);
    } catch (_) {
      // 실패 시 mock 유지.
    }
  }

  void _apply(ReservationResult result) {
    if (!mounted) return;
    final times = result.recommendedCandidates
        .where((c) => !c.conflict && c.startTime.isNotEmpty)
        .map((c) => c.startTime)
        .take(3)
        .toList();
    if (times.isEmpty) return; // 후보 없으면 mock 유지
    setState(() {
      _candidates = times;
      _title = '오늘 예약 가능한 시간';
    });
  }

  static String _today() {
    final n = DateTime.now();
    String two(int v) => v.toString().padLeft(2, '0');
    return '${n.year}-${two(n.month)}-${two(n.day)}';
  }

  @override
  Widget build(BuildContext context) {
    final spec = WidgetCatalog.of(DashboardWidgetType.reservation);
    final candidates = _candidates;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        WidgetCardHeader(
          icon: spec.icon,
          accent: spec.accent,
          title: spec.title,
          showChevron: true,
        ),
        const SizedBox(height: 4),
        Text(
          _title,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(
            fontSize: 11.5,
            fontWeight: FontWeight.w500,
            color: AppTheme.textSecondary,
          ),
        ),
        const Spacer(),
        Row(
          children: [
            for (final time in candidates) ...[
              Expanded(
                child: Container(
                  padding: const EdgeInsets.symmetric(vertical: 10),
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    color: spec.accent.withValues(alpha: 0.10),
                    borderRadius: BorderRadius.circular(11),
                    border: Border.all(
                      color: spec.accent.withValues(alpha: 0.20),
                    ),
                  ),
                  child: Text(
                    time,
                    style: TextStyle(
                      fontSize: 13.5,
                      fontWeight: FontWeight.w700,
                      color: spec.accent,
                    ),
                  ),
                ),
              ),
              if (time != candidates.last) const SizedBox(width: 8),
            ],
          ],
        ),
        const Spacer(),
      ],
    );
  }
}
