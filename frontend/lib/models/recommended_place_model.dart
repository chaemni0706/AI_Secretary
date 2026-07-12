/// 업체 추천 결과(백엔드 /voice/route 의 data.recommended_places 항목).
class RecommendedPlace {
  final String placeId;
  final String name;
  final String? category;
  final String? address;
  final String? roadAddress;
  final String? phone;
  final String? mapUrl;
  final int score;
  final String reason;
  final List<String> tags;
  final String source; // naver | mock
  final PlaceTravel? travel; // 자동차 이동 정보(상위 N개에만 채워짐, 없으면 null)
  final PlaceTravel? travelWalk; // 도보 정보(도보 15분 이하일 때만, 아니면 null)

  const RecommendedPlace({
    required this.placeId,
    required this.name,
    this.category,
    this.address,
    this.roadAddress,
    this.phone,
    this.mapUrl,
    this.score = 0,
    this.reason = '',
    this.tags = const [],
    this.source = 'naver',
    this.travel,
    this.travelWalk,
  });

  bool get isMock => source == 'mock';

  /// 카드에 바로 쓸 소요시간 라벨(예: "약 12분 · 3.2km"). travel 없으면 null.
  String? get travelLabel => travel?.label;

  factory RecommendedPlace.fromJson(Map<String, dynamic> j) => RecommendedPlace(
    placeId: (j['place_id'] ?? '').toString(),
    name: (j['name'] ?? '이름 미상').toString(),
    category: j['category'] as String?,
    address: j['address'] as String?,
    roadAddress: j['road_address'] as String?,
    phone: j['phone'] as String?,
    mapUrl: j['map_url'] as String?,
    score: (j['score'] as num?)?.toInt() ?? 0,
    reason: (j['reason'] ?? '').toString(),
    tags: ((j['recommendation_tags'] as List?) ?? const [])
        .map((e) => e.toString())
        .toList(),
    source: (j['source'] ?? 'naver').toString(),
    travel: j['travel'] is Map
        ? PlaceTravel.fromJson((j['travel'] as Map).cast<String, dynamic>())
        : null,
    travelWalk: j['travel_walk'] is Map
        ? PlaceTravel.fromJson((j['travel_walk'] as Map).cast<String, dynamic>())
        : null,
  );

  /// route.data['recommended_places'](List<dynamic>) → List<RecommendedPlace>.
  static List<RecommendedPlace> listFrom(dynamic raw) {
    final list = (raw as List?) ?? const [];
    return list
        .map(
          (e) => RecommendedPlace.fromJson((e as Map).cast<String, dynamic>()),
        )
        .toList();
  }
}

/// 현재 위치 → 업체까지의 이동 정보(백엔드 place.travel 블록).
class PlaceTravel {
  final int? durationMinutes;
  final int? distanceMeters;
  final String transportMode; // car | public_transit | walking
  final String? routeSummary;

  const PlaceTravel({
    this.durationMinutes,
    this.distanceMeters,
    this.transportMode = 'car',
    this.routeSummary,
  });

  factory PlaceTravel.fromJson(Map<String, dynamic> j) => PlaceTravel(
    durationMinutes: (j['duration_minutes'] as num?)?.toInt(),
    distanceMeters: (j['distance_meters'] as num?)?.toInt(),
    transportMode: (j['transport_mode'] ?? 'car').toString(),
    routeSummary: j['route_summary'] as String?,
  );

  /// 이동 수단 아이콘 선택에 쓰는 힌트.
  bool get isWalking => transportMode == 'walking';
  bool get isTransit => transportMode == 'public_transit';

  /// "약 12분 · 3.2km" 형태. 소요시간이 없으면 null.
  String? get label {
    if (durationMinutes == null) return null;
    final buf = StringBuffer('약 $durationMinutes분');
    final d = distanceMeters;
    if (d != null && d > 0) {
      final dist =
          d >= 1000 ? '${(d / 1000).toStringAsFixed(1)}km' : '${d}m';
      buf.write(' · $dist');
    }
    return buf.toString();
  }
}
