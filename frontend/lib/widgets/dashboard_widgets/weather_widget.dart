import 'package:flutter/material.dart';
import '../../data/widget_catalog.dart';
import '../../data/widget_mock_data.dart';
import '../../models/dashboard_widget_model.dart';
import '../../theme/app_theme.dart';
import '../../theme/illustrations.dart';
import 'dashboard_widget_card.dart';

/// 날씨 아이콘(IconData)을 조건에 맞는 3D 일러스트 경로로 매핑.
String _illustrationFor(IconData icon) {
  if (icon == Icons.grain) return AppIllustrations.rain;
  if (icon == Icons.wb_cloudy_outlined || icon == Icons.cloud_outlined) {
    return AppIllustrations.cloudSun;
  }
  return AppIllustrations.sun;
}

/// 날씨 위젯 (Small / Medium).
/// 현재는 mock([WidgetMockData]). 향후 날씨 API 연결 예정 — 데이터 진입점만 교체하면 됨.
class WeatherWidget extends StatelessWidget {
  final WidgetSize size;

  const WeatherWidget({super.key, required this.size});

  @override
  Widget build(BuildContext context) {
    return size == WidgetSize.small ? _buildSmall() : _buildMedium();
  }

  Widget _buildSmall() {
    final spec = WidgetCatalog.of(DashboardWidgetType.weather);
    final now = WidgetMockData.weatherNow;
    return Stack(
      children: [
        // 우측 하단 빈 공간을 채우는 날씨 일러스트 — 첫인상 포인트.
        // 카드가 내용을 클리핑하지 않으므로 음수 오프셋 없이 경계 안에 배치한다.
        Positioned(
          right: 0,
          bottom: 0,
          child: Image.asset(
            _illustrationFor(now.icon),
            width: 72,
            height: 72,
            fit: BoxFit.contain,
          ),
        ),
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(now.icon, size: 22, color: spec.accent),
                const Spacer(),
                Text(
                  now.location,
                  style: const TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.textSecondary,
                  ),
                ),
              ],
            ),
            const Spacer(),
            Text(
              '${now.tempC}°',
              style: const TextStyle(
                fontSize: 34,
                fontWeight: FontWeight.w700,
                letterSpacing: -1,
                color: AppTheme.textPrimary,
              ),
            ),
            const SizedBox(height: 2),
            Text(
              now.summary,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                fontSize: 11.5,
                fontWeight: FontWeight.w500,
                color: AppTheme.textTertiary,
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildMedium() {
    final spec = WidgetCatalog.of(DashboardWidgetType.weather);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        WidgetCardHeader(
          icon: spec.icon,
          accent: spec.accent,
          title: '주간 날씨',
          trailing: Text(
            '${WidgetMockData.weatherNow.tempC}° ${WidgetMockData.weatherNow.location}',
            style: const TextStyle(
              fontSize: 11.5,
              fontWeight: FontWeight.w600,
              color: AppTheme.textSecondary,
            ),
          ),
        ),
        const Spacer(),
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            for (final day in WidgetMockData.weeklyWeather)
              Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    day.day,
                    style: const TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                      color: AppTheme.textSecondary,
                    ),
                  ),
                  const SizedBox(height: 7),
                  Icon(day.icon, size: 20, color: spec.accent),
                  const SizedBox(height: 7),
                  Text(
                    '${day.high}°',
                    style: const TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w700,
                      color: AppTheme.textPrimary,
                    ),
                  ),
                  Text(
                    '${day.low}°',
                    style: const TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w500,
                      color: AppTheme.textSecondary,
                    ),
                  ),
                ],
              ),
          ],
        ),
        const Spacer(),
      ],
    );
  }
}
