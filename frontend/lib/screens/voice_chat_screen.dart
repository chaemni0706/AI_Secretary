import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../widgets/glass_card.dart';
import '../models/voice_chat_message.dart';
import '../data/mock_voice_data.dart';
import '../services/mock_voice_service.dart';

/// AI 음성 챗봇 화면 (Mock).
///
/// 실제 STT/TTS 는 연결하지 않는다.
///  - 마이크 버튼: 미리 정해둔 사용자 발화를 입력한 것처럼 처리 → AI Mock 응답.
///  - 전송 버튼: 입력창 문장을 사용자 메시지로 추가 → 동일한 AI Mock 응답.
///  - "음성으로 듣기": 실제 TTS 대신 SnackBar 안내.
///
/// 추후 STT/TTS 연결을 위한 진입점:
///   `_handleMockSpeechInput()`, `_sendMessage(text)`, `_playTts(text)`
class VoiceChatScreen extends StatefulWidget {
  const VoiceChatScreen({super.key});

  @override
  State<VoiceChatScreen> createState() => _VoiceChatScreenState();
}

class _VoiceChatScreenState extends State<VoiceChatScreen> {
  final _service = mockVoiceService;
  final _inputController = TextEditingController();
  final _scrollController = ScrollController();

  final List<VoiceChatMessage> _messages = [];
  bool _sending = false;

