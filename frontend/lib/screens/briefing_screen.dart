import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../widgets/glass_card.dart';

class BriefingScreen extends StatelessWidget {
  const BriefingScreen({super.key});

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
          title: const Text('오늘의 브리핑'),
        ),
        body: SingleChildScrollView(
          physics: const BouncingScrollPhysics(),
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 80),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _buildDateBadge(),
              const SizedBox(height: 16),
              _buildSummaryCard(),
              const SizedBox(height: 16),
              _buildKeySchedules(),
              const SizedBox(height: 16),
              _buildChecklistSection(),
              const SizedBox(height: 16),
              _buildDepartureCard(),
              const SizedBox(height: 16),
              _buildNotificationsSection(),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildDateBadge() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
      decoration: BoxDecoration(
        color: AppTheme.blue.withOpacity(0.1),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppTheme.blue.withOpacity(0.2)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.auto_awesome, color: AppTheme.blue, size: 16),
          const SizedBox(width: 6),
          const Text(
            '6월 29일 일요일',
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w600,
              color: AppTheme.blue,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSummaryCard() {
    return GlassCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.auto_awesome, color: AppTheme.purple, size: 18),
              SizedBox(width: 8),
              Text(
                '요약',
                style: TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w700,
                  color: AppTheme.textPrimary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          const Text(
            '오늘은 오전 발표 준비와 오후 병원 일정이 중요합니다. '
            '병원 예약 전에는 신분증과 진료카드를 챙기고, '
            '이동 시간을 고려해 13시 15분쯤 출발하는 것이 좋습니다.',
            style: TextStyle(
              fontSize: 14,
              color: AppTheme.textPrimary,
              height: 1.55,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildKeySchedules() {
    final items = [
      _BriefingSchedule(
        icon: Icons.work_outline,
        iconColor: AppTheme.blue,
        badge: '중요',
        badgeColor: AppTheme.red,
        title: '발표 자료 최종 확인',
        subtitle: '09:30 · 13:00 마감',
      ),
      _BriefingSchedule(
        icon: Icons.local_hospital_outlined,
        iconColor: AppTheme.teal,
        badge: '병원',
        badgeColor: AppTheme.teal,
        title: '병원 예약',
        subtitle: '14:00 · 출발 준비 필요',
      ),
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SectionHeader(title: '핵심 일정'),
        ...items.map((item) => Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: GlassCard(
                padding: const EdgeInsets.all(14),
                child: Row(
                  children: [
                    Container(
                      width: 40,
                      height: 40,
                      decoration: BoxDecoration(
                        color: item.iconColor.withOpacity(0.12),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Icon(item.icon,
                          color: item.iconColor, size: 20),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Text(
                                item.title,
                                style: const TextStyle(
                                  fontSize: 14,
                                  fontWeight: FontWeight.w600,
                                  color: AppTheme.textPrimary,
                                ),
                              ),
                              const SizedBox(width: 8),
                              PillBadge(
                                  label: item.badge,
                                  color: item.badgeColor),
                            ],
                          ),
                          const SizedBox(height: 3),
                          Text(
                            item.subtitle,
                            style: const TextStyle(
                              fontSize: 12,
                              color: AppTheme.textSecondary,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            )),
      ],
    );
  }

  Widget _buildChecklistSection() {
    final supplies = [
      (Icons.credit_card_outlined, '신분증', true),
      (Icons.contact_page_outlined, '진료카드', true),
      (Icons.umbrella_outlined, '우산', false),
    ];

    return GlassCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.checklist, color: AppTheme.green, size: 20),
              SizedBox(width: 8),
              Text(
                '챙길 준비물',
                style: TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w700,
                  color: AppTheme.textPrimary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          ...supplies.map((s) {
            final (icon, label, isDone) = s;
            return Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: Row(
                children: [
                  Container(
                    width: 34,
                    height: 34,
                    decoration: BoxDecoration(
                      color: isDone
                          ? AppTheme.green.withOpacity(0.12)
                          : AppTheme.textSecondary.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Icon(icon,
                        color:
                            isDone ? AppTheme.green : AppTheme.textSecondary,
                        size: 18),
                  ),
                  const SizedBox(width: 10),
                  Text(
                    label,
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w500,
                      color: isDone
                          ? AppTheme.textSecondary
                          : AppTheme.textPrimary,
                      decoration:
                          isDone ? TextDecoration.lineThrough : null,
                    ),
                  ),
                  const Spacer(),
                  Icon(
                    isDone ? Icons.check_circle : Icons.radio_button_unchecked,
                    color:
                        isDone ? AppTheme.green : AppTheme.textSecondary,
                    size: 20,
                  ),
                ],
              ),
            );
          }),
        ],
      ),
    );
  }

  Widget _buildDepartureCard() {
    return GlassCard(
      color: AppTheme.blue.withOpacity(0.08),
      child: Row(
        children: [
          Container(
            width: 48,
            height: 48,
            decoration: BoxDecoration(
              color: AppTheme.blue.withOpacity(0.15),
              borderRadius: BorderRadius.circular(14),
            ),
            child: const Icon(Icons.directions_walk,
                color: AppTheme.blue, size: 26),
          ),
          const SizedBox(width: 14),
          const Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '13:15 출발 권장',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w700,
                    color: AppTheme.blue,
                  ),
                ),
                SizedBox(height: 3),
                Text(
                  '이동 25분 · 여유 20분 · 비 예보',
                  style: TextStyle(
                    fontSize: 13,
                    color: AppTheme.textTertiary,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildNotificationsSection() {
    return GlassCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.notifications_outlined,
                  color: AppTheme.orange, size: 20),
              SizedBox(width: 8),
              Text(
                '알림 설정',
                style: TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w700,
                  color: AppTheme.textPrimary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          _notifRow('발표 자료 확인', '30분 전 · 오전 9:00'),
          const SizedBox(height: 8),
          _notifRow('출발 알림', '오후 1:00'),
          const SizedBox(height: 8),
          _notifRow('병원 예약', '1시간 전 · 오후 1:00'),
        ],
      ),
    );
  }

  Widget _notifRow(String title, String time) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(title,
            style: const TextStyle(
                fontSize: 13, color: AppTheme.textPrimary)),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
          decoration: BoxDecoration(
            color: AppTheme.orange.withOpacity(0.12),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Text(
            time,
            style: const TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: AppTheme.orange,
            ),
          ),
        ),
      ],
    );
  }
}

class _BriefingSchedule {
  final IconData icon;
  final Color iconColor;
  final String badge;
  final Color badgeColor;
  final String title;
  final String subtitle;

  const _BriefingSchedule({
    required this.icon,
    required this.iconColor,
    required this.badge,
    required this.badgeColor,
    required this.title,
    required this.subtitle,
  });
}
