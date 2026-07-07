import 'package:flutter/material.dart';
import '../../data/widget_catalog.dart';
import '../../models/dashboard_widget_model.dart';
import '../../models/weather_model.dart';
import '../../services/weather_api.dart';
import '../../theme/app_theme.dart';
import 'dashboard_widget_card.dart';

/// 날씨 위젯 (Small / Medium). 기상청 API(/weather)에서 현재+오늘 예보를 받아온다.
/// 로딩/실패 시에는 안전한 기본값으로 렌더링(앱이 비지 않음).
class WeatherWidget extends StatefulWidget {
  final WidgetSize size;

  const WeatherWidget({super.key, required this.size});

  @override
  State<WeatherWidget> createState() => _WeatherWidgetState();
}

class _WeatherWidgetState extends State<WeatherWidget> {
  static const WeatherModel _fallback = WeatherModel(
    location: '—',
    now: WeatherNow(sky: null, summary: '날씨 불러오는 중…'),
    today: [],
    source: 'mock',
  );

  WeatherModel? _model;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final m = await weatherApi.fetchAuto();
      if (mounted) setState(() => _model = m);
    } catch (_) {
      if (mounted) setState(() => _model = _fallback);
    }
  }

  @override
  Widget build(BuildContext context) {
    final m = _model ?? _fallback;
    return widget.size == WidgetSize.small ? _buildSmall(m) : _buildMedium(m);
  }

  String _tempText(double? t) => t == null ? '--' : '${t.round()}';

  Widget _buildSmall(WeatherModel m) {
    final spec = WidgetCatalog.of(DashboardWidgetType.weather);
    final now = m.now;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(weatherIcon(now.sky, now.precipitation), size: 22, color: spec.accent),
            const Spacer(),
            Text(
              m.location,
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
          '${_tempText(now.tempC)}°',
          style: const TextStyle(
            fontSize: 34,
            fontWeight: FontWeight.w700,
            letterSpacing: -1,
            color: AppTheme.textPrimary,
          ),
        ),
        const SizedBox(height: 2),
        Text(
          now.summary ?? now.sky ?? '',
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(
            fontSize: 11.5,
            fontWeight: FontWeight.w500,
            color: AppTheme.textTertiary,
          ),
        ),
      ],
    );
  }

  Widget _buildMedium(WeatherModel m) {
    final spec = WidgetCatalog.of(DashboardWidgetType.weather);
    // 오늘 시간별 예보에서 앞쪽 5개 슬롯만 표시.
    final slots = m.today.take(5).toList();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        WidgetCardHeader(
          icon: spec.icon,
          accent: spec.accent,
          title: '오늘 날씨',
          trailing: Text(
            '${_tempText(m.now.tempC)}° ${m.location}',
            style: const TextStyle(
              fontSize: 11.5,
              fontWeight: FontWeight.w600,
              color: AppTheme.textSecondary,
            ),
          ),
        ),
        const Spacer(),
        if (slots.isEmpty)
          Text(
            m.now.summary ?? '예보 정보를 불러오지 못했어요',
            style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
          )
        else
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              for (final h in slots)
                Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      h.time,
                      style: const TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w600,
                        color: AppTheme.textSecondary,
                      ),
                    ),
                    const SizedBox(height: 7),
                    Icon(weatherIcon(h.sky, h.precipitation), size: 20, color: spec.accent),
                    const SizedBox(height: 7),
                    Text(
                      '${_tempText(h.tempC)}°',
                      style: const TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w700,
                        color: AppTheme.textPrimary,
                      ),
                    ),
                    if (h.pop != null)
                      Text(
                        '${h.pop}%',
                        style: const TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.w500,
                          color: AppTheme.blue,
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
