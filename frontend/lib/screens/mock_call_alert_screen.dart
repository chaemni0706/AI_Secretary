import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../models/mock_call_alert.dart';
import '../services/mock_voice_service.dart';
import '../services/voice_tts_service.dart';

/// 가짜 전화 알림 화면 (Mock).
///
/// 실제 전화/통화/발신 기능이 아니다. 일정 전 알림이 왔을 때 AI 비서 "챔니"가
/// 전화하는 것처럼 보이는 발표/시연용 화면이다.
///  - "알림 듣기": 실제 TTS 대신 SnackBar 로 voice_alert_text 안내.
///  - "확인했어요": Navigator.pop.
///  - "나중에 다시 알림": SnackBar 안내.
///
/// 추후 로컬 알림(firebase_messaging 등) 클릭 시 이 화면으로 이동하도록
/// 라우팅만 준비한다. (예: Navigator.push(MockCallAlertScreen()))
class MockCallAlertScreen extends StatefulWidget {
  const MockCallAlertScreen({super.key});

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
    final res = await _service.getMockCallAlert();
    if (!mounted) return;
    setState(() {
      _data = MockCallAlert.fromJson(res['data'] as Map<String, dynamic>);
      _loading = false;
    });
  }

  /// "알림 듣기" — flutter_tts 로 voice_alert_text 를 실제로 재생한다.
  Future<void> _playAlertVoice() async {
    final text = _data?.alertPlan.voiceAlertText ??
        '챔니가 알려드려요. 곧 일정이 시작돼요.';
    debugPrint('Mock call alert TTS text: $text');
    await _ttsService.speak(text);
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
          child: _loading || _data == null
              ? const Center(
                  child: CircularProgressIndicator(color: Colors.white))
              : _buildContent(_data!),
        ),
      ),
    );
  }

  Widget _buildContent(MockCallAlert d) {
    final plan = d.alertPlan;
    final reminder = plan.primary;
    // 일정 제목은 알림 메시지에서 유추(“팀 회의”)하기보다 next_event 성격상
    // reminder.title 은 "챔니 전화 알림" 이므로, 데모용 일정 제목은 고정 사용.
    const scheduleTitle = '팀 회의';

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 12),
      child: Column(
        children: [
          const SizedBox(height: 8),
          // 상단: 타이틀 + 부제
          Column(
            children: [
              Text(
                reminder?.title ?? '챔니 전화 알림',
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
              boxShadow: TossShadow.glow(
                AppTheme.purple,
                alpha: 0.5,
                blur: 40,
                offset: Offset.zero,
                spreadRadius: 6,
              ),
            ),
            child: const Icon(Icons.assistant_rounded,
                color: Colors.white, size: 64),
          ),
          const SizedBox(height: 24),
          Text(
            scheduleTitle,
            style: const TextStyle(
              fontSize: 26,
              fontWeight: FontWeight.w700,
              color: Colors.white,
            ),
          ),
          const SizedBox(height: 12),
          Text(
            reminder?.message ?? '팀 회의가 곧 시작돼요.',
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 16,
              height: 1.4,
              color: Colors.white.withOpacity(0.9),
            ),
          ),
          const SizedBox(height: 8),
          Text(
            _checklistLine(plan.checklist),
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 14,
              height: 1.4,
              color: Colors.white.withOpacity(0.7),
            ),
          ),
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
