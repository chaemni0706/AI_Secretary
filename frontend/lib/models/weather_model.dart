import 'package:flutter/material.dart';

/// 기상청 날씨 응답 모델(백엔드 /api/v1/weather).
class WeatherNow {
  final double? tempC;
  final String? sky; // 맑음 | 구름많음 | 흐림
  final String? precipitation; // 없음 | 비 | 비/눈 | 눈 | 소나기 ...
  final int? humidity;
  final String? summary;

  const WeatherNow({
    this.tempC,
    this.sky,
    this.precipitation,
    this.humidity,
    this.summary,
  });

  factory WeatherNow.fromJson(Map<String, dynamic> j) => WeatherNow(
        tempC: (j['temp_c'] as num?)?.toDouble(),
        sky: j['sky'] as String?,
        precipitation: j['precipitation'] as String?,
        humidity: j['humidity'] as int?,
        summary: j['summary'] as String?,
      );
}

class WeatherHour {
  final String time; // HH:mm
  final double? tempC;
  final String? sky;
  final String? precipitation;
  final int? pop; // 강수확률(%)

  const WeatherHour({
    required this.time,
    this.tempC,
    this.sky,
    this.precipitation,
    this.pop,
  });

  factory WeatherHour.fromJson(Map<String, dynamic> j) => WeatherHour(
        time: (j['time'] ?? '').toString(),
        tempC: (j['temp_c'] as num?)?.toDouble(),
        sky: j['sky'] as String?,
        precipitation: j['precipitation'] as String?,
        pop: j['pop'] as int?,
      );
}

class WeatherDay {
  final String date; // 'YYYY-MM-DD'
  final String dow; // 요일 라벨(월~일)
  final double? tempMin;
  final double? tempMax;
  final String? sky;
  final String? precipitation;

  const WeatherDay({
    required this.date,
    required this.dow,
    this.tempMin,
    this.tempMax,
    this.sky,
    this.precipitation,
  });

  factory WeatherDay.fromJson(Map<String, dynamic> j) => WeatherDay(
        date: (j['date'] ?? '').toString(),
        dow: (j['dow'] ?? '').toString(),
        tempMin: (j['temp_min'] as num?)?.toDouble(),
        tempMax: (j['temp_max'] as num?)?.toDouble(),
        sky: j['sky'] as String?,
        precipitation: j['precipitation'] as String?,
      );

  IconData get icon => weatherIcon(sky, precipitation);
}

class WeatherModel {
  final String location;
  final WeatherNow now;
  final List<WeatherHour> today;
  final List<WeatherDay> daily;
  final double? tempMin;
  final double? tempMax;
  final String source; // kma | mock

  const WeatherModel({
    required this.location,
    required this.now,
    this.today = const [],
    this.daily = const [],
    this.tempMin,
    this.tempMax,
    this.source = 'kma',
  });

  factory WeatherModel.fromJson(Map<String, dynamic> j) => WeatherModel(
        location: (j['location'] ?? '현재 위치').toString(),
        now: WeatherNow.fromJson(
            (j['now'] as Map?)?.cast<String, dynamic>() ?? const {}),
        today: ((j['today'] as List?) ?? const [])
            .map((e) => WeatherHour.fromJson((e as Map).cast<String, dynamic>()))
            .toList(),
        daily: ((j['daily'] as List?) ?? const [])
            .map((e) => WeatherDay.fromJson((e as Map).cast<String, dynamic>()))
            .toList(),
        tempMin: (j['temp_min'] as num?)?.toDouble(),
        tempMax: (j['temp_max'] as num?)?.toDouble(),
        source: (j['source'] ?? 'kma').toString(),
      );

  WeatherModel copyWith({String? location}) => WeatherModel(
        location: location ?? this.location,
        now: now,
        today: today,
        daily: daily,
        tempMin: tempMin,
        tempMax: tempMax,
        source: source,
      );
}

/// 하늘/강수 상태 → 아이콘. 강수가 있으면 강수 우선.
IconData weatherIcon(String? sky, String? precipitation) {
  switch (precipitation) {
    case '비':
    case '소나기':
    case '빗방울':
      return Icons.umbrella_outlined;
    case '눈':
    case '눈날림':
      return Icons.ac_unit;
    case '비/눈':
    case '빗방울눈날림':
      return Icons.cloudy_snowing;
  }
  switch (sky) {
    case '맑음':
      return Icons.wb_sunny_outlined;
    case '구름많음':
      return Icons.wb_cloudy_outlined;
    case '흐림':
      return Icons.cloud_outlined;
  }
  return Icons.wb_sunny_outlined;
}
