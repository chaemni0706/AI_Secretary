import 'package:flutter/material.dart';
import '../models/recommended_place_model.dart';
import '../screens/calendar_screen.dart';
import '../screens/place_recommendation_screen.dart';
import '../services/briefing_scheduler_service.dart';
import '../services/dashboard_api.dart';
import '../services/schedule_api.dart';
import '../services/voice_router_api.dart';
import '../theme/app_theme.dart';
import 'glass_card.dart';
import 'place_carousel_card.dart';

/// 선택 진행 중 강조색(살구) — 시연 시나리오 색상.
const Color _kApricot = Color(0xFFF2A66D);

/// `POST /api/v1/voice/route` 결과를 화면에 그리는 공용 위젯 모음.
///
/// `voice_chat_screen.dart` 와 `ai_chat_screen.dart` 는 서로 다른 화면이지만
/// 텍스트/음성 입력 모두 반드시 같은 `/voice/route` 엔드포인트로 보내고, 그
/// 결과도 이 파일의 함수들로 동일하게 렌더링한다 — 같은 발화가 화면마다
/// 다르게 처리되는 것을 막기 위함이다.
///
/// [handleVoiceScreenAction] 은 `screen_action.type == 'navigate'` 일 때
/// 실제로 화면 전환을 수행한다(예: 예약/장소 추천 → [PlaceRecommendationScreen]).
void handleVoiceScreenAction(BuildContext context, VoiceRouteResult route) {
  final action = route.screenAction;
  if (action.type != 'navigate') return;

  switch (action.target) {
    case 'reservation_recommendation':
      final places = (route.data['recommended_places'] as List?) ?? const [];
      final query = (route.data['query'] ?? '').toString();
      debugPrint(
        '[VoiceIntent] navigate -> PlaceRecommendationScreen '
        '(query="$query", results=${places.length})',
      );
      Navigator.of(context, rootNavigator: true).push(
        MaterialPageRoute(
          builder: (_) =>
              PlaceRecommendationScreen(query: query, places: places),
        ),
      );
      break;
    case 'calendar':
      debugPrint('[VoiceIntent] navigate -> CalendarScreen');
      Navigator.of(
        context,
        rootNavigator: true,
      ).push(MaterialPageRoute(builder: (_) => const CalendarScreen()));
      break;
    default:
      debugPrint(
        '[VoiceIntent] navigate target not wired yet: ${action.target}',
      );
  }
}

/// intent 에 따른 화면 갱신 부수효과. 화면 전환과 무관하게 항상 수행해야
/// 하는 것들(예: 새로 등록된 일정이 캘린더/대시보드에 즉시 보이도록 새로고침
/// 신호 보내기)을 한 곳에 모아, voice_chat_screen/ai_chat_screen 양쪽에서
/// 빠짐없이 동일하게 호출되도록 한다.
void handleVoiceSideEffects(VoiceRouteResult route) {
  if (route.intent == 'schedule_create' && route.data['item'] != null) {
    debugPrint('[VoiceIntent] schedule_create succeeded -> dashboard refresh');
    triggerDashboardRefresh();
  }
  // 음성으로 알림을 설정하면 서버가 만들어 준 reminder_plan 을 실제 OS 알림으로 예약.
  if (route.intent == 'reminder_setting') {
    debugPrint(
      '[VoiceIntent] reminder_setting -> schedule local notifications',
    );
    briefingSchedulerService.scheduleFromVoiceReminderPlan(route.data);
  }
}

/// intent 별 결과 카드. `reservation_recommendation`/`schedule_query` 처럼
/// 백엔드가 `navigate` 를 지시한 intent는 [handleVoiceScreenAction] 이 실제
/// 화면 전환을 담당하므로, 카드는 채팅 안에서 바로 의미 있는 나머지 intent
/// (감정 코칭/브리핑/일정 등록/알림 설정)에 대해서만 그린다.
Widget buildVoiceIntentCard(
  BuildContext context,
  VoiceRouteResult route, {
  void Function(RecommendedPlace place)? onSelectPlace,
}) {
  switch (route.intent) {
    case 'reservation_recommendation':
      final places = RecommendedPlace.listFrom(
        route.data['recommended_places'],
      );
      if (places.isEmpty) return const SizedBox.shrink();
      return PlaceCarouselCard(
        places: places,
        onSelect: (p) => onSelectPlace?.call(p),
      );
    case 'emotion_schedule_coaching':
      return _buildCoachingCard(context, route.data);
    case 'daily_briefing':
      return _buildBriefingCard(route.data);
    case 'schedule_create':
      return _buildScheduleCreateCard(route.data);
    case 'reminder_setting':
      return _buildReminderCard(route.data);
    default:
      return const SizedBox.shrink();
  }
}

