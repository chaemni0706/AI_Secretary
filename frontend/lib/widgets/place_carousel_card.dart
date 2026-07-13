import 'package:flutter/material.dart';
import '../models/recommended_place_model.dart';
import '../theme/app_constants.dart';
import '../theme/app_theme.dart';
import 'glass_card.dart';

/// 챗 안에서 추천 업체를 좌우 슬라이드(캐러셀)로 보여주고, 선택 콜백을 준다.
/// 반복되는 업체 카드 UI를 위젯으로 분리했다.
class PlaceCarouselCard extends StatefulWidget {
  final List<RecommendedPlace> places;
  final void Function(RecommendedPlace place) onSelect;

  const PlaceCarouselCard({
    super.key,
    required this.places,
    required this.onSelect,
  });

  @override
  State<PlaceCarouselCard> createState() => _PlaceCarouselCardState();
}

/// 선택 강조용 살구색(시연 시나리오 색).
const Color _kApricot = Color(0xFFF2A66D);

class _PlaceCarouselCardState extends State<PlaceCarouselCard> {
  final _controller = PageController(viewportFraction: 0.86);
  int _page = 0;

  /// "이 업체로 예약"으로 고른 카드 인덱스(살구색 테두리 강조).
  int? _selectedIndex;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (widget.places.isEmpty) {
      return const GlassCard(
        padding: EdgeInsets.all(14),
        child: Text(
          '조건에 맞는 업체를 찾지 못했어요.',
          style: TextStyle(fontSize: 13, color: AppTheme.textSecondary),
        ),
      );
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const Icon(
              Icons.storefront_outlined,
              size: 16,
              color: AppTheme.blue,
            ),
            const SizedBox(width: 6),
            Text(
              '추천 업체 ${widget.places.length}곳',
              style: const TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w700,
                color: AppTheme.textSecondary,
              ),
            ),
            if (widget.places.first.isMock) ...[
              const SizedBox(width: 6),
              const _MiniBadge('예시'),
            ],
          ],
        ),
        const SizedBox(height: 8),
        SizedBox(
          height: 220,
          child: PageView.builder(
            controller: _controller,
            itemCount: widget.places.length,
            onPageChanged: (i) => setState(() => _page = i),
            itemBuilder: (_, i) => Padding(
              padding: const EdgeInsets.only(right: 8),
              child: _PlaceCard(
                place: widget.places[i],
                selected: _selectedIndex == i,
                onSelect: () {
                  setState(() => _selectedIndex = i);
                  widget.onSelect(widget.places[i]);
                },
              ),
            ),
          ),
        ),
        const SizedBox(height: 8),
        Center(
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              for (var i = 0; i < widget.places.length; i++)
                Container(
                  width: 6,
                  height: 6,
                  margin: const EdgeInsets.symmetric(horizontal: 3),
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: i == _page ? AppTheme.blue : AppTheme.separator,
                  ),
                ),
            ],
          ),
        ),
      ],
    );
  }
}

class _PlaceCard extends StatelessWidget {
  final RecommendedPlace place;
  final VoidCallback onSelect;
  final bool selected;

  const _PlaceCard({
    required this.place,
    required this.onSelect,
    this.selected = false,
  });

  @override
  Widget build(BuildContext context) {
    // 선택된 카드는 살구색 테두리로 강조한다(시연 포인트).
    return AnimatedContainer(
      duration: const Duration(milliseconds: 200),
      curve: Curves.easeOut,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(TossRadius.lg),
        border: Border.all(
          color: selected ? _kApricot : Colors.transparent,
          width: 2,
        ),
      ),
      child: GlassCard(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  place.name,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppTextStyles.cardTitle.copyWith(
                    fontSize: 15,
                    color: AppTheme.textPrimary,
                  ),
                ),
              ),
              if (place.score > 0)
                Text(
                  '${place.score}점',
                  style: const TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                    color: AppTheme.blue,
                  ),
                ),
            ],
          ),
          if (place.address != null) ...[
            const SizedBox(height: 4),
            Text(
              place.address!,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                fontSize: 12,
                color: AppTheme.textSecondary,
              ),
            ),
          ],
          if (place.travel != null) ...[
            const SizedBox(height: 6),
            _TravelLine(travel: place.travel!),
          ],
          if (place.travelWalk != null) ...[
            const SizedBox(height: 2),
            _TravelLine(travel: place.travelWalk!),
          ],
          const Spacer(),
          if (place.tags.isNotEmpty) ...[
            const SizedBox(height: 8),
            Wrap(
              spacing: 6,
              runSpacing: 4,
              children: [for (final t in place.tags.take(3)) _MiniBadge(t)],
            ),
          ],
          const SizedBox(height: 8),
          SizedBox(
            width: double.infinity,
            child: FilledButton(
              onPressed: selected ? null : onSelect,
              style: FilledButton.styleFrom(
                backgroundColor: AppTheme.blue,
                foregroundColor: Colors.white,
                disabledBackgroundColor: _kApricot,
                disabledForegroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 8),
                minimumSize: const Size(0, 34),
              ),
              child: Text(
                selected ? '선택됨 ✓' : '이 업체로 예약',
                style: const TextStyle(fontSize: 13),
              ),
            ),
          ),
        ],
      ),
      ),
    );
  }
}

/// 현재 위치 → 업체까지의 소요시간·거리 한 줄. (예: 🚗 약 12분 · 3.2km)
class _TravelLine extends StatelessWidget {
  final PlaceTravel travel;
  const _TravelLine({required this.travel});

  IconData get _icon {
    if (travel.isWalking) return Icons.directions_walk_rounded;
    if (travel.isTransit) return Icons.directions_transit_rounded;
    return Icons.directions_car_filled_rounded;
  }

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(_icon, size: 14, color: AppTheme.blue),
        const SizedBox(width: 4),
        Flexible(
          child: Text(
            travel.label ?? '',
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: AppTheme.blue,
            ),
          ),
        ),
      ],
    );
  }
}

class _MiniBadge extends StatelessWidget {
  final String label;
  const _MiniBadge(this.label);

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: AppTheme.blue.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Text(
        label,
        style: const TextStyle(
          fontSize: 10.5,
          fontWeight: FontWeight.w600,
          color: AppTheme.blue,
        ),
      ),
    );
  }
}
