import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../widgets/glass_card.dart';
import '../models/voice_chat_message.dart';
import '../services/emotion_api.dart';
import '../services/preference_store.dart';
import '../services/voice_api.dart';
import '../services/voice_stt_service.dart';
import '../services/voice_tts_service.dart';

/// AI 음성 챗봇 화면.
///
///  - 마이크 버튼: 온디바이스 STT(speech_to_text)로 음성을 텍스트로 변환한 뒤,
///    그 텍스트를 [_sendMessage] 로 전달한다(= 서버에는 텍스트만 전달).
///  - 전송 버튼: 입력창 문장을 사용자 메시지로 추가 → 동일 흐름.
///  - "음성으로 듣기": flutter_tts 로 실제 재생.
///
/// 감정 코칭은 실제 `/emotion/analyze`([emotionApi])를 호출하며, 서버 실패 시
/// EmotionApi 내부에서 온디바이스 공감 fallback([LocalEmotion])으로 대체된다.
/// STT/TTS 는 온디바이스 실동작. (실 응답 스키마상 schedule_suggestions 는
/// 비어 있을 수 있어, 해당 카드는 값이 있을 때만 표시한다.)
class VoiceChatScreen extends StatefulWidget {
  const VoiceChatScreen({super.key});

  @override
  State<VoiceChatScreen> createState() => _VoiceChatScreenState();
}

class _VoiceChatScreenState extends State<VoiceChatScreen> {
  // AI 일정 생성 화면과 동일한 STT 서비스를 재사용한다.
  final VoiceSttService _stt = VoiceSttService();
  final VoiceTtsService _ttsService = VoiceTtsService();
  final _inputController = TextEditingController();
  final _scrollController = ScrollController();

  final List<VoiceChatMessage> _messages = [];
  bool _sending = false;

  /// 음성 인식 진행 여부.
  bool _isListening = false;

  /// 마이크 상태/안내 문구(null 이면 표시 안 함).
  String? _voiceStatus;

  /// 음성 인식 누적 텍스트.
  String _recognized = '';

  @override
  void initState() {
    super.initState();
    _ttsService.init();
  }