Widget _buildCoachingCard(BuildContext context, Map<String, dynamic> data) {
  final solutions = (data['solutions'] as List?) ?? const [];
  final today = (data['today_schedule'] as List?) ?? const [];
  // 재조정 시간 후보(백엔드 reschedule_recommender 결과). 탭하면 실제로
  // 일정 시간이 변경된다(PATCH).
  final rescheduleCandidates = ((data['reschedule_candidates'] as List?) ?? const [])
      .whereType<Map>()
      .map((c) => Map<String, dynamic>.from(c))
      .where((c) =>
          (c['target_event_id'] ?? '').toString().isNotEmpty &&
          (c['suggested_start_time'] ?? '').toString().isNotEmpty)
      .toList();
  return GlassCard(
    padding: const EdgeInsets.all(14),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: const [
            Icon(Icons.favorite_outline, color: AppTheme.red, size: 18),
            SizedBox(width: 8),
            Text(
              '감정 기반 일정 코칭',
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w700,
                color: AppTheme.textPrimary,
              ),
            ),
          ],
        ),
        if (today.isNotEmpty) ...[
          const SizedBox(height: 10),
          const Text(
            '오늘 일정',
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: AppTheme.textSecondary,
            ),
          ),
          const SizedBox(height: 4),
          ...today.map((s) {
            final sched = Map<String, dynamic>.from(s as Map);
            return Text(
              '${sched['start_time'] ?? ''} ${sched['title'] ?? ''}'.trim(),
              style: const TextStyle(fontSize: 13, color: AppTheme.textPrimary),
            );
          }),
        ],
        if (solutions.isNotEmpty) ...[
          const SizedBox(height: 10),
          const Text(
            '추천 대처',
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: AppTheme.textSecondary,
            ),
          ),
          const SizedBox(height: 4),
          ...solutions.map((s) {
            final sol = Map<String, dynamic>.from(s as Map);
            return Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    (sol['title'] ?? '').toString(),
                    style: const TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                      color: AppTheme.textPrimary,
                    ),
                  ),
                  Text(
                    (sol['reason'] ?? '').toString(),
                    style: const TextStyle(
                      fontSize: 12,
                      color: AppTheme.textTertiary,
                    ),
                  ),
                ],
              ),
            );
          }),
        ],
        if (rescheduleCandidates.isNotEmpty) ...[
          const SizedBox(height: 12),
          Text(
            '"${rescheduleCandidates.first['target_title'] ?? '일정'}" 옮길 시간 후보',
            style: const TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: AppTheme.textSecondary,
            ),
          ),
          const SizedBox(height: 6),
          RescheduleCandidateChips(candidates: rescheduleCandidates),
        ],
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            _actionChip('오늘 일정 보기', () {
              Navigator.of(
                context,
                rootNavigator: true,
              ).push(MaterialPageRoute(builder: (_) => const CalendarScreen()));
            }),
          ],
        ),
      ],
    ),
  );
}

/// 재조정 시간 후보 칩 목록. 탭 → (살구색 진행) → PATCH 로 실제 일정 이동 →
/// (그린 체크) 순으로 바뀐다. 하나를 적용하면 나머지는 비활성화된다.
class RescheduleCandidateChips extends StatefulWidget {
  final List<Map<String, dynamic>> candidates;

  const RescheduleCandidateChips({super.key, required this.candidates});

  @override
  State<RescheduleCandidateChips> createState() =>
      _RescheduleCandidateChipsState();
}

class _RescheduleCandidateChipsState extends State<RescheduleCandidateChips> {
  int? _busyIndex; // PATCH 진행 중인 칩
  int? _appliedIndex; // 적용 완료된 칩

  String _label(Map<String, dynamic> c) {
    final day = (c['day_label'] ?? '').toString();
    final start = (c['suggested_start_time'] ?? '').toString();
    return day.isEmpty ? start : '$day $start';
  }

