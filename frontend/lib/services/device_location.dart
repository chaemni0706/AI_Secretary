import 'package:flutter/foundation.dart';
import 'package:geolocator/geolocator.dart';

/// 위치 조회 결과 상태.
enum LocationStatus {
  ok, // 좌표 획득 성공
  serviceDisabled, // 기기 위치 서비스 OFF (권한 프롬프트가 뜨지 않음)
  denied, // 이번에 거부
  deniedForever, // 영구 거부 (OS가 재프롬프트를 막음 → 설정에서 허용해야 함)
  error,
}

class DeviceLocationResult {
  final LocationStatus status;
  final Map<String, dynamic>? latLon; // {latitude, longitude} or null

  const DeviceLocationResult(this.status, [this.latLon]);

  bool get ok => status == LocationStatus.ok && latLon != null;

  /// 사용자에게 보여줄 안내 문구(성공이면 null).
  String? get guideMessage {
    switch (status) {
      case LocationStatus.serviceDisabled:
        return '기기 위치(GPS)가 꺼져 있어요. 위치를 켜면 현재 위치 기반으로 추천해요.';
      case LocationStatus.deniedForever:
        return '위치 권한이 꺼져 있어요. 설정에서 허용하면 현재 위치 기반으로 추천해요.';
      case LocationStatus.denied:
        return '위치 권한이 필요해요. 허용하면 현재 위치 기반으로 추천해요.';
      case LocationStatus.error:
        return '위치를 가져오지 못했어요.';
      case LocationStatus.ok:
        return null;
    }
  }
}

/// 기기 GPS 좌표 조회(best-effort). 위치 기반 기능(업체 추천 등)에서 공용으로 쓴다.
///
/// 백엔드 `/voice/route`·`/places/recommend` 의 `location` 규약에 맞춰
/// `{latitude, longitude}` 형태로 반환한다.
class DeviceLocation {
  const DeviceLocation._();

  /// 좌표만 필요할 때(실패 시 null). 프롬프트는 권한이 'denied'일 때만 뜬다.
  static Future<Map<String, dynamic>?> currentLatLon() async {
    return (await resolve()).latLon;
  }

  /// 상태까지 함께 얻는다(안내 메시지/설정 유도용).
  static Future<DeviceLocationResult> resolve() async {
    try {
      if (!await Geolocator.isLocationServiceEnabled()) {
        return const DeviceLocationResult(LocationStatus.serviceDisabled);
      }
      var perm = await Geolocator.checkPermission();
      if (perm == LocationPermission.denied) {
        perm = await Geolocator.requestPermission(); // 여기서 시스템 프롬프트
      }
      if (perm == LocationPermission.deniedForever) {
        return const DeviceLocationResult(LocationStatus.deniedForever);
      }
      if (perm == LocationPermission.denied) {
        return const DeviceLocationResult(LocationStatus.denied);
      }
      final pos = await Geolocator.getCurrentPosition(
        locationSettings: const LocationSettings(
          accuracy: LocationAccuracy.low,
        ),
      );
      return DeviceLocationResult(LocationStatus.ok, {
        'latitude': pos.latitude,
        'longitude': pos.longitude,
      });
    } catch (e) {
      debugPrint('DeviceLocation error: $e');
      return const DeviceLocationResult(LocationStatus.error);
    }
  }

  /// 앱 권한 설정 화면 열기(영구 거부일 때 유도).
  static Future<void> openAppSettings() => Geolocator.openAppSettings();

  /// 기기 위치 서비스 설정 열기(GPS가 꺼져 있을 때 유도).
  static Future<void> openLocationSettings() =>
      Geolocator.openLocationSettings();
}
