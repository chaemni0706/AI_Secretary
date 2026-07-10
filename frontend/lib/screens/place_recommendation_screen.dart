import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../widgets/glass_card.dart';

/// 예약 후보/장소 추천 결과 화면.
///
/// `voice_intent_router`가 `reservation_recommendation` 으로 분류하면
/// `voice_route_orchestrator`가 `place_recommendation_service`(`/places/recommend`,
/// 네이버 지역 검색 기반)를 호출한 결과를 이 화면으로 그대로 넘긴다.
/// `screen_action.type == 'navigate'` 일 때 실제로 화면 전환이 일어나도록
/// (voice_chat_screen / ai_chat_screen 공용) 이 화면이 그 대상이다.
class PlaceRecommendationScreen extends StatelessWidget {
  final String query;
  final List<dynamic> places;

  const PlaceRecommendationScreen({
    super.key,
    required this.query,
    required this.places,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: AppTheme.screenBackground,
      child: Scaffold(
        backgroundColor: Colors.transparent,
        appBar: AppBar(
          backgroundColor: Colors.transparent,
          leading: GestureDetector(
            onTap: () => Navigator.pop(context),
            child: Container(
              margin: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.7),
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.chevron_left,
                color: AppTheme.textPrimary,
                size: 26,
              ),
            ),
          ),
          title: const Text('추천 장소'),
        ),
        body: SafeArea(
          top: false,
          child: places.isEmpty ? _buildEmpty() : _buildList(),
        ),
      ),
    );
  }

  Widget _buildEmpty() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(
              Icons.search_off_rounded,
              size: 48,
              color: AppTheme.textSecondary,
            ),
            const SizedBox(height: 12),
            Text(
              query.isEmpty
                  ? '조건에 맞는 추천 장소를 찾지 못했어요.'
                  : '"$query"에 맞는 추천 장소를 찾지 못했어요.',
              textAlign: TextAlign.center,
              style: const TextStyle(
                fontSize: 14,
                color: AppTheme.textSecondary,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildList() {
    return ListView.builder(
      physics: const BouncingScrollPhysics(),
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
      itemCount: places.length + 1,
      itemBuilder: (context, i) {
        if (i == 0) {
          return Padding(
            padding: const EdgeInsets.only(bottom: 8, left: 4),
            child: Text(
              query.isEmpty ? '추천 결과' : '"$query" 검색 결과',
              style: const TextStyle(
                fontSize: 13,
                color: AppTheme.textSecondary,
              ),
            ),
          );
        }
        final place = Map<String, dynamic>.from(places[i - 1] as Map);
        return Padding(
          padding: const EdgeInsets.only(bottom: 12),
          child: _buildPlaceCard(place),
        );
      },
    );
  }

  Widget _buildPlaceCard(Map<String, dynamic> place) {
    final tags = (place['recommendation_tags'] as List?) ?? const [];
    return GlassCard(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  (place['name'] ?? '이름 미상').toString(),
                  style: const TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w700,
                    color: AppTheme.textPrimary,
                  ),
                ),
              ),
              PillBadge(
                label: '${place['score'] ?? '-'}점',
                color: AppTheme.orange,
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            (place['reason'] ?? '').toString(),
            style: const TextStyle(
              fontSize: 13,
              color: AppTheme.textTertiary,
              height: 1.4,
            ),
          ),
          if ((place['road_address'] ?? place['address']) != null) ...[
            const SizedBox(height: 8),
            Row(
              children: [
                const Icon(
                  Icons.place_outlined,
                  size: 15,
                  color: AppTheme.textSecondary,
                ),
                const SizedBox(width: 4),
                Expanded(
                  child: Text(
                    (place['road_address'] ?? place['address']).toString(),
                    style: const TextStyle(
                      fontSize: 12,
                      color: AppTheme.textSecondary,
                    ),
                  ),
                ),
              ],
            ),
          ],
          if (place['phone'] != null &&
              place['phone'].toString().isNotEmpty) ...[
            const SizedBox(height: 4),
            Row(
              children: [
                const Icon(
                  Icons.call_outlined,
                  size: 15,
                  color: AppTheme.textSecondary,
                ),
                const SizedBox(width: 4),
                Text(
                  place['phone'].toString(),
                  style: const TextStyle(
                    fontSize: 12,
                    color: AppTheme.textSecondary,
                  ),
                ),
              ],
            ),
          ],
          if (tags.isNotEmpty) ...[
            const SizedBox(height: 8),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: tags
                  .map(
                    (t) => PillBadge(label: t.toString(), color: AppTheme.blue),
                  )
                  .toList(),
            ),
          ],
        ],
      ),
    );
  }
}
