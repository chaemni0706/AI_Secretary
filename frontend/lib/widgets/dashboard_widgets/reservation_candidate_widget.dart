import 'package:flutter/material.dart';
import '../../data/widget_catalog.dart';
import '../../data/widget_mock_data.dart';
import '../../models/dashboard_widget_model.dart';
import '../../theme/app_theme.dart';
import 'dashboard_widget_card.dart';

/// 예약 후보 추천 위젯 (Medium).
/// 현재 mock([WidgetMockData.reservationCandidates]). 예약 추천 API 준비 시 교체.
class ReservationCandidateWidget extends StatelessWidget {
  const ReservationCandidateWidget({super.key});

  @override
  Widget build(BuildContext context) {
    final spec = WidgetCatalog.of(DashboardWidgetType.reservation);
    final candidates = WidgetMockData.reservationCandidates;

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
          WidgetMockData.reservationTitle,
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
                    border:
                        Border.all(color: spec.accent.withValues(alpha: 0.20)),
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
