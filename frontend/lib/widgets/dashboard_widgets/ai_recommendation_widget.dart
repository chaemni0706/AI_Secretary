import 'package:flutter/material.dart';
import '../../data/widget_catalog.dart';
import '../../data/widget_mock_data.dart';
import '../../models/dashboard_widget_model.dart';
import '../../theme/app_theme.dart';
import 'dashboard_widget_card.dart';

/// AI 추천 위젯 (Medium).
/// 현재 mock([WidgetMockData.aiRecommendations]). 추천 API 준비 시 교체.
class AiRecommendationWidget extends StatelessWidget {
  const AiRecommendationWidget({super.key});

  @override
  Widget build(BuildContext context) {
    final spec = WidgetCatalog.of(DashboardWidgetType.aiRecommendation);
    final recommendation = WidgetMockData.aiRecommendations.first;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        WidgetCardHeader(
          icon: spec.icon,
          accent: spec.accent,
          title: spec.title,
          showChevron: true,
        ),
        const Spacer(),
        Container(
          padding: const EdgeInsets.all(11),
          decoration: BoxDecoration(
            color: spec.accent.withValues(alpha: 0.08),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: spec.accent.withValues(alpha: 0.16)),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(
                Icons.tips_and_updates_outlined,
                size: 16,
                color: spec.accent,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  recommendation,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    fontSize: 12.5,
                    height: 1.35,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.textPrimary,
                  ),
                ),
              ),
            ],
          ),
        ),
        const Spacer(),
        Text(
          '탭하여 AI에게 물어보기',
          style: TextStyle(
            fontSize: 11,
            fontWeight: FontWeight.w600,
            color: spec.accent,
          ),
        ),
      ],
    );
  }
}
