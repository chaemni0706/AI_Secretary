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
  });

  bool get isMock => source == 'mock';

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
      );

  /// route.data['recommended_places'](List<dynamic>) → List<RecommendedPlace>.
  static List<RecommendedPlace> listFrom(dynamic raw) {
    final list = (raw as List?) ?? const [];
    return list
        .map((e) => RecommendedPlace.fromJson(
            (e as Map).cast<String, dynamic>()))
        .toList();
  }
}
