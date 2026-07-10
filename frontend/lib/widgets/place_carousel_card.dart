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

class _PlaceCarouselCardState extends State<PlaceCarouselCard> {
  final _controller = PageController(viewportFraction: 0.86);
  int _page = 0;

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
          height: 184,
          child: PageView.builder(
            controller: _controller,
            itemCount: widget.places.length,
            onPageChanged: (i) => setState(() => _page = i),
            itemBuilder: (_, i) => Padding(
              padding: const EdgeInsets.only(right: 8),
              child: _PlaceCard(
                place: widget.places[i],
                onSelect: () => widget.onSelect(widget.places[i]),
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

  const _PlaceCard({required this.place, required this.onSelect});

  @override
  Widget build(BuildContext context) {
    return GlassCard(
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
          if (place.reason.isNotEmpty) ...[
            const SizedBox(height: 6),
            Text(
              place.reason,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                fontSize: 12.5,
                height: 1.3,
                color: AppTheme.textPrimary,
              ),
            ),
          ],
          const Spacer(),
          if (place.tags.isNotEmpty)
            Wrap(
              spacing: 6,
              children: [for (final t in place.tags.take(3)) _MiniBadge(t)],
            ),
          const SizedBox(height: 8),
          SizedBox(
            width: double.infinity,
            child: FilledButton(
              onPressed: onSelect,
              style: FilledButton.styleFrom(
                backgroundColor: AppTheme.blue,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 8),
                minimumSize: const Size(0, 34),
              ),
              child: const Text('이 업체로 예약', style: TextStyle(fontSize: 13)),
            ),
          ),
        ],
      ),
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
