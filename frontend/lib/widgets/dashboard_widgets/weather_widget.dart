import 'package:flutter/material.dart';
import '../../data/widget_catalog.dart';
import '../../data/widget_mock_data.dart' show WidgetMockData;
import '../../models/dashboard_widget_model.dart';
import '../../models/weather_model.dart';
import '../../services/weather_api.dart';
import '../../theme/app_theme.dart';
import '../../theme/illustrations.dart';
import 'dashboard_widget_card.dart';

/// 날씨 아이콘(IconData)을 조건에 맞는 3D 일러스트 경로로 매핑.
String _illustrationFor(IconData icon) {
  if (icon == Icons.umbrella_outlined ||
      icon == Icons.grain ||
      icon == Icons.cloudy_snowing ||
      icon == Icons.ac_unit) {
    return AppIllustrations.rain;
  }
  if (icon == Icons.wb_cloudy_outlined || icon == Icons.cloud_outlined) {
    return AppIllustrations.cloudSun;
  }
  return AppIllustrations.sun;
}

/// 날씨 위젯 (Small / Medium).
/// 실제 날씨 API(`/api/v1/weather`) 기반. 서버 미도달 시에만 [WidgetMockData] 로 fallback.
class WeatherWidget extends StatefulWidget {
  final WidgetSize size;

  const WeatherWidget({super.key, required this.size});

  @override
  State<WeatherWidget> createState() => _WeatherWidgetState();
}

class _WeatherWidgetState extends State<WeatherWidget> {
  WeatherModel? _model; // null = 아직 로드 전/실패 → mock 표시

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final m = await weatherApi.fetchAuto();
      if (!mounted) return;
      setState(() => _model = m);
    } catch (_) {
      // 네트워크/위치 실패 → mock fallback 유지(항상 무언가를 표시).
      if (!mounted) return;
      setState(() => _model = null);
    }
  }

  // --- 표시값 해석: 실제 모델 우선, 없으면 mock ---------------------------
  IconData get _nowIcon => _model != null
      ? weatherIcon(_model!.now.sky, _model!.now.precipitation)
      : WidgetMockData.weatherNow.icon;

  int get _nowTemp =>
      _model?.now.tempC?.round() ?? WidgetMockData.weatherNow.tempC;

  String get _nowLocation =>
      _model?.location ?? WidgetMockData.weatherNow.location;

  String get _nowSummary {
    final s = _model?.now.summary;
    if (s != null && s.trim().isNotEmpty) return s;
    return WidgetMockData.weatherNow.summary;
  }

  List<({String day, IconData icon, int high, int low})> get _weekly {
    final d = _model?.daily;
    if (d != null && d.isNotEmpty) {
      return d
          .take(7)
          .map((x) => (
                day: x.dow,
                icon: x.icon,
                high: (x.tempMax ?? 0).round(),
                low: (x.tempMin ?? 0).round(),
              ))
          .toList();
    }
    return WidgetMockData.weeklyWeather
        .map((w) => (day: w.day, icon: w.icon, high: w.high, low: w.low))
        .toList();
  }

  @override
  Widget build(BuildContext context) {
    return widget.size == WidgetSize.small ? _buildSmall() : _buildMedium();
  }

  Widget _buildSmall() {
    final spec = WidgetCatalog.of(DashboardWidgetType.weather);
    final icon = _nowIcon;
    return Stack(
      children: [
        // 우측 하단 빈 공간을 채우는 날씨 일러스트 — 첫인상 포인트.
        Positioned(
          right: 0,
          bottom: 0,
          child: Image.asset(
            _illustrationFor(icon),
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
                Icon(icon, size: 22, color: spec.accent),
                const Spacer(),
                Text(
                  _nowLocation,
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
              '$_nowTemp°',
              style: const TextStyle(
                fontSize: 34,
                fontWeight: FontWeight.w700,
                letterSpacing: -1,
                color: AppTheme.textPrimary,
              ),
            ),
            const SizedBox(height: 2),
            Text(
              _nowSummary,
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
            '$_nowTemp° $_nowLocation',
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
            for (final day in _weekly)
              Expanded(
                child: Column(
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
              ),
          ],
        ),
        const Spacer(),
      ],
    );
  }
}
