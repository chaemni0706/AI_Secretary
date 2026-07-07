import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import '../theme/app_constants.dart';
import '../theme/app_theme.dart';
import '../models/mock_call_alert.dart';
import '../services/mock_voice_service.dart';
import '../services/preference_store.dart';
import '../services/voice_api.dart';
import '../services/voice_tts_service.dart';

/// 가짜 전화 알림 화면.
///
/// 실제 전화/통화/발신 기능이 아니다. 일정 전 알림 또는 자동 브리핑 시각이
/// 됐을 때 AI 비서 "챔니"가 전화하는 것처럼 보이는 화면이다.
///  - "알림 듣기": flutter_tts 로 voice_alert_text(또는 주입된 문구) 재생.
///  - "확인했어요": Navigator.pop.
///  - "나중에 다시 알림": SnackBar 안내.
///
/// 기본(파라미터 없이 push)으로는 기존처럼 Mock 출발 알림을 불러온다.
/// [briefingScheduler]가 예약 알림을 탭했을 때는 [overrideTitle]/
/// [overrideMessage]/[overrideChecklist]/[overrideTtsText]를 채워 넘기고,
/// 이 경우 화면이 뜨자마자 TTS를 자동 재생한다(전화를 받는 느낌).
class MockCallAlertScreen extends StatefulWidget {
  final String? overrideTitle;
  final String? overrideMessage;
  final List<String>? overrideChecklist;
  final String? overrideTtsText;
  final bool autoPlay;

  const MockCallAlertScreen({
    super.key,
    this.overrideTitle,
    this.overrideMessage,
    this.overrideChecklist,
    this.overrideTtsText,
    this.autoPlay = false,
  });

  bool get _isOverridden => overrideTitle != null || overrideMessage != null;

  @override
  State<MockCallAlertScreen> createState() => _MockCallAlertScreenState();
}

class _MockCallAlertScreenState extends State<MockCallAlertScreen> {
  final _service = mockVoiceService;
  final VoiceTtsService _ttsService = VoiceTtsService();

