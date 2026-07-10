import 'package:flutter/foundation.dart';
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
      query: {if (lat != null) 'lat': lat, if (lon != null) 'lon': lon},
    );
    return WeatherModel.fromJson(data as Map<String, dynamic>);
  }

  /// 현재 위치 기반 조회. 위치 권한/획득 실패 시 좌표 없이 호출.
  /// 지역명은 백엔드(/weather)가 좌표를 역지오코딩해 location 으로 내려준다.
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
    return fetch(lat: lat, lon: lon);
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
