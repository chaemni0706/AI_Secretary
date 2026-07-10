import 'package:flutter/material.dart';
import '../models/weather_model.dart';
import '../services/api_client.dart';
import '../services/weather_api.dart';
import '../theme/app_theme.dart';
import '../theme/illustrations.dart';

/// 날씨 상세 — 토스(TDS) 스타일.
/// 그라디언트 히어로(현재) + 지표 타일 + 오늘 시간별(가로) + 주간 예보(온도 레인지 바).
/// 키가 없으면 서버가 Mock 을 주므로 항상 무언가를 표시한다.
class WeatherDetailScreen extends StatefulWidget {
  const WeatherDetailScreen({super.key});

  @override
  State<WeatherDetailScreen> createState() => _WeatherDetailScreenState();
}

class _WeatherDetailScreenState extends State<WeatherDetailScreen> {
  WeatherModel? _model;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final m = await weatherApi.fetchAuto();
      if (!mounted) return;
      setState(() {
        _model = m;
        _loading = false;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.message;
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = '날씨를 불러오지 못했어요.';
        _loading = false;
      });
    }
  }

  // --- 3D 일러스트 매핑 -----------------------------------------------------
  String _illustration(IconData icon) {
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

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: AppTheme.screenBackground,
      child: Scaffold(
        backgroundColor: Colors.transparent,
        appBar: AppBar(
          backgroundColor: Colors.transparent,
          elevation: 0,
          title: const Text('날씨'),
          centerTitle: false,
          actions: [
            IconButton(
              onPressed: _loading ? null : _load,
              icon: const Icon(Icons.refresh_rounded),
              tooltip: '새로고침',
            ),
          ],
        ),
        body: SafeArea(
          top: false,
          child: _loading && _model == null
              ? const Center(child: CircularProgressIndicator())
              : (_error != null && _model == null
                    ? _buildError(_error!)
                    : _buildContent(_model!)),
        ),
      ),
    );
  }

  Widget _buildError(String message) => Center(
    child: Padding(
      padding: const EdgeInsets.all(TossSpacing.xxl),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(
            Icons.cloud_off_rounded,
            size: 40,
            color: TossColors.grey400,
          ),
          const SizedBox(height: 12),
          Text(
            message,
            textAlign: TextAlign.center,
            style: TossTypography.caption,
          ),
          const SizedBox(height: 16),
          FilledButton(onPressed: _load, child: const Text('다시 시도')),
        ],
      ),
    ),
  );

  Widget _buildContent(WeatherModel m) {
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(
          parent: BouncingScrollPhysics(),
        ),
        padding: const EdgeInsets.fromLTRB(
          TossSpacing.lg,
          TossSpacing.sm,
          TossSpacing.lg,
          TossSpacing.xxl,
        ),
        children: [
          _HeroCard(model: m, illustration: _illustration),
          const SizedBox(height: 14),
          _StatTiles(model: m),
          if (m.today.isNotEmpty) ...[
            const SizedBox(height: 22),
            _sectionTitle('오늘 시간별'),
            const SizedBox(height: 10),
            _HourlyStrip(hours: m.today),
          ],
          if (m.daily.isNotEmpty) ...[
            const SizedBox(height: 22),
            _sectionTitle('주간 예보'),
            const SizedBox(height: 10),
            _WeeklyCard(days: m.daily),
          ],
        ],
      ),
    );
  }

  Widget _sectionTitle(String text) => Padding(
    padding: const EdgeInsets.only(left: 4),
    child: Text(text, style: TossTypography.title3),
  );
}

// ---------------------------------------------------------------------------
// 히어로: 그라디언트 카드(현재 날씨)
// ---------------------------------------------------------------------------
class _HeroCard extends StatelessWidget {
  final WeatherModel model;
  final String Function(IconData) illustration;

  const _HeroCard({required this.model, required this.illustration});