  @override
  void dispose() {
    _stt.cancelListening();
    _ttsService.stop();
    _inputController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  // ---------------------------------------------------------------------- //
  // 음성 입력 (STT) — 마이크 → 인식 → 입력창 → 전송
  // ---------------------------------------------------------------------- //

  /// 마이크 버튼: 듣는 중이면 정지, 아니면 권한 확인 후 인식을 시작한다.
  Future<void> _handleMicPressed() async {
    if (_isListening) {
      await _stt.stopListening();
      await _finishListening();
      return;
    }
    if (_sending) return;

    final granted = await _stt.ensureMicPermission();
    if (!mounted) return;
    if (!granted) {
      setState(() => _voiceStatus = SttMessages.micDenied);
      return;
    }

    final ready = await _stt.initialize(
      onStatus: (s) {
        // 인식이 끝나면(done/notListening) 자동으로 마무리.
        if ((s == 'done' || s == 'notListening') && _isListening) {
          _finishListening();
        }
      },
      onError: (_) {
        if (mounted && _isListening) {
          setState(() {
            _isListening = false;
            _voiceStatus = SttMessages.error;
          });
        }
      },
    );
    if (!mounted) return;
    if (!ready) {
      setState(() => _voiceStatus = SttMessages.unavailable);
      return;
    }

    setState(() {
      _isListening = true;
      _recognized = '';
      _voiceStatus = '듣는 중...';
    });

    final started = await _stt.startListening(
      onResult: (r) {
        _recognized = r.text;
        if (mounted) {
          setState(() => _inputController.text = r.text);
        }
      },
      onError: (msg) {
        if (mounted && _isListening) {
          setState(() {
            _isListening = false;
            _voiceStatus = msg;
          });
        }
      },
      localeId: 'ko_KR',
    );
    if (!started && mounted && _isListening) {
      setState(() {
        _isListening = false;
        _voiceStatus = SttMessages.error;
      });
    }
  }

  /// 인식 종료 처리: 결과가 있으면 전송, 무음이면 안내 문구.
  Future<void> _finishListening() async {
    if (!_isListening || !mounted) return;
    setState(() => _isListening = false);

    final text = _recognized.trim();
    if (text.isEmpty) {
      setState(() => _voiceStatus = SttMessages.empty);
      return;
    }
    setState(() => _voiceStatus = null);
    await _sendMessage(text);
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

    // 실제 /emotion/analyze 호출. 말투/음성 설정을 계약 필드로 함께 전달한다.
    // 서버 실패 시 EmotionApi 내부에서 온디바이스 공감 fallback 으로 대체된다
    // (이 호출은 예외를 던지지 않는다 → 앱 크래시 없음).
    await preferenceStore.ensureLoaded();
    final analysis = await emotionApi.analyze(
      trimmed,
      inputType: 'text',
      userContext: preferenceStore.userContext,
      voice: preferenceStore.voice,
    );
    if (!mounted) return;

    setState(() {
      _messages.add(VoiceChatMessage(
        role: ChatRole.assistant,
        text: analysis.coachingReply.isNotEmpty
            ? analysis.coachingReply
            : '이야기해 주셔서 고마워요.',
        analysis: analysis,
        ttsText: analysis.ttsText,
      ));
      // 위기/주의 안전 안내가 있으면 별도 말풍선으로 표시한다.
      if (analysis.safetyNote.trim().isNotEmpty) {
        _messages.add(VoiceChatMessage(
          role: ChatRole.assistant,
          text: analysis.safetyNote,
        ));
      }
      _sending = false;
    });
    _scrollToBottom();
  }

  /// "음성으로 듣기" — /voice/tts 규칙에 따라 기기 TTS 로 재생한다.
  /// AI 메시지의 tts_text 우선, 없으면 coaching_reply(=말풍선 text) 사용.
  /// 빈 텍스트면 재생하지 않고 안내한다.
  Future<void> _playTts(String text) async {
    debugPrint('Voice chat TTS text: $text');
    if (text.trim().isEmpty) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('읽어드릴 내용이 없어요.')),
        );
      }
      return;
    }
    await voiceApi.speak(_ttsService, text, source: 'chatbot_reply');
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
              if (_voiceStatus != null) _buildVoiceStatus(_voiceStatus!),
              _buildInputBar(),
            ],
          ),
        ),
      ),
    );
  }

  /// 마이크 상태/안내 문구를 입력창 위에 작게 표시한다.
  Widget _buildVoiceStatus(String status) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 6),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            _isListening ? Icons.mic : Icons.info_outline,
            size: 14,
            color: _isListening ? AppTheme.red : AppTheme.textSecondary,
          ),
          const SizedBox(width: 6),
          Flexible(
            child: Text(
              status,
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: _isListening ? AppTheme.red : AppTheme.textSecondary,
              ),
            ),
          ),
        ],
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
              // 일정 조정 추천은 값이 있을 때만 표시(실 서버 응답엔 없을 수 있음).
              if (m.analysis!.scheduleSuggestions.isNotEmpty) ...[
                const SizedBox(height: 10),
                _buildSuggestionsCard(m.analysis!),
              ],
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
          // 마이크 버튼 (온디바이스 STT). 듣는 중이면 정지 아이콘.
          GestureDetector(
            onTap: _sending ? null : _handleMicPressed,
            child: Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                color: _isListening
                    ? AppTheme.red.withOpacity(0.16)
                    : AppTheme.purple.withOpacity(0.14),
                shape: BoxShape.circle,
              ),
              child: Icon(
                _isListening ? Icons.stop_rounded : Icons.mic_none_rounded,
                color: _isListening ? AppTheme.red : AppTheme.purple,
                size: 22,
              ),
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
