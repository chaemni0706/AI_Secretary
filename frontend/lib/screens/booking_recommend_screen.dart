import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../widgets/glass_card.dart';
import 'booking_message_screen.dart';

class BookingRecommendScreen extends StatefulWidget {
  const BookingRecommendScreen({super.key});

  @override
  State<BookingRecommendScreen> createState() =>
      _BookingRecommendScreenState();
}

class _BookingRecommendScreenState extends State<BookingRecommendScreen> {
  int _selectedSlot = 0;

  static const _slots = [
    _TimeSlot(
      rank: 1,
      score: 92,
      date: '7월 3일 (금)',
      time: '오후 7:00 – 8:00',
      reason: '기존 일정 사이의 빈 시간 · 충돌 없음',
      reasonIcon: Icons.check_circle_outline,
      reasonColor: AppTheme.green,
    ),
    _TimeSlot(
      rank: 2,
      score: 85,
      date: '7월 3일 (금)',
      time: '오후 8:30 – 9:30',
      reason: '이동 시간 여유 있음',
      reasonIcon: Icons.directions_car_outlined,
      reasonColor: AppTheme.blue,
    ),
    _TimeSlot(
      rank: 3,
      score: 78,
      date: '7월 4일 (토)',
      time: '오전 11:00 – 12:00',
      reason: '오전 시간대 가능',
      reasonIcon: Icons.wb_twilight,
      reasonColor: AppTheme.orange,
    ),
  ];

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
                color: Colors.white.withOpacity(0.7),
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.chevron_left,
                  color: AppTheme.textPrimary, size: 26),
            ),
          ),
          title: const Text('예약 후보 추천'),
        ),
        body: SingleChildScrollView(
          physics: const BouncingScrollPhysics(),
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 80),
          child: Column(
            children: [
              _buildRequestCard(),
              const SizedBox(height: 16),
              _buildSlotsHeader(),
              const SizedBox(height: 10),
              ..._buildSlotCards(context),
              const SizedBox(height: 20),
              _buildActionButtons(context),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildRequestCard() {
    return GlassCard(
      child: Row(
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: AppTheme.purple.withOpacity(0.12),
              borderRadius: BorderRadius.circular(14),
            ),
            child: const Icon(Icons.content_cut,
                color: AppTheme.purple, size: 22),
          ),
          const SizedBox(width: 14),
          const Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '미용실 · 커트',
                  style: TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w700,
                    color: AppTheme.textPrimary,
                  ),
                ),
                SizedBox(height: 3),
                Text(
                  '이번 주 금요일 저녁 · 소요 60분',
                  style: TextStyle(
                    fontSize: 13,
                    color: AppTheme.textSecondary,
                  ),
                ),
              ],
            ),
          ),
          GestureDetector(
            onTap: () {},
            child: Container(
              width: 32,
              height: 32,
              decoration: BoxDecoration(
                color: AppTheme.textSecondary.withOpacity(0.1),
                borderRadius: BorderRadius.circular(10),
              ),
              child: const Icon(Icons.edit_outlined,
                  color: AppTheme.textSecondary, size: 16),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSlotsHeader() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        const Text(
          '추천 후보 3',
          style: TextStyle(
            fontSize: 17,
            fontWeight: FontWeight.w700,
            color: AppTheme.textPrimary,
          ),
        ),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
          decoration: BoxDecoration(
            color: AppTheme.blue.withOpacity(0.1),
            borderRadius: BorderRadius.circular(10),
          ),
          child: const Text(
            '충돌 없는 시간대',
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: AppTheme.blue,
            ),
          ),
        ),
      ],
    );
  }

  List<Widget> _buildSlotCards(BuildContext context) {
    return List.generate(_slots.length, (i) {
      final slot = _slots[i];
      final isSelected = i == _selectedSlot;
      return Padding(
        padding: const EdgeInsets.only(bottom: 10),
        child: GestureDetector(
          onTap: () => setState(() => _selectedSlot = i),
          child: GlassCard(
            color: isSelected
                ? AppTheme.blue.withOpacity(0.08)
                : Colors.white.withOpacity(0.72),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Rank circle
                Container(
                  width: 36,
                  height: 36,
                  decoration: BoxDecoration(
                    color: isSelected
                        ? AppTheme.blue
                        : AppTheme.textSecondary.withOpacity(0.12),
                    shape: BoxShape.circle,
                  ),
                  child: Center(
                    child: Text(
                      '${slot.rank}',
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                        color: isSelected
                            ? Colors.white
                            : AppTheme.textSecondary,
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Text(
                            slot.date,
                            style: const TextStyle(
                              fontSize: 15,
                              fontWeight: FontWeight.w700,
                              color: AppTheme.textPrimary,
                            ),
                          ),
                          const Spacer(),
                          // Score badge
                          Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 8, vertical: 3),
                            decoration: BoxDecoration(
                              color: isSelected
                                  ? AppTheme.blue
                                  : AppTheme.textSecondary.withOpacity(0.1),
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Text(
                              '${slot.score}점',
                              style: TextStyle(
                                fontSize: 12,
                                fontWeight: FontWeight.w700,
                                color: isSelected
                                    ? Colors.white
                                    : AppTheme.textSecondary,
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 4),
                      Text(
                        slot.time,
                        style: TextStyle(
                          fontSize: 14,
                          color: isSelected
                              ? AppTheme.blue
                              : AppTheme.textPrimary,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                      const SizedBox(height: 6),
                      Row(
                        children: [
                          Icon(slot.reasonIcon,
                              size: 14, color: slot.reasonColor),
                          const SizedBox(width: 5),
                          Text(
                            slot.reason,
                            style: TextStyle(
                              fontSize: 12,
                              color: slot.reasonColor,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      );
    });
  }

  Widget _buildActionButtons(BuildContext context) {
    return Column(
      children: [
        SizedBox(
          width: double.infinity,
          child: FilledButton.icon(
            onPressed: () {},
            icon: const Icon(Icons.event_available, size: 18),
            label: const Text('캘린더에 등록하기',
                style:
                    TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
            style: FilledButton.styleFrom(
              backgroundColor: AppTheme.blue,
              padding: const EdgeInsets.symmetric(vertical: 14),
              shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(14)),
            ),
          ),
        ),
        const SizedBox(height: 10),
        SizedBox(
          width: double.infinity,
          child: OutlinedButton.icon(
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => const BookingMessageScreen()),
            ),
            icon: const Icon(Icons.forum_outlined, size: 18),
            label: const Text('예약 메시지 생성',
                style:
                    TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
            style: OutlinedButton.styleFrom(
              foregroundColor: AppTheme.textPrimary,
              side: const BorderSide(color: AppTheme.separator, width: 1.5),
              padding: const EdgeInsets.symmetric(vertical: 14),
              shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(14)),
            ),
          ),
        ),
      ],
    );
  }
}

class _TimeSlot {
  final int rank;
  final int score;
  final String date;
  final String time;
  final String reason;
  final IconData reasonIcon;
  final Color reasonColor;

  const _TimeSlot({
    required this.rank,
    required this.score,
    required this.date,
    required this.time,
    required this.reason,
    required this.reasonIcon,
    required this.reasonColor,
  });
}