  @override
  Widget build(BuildContext context) {
    final now = model.now;
    final icon = weatherIcon(now.sky, now.precipitation);
    final temp = now.tempC == null ? '--' : '${now.tempC!.round()}';
    final summary = (now.summary != null && now.summary!.trim().isNotEmpty)
        ? now.summary!
        : [
            now.sky,
            now.precipitation,
          ].whereType<String>().where((s) => s != '없음').join(' · ');

    return Container(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(TossRadius.xl),
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [TossColors.blue700, TossColors.blue600, TossColors.blue500],
          stops: [0.0, 0.55, 1.0],
        ),
        boxShadow: TossShadow.glow(
          TossColors.blue700,
          alpha: 0.28,
          blur: 22,
          offset: const Offset(0, 8),
        ),
      ),
      padding: const EdgeInsets.fromLTRB(20, 18, 20, 20),
      child: Stack(
        children: [
          Positioned(
            right: 0,
            top: 0,
            child: Image.asset(
              illustration(icon),
              width: 76,
              height: 76,
              fit: BoxFit.contain,
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  const Icon(
                    Icons.location_on_rounded,
                    size: 15,
                    color: Color(0xFFBFDBFF),
                  ),
                  const SizedBox(width: 4),
                  Text(
                    model.location,
                    style: TossTypography.caption.copyWith(
                      color: Colors.white,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(width: 8),
                  if (model.source == 'mock') _heroBadge('예시'),
                ],
              ),
              const SizedBox(height: 18),
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    temp,
                    style: const TextStyle(
                      fontFamily: TossTypography.fontFamily,
                      fontSize: 68,
                      height: 1.0,
                      fontWeight: FontWeight.w700,
                      letterSpacing: -2,
                      color: Colors.white,
                    ),
                  ),
                  const Padding(
                    padding: EdgeInsets.only(top: 8),
                    child: Text(
                      '°',
                      style: TextStyle(
                        fontSize: 34,
                        fontWeight: FontWeight.w600,
                        color: Colors.white,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 4),
              Text(
                summary.isEmpty ? '오늘의 날씨' : summary,
                style: const TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w600,
                  color: Color(0xFFEFF5FF),
                ),
              ),
              const SizedBox(height: 14),
              Row(
                children: [
                  _heroTemp('최저', model.tempMin),
                  const SizedBox(width: 18),
                  _heroTemp('최고', model.tempMax),
                ],
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _heroBadge(String text) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
    decoration: BoxDecoration(
      color: Colors.white.withValues(alpha: 0.2),
      borderRadius: BorderRadius.circular(TossRadius.full),
    ),
    child: Text(
      text,
      style: const TextStyle(
        fontSize: 10.5,
        fontWeight: FontWeight.w700,
        color: Colors.white,
      ),
    ),
  );

  Widget _heroTemp(String label, double? v) => Row(
    children: [
      Text(
        label,
        style: const TextStyle(
          fontSize: 12.5,
          fontWeight: FontWeight.w500,
          color: Color(0xFFBFDBFF),
        ),
      ),
      const SizedBox(width: 5),
      Text(
        v == null ? '--°' : '${v.round()}°',
        style: const TextStyle(
          fontSize: 14,
          fontWeight: FontWeight.w700,
          color: Colors.white,
        ),
      ),
    ],
  );
}

// ---------------------------------------------------------------------------
// 지표 타일(습도 / 하늘 / 강수)
// ---------------------------------------------------------------------------
class _StatTiles extends StatelessWidget {
  final WeatherModel model;

  const _StatTiles({required this.model});

  @override
  Widget build(BuildContext context) {
    final now = model.now;
    final tiles = <Widget>[
      _tile(
        Icons.water_drop_outlined,
        '습도',
        now.humidity == null ? '--' : '${now.humidity}%',
      ),
      _tile(Icons.wb_cloudy_outlined, '하늘', now.sky ?? '--'),
      _tile(
        Icons.umbrella_outlined,
        '강수',
        (now.precipitation == null || now.precipitation == '없음')
            ? '없음'
            : now.precipitation!,
      ),
    ];
    return Row(
      children: [
        for (int i = 0; i < tiles.length; i++) ...[
          Expanded(child: tiles[i]),
          if (i != tiles.length - 1) const SizedBox(width: 10),
        ],
      ],
    );
  }

  Widget _tile(IconData icon, String label, String value) => Container(
    decoration: BoxDecoration(
      color: TossColors.bgWhite,
      borderRadius: BorderRadius.circular(TossRadius.lg),
      boxShadow: TossShadow.tiny,
    ),
    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 14),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, size: 18, color: TossColors.blue500),
        const SizedBox(height: 10),
        Text(label, style: TossTypography.small),
        const SizedBox(height: 2),
        Text(
          value,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: TossTypography.title3,
        ),
      ],
    ),
  );
}

// ---------------------------------------------------------------------------
// 오늘 시간별 (가로 스트립)
// ---------------------------------------------------------------------------
class _HourlyStrip extends StatelessWidget {
  final List<WeatherHour> hours;

