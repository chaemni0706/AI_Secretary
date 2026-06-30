import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../widgets/glass_card.dart';
import '../widgets/circular_timeline.dart';
import 'briefing_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final _pageController = PageController();
  int _timelinePage = 0;

  static const _events = [
    TimelineEvent(
        title: '발표', startHour: 9.5, endHour: 10.5, color: AppTheme.blue),
    TimelineEvent(
        title: '병원', startHour: 11.0, endHour: 11.5, color: AppTheme.teal),
    TimelineEvent(
        title: 'AI스터디',
        startHour: 14.0,
        endHour: 15.0,
        color: AppTheme.purple),
    TimelineEvent(
        title: '저녁', startHour: 19.0, endHour: 21.0, color: AppTheme.orange),
  ];

  static const _schedule = [
    _ScheduleItem('09:30', '발표 자료 최종 확인', AppTheme.blue),
    _ScheduleItem('11:00', '병원 예약 확인 전화', AppTheme.teal),
    _ScheduleItem('14:00', 'AI 스터디 노트 정리', AppTheme.purple),
    _ScheduleItem('19:00', '저녁 약속 준비', AppTheme.orange),
  ];

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: AppTheme.screenBackground,
      child: SafeArea(
        child: SingleChildScrollView(
          physics: const BouncingScrollPhysics(),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _buildHeader(),
              _buildBriefingCard(),
              _buildTimelineSection(),
              _buildDepartureCard(),
              _buildScheduleSection(),
              const SizedBox(height: 32),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          const Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '6월 29일 일요일',
                style: TextStyle(
                  fontSize: 26,
                  fontWeight: FontWeight.w700,
                  color: AppTheme.textPrimary,
                  letterSpacing: -0.5,
                ),
              ),
              SizedBox(height: 2),
              Text('오늘',
                  style: TextStyle(
                      fontSize: 14, color: AppTheme.textSecondary)),
            ],
          ),
          GestureDetector(
            onTap: () {},
            child: Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: Colors.white.withOpacity(0.7),
                shape: BoxShape.circle,
                border: Border.all(
                    color: AppTheme.separator.withOpacity(0.8), width: 0.5),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withOpacity(0.05),
                    blurRadius: 8,
                    offset: const Offset(0, 2),
                  ),
                ],
              ),
              child: const Icon(Icons.notifications_outlined,
                  color: AppTheme.textPrimary, size: 20),
            ),
          ),
        ],
      ),
    );
  }

  // 브리핑 카드: 파란색→보라색 그라데이션
  Widget _buildBriefingCard() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
      child: GestureDetector(
        onTap: () => Navigator.push(
          context,
          MaterialPageRoute(builder: (_) => const BriefingScreen()),
        ),
        child: Container(
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              colors: [AppTheme.blue, AppTheme.purple],
              begin: Alignment.centerLeft,
              end: Alignment.centerRight,
            ),
            borderRadius: BorderRadius.circular(18),
            boxShadow: [
              BoxShadow(
                color: AppTheme.blue.withOpacity(0.35),
                blurRadius: 18,
                offset: const Offset(0, 6),
              ),
            ],
          ),
          padding: const EdgeInsets.all(16),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 34,
                height: 34,
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.22),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Icon(Icons.auto_awesome,
                    color: Colors.white, size: 18),
              ),
              const SizedBox(width: 12),
              const Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '하루 브리핑',
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w600,
                        color: Colors.white70,
                        letterSpacing: 0.3,
                      ),
                    ),
                    SizedBox(height: 4),
                    Text(
                      '오전 발표 준비와 오후 병원 일정이 중요해요. 13시 15분쯤 출발하세요.',
                      style: TextStyle(
                          fontSize: 14, color: Colors.white, height: 1.45),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 4),
              const Icon(Icons.chevron_right,
                  color: Colors.white70, size: 20),
            ],
          ),
        ),
      ),
    );
  }

  // 타임라인 섹션: 좌우 슬라이드 (도넛 / 크로노덱스)
  Widget _buildTimelineSection() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 0),
      child: GlassCard(
        padding: const EdgeInsets.fromLTRB(16, 20, 16, 14),
        child: LayoutBuilder(
          builder: (context, constraints) {
            final tlSize = constraints.maxWidth - 0; // 카드 inner width
            return Column(
              children: [
                // ─ PageView: 도넛 / 크로노덱스 ─
                SizedBox(
                  height: tlSize,
                  child: PageView(
                    controller: _pageController,
                    physics: const PageScrollPhysics(),
                    onPageChanged: (i) => setState(() => _timelinePage = i),
                    children: [
                      // Page 0: 도넛 타임라인
                      Center(
                        child: CircularTimeline(
                          events: _events,
                          currentHour: 9.68,
                          size: tlSize,
                          progressPercent: 0.68,
                        ),
                      ),
                      // Page 1: 하루 일정 타임라인
                      _buildDailySlide(),
                    ],
                  ),
                ),

                // ─ 페이지 도트 인디케이터 ─
                const SizedBox(height: 12),
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: List.generate(2, (i) {
                    final active = i == _timelinePage;
                    return AnimatedContainer(
                      duration: const Duration(milliseconds: 250),
                      margin: const EdgeInsets.symmetric(horizontal: 3),
                      width: active ? 18 : 6,
                      height: 6,
                      decoration: BoxDecoration(
                        color: active
                            ? AppTheme.blue
                            : AppTheme.separator,
                        borderRadius: BorderRadius.circular(3),
                      ),
                    );
                  }),
                ),

                // ─ 범례 ─
                const SizedBox(height: 14),
                const Divider(color: AppTheme.separator, height: 1),
                const SizedBox(height: 10),
                Wrap(
                  spacing: 14,
                  runSpacing: 6,
                  alignment: WrapAlignment.center,
                  children: _events
                      .map((e) => Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Container(
                                width: 7,
                                height: 7,
                                decoration: BoxDecoration(
                                    color: e.color,
                                    shape: BoxShape.circle),
                              ),
                              const SizedBox(width: 5),
                              Text(e.title,
                                  style: const TextStyle(
                                    fontSize: 12,
                                    color: AppTheme.textSecondary,
                                  )),
                            ],
                          ))
                      .toList(),
                ),
              ],
            );
          },
        ),
      ),
    );
  }

  // 하루 일정 타임라인 슬라이드 (PageView page 1)
  Widget _buildDailySlide() {
    return ListView.builder(
      padding: const EdgeInsets.fromLTRB(0, 4, 4, 4),
      physics: const ClampingScrollPhysics(),
      itemCount: 14, // 8:00 ~ 21:00
      itemBuilder: (context, i) {
        final hour = 8 + i;
        final event = _schedule.cast<_ScheduleItem?>().firstWhere(
          (s) => s != null && int.parse(s.time.split(':')[0]) == hour,
          orElse: () => null,
        );
        final isCurrent = hour == 9;

        return Padding(
          padding: const EdgeInsets.only(bottom: 2),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SizedBox(
                width: 38,
                child: Padding(
                  padding: const EdgeInsets.only(top: 3),
                  child: Text(
                    '$hour:00',
                    textAlign: TextAlign.right,
                    style: TextStyle(
                      fontSize: 10,
                      color: isCurrent ? AppTheme.blue : AppTheme.textSecondary,
                      fontWeight:
                          isCurrent ? FontWeight.w700 : FontWeight.w400,
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      height: 1,
                      color: isCurrent
                          ? AppTheme.blue.withOpacity(0.4)
                          : AppTheme.separator,
                    ),
                    if (event != null) ...[
                      const SizedBox(height: 3),
                      Container(
                        margin: const EdgeInsets.only(bottom: 4),
                        padding: const EdgeInsets.symmetric(
                            horizontal: 10, vertical: 7),
                        decoration: BoxDecoration(
                          color: event.color.withOpacity(0.09),
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(
                              color: event.color.withOpacity(0.28)),
                        ),
                        child: Row(
                          children: [
                            Container(
                              width: 3,
                              height: 16,
                              decoration: BoxDecoration(
                                color: event.color,
                                borderRadius: BorderRadius.circular(2),
                              ),
                            ),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                event.title,
                                style: TextStyle(
                                  fontSize: 12,
                                  fontWeight: FontWeight.w600,
                                  color: event.color,
                                ),
                              ),
                            ),
                            Text(
                              event.time,
                              style: TextStyle(
                                fontSize: 10,
                                color: event.color.withOpacity(0.65),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ] else
                      const SizedBox(height: 26),
                  ],
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  // AI 추천 출발 알림 카드
  Widget _buildDepartureCard() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 0),
      child: GlassCard(
        color: AppTheme.blue.withOpacity(0.1),
        child: Row(
          children: [
            Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: AppTheme.blue.withOpacity(0.15),
                borderRadius: BorderRadius.circular(12),
              ),
              child: const Icon(Icons.directions_walk,
                  color: AppTheme.blue, size: 22),
            ),
            const SizedBox(width: 12),
            const Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('13:15 출발 권장',
                      style: TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                        color: AppTheme.blue,
                      )),
                  SizedBox(height: 2),
                  Text('병원 전 신분증·진료카드·우산 챙기기 (비 예보)',
                      style: TextStyle(
                          fontSize: 12, color: AppTheme.textTertiary)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  // 오늘 일정
  Widget _buildScheduleSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 18, 20, 10),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text('오늘 일정',
                  style: TextStyle(
                    fontSize: 17,
                    fontWeight: FontWeight.w700,
                    color: AppTheme.textPrimary,
                  )),
              GestureDetector(
                onTap: () {},
                child: Container(
                  width: 30,
                  height: 30,
                  decoration: BoxDecoration(
                    color: Colors.white,
                    shape: BoxShape.circle,
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withOpacity(0.1),
                        blurRadius: 8,
                        offset: const Offset(0, 2),
                      ),
                    ],
                  ),
                  child: const Icon(Icons.add,
                      size: 18, color: AppTheme.textPrimary),
                ),
              ),
            ],
          ),
        ),
        ...List.generate(_schedule.length, (i) {
          return Padding(
            padding:
                EdgeInsets.fromLTRB(16, i == 0 ? 0 : 6, 16, 0),
            child: GlassCard(
              padding: const EdgeInsets.symmetric(
                  horizontal: 16, vertical: 13),
              child: Row(
                children: [
                  Container(
                    width: 3,
                    height: 36,
                    decoration: BoxDecoration(
                      color: _schedule[i].color,
                      borderRadius: BorderRadius.circular(2),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(_schedule[i].title,
                            style: const TextStyle(
                              fontSize: 14,
                              fontWeight: FontWeight.w600,
                              color: AppTheme.textPrimary,
                            )),
                        const SizedBox(height: 2),
                        Text(_schedule[i].time,
                            style: const TextStyle(
                              fontSize: 12,
                              color: AppTheme.textSecondary,
                            )),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          );
        }),
      ],
    );
  }
}

class _ScheduleItem {
  final String time;
  final String title;
  final Color color;
  const _ScheduleItem(this.time, this.title, this.color);
}
