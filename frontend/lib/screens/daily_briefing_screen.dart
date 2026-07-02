import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../widgets/glass_card.dart';
import '../models/daily_briefing_mock.dart';
import '../services/mock_voice_service.dart';

/// 하루 브리핑 화면 (Mock).
///
/// `MockVoiceService.getDailyBriefing()` 로 Mock 응답을 받아
/// 요약 / 메인 브리핑 / 섹션 / 다음 일정 / 추천 행동 카드를 표시한다.
/// "브리핑 듣기" 는 실제 TTS 대신 `_playBriefingTts()` 에서 SnackBar 로 안내한다.
class DailyBriefingScreen extends StatefulWidget {
  const DailyBriefingScreen({super.key});

  @override
  State<DailyBriefingScreen> createState() => _DailyBriefingScreenState();
}

class _DailyBriefingScreenState extends State<DailyBriefingScreen> {
  final _service = mockVoiceService;

  bool _loading = true;
  DailyBriefingMock? _data;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    // Mock: 공통 응답 envelope 중 data 만 파싱 (실제 API 연결 시에도 동일).
    final res = await _service.getDailyBriefing();
    if (!mounted) return;
    setState(() {
      _data = DailyBriefingMock.fromJson(res['data'] as Map<String, dynamic>);
      _loading = false;
    });
  }

  /// "브리핑 듣기" 버튼 로직. 추후 `/api/v1/voice/tts` 연결 시 이 메서드만 수정.
  Future<void> _playBriefingTts() async {
    final text = _data?.ttsText ?? '';
    // 실제 TTS 대신 Mock 서비스 호출 후 안내 SnackBar 표시.
    await _service.requestTts(text, source: 'briefing');
    if (!mounted) return;
    final preview = text.length > 30 ? '${text.substring(0, 30)}...' : text;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('TTS 재생 예정: $preview'),
        behavior: SnackBarBehavior.floating,
        backgroundColor: AppTheme.dark,
      ),
    );
  }

  String _dateLabel(String iso) {
    final dt = DateTime.tryParse(iso);
    if (dt == null) return iso;
    return '${dt.year}년 ${dt.month}월 ${dt.day}일';
  }

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
        body: _loading || _data == null
            ? const Center(child: CircularProgressIndicator())
            : _buildContent(_data!),
      ),
    );
  }

  Widget _buildContent(DailyBriefingMock d) {
    return SafeArea(
      top: false,
      child: ListView(
        physics: const BouncingScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
        children: [
          Text(
            _dateLabel(d.date),
            style: const TextStyle(
              fontSize: 14,
              color: AppTheme.textSecondary,
              fontWeight: FontWeight.w500,
            ),
          ),
          const SizedBox(height: 12),
          _buildSummaryCard(d.summary),
          const SizedBox(height: 14),
          _buildMainBriefingCard(d),
          const SizedBox(height: 14),
          ...d.sections.map(_buildSectionCard),
          if (d.nextEvent != null) ...[
            const SizedBox(height: 4),
            _buildNextEventCard(d.nextEvent!),
          ],
          const SizedBox(height: 14),
          _buildRecommendedActions(d.recommendedActions),
        ],
      ),
    );
  }

  Widget _buildSummaryCard(BriefingSummary s) {
    Widget item(IconData icon, Color color, String value, String label) {
      return Expanded(
        child: Column(
          children: [
            Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                color: color.withOpacity(0.14),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(icon, color: color, size: 22),
            ),
            const SizedBox(height: 8),
            Text(
              value,
              style: const TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.w700,
                color: AppTheme.textPrimary,
              ),
            ),
            Text(
              label,
              style: const TextStyle(
                fontSize: 12,
                color: AppTheme.textSecondary,
              ),
            ),
          ],
        ),
      );
    }

    return GlassCard(
      child: Row(
        children: [
          item(Icons.event_note_outlined, AppTheme.blue,
              '${s.scheduleCount}개', '일정'),
          item(Icons.checklist_outlined, AppTheme.green,
              '${s.todoCount}개', '할 일'),
          item(Icons.priority_high_rounded, AppTheme.red,
              '${s.highPriorityCount}개', '중요'),
        ],
      ),
    );
  }

  Widget _buildMainBriefingCard(DailyBriefingMock d) {
    return GlassCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 36,
                height: 36,
                decoration: BoxDecoration(
                  color: AppTheme.purple.withOpacity(0.14),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Icon(Icons.auto_awesome,
                    color: AppTheme.purple, size: 20),
              ),
              const SizedBox(width: 10),
              const Text(
                '오늘의 요약',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w700,
                  color: AppTheme.textPrimary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            d.briefingText,
            style: const TextStyle(
              fontSize: 15,
              height: 1.5,
              color: AppTheme.textPrimary,
            ),
          ),
          const SizedBox(height: 16),
          SizedBox(
            width: double.infinity,
            child: FilledButton.icon(
              onPressed: _playBriefingTts,
              style: FilledButton.styleFrom(
                backgroundColor: AppTheme.blue,
                padding: const EdgeInsets.symmetric(vertical: 14),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(14),
                ),
              ),
              icon: const Icon(Icons.volume_up_rounded, size: 20),
              label: const Text(
                '브리핑 듣기',
                style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSectionCard(BriefingSection section) {
    final (icon, color) = _sectionStyle(section.type);
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: GlassCard(
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 36,
              height: 36,
              decoration: BoxDecoration(
                color: color.withOpacity(0.14),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Icon(icon, color: color, size: 20),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    section.title,
                    style: const TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.w700,
                      color: AppTheme.textPrimary,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    section.content,
                    style: const TextStyle(
                      fontSize: 14,
                      height: 1.4,
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

  (IconData, Color) _sectionStyle(String type) {
    switch (type) {
      case 'today_schedule':
        return (Icons.event_available_outlined, AppTheme.blue);
      case 'important_todo':
        return (Icons.flag_outlined, AppTheme.red);
      case 'recommendation':
        return (Icons.lightbulb_outline, AppTheme.orange);
      default:
        return (Icons.info_outline, AppTheme.teal);
    }
  }

  Widget _buildNextEventCard(NextEvent e) {
    return GlassCard(
      color: AppTheme.blue.withOpacity(0.10),
      child: Row(
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: AppTheme.blue.withOpacity(0.16),
              borderRadius: BorderRadius.circular(12),
            ),
            child: const Icon(Icons.access_time_filled_rounded,
                color: AppTheme.blue, size: 22),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '다음 일정: ${e.title}',
                  style: const TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w700,
                    color: AppTheme.textPrimary,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  '${e.startTime} 시작',
                  style: const TextStyle(
                    fontSize: 13,
                    color: AppTheme.textTertiary,
                  ),
                ),
              ],
            ),
          ),
          PillBadge(
            label: '${e.minutesUntilStart}분 남음',
            color: AppTheme.blue,
          ),
        ],
      ),
    );
  }

  Widget _buildRecommendedActions(List<String> actions) {
    return GlassCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '추천 행동',
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w700,
              color: AppTheme.textPrimary,
            ),
          ),
          const SizedBox(height: 12),
          ...actions.map(
            (a) => Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.check_circle_outline,
                      color: AppTheme.green, size: 20),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      a,
                      style: const TextStyle(
                        fontSize: 14,
                        height: 1.4,
                        color: AppTheme.textPrimary,
                      ),
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
}
