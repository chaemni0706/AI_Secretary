import 'package:flutter/material.dart';
import '../models/weather_model.dart';
import '../services/api_client.dart';
import '../services/weather_api.dart';
import '../theme/app_constants.dart';
import '../theme/app_theme.dart';
import '../widgets/glass_card.dart';

/// 날씨 상세 화면 — 현재 날씨 + 오늘 시간별 예보(기상청).
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
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = '날씨를 불러오지 못했어요. ($e)';
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: AppTheme.screenBackground,
      child: Scaffold(
        backgroundColor: Colors.transparent,
        appBar: AppBar(
          title: const Text('날씨'),
          centerTitle: false,
          actions: [
            IconButton(
              onPressed: _loading ? null : _load,
              icon: const Icon(Icons.refresh),
              tooltip: '새로고침',
            ),
          ],
        ),
        body: SafeArea(
          top: false,
          child: _loading
              ? const Center(child: CircularProgressIndicator())
              : (_error != null
                  ? _buildError(_error!)
                  : _buildContent(_model!)),
        ),
      ),
    );
  }

  Widget _buildError(String message) => Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Text(message, textAlign: TextAlign.center),
        ),
      );

  Widget _buildContent(WeatherModel m) {
    final now = m.now;
    return ListView(
      physics: const BouncingScrollPhysics(),
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
      children: [
        GlassCard(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(weatherIcon(now.sky, now.precipitation),
                      size: 44, color: AppTheme.blue),
                  const SizedBox(width: 14),
                  Text(
                    now.tempC == null ? '--°' : '${now.tempC!.round()}°',
                    style: AppTextStyles.screenTitle.copyWith(
                        fontSize: 44, color: AppTheme.textPrimary),
                  ),
                  const Spacer(),
                  Text(m.location,
                      style: AppTextStyles.meta
                          .copyWith(color: AppTheme.textSecondary)),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                now.summary ?? [now.sky, now.precipitation].whereType<String>().join(' · '),
                style: AppTextStyles.cardTitle.copyWith(color: AppTheme.textPrimary),
              ),
              const SizedBox(height: 10),
              Wrap(
                spacing: 16,
                children: [
                  if (m.tempMin != null) _chip('최저 ${m.tempMin!.round()}°'),
                  if (m.tempMax != null) _chip('최고 ${m.tempMax!.round()}°'),
                  if (now.humidity != null) _chip('습도 ${now.humidity}%'),
                  if (m.source == 'mock') _chip('예시 데이터'),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(height: 14),
        if (m.today.isNotEmpty)
          GlassCard(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('오늘 시간별',
                    style: AppTextStyles.sectionTitle
                        .copyWith(color: AppTheme.textPrimary)),
                const SizedBox(height: 8),
                for (final h in m.today) _hourRow(h),
              ],
            ),
          ),
      ],
    );
  }

  Widget _chip(String text) => Text(
        text,
        style: AppTextStyles.meta.copyWith(
            color: AppTheme.textSecondary, fontWeight: FontWeight.w600),
      );

  Widget _hourRow(WeatherHour h) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 6),
        child: Row(
          children: [
            SizedBox(
              width: 56,
              child: Text(h.time,
                  style: AppTextStyles.cardTitle
                      .copyWith(color: AppTheme.textSecondary)),
            ),
            Icon(weatherIcon(h.sky, h.precipitation),
                size: 20, color: AppTheme.blue),
            const SizedBox(width: 12),
            Text(h.tempC == null ? '--°' : '${h.tempC!.round()}°',
                style: AppTextStyles.cardTitle.copyWith(color: AppTheme.textPrimary)),
            const Spacer(),
            if (h.pop != null)
              Text('강수 ${h.pop}%',
                  style: AppTextStyles.meta.copyWith(color: AppTheme.blue)),
          ],
        ),
      );
}