  bool _loading = true;
  MockCallAlert? _data;

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
    if (widget._isOverridden) {
      // 자동 브리핑 등 외부에서 주입된 콜: 목업 API를 부르지 않는다.
      setState(() => _loading = false);
      if (widget.autoPlay) await _playAlertVoice();
      return;
    }
    final res = await _service.getMockCallAlert();
    if (!mounted) return;
    setState(() {
      _data = MockCallAlert.fromJson(res['data'] as Map<String, dynamic>);
      _loading = false;
    });
  }

  /// "알림 듣기" — flutter_tts 로 voice_alert_text(또는 주입된 문구)를 재생한다.
  Future<void> _playAlertVoice() async {
    final base = widget.overrideTtsText ??
        _data?.alertPlan.voiceAlertText ??
        '${AppStrings.assistantNotifiesPrefix()} 곧 일정이 시작돼요.';
    // reminder_strength 에 따라 알림 문구 강도를 로컬에서 조절(gentle/strong).
    final text = preferenceStore.applyReminderStrength(base);
    debugPrint('Mock call alert TTS text: $text');
    await voiceApi.speak(_ttsService, text, source: 'call_alert');
  }

  /// "확인했어요" — TTS 정지 후 화면을 닫는다.
  Future<void> _confirm() async {
    await _ttsService.stop();
    if (!mounted) return;
    Navigator.pop(context);
  }

  /// "나중에 다시 알림" — TTS 정지 후 기존 SnackBar 유지.
  Future<void> _snooze() async {
    await _ttsService.stop();
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('10분 뒤 다시 알림으로 설정했어요.'),
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    // 전화 수신 화면 느낌의 어두운 그라데이션 전체 화면.
    final ready = widget._isOverridden ? !_loading : (!_loading && _data != null);
    return Scaffold(
      backgroundColor: AppTheme.dark,
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [Color(0xFF2A2350), Color(0xFF1A1A1C)],
          ),
        ),
        child: SafeArea(
          child: ready
              ? _buildContent()
              : const Center(
                  child: CircularProgressIndicator(color: Colors.white)),
        ),
      ),
    );
  }

  Widget _buildContent() {
    final plan = _data?.alertPlan;
    final reminder = plan?.primary;

    final headerTitle =
        widget.overrideTitle ?? reminder?.title ?? AppStrings.callAlertTitle();
    // 일정 전 알림(Mock)에서는 next_event 성격상 reminder.title 이
    // "챔니 전화 알림" 고정값이라 데모용 일정 제목을 별도로 고정 사용했다.
    // 자동 브리핑 등 override 호출은 overrideMessage 를 본문으로 그대로 쓴다.
    final bodyTitle = widget.overrideTitle ?? '팀 회의';
    final message = widget.overrideMessage ?? reminder?.message ?? '팀 회의가 곧 시작돼요.';
    final checklist = widget.overrideChecklist ?? plan?.checklist ?? const [];

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 12),
      child: Column(
        children: [
          const SizedBox(height: 8),
          // 상단: 타이틀 + 부제
          Column(
            children: [
              Text(
                headerTitle,
                style: const TextStyle(
                  fontSize: 22,
                  fontWeight: FontWeight.w700,
                  color: Colors.white,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                'AI 일정 비서',
                style: TextStyle(
                  fontSize: 14,
                  color: Colors.white.withOpacity(0.65),
                ),
              ),
            ],
          ),
          const Spacer(),
          // 중앙: 원형 캐릭터 아이콘 + 일정 제목 + 안내 문구
          Container(
            width: 128,
            height: 128,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: const LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [AppTheme.purple, AppTheme.blue],
              ),
              boxShadow: [
                BoxShadow(
                  color: AppTheme.purple.withOpacity(0.5),
                  blurRadius: 40,
                  spreadRadius: 6,
                ),
              ],
            ),
            child: const Icon(Icons.assistant_rounded,
                color: Colors.white, size: 64),
          ),
          const SizedBox(height: 24),
          Text(
            bodyTitle,
            style: const TextStyle(
              fontSize: 26,
              fontWeight: FontWeight.w700,
              color: Colors.white,
            ),
          ),
          const SizedBox(height: 12),
          Text(
            message,
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 16,
              height: 1.4,
              color: Colors.white.withOpacity(0.9),
            ),
          ),
          if (checklist.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              _checklistLine(checklist),
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 14,
                height: 1.4,
                color: Colors.white.withOpacity(0.7),
              ),
            ),
          ],
          const Spacer(),
          // 하단 버튼들
          _buildActionButton(
            icon: Icons.volume_up_rounded,
            label: '알림 듣기',
            color: AppTheme.blue,
            onTap: _playAlertVoice,
          ),
          const SizedBox(height: 12),
          _buildActionButton(
            icon: Icons.check_rounded,
            label: '확인했어요',
            color: AppTheme.green,
            onTap: _confirm,
          ),
          const SizedBox(height: 12),
          _buildActionButton(
            icon: Icons.snooze_rounded,
            label: '나중에 다시 알림',
            color: Colors.white.withOpacity(0.18),
            textColor: Colors.white,
            onTap: _snooze,
          ),
          const SizedBox(height: 12),
        ],
      ),
    );
  }

  String _checklistLine(List<String> checklist) {
    if (checklist.isEmpty) return '';
    return '${checklist.join(', ')}를 챙겨주세요.';
  }

  Widget _buildActionButton({
    required IconData icon,
    required String label,
    required Color color,
    Color textColor = Colors.white,
    required VoidCallback onTap,
  }) {
    return SizedBox(
      width: double.infinity,
      child: FilledButton.icon(
        onPressed: onTap,
        style: FilledButton.styleFrom(
          backgroundColor: color,
          padding: const EdgeInsets.symmetric(vertical: 16),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
        ),
        icon: Icon(icon, size: 20, color: textColor),
        label: Text(
          label,
          style: TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w600,
            color: textColor,
          ),
        ),
      ),
    );
  }
}
