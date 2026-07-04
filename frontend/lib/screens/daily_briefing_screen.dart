import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../widgets/glass_card.dart';
import '../models/daily_briefing_mock.dart';
import '../data/mock_voice_data.dart';
import '../services/mock_voice_service.dart';
import '../services/voice_tts_service.dart';

/// 하루 브리핑 화면 (Mock).
///
/// `MockVoiceService.getDailyBriefing()` 로 Mock 응답을 받아
/// 요약 / 메인 브리핑 / 섹션 / 다음 일정 / 추천 행동 카드를 표시한다.
/// "브리핑 듣기" 는 `_playBriefingTts()` 에서 flutter_tts 로 실제 음성을 재생한다.
class DailyBriefingScreen extends StatefulWidget {
  const DailyBriefingScreen({super.key});

  @override
  State<DailyBriefingScreen> createState() => _DailyBriefingScreenState();
}

class _DailyBriefingScreenState extends State<DailyBriefingScreen> {
  final _service = mockVoiceService;
  final VoiceTtsService _ttsService = VoiceTtsService();

  bool _loading = true;
  DailyBriefingMock? _data;

  @override
  void initState() {
    super.initState();
    _ttsService.init();
    _load();
  }

  @override
  void dispose() {
    _ttsService.stop();
    super.dispose();
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

  /// "브리핑 듣기" 버튼 로직. flutter_tts 로 실제 음성을 재생한다.
  ///
  /// 백엔드 응답 필드가 엔드포인트마다 다르므로(tts_text / text / summary /
  /// briefing_text) 아래 우선순위로 비어 있지 않은 첫 텍스트를 사용한다.
  /// 어느 것도 없으면 무음 대신 안내 문구를 읽는다.
  ///   tts_text → text → summary → briefing_text → 안내 문구
  Future<void> _playBriefingTts() async {
    final raw = mockDailyBriefing['data'] as Map<String, dynamic>;

    final ttsText = _pickTtsText([
      raw['tts_text'], // 파싱 전 원본 tts_text
      raw['text'], // /api/v1/voice/tts 계열 응답 필드
      raw['summary'], // /api/v1/briefings/daily 의 요약 문장(문자열일 때만)
      raw['briefing_text'], // 화면 본문 텍스트
      _data?.ttsText, // 파싱된 값(실제 API 연결 시에도 동작)
      _data?.briefingText,
    ]);

    debugPrint('Daily briefing TTS text: "$ttsText"');
    await _ttsService.speak(ttsText);
  }

  /// 후보들 중 비어 있지 않은 첫 문자열을 고른다. 없으면 안내 문구를 반환한다.
  /// summary 등 일부 필드는 Map(카운트) 형태일 수 있어 String 일 때만 사용한다.
  String _pickTtsText(List<dynamic> candidates) {
    for (final c in candidates) {
      if (c is String && c.trim().isNotEmpty) return c.trim();
    }
    return '오늘 브리핑을 불러오지 못했습니다.';
  }

  // ===== 디버깅용 임시 메서드 (원인 분리 후 삭제 가능) =====
  // 이 버튼에서도 소리가 안 나면 태블릿 TTS 엔진/볼륨 문제,
  // 이 버튼은 되는데 "브리핑 듣기"만 안 되면 데이터 연결 문제.
  Future<void> _playTtsTest() async {
    debugPrint('Daily briefing TTS TEST button pressed');
    await _ttsService.speak('안녕하세요. 챔니 음성 테스트입니다.');
  }
  // ===== 디버깅용 임시 메서드 끝 =====

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
          // ===== 디버깅용 임시 버튼 (원인 분리 후 삭제 가능) =====
          const SizedBox(height: 8),
          SizedBox(
            width: double.infinity,
            child: OutlinedButton.icon(
              onPressed: _playTtsTest,
              style: OutlinedButton.styleFrom(
                foregroundColor: AppTheme.purple,
                side: const BorderSide(color: AppTheme.purple),
                padding: const EdgeInsets.symmetric(vertical: 12),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(14),
                ),
              ),
              icon: const Icon(Icons.bug_report_outlined, size: 18),
              label: const Text('태블릿 TTS 테스트'),
            ),
          ),
          // ===== 디버깅용 임시 버튼 끝 =====
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