  const _HourlyStrip({required this.hours});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: TossColors.bgWhite,
        borderRadius: BorderRadius.circular(TossRadius.xl),
        boxShadow: TossShadow.weak,
      ),
      padding: const EdgeInsets.symmetric(vertical: 16),
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        physics: const BouncingScrollPhysics(),
        padding: const EdgeInsets.symmetric(horizontal: 8),
        child: Row(children: [for (final h in hours) _hourCell(h)]),
      ),
    );
  }

  Widget _hourCell(WeatherHour h) => SizedBox(
    width: 60,
    child: Column(
      children: [
        Text(
          h.time,
          style: TossTypography.small.copyWith(fontWeight: FontWeight.w600),
        ),
        const SizedBox(height: 10),
        Icon(
          weatherIcon(h.sky, h.precipitation),
          size: 22,
          color: TossColors.blue500,
        ),
        const SizedBox(height: 10),
        Text(
          h.tempC == null ? '--°' : '${h.tempC!.round()}°',
          style: TossTypography.label.copyWith(fontWeight: FontWeight.w700),
        ),
        const SizedBox(height: 4),
        Text(
          h.pop == null ? '' : '${h.pop}%',
          style: TossTypography.small.copyWith(color: TossColors.blue500),
        ),
      ],
    ),
  );
}

// ---------------------------------------------------------------------------
// 주간 예보 (요일 + 아이콘 + 온도 레인지 바 + 최저/최고)
// ---------------------------------------------------------------------------
class _WeeklyCard extends StatelessWidget {
  final List<WeatherDay> days;

  const _WeeklyCard({required this.days});

  @override
  Widget build(BuildContext context) {
    // 주간 전체 최저/최고로 레인지 바 스케일 계산.
    final mins = days.map((d) => d.tempMin).whereType<double>().toList();
    final maxs = days.map((d) => d.tempMax).whereType<double>().toList();
    final allMin = mins.isEmpty ? 0.0 : mins.reduce((a, b) => a < b ? a : b);
    final allMax = maxs.isEmpty ? 1.0 : maxs.reduce((a, b) => a > b ? a : b);

    return Container(
      decoration: BoxDecoration(
        color: TossColors.bgWhite,
        borderRadius: BorderRadius.circular(TossRadius.xl),
        boxShadow: TossShadow.weak,
      ),
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 6),
      child: Column(
        children: [
          for (int i = 0; i < days.length; i++)
            _dayRow(days[i], allMin, allMax, last: i == days.length - 1),
        ],
      ),
    );
  }

  Widget _dayRow(
    WeatherDay d,
    double allMin,
    double allMax, {
    required bool last,
  }) {
    return Container(
      decoration: last
          ? null
          : const BoxDecoration(
              border: Border(
                bottom: BorderSide(color: TossColors.grey100, width: 1),
              ),
            ),
      padding: const EdgeInsets.symmetric(vertical: 13),
      child: Row(
        children: [
          SizedBox(
            width: 28,
            child: Text(
              d.dow,
              style: TossTypography.label.copyWith(fontWeight: FontWeight.w700),
            ),
          ),
          Icon(
            weatherIcon(d.sky, d.precipitation),
            size: 20,
            color: TossColors.blue500,
          ),
          const SizedBox(width: 14),
          Text(
            d.tempMin == null ? '--°' : '${d.tempMin!.round()}°',
            style: TossTypography.caption.copyWith(color: TossColors.grey500),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: _RangeBar(
              dayMin: d.tempMin ?? allMin,
              dayMax: d.tempMax ?? allMax,
              allMin: allMin,
              allMax: allMax,
            ),
          ),
          const SizedBox(width: 8),
          Text(
            d.tempMax == null ? '--°' : '${d.tempMax!.round()}°',
            style: TossTypography.label.copyWith(fontWeight: FontWeight.w700),
          ),
        ],
      ),
    );
  }
}

/// 주간 온도 범위 바 — 전체 최저~최고 축 위에서 그날 범위를 파랑→주황 그라디언트로.
class _RangeBar extends StatelessWidget {
  final double dayMin;
  final double dayMax;
  final double allMin;
  final double allMax;

  const _RangeBar({
    required this.dayMin,
    required this.dayMax,
    required this.allMin,
    required this.allMax,
  });

  @override
  Widget build(BuildContext context) {
    final span = (allMax - allMin);
    double leftF = 0, midF = 1, rightF = 0;
    if (span > 0) {
      leftF = ((dayMin - allMin) / span).clamp(0.0, 1.0);
      rightF = ((allMax - dayMax) / span).clamp(0.0, 1.0);
      midF = (1 - leftF - rightF).clamp(0.08, 1.0);
    }
    return SizedBox(
      height: 6,
      child: Row(
        children: [
          Expanded(flex: (leftF * 1000).round(), child: const SizedBox()),
          Expanded(
            flex: (midF * 1000).round().clamp(1, 1000),
            child: Container(
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(TossRadius.full),
                gradient: const LinearGradient(
                  colors: [TossColors.blue500, TossColors.orange],
                ),
              ),
            ),
          ),
          Expanded(flex: (rightF * 1000).round(), child: const SizedBox()),
        ],
      ),
    );
  }
}