  @override
  void dispose() {
    _inputController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  /// 마이크 버튼: 미리 정해둔 사용자 발화가 인식된 것처럼 처리.
  /// (추후 speech_to_text 연동 시 인식 결과를 [_sendMessage] 로 전달)
  void _handleMockSpeechInput() {
    _sendMessage(mockUserSpeechText);
  }

  /// 사용자 메시지를 추가하고, 로딩 후 AI Mock 응답을 붙인다.
  /// [text] 가 비어있으면 무시. 추후 실제 API 연결 시 이 메서드만 수정.
  Future<void> _sendMessage(String text) async {
    final trimmed = text.trim();
    if (trimmed.isEmpty || _sending) return;

    setState(() {
      _messages.add(VoiceChatMessage(role: ChatRole.user, text: trimmed));
      _sending = true;
    });
    _inputController.clear();
    _scrollToBottom();

    // Mock: 감정 코칭 응답을 받아 envelope 중 data 만 파싱.
    final res = await _service.getEmotionCoaching(trimmed);
    if (!mounted) return;
    final analysis =
        EmotionAnalysis.fromJson(res['data'] as Map<String, dynamic>);

    setState(() {
      _messages.add(VoiceChatMessage(
        role: ChatRole.assistant,
        text: analysis.coachingReply,
        analysis: analysis,
        ttsText: analysis.ttsText,
      ));
      _sending = false;
    });
    _scrollToBottom();
  }

  /// "음성으로 듣기" — 실제 TTS 대신 SnackBar 안내. 추후 flutter_tts 연동 지점.
  Future<void> _playTts(String text) async {
    await _service.requestTts(text, source: 'chatbot_reply');
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

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
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
          title: const Text('AI 음성 챗봇'),
        ),
        body: SafeArea(
          top: false,
          child: Column(
            children: [
              _buildGuide(),
              Expanded(
                child: _messages.isEmpty
                    ? _buildEmptyState()
                    : ListView.builder(
                        controller: _scrollController,
                        physics: const BouncingScrollPhysics(),
                        padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
                        itemCount: _messages.length + (_sending ? 1 : 0),
                        itemBuilder: (context, i) {
                          if (i >= _messages.length) {
                            return _buildTypingBubble();
                          }
                          return _buildMessage(_messages[i]);
                        },
                      ),
              ),
              _buildInputBar(),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildGuide() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 8),
      child: GlassCard(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        child: Row(
          children: const [
            Icon(Icons.tips_and_updates_outlined,
                color: AppTheme.purple, size: 20),
            SizedBox(width: 10),
            Expanded(
              child: Text(
                '마이크를 누르면 챔니가 일정과 감정을 함께 고려해 답변해요.',
                style: TextStyle(fontSize: 13, color: AppTheme.textTertiary),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 72,
            height: 72,
            decoration: BoxDecoration(
              color: AppTheme.purple.withOpacity(0.12),
              shape: BoxShape.circle,
            ),
            child: const Icon(Icons.auto_awesome,
                color: AppTheme.purple, size: 34),
          ),
          const SizedBox(height: 16),
          const Text(
            '무엇이든 편하게 이야기해 주세요',
            style: TextStyle(
              fontSize: 15,
              fontWeight: FontWeight.w600,
              color: AppTheme.textPrimary,
            ),
          ),
          const SizedBox(height: 4),
          const Text(
            '아래 마이크 버튼을 눌러 시작할 수 있어요',
            style: TextStyle(fontSize: 13, color: AppTheme.textSecondary),
          ),
        ],
      ),
    );
  }

  Widget _buildMessage(VoiceChatMessage m) {
    if (m.isUser) {
      return Align(
        alignment: Alignment.centerRight,
        child: Container(
          margin: const EdgeInsets.only(top: 6, bottom: 6, left: 48),
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          decoration: BoxDecoration(
            color: AppTheme.blue,
            borderRadius: const BorderRadius.only(
              topLeft: Radius.circular(16),
              topRight: Radius.circular(16),
              bottomLeft: Radius.circular(16),
              bottomRight: Radius.circular(4),
            ),
          ),
          child: Text(
            m.text,
            style: const TextStyle(
                fontSize: 14, color: Colors.white, height: 1.4),
          ),
        ),
      );
    }

    // AI 메시지: 말풍선 + 음성으로 듣기 + 감정/일정 카드.
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(top: 6, bottom: 6, right: 32),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              decoration: BoxDecoration(
                color: Colors.white.withOpacity(0.85),
                borderRadius: const BorderRadius.only(
                  topLeft: Radius.circular(4),
                  topRight: Radius.circular(16),
                  bottomLeft: Radius.circular(16),
                  bottomRight: Radius.circular(16),
                ),
                border: Border.all(color: AppTheme.separator),
              ),
              child: Text(
                m.text,
                style: const TextStyle(
                    fontSize: 14, color: AppTheme.textPrimary, height: 1.5),
              ),
            ),
            const SizedBox(height: 6),
            GestureDetector(
              onTap: () => _playTts(m.ttsText ?? m.text),
              child: Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                decoration: BoxDecoration(
                  color: AppTheme.purple.withOpacity(0.12),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: const [
                    Icon(Icons.volume_up_rounded,
                        size: 16, color: AppTheme.purple),
                    SizedBox(width: 6),
                    Text(
                      '음성으로 듣기',
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                        color: AppTheme.purple,
                      ),
                    ),
                  ],
                ),
              ),
            ),
            if (m.analysis != null) ...[
              const SizedBox(height: 10),
              _buildEmotionCard(m.analysis!),
              const SizedBox(height: 10),
              _buildSuggestionsCard(m.analysis!),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildTypingBubble() {
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(top: 6, bottom: 6),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          color: Colors.white.withOpacity(0.85),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: AppTheme.separator),
        ),
        child: const SizedBox(
          width: 40,
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _Dot(),
              _Dot(),
              _Dot(),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildEmotionCard(EmotionAnalysis a) {
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
                '감정 분석 결과',
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w700,
                  color: AppTheme.textPrimary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              PillBadge(label: '감정: ${a.emotion.label}', color: AppTheme.red),
              PillBadge(
                  label: '강도: ${a.emotion.intensity}', color: AppTheme.orange),
              PillBadge(
                  label: '부담도: ${a.burden.level}', color: AppTheme.purple),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            a.burden.reason,
            style: const TextStyle(
                fontSize: 13, color: AppTheme.textTertiary, height: 1.4),
          ),
        ],
      ),
    );
  }

  Widget _buildSuggestionsCard(EmotionAnalysis a) {
    return GlassCard(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: const [
              Icon(Icons.event_note_outlined, color: AppTheme.blue, size: 18),
              SizedBox(width: 8),
              Text(
                '일정 조정 추천',
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w700,
                  color: AppTheme.textPrimary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          ...a.scheduleSuggestions.map((s) {
            final (icon, color, label) = _suggestionStyle(s.type);
            return Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    width: 32,
                    height: 32,
                    decoration: BoxDecoration(
                      color: color.withOpacity(0.14),
                      borderRadius: BorderRadius.circular(9),
                    ),
                    child: Icon(icon, color: color, size: 17),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '${s.startHhmm} ~ ${s.endHhmm}  $label',
                          style: const TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w600,
                            color: AppTheme.textPrimary,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          s.reason,
                          style: const TextStyle(
                            fontSize: 12,
                            color: AppTheme.textTertiary,
                            height: 1.4,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            );
          }),
        ],
      ),
    );
  }

  (IconData, Color, String) _suggestionStyle(String type) {
    switch (type) {
      case 'reschedule_todo':
        return (Icons.menu_book_outlined, AppTheme.blue, '과제 집중 시간 추천');
      case 'rest':
        return (Icons.self_improvement_outlined, AppTheme.green, '휴식 추천');
      default:
        return (Icons.schedule_outlined, AppTheme.teal, '일정 추천');
    }
  }

  Widget _buildInputBar() {
    return Container(
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 12),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.9),
        border: Border(
          top: BorderSide(color: AppTheme.separator, width: 0.5),
        ),
      ),
      child: Row(
        children: [
          // 마이크 버튼
          GestureDetector(
            onTap: _sending ? null : _handleMockSpeechInput,
            child: Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                color: AppTheme.purple.withOpacity(0.14),
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.mic_none_rounded,
                  color: AppTheme.purple, size: 22),
            ),
          ),
          const SizedBox(width: 8),
          // 텍스트 입력창
          Expanded(
            child: Container(
              decoration: BoxDecoration(
                color: AppTheme.background,
                borderRadius: BorderRadius.circular(22),
                border: Border.all(color: AppTheme.separator),
              ),
              child: TextField(
                controller: _inputController,
                textInputAction: TextInputAction.send,
                onSubmitted: (v) => _sendMessage(v),
                style: const TextStyle(
                    fontSize: 14, color: AppTheme.textPrimary),
                decoration: const InputDecoration(
                  hintText: '메시지를 입력하세요',
                  hintStyle:
                      TextStyle(fontSize: 14, color: AppTheme.textSecondary),
                  border: InputBorder.none,
                  contentPadding:
                      EdgeInsets.symmetric(horizontal: 16, vertical: 11),
                ),
              ),
            ),
          ),
          const SizedBox(width: 8),
          // 전송 버튼
          GestureDetector(
            onTap: _sending ? null : () => _sendMessage(_inputController.text),
            child: Container(
              width: 44,
              height: 44,
              decoration: const BoxDecoration(
                color: AppTheme.blue,
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.arrow_upward_rounded,
                  color: Colors.white, size: 22),
            ),
          ),
        ],
      ),
    );
  }
}

/// 타이핑 인디케이터용 점.
class _Dot extends StatelessWidget {
  const _Dot();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 8,
      height: 8,
      decoration: BoxDecoration(
        color: AppTheme.textSecondary.withOpacity(0.5),
        shape: BoxShape.circle,
      ),
    );
  }
}
