import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../widgets/glass_card.dart';
import '../widgets/circular_timeline.dart';
import '../models/dashboard_model.dart';
import '../models/schedule_model.dart';
import '../services/dashboard_api.dart';
import '../services/api_client.dart';
import 'briefing_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  bool _loading = true;
  String? _error;
  DashboardData? _data;

  @override
  void initState() {
    super.initState();
    _load();
    // 다른 화면(AI 챗 등)에서 저장 후 트리거하면 대시보드를 다시 불러온다.
    dashboardRefresh.addListener(_load);
  }

  @override
  void dispose() {
    dashboardRefresh.removeListener(_load);
    super.dispose();
  }

  Future<void> _load() async {
    if (mounted) {
      setState(() {
        _loading = true;
        _error = null;
      });
    }
    try {
      // date 미지정 → 서버가 오늘 날짜로 응답.
      final data = await dashboardApi.getTodayDashboard();
      if (!mounted) return;
      setState(() {
        _data = data;
        _loading = false;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.message;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = '대시보드를 불러오지 못했습니다. ($e)';
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: AppTheme.screenBackground,
      child: SafeArea(
        child: RefreshIndicator(
          onRefresh: _load,
          child: SingleChildScrollView(
            physics: const AlwaysScrollableScrollPhysics(
              parent: BouncingScrollPhysics(),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _buildHeader(context),
                if (_loading)
                  _buildLoading()
                else if (_error != null)
                  _buildError()
                else ...[
                  _buildBriefingCard(context),
                  _buildProgressRow(),
                  _buildTimelineSection(context),
                  _buildScheduleSection(context),
                  _buildDepartureCard(),
                  _buildQuickActions(context),
                ],
                const SizedBox(height: 24),
              ],
            ),
          ),
        ),
      ),
    );
  }

  // ---- helpers --------------------------------------------------------------

  static const List<String> _weekdayKo = ['월', '화', '수', '목', '금', '토', '일'];

  String _formatHeaderDate(String? isoDate) {
    if (isoDate == null || isoDate.length < 10) return '오늘';
    try {
      final d = DateTime.parse(isoDate);
      final w = _weekdayKo[(d.weekday - 1) % 7];
      return '${d.month}월 ${d.day}일 $w요일';
    } catch (_) {
      return isoDate;
    }
  }

  double _timeToHour(String? hhmm) {
    if (hhmm == null || !hhmm.contains(':')) return 0;
    final parts = hhmm.split(':');
    final h = int.tryParse(parts[0]) ?? 0;
    final m = int.tryParse(parts[1]) ?? 0;
    return h + m / 60.0;
  }

  static const List<Color> _palette = [
    AppTheme.blue,
    AppTheme.teal,
    AppTheme.purple,
    AppTheme.orange,
    AppTheme.green,
  ];

  Color _colorFor(String? category, int index) {
    switch (category) {
      case 'hospital':
        return AppTheme.teal;
      case 'meeting':
      case 'work':
        return AppTheme.blue;
      case 'study':
        return AppTheme.purple;
      case 'meal':
      case 'beauty':
        return AppTheme.orange;
      case 'exercise':
        return AppTheme.green;
      default:
        return _palette[index % _palette.length];
    }
  }

  IconData _iconFor(String? category) {
    switch (category) {
      case 'hospital':
        return Icons.local_hospital_outlined;
      case 'study':
        return Icons.book_outlined;
      case 'meeting':
      case 'work':
        return Icons.work_outline;
      case 'meal':
        return Icons.restaurant_outlined;
      case 'beauty':
        return Icons.content_cut_outlined;
      case 'exercise':
        return Icons.fitness_center_outlined;
      default:
        return Icons.event_outlined;
    }
  }

  // ---- sections -------------------------------------------------------------

  Widget _buildLoading() {
    return const Padding(
      padding: EdgeInsets.only(top: 120),
      child: Center(child: CircularProgressIndicator()),
    );
  }

  Widget _buildError() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 60, 16, 0),
      child: GlassCard(
        padding: const EdgeInsets.all(20),
        child: Column(
          children: [
            const Icon(Icons.cloud_off, color: AppTheme.textSecondary, size: 36),
            const SizedBox(height: 12),
            Text(
              _error ?? '데이터를 불러오지 못했습니다.',
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 14, color: AppTheme.textPrimary),
            ),
            const SizedBox(height: 6),
            const Text(
              '백엔드 서버(127.0.0.1:8000)가 실행 중인지 확인하세요.',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
            ),
            const SizedBox(height: 14),
            FilledButton(
              onPressed: _load,
              style: FilledButton.styleFrom(backgroundColor: AppTheme.blue),
              child: const Text('다시 시도'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                _formatHeaderDate(_data?.date),
                style: const TextStyle(
                  fontSize: 26,
                  fontWeight: FontWeight.w700,
                  color: AppTheme.textPrimary,
                  letterSpacing: -0.5,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                '오늘',
                style: TextStyle(
                  fontSize: 14,
                  color: AppTheme.textSecondary,
                ),
              ),
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
                boxShadow: TossShadow.tiny,
              ),
              child: const Icon(Icons.notifications_outlined,
                  color: AppTheme.textPrimary, size: 20),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildBriefingCard(BuildContext context) {
    // summary_message 가 있으면 API 값을, 없으면 기본 문구.
    final summary = (_data?.summaryMessage.isNotEmpty ?? false)
        ? _data!.summaryMessage
        : '오늘의 일정과 할 일을 확인해 보세요.';
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
      child: GlassCard(
        onTap: () => Navigator.push(
          context,
          MaterialPageRoute(builder: (_) => const BriefingScreen()),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 34,
              height: 34,
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [AppTheme.purple, AppTheme.blue],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                borderRadius: BorderRadius.circular(10),
              ),
              child: const Icon(Icons.auto_awesome,
                  color: Colors.white, size: 18),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                summary,
                style: const TextStyle(
                  fontSize: 14,
                  color: AppTheme.textPrimary,
                  height: 1.45,
                ),
              ),
            ),
            const SizedBox(width: 4),
            const Icon(Icons.chevron_right,
                color: AppTheme.textSecondary, size: 20),
          ],
        ),
      ),
    );
  }

  Widget _buildProgressRow() {
    final stats = _data?.stats ?? const DashboardStats();
    final rate = stats.todoCompletionRate.clamp(0.0, 1.0);
    final percent = (rate * 100).round();
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
      child: Row(
        children: [
          Expanded(
            flex: 3,
            child: GlassCard(
              padding: const EdgeInsets.all(14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '$percent%',
                    style: const TextStyle(
                      fontSize: 24,
                      fontWeight: FontWeight.w700,
                      color: AppTheme.blue,
                      letterSpacing: -0.5,
                    ),
                  ),
                  const SizedBox(height: 6),
                  ClipRRect(
                    borderRadius: BorderRadius.circular(4),
                    child: LinearProgressIndicator(
                      value: rate,
                      backgroundColor: AppTheme.separator,
                      valueColor: const AlwaysStoppedAnimation(AppTheme.blue),
                      minHeight: 5,
                    ),
                  ),
                  const SizedBox(height: 6),
                  const Text(
                    '오늘 할 일 진행률',
                    style: TextStyle(
                      fontSize: 12,
                      color: AppTheme.textSecondary,
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            flex: 2,
            child: GlassCard(
              padding: const EdgeInsets.all(14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '${stats.scheduleCount}개',
                    style: const TextStyle(
                      fontSize: 24,
                      fontWeight: FontWeight.w700,
                      color: AppTheme.orange,
                      letterSpacing: -0.5,
                    ),
                  ),
                  const SizedBox(height: 12),
                  const Text(
                    '오늘 일정',
                    style: TextStyle(
                      fontSize: 12,
                      color: AppTheme.textSecondary,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTimelineSection(BuildContext context) {
    final schedules = _data?.schedules ?? const [];
    final events = <TimelineEvent>[];
    for (var i = 0; i < schedules.length; i++) {
      final s = schedules[i];
      if (s.startTime == null) continue;
      final start = _timeToHour(s.startTime);
      final end = s.endTime != null ? _timeToHour(s.endTime) : start + 1;
      events.add(TimelineEvent(
        title: s.title,
        startHour: start,
        endHour: end > start ? end : start + 0.5,
        color: _colorFor(s.category, i),
      ));
    }
    final now = DateTime.now();
    final currentHour = now.hour + now.minute / 60.0;

    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
      child: GlassCard(
        padding: const EdgeInsets.all(20),
        child: Column(
          children: [
            Center(
              child: CircularTimeline(
                events: events,
                currentHour: currentHour,
                size: MediaQuery.of(context).size.width - 112,
              ),
            ),
            const SizedBox(height: 16),
            const Divider(color: AppTheme.separator, height: 1),
            const SizedBox(height: 12),
            if (events.isEmpty)
              const Text(
                '오늘 등록된 일정이 없습니다.',
                style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
              )
            else
              Wrap(
                spacing: 12,
                runSpacing: 6,
                children: events
                    .map((e) => Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Container(
                              width: 8,
                              height: 8,
                              decoration: BoxDecoration(
                                  color: e.color, shape: BoxShape.circle),
                            ),
                            const SizedBox(width: 5),
                            Text(
                              e.title,
                              style: const TextStyle(
                                fontSize: 12,
                                color: AppTheme.textSecondary,
                              ),
                            ),
                          ],
                        ))
                    .toList(),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildScheduleSection(BuildContext context) {
    final schedules = _data?.schedules ?? const [];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SectionHeader(title: '오늘 일정', trailing: '전체 보기'),
        if (schedules.isEmpty)
          const Padding(
            padding: EdgeInsets.fromLTRB(16, 0, 16, 0),
            child: GlassCard(
              padding: EdgeInsets.symmetric(horizontal: 16, vertical: 18),
              child: Text(
                '오늘 일정이 없습니다. AI 탭에서 자연어로 추가해 보세요.',
                style: TextStyle(fontSize: 13, color: AppTheme.textSecondary),
              ),
            ),
          )
        else
          ...List.generate(
            schedules.length,
            (i) => Padding(
              padding: EdgeInsets.fromLTRB(16, i == 0 ? 0 : 6, 16, 0),
              child: _scheduleRow(schedules[i], i),
            ),
          ),
      ],
    );
  }

  Widget _scheduleRow(ScheduleModel s, int i) {
    final color = _colorFor(s.category, i);
    final timeText = s.startTime == null
        ? '시간 미정'
        : (s.endTime != null ? '${s.startTime} – ${s.endTime}' : s.startTime!);
    return GlassCard(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: Row(
        children: [
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              color: color.withOpacity(0.12),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(_iconFor(s.category), color: color, size: 18),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  s.title,
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.textPrimary,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  timeText,
                  style: const TextStyle(
                    fontSize: 12,
                    color: AppTheme.textSecondary,
                  ),
                ),
              ],
            ),
          ),
          Container(
            width: 6,
            height: 6,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          ),
        ],
      ),
    );
  }

  Widget _buildDepartureCard() {
    // NOTE: 출발 권장/준비물은 아직 mock. (알림 API 연동은 후속 단계)
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
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
                  Text(
                    '출발/준비물 알림',
                    style: TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.w700,
                      color: AppTheme.blue,
                    ),
                  ),
                  SizedBox(height: 2),
                  Text(
                    '일정을 선택하면 알림 계획을 만들 수 있어요.',
                    style: TextStyle(
                      fontSize: 12,
                      color: AppTheme.textTertiary,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildQuickActions(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
      child: Row(
        children: [
          _QuickAction(
            icon: Icons.mic,
            label: 'AI 말하기',
            color: AppTheme.purple,
            onTap: () {},
          ),
          const SizedBox(width: 10),
          _QuickAction(
            icon: Icons.event,
            label: '일정 추가',
            color: AppTheme.blue,
            onTap: () {},
          ),
          const SizedBox(width: 10),
          _QuickAction(
            icon: Icons.add_task,
            label: '할 일 추가',
            color: AppTheme.green,
            onTap: () {},
          ),
          const SizedBox(width: 10),
          _QuickAction(
            icon: Icons.summarize_outlined,
            label: '브리핑',
            color: AppTheme.orange,
            onTap: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => const BriefingScreen()),
            ),
          ),
        ],
      ),
    );
  }
}

class _QuickAction extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color color;
  final VoidCallback onTap;

  const _QuickAction({
    required this.icon,
    required this.label,
    required this.color,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: GestureDetector(
        onTap: onTap,
        child: GlassCard(
          padding: const EdgeInsets.symmetric(vertical: 12),
          child: Column(
            children: [
              Container(
                width: 38,
                height: 38,
                decoration: BoxDecoration(
                  color: color.withOpacity(0.14),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(icon, color: color, size: 20),
              ),
              const SizedBox(height: 6),
              Text(
                label,
                style: const TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w500,
                  color: AppTheme.textPrimary,
                ),
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