  Future<void> _apply(int i) async {
    if (_busyIndex != null || _appliedIndex != null) return;
    final c = widget.candidates[i];
    final id = (c['target_event_id'] ?? '').toString();
    setState(() => _busyIndex = i);
    try {
      await scheduleApi.update(id, {
        'date': c['suggested_date'],
        'start_time': c['suggested_start_time'],
        'end_time': c['suggested_end_time'],
      });
      triggerDashboardRefresh();
      if (!mounted) return;
      setState(() {
        _busyIndex = null;
        _appliedIndex = i;
      });
      ScaffoldMessenger.of(context)
        ..hideCurrentSnackBar()
        ..showSnackBar(
          SnackBar(
            content: Text(
              '"${c['target_title'] ?? '일정'}"을(를) ${_label(c)}로 옮겼어요 ✓',
            ),
          ),
        );
    } catch (e) {
      if (!mounted) return;
      setState(() => _busyIndex = null);
      ScaffoldMessenger.of(context)
        ..hideCurrentSnackBar()
        ..showSnackBar(
          const SnackBar(content: Text('일정을 옮기지 못했어요. 다시 시도해 주세요.')),
        );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        for (var i = 0; i < widget.candidates.length; i++) _chip(i),
      ],
    );
  }

  Widget _chip(int i) {
    final applied = _appliedIndex == i;
    final busy = _busyIndex == i;
    final disabled = _appliedIndex != null && !applied;

    final Color bg = applied
        ? AppTheme.green
        : busy
        ? _kApricot.withValues(alpha: 0.25)
        : AppTheme.blue.withValues(alpha: disabled ? 0.05 : 0.12);
    final Color fg = applied
        ? Colors.white
        : disabled
        ? AppTheme.textSecondary
        : AppTheme.blue;

    return GestureDetector(
      onTap: (applied || busy || disabled) ? null : () => _apply(i),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        curve: Curves.easeOut,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: bg,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: busy ? _kApricot : Colors.transparent,
            width: 1.5,
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (applied) ...[
              const Icon(Icons.check_rounded, size: 14, color: Colors.white),
              const SizedBox(width: 4),
            ],
            if (busy) ...[
              const SizedBox(
                width: 12,
                height: 12,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
              const SizedBox(width: 6),
            ],
            Text(
              _label(widget.candidates[i]),
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: fg,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

Widget _actionChip(String label, VoidCallback? onTap) {
  return GestureDetector(
    onTap: onTap,
    child: Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: AppTheme.blue.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Text(
        label,
        style: const TextStyle(
          fontSize: 12,
          fontWeight: FontWeight.w600,
          color: AppTheme.blue,
        ),
      ),
    ),
  );
}

Widget _buildBriefingCard(Map<String, dynamic> data) {
  final summary = (data['summary'] ?? '').toString();
  final keyPoints = (data['key_points'] as List?) ?? const [];
  return GlassCard(
    padding: const EdgeInsets.all(14),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: const [
            Icon(Icons.wb_sunny_outlined, color: AppTheme.orange, size: 18),
            SizedBox(width: 8),
            Text(
              '오늘의 브리핑',
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w700,
                color: AppTheme.textPrimary,
              ),
            ),
          ],
        ),
        if (summary.isNotEmpty) ...[
          const SizedBox(height: 10),
          Text(
            summary,
            style: const TextStyle(
              fontSize: 13,
              height: 1.4,
              color: AppTheme.textPrimary,
            ),
          ),
        ],
        if (keyPoints.isNotEmpty) ...[
          const SizedBox(height: 8),
          ...keyPoints.map(
            (k) => Padding(
              padding: const EdgeInsets.only(bottom: 4),
              child: Text(
                '• $k',
                style: const TextStyle(
                  fontSize: 12,
                  color: AppTheme.textTertiary,
                ),
              ),
            ),
          ),
        ],
      ],
    ),
  );
}

Widget _buildScheduleCreateCard(Map<String, dynamic> data) {
  final item = data['item'] as Map?;
  if (item == null) return const SizedBox.shrink();
  return GlassCard(
    padding: const EdgeInsets.all(14),
    child: Row(
      children: [
        const Icon(Icons.check_circle_outline, color: AppTheme.green, size: 20),
        const SizedBox(width: 10),
        Expanded(
          child: Text(
            '${item['title'] ?? ''} · ${item['date'] ?? ''} ${item['start_time'] ?? ''}'
                .trim(),
            style: const TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w600,
              color: AppTheme.textPrimary,
            ),
          ),
        ),
      ],
    ),
  );
}

Widget _buildReminderCard(Map<String, dynamic> data) {
  final enabled = data['reminder_enabled'] == true;
  final minutes = data['reminder_minutes_before'];
  return GlassCard(
    padding: const EdgeInsets.all(14),
    child: Row(
      children: [
        Icon(
          enabled
              ? Icons.notifications_active_outlined
              : Icons.notifications_off_outlined,
          color: enabled ? AppTheme.blue : AppTheme.textSecondary,
          size: 20,
        ),
        const SizedBox(width: 10),
        Text(
          enabled ? '$minutes분 전 알림 설정됨' : '알림 없음',
          style: const TextStyle(
            fontSize: 13,
            fontWeight: FontWeight.w600,
            color: AppTheme.textPrimary,
          ),
        ),
      ],
    ),
  );
}
