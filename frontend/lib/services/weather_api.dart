import 'package:flutter/foundation.dart';
import 'package:geocoding/geocoding.dart';
import 'package:geolocator/geolocator.dart';

import '../models/weather_model.dart';
import 'api_client.dart';

/// 기상청 날씨 API 클라이언트.
/// `GET /api/v1/weather?lat=&lon=` — 키가 없으면 서버가 Mock 을 돌려주므로
/// 앱은 항상 무언가를 표시한다. 위치는 기기 GPS(best-effort)로 얻고, 실패하면
/// 좌표 없이 호출(서버가 서울 기본 격자 사용).
class WeatherApi {
  Future<WeatherModel> fetch({double? lat, double? lon}) async {
    final data = await apiClient.getData(
      '$apiPrefix/weather',
      query: {
        if (lat != null) 'lat': lat,
        if (lon != null) 'lon': lon,
      },
    );
    return WeatherModel.fromJson(data as Map<String, dynamic>);
  }

  /// 현재 위치 기반 조회. 위치 권한/획득 실패 시 좌표 없이 호출.
  /// 좌표가 있으면 기기 지오코더로 지역명을 얻어 표시 위치를 그 이름으로 바꾼다.
  Future<WeatherModel> fetchAuto() async {
    double? lat;
    double? lon;
    try {
      final pos = await _currentPosition();
      if (pos != null) {
        lat = pos.latitude;
        lon = pos.longitude;
      }
    } catch (e) {
      debugPrint('Weather GPS 실패(좌표 없이 조회): $e');
    }
    final model = await fetch(lat: lat, lon: lon);
    if (lat != null && lon != null) {
      final name = await _regionName(lat, lon);
      if (name != null && name.isNotEmpty) return model.copyWith(location: name);
    }
    return model;
  }

  /// 좌표 → 지역명("시/도 시·군·구"). 기기 지오코더 사용(키 불필요). 실패 시 null.
  Future<String?> _regionName(double lat, double lon) async {
    if (kIsWeb) return null; // 웹은 기기 지오코더 미지원 → 백엔드 지역명 사용
    try {
      final marks = await placemarkFromCoordinates(lat, lon);
      if (marks.isEmpty) return null;
      final p = marks.first;
      // 한국: administrativeArea(시/도) + (subLocality 또는 locality: 구/시)
      final admin = p.administrativeArea ?? '';
      final sub = (p.subLocality?.isNotEmpty == true)
          ? p.subLocality!
          : (p.locality ?? '');
      final name = [admin, sub].where((e) => e.isNotEmpty).join(' ').trim();
      return name.isEmpty ? null : name;
    } catch (e) {
      debugPrint('역지오코딩(기기) 실패: $e');
      return null;
    }
  }

  Future<Position?> _currentPosition() async {
    if (!await Geolocator.isLocationServiceEnabled()) return null;
    var perm = await Geolocator.checkPermission();
    if (perm == LocationPermission.denied) {
      perm = await Geolocator.requestPermission();
    }
    if (perm == LocationPermission.denied ||
        perm == LocationPermission.deniedForever) {
      return null;
    }
    return Geolocator.getCurrentPosition(
      locationSettings: const LocationSettings(accuracy: LocationAccuracy.low),
    );
  }
}

final weatherApi = WeatherApi();
