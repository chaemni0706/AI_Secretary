import 'package:flutter/material.dart';
import '../models/reservation_model.dart';
import '../theme/app_theme.dart';
import 'glass_card.dart';

/// 선택한 업체의 예약 후보 시간을 챗 안에서 보여주고 시간 선택 콜백을 준다.
class ReservationTimeCard extends StatelessWidget {
  final String placeName;
  final String dateLabel;
  final List<ReservationCandidate> candidates;
  final void Function(ReservationCandidate candidate) onSelect;

  const ReservationTimeCard({
    super.key,
    required this.placeName,
    required this.dateLabel,
    required this.candidates,
    required this.onSelect,
  });

  @override
  Widget build(BuildContext context) {
    final open = candidates.where((c) => !c.conflict).toList();
    return GlassCard(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.event_available_outlined,
                  size: 16, color: AppTheme.teal),
              const SizedBox(width: 6),
              Expanded(
                child: Text('$placeName · $dateLabel 예약 가능 시간',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w700,
                        color: AppTheme.textPrimary)),
              ),
            ],
          ),
          const SizedBox(height: 10),
          if (open.isEmpty)
            const Text('예약 가능한 시간을 찾지 못했어요. 다른 날짜로 다시 시도해주세요.',
                style: TextStyle(fontSize: 12.5, color: AppTheme.textSecondary))
          else
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final c in open.take(6))
                  GestureDetector(
                    onTap: () => onSelect(c),
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 14, vertical: 9),
                      decoration: BoxDecoration(
                        color: AppTheme.blue.withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(14),
                        border: Border.all(
                            color: AppTheme.blue.withValues(alpha: 0.4)),
                      ),
                      child: Text(
                        c.startTime,
                        style: const TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w700,
                            color: AppTheme.blue),
                      ),
                    ),
                  ),
              ],
            ),
        ],
      ),
    );
  }
}
