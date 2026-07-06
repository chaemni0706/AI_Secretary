import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../widgets/glass_card.dart';
import '../widgets/voice_intent_card.dart';
import '../models/voice_chat_message.dart';
import '../services/preference_store.dart';
import '../services/voice_router_api.dart';
import '../services/voice_stt_service.dart';
import '../services/voice_tts_service.dart';

/// AI 음성 비서 화면 — 음성 입력의 공용 진입점.
///
/// 이 화면은 더 이상 "일정 등록 전용" 이 아니다. 마이크로 말하거나 텍스트를
/// 입력하면 `POST /api/v1/voice/route` 가 발화를 의도별로 분류해:
///   예약/장소 추천 · 감정 기반 일정 코칭 · 오늘 브리핑 · 일정 조회/등록 ·
///   알림 설정 · 일반 대화
/// 중 알맞은 곳으로 위임하고, 그 결과(tts_text/screen_action/data)를 돌려준다.
/// 화면은 intent 에 맞는 카드를 붙이고, 응답은 항상 flutter_tts 로 읽어준다.
class VoiceChatScreen extends StatefulWidget {
  const VoiceChatScreen({super.key});

  @override
  State<VoiceChatScreen> createState() => _VoiceChatScreenState();
}

class _VoiceChatScreenState extends State<VoiceChatScreen> {
  final VoiceSttService _stt = VoiceSttService();
  final VoiceTtsService _ttsService = VoiceTtsService();
  final _inputController = TextEditingController();
  final _scrollController = ScrollController();

  final List<VoiceChatMessage> _messages = [];
  bool _sending = false;
  bool _isListening = false;
  String? _voiceStatus;

  /// 직전 turn 에서 서버가 돌려준 pending context(예: 방금 등록한 일정).
  /// 다음 발화 한 번에만 유효하며, 사용 여부와 무관하게 매 턴 종료 시 비운다.
  Map<String, dynamic>? _pendingContext;

  @override
  void initState() {
    super.initState();
    _ttsService.init();
  }

  @override
  void dispose() {
    _stt.cancel();
    _ttsService.stop();
    _inputController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  String _nowIso() {
    final now = DateTime.now();
    final o = now.timeZoneOffset;
    final sign = o.isNegative ? '-' : '+';
    final hh = o.inHours.abs().toString().padLeft(2, '0');
    final mm = (o.inMinutes.abs() % 60).toString().padLeft(2, '0');
    final base = now.toIso8601String().split('.').first;
    return '$base$sign$hh:$mm';
  }

  // --------------------------------------------------------------------- //
  // 음성 입력 (STT) — 마이크 → 인식 → 자동 전송
  // --------------------------------------------------------------------- //
  Future<void> _handleMicPressed() async {
    if (_isListening) {
      await _stt.stop();
      return;
    }
    if (_sending) return;

    final granted = await _stt.ensureMicPermission();
    if (!mounted) return;
    if (!granted) {
      setState(() => _voiceStatus = '마이크 권한이 필요해요.');
      return;
    }

    final ready = await _stt.init(
      onStatus: (s) {
        if ((s == 'done' || s == 'notListening') && _isListening) {
          _finishListening();
        }
      },
      onError: (_) {
        if (mounted && _isListening) {
          setState(() {
            _isListening = false;
            _voiceStatus = '음성 인식 중 오류가 발생했어요.';
          });
        }
      },
    );
    if (!mounted) return;
    if (!ready) {
      setState(() => _voiceStatus = '기기에서 음성 인식을 사용할 수 없어요.');
      return;
    }

    String recognized = '';
    setState(() {
      _isListening = true;
      _voiceStatus = '듣는 중...';
    });

    await _stt.listen(
      onResult: (r) => recognized = r.text,
      localeId: 'ko_KR',
    );
    // 인식 텍스트는 종료 시점에 다시 읽어야 하므로 콜백 스코프 밖의 변수에 보관.
    _lastRecognized = recognized;
  }

  String _lastRecognized = '';

  Future<void> _finishListening() async {
    if (!_isListening) return;
    if (!mounted) return;
    setState(() {
      _isListening = false;
      _voiceStatus = null;
    });

    final text = _lastRecognized.trim();
    if (text.isEmpty) {
      setState(() => _voiceStatus = '음성을 인식하지 못했어요. 다시 말해주세요.');
      return;
    }
    await _sendMessage(text);
  }

  // --------------------------------------------------------------------- //
  // 발화 전송 → 통합 라우팅 → 응답 표시 + TTS
  // --------------------------------------------------------------------- //
  Future<void> _sendMessage(String text) async {
    final trimmed = text.trim();
    if (trimmed.isEmpty || _sending) return;

    // 직전 턴의 pending context 는 "바로 다음 발화 한 번"에만 유효하다.
    final contextToSend = _pendingContext;
    _pendingContext = null;

    setState(() {
      _messages.add(VoiceChatMessage(role: ChatRole.user, text: trimmed));
      _sending = true;
    });
    _inputController.clear();
    _scrollToBottom();

    try {
      await preferenceStore.ensureLoaded();
      final result = await voiceRouterApi.route(
        trimmed,
        currentDatetime: _nowIso(),
        context: contextToSend,
        assistantTone: preferenceStore.assistantTone,
        responseLength: preferenceStore.responseLength,
        reminderStrength: preferenceStore.reminderStrength,
      );
      if (!mounted) return;
      setState(() {
        _messages.add(VoiceChatMessage(
          role: ChatRole.assistant,
          text: result.ttsText.isNotEmpty ? result.ttsText : '확인했어요.',
          route: result,
        ));
        _pendingContext = result.context;
        _sending = false;
      });
      _scrollToBottom();
      handleVoiceSideEffects(result);
      if (mounted) handleVoiceScreenAction(context, result);
      await _ttsService.speak(result.ttsText);
    } catch (e) {
      debugPrint('VoiceChatScreen route failed: $e');
      if (!mounted) return;
      setState(() {
        _messages.add(const VoiceChatMessage(
          role: ChatRole.assistant,
          text: '지금은 응답을 받지 못했어요. 잠시 후 다시 시도해주세요.',
        ));
        _sending = false;
      });
      _scrollToBottom();
    }
  }

  Future<void> _playTts(String text) async {
    debugPrint('Voice chat TTS text: $text');
    await _ttsService.speak(text);
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
          title: const Text('AI 음성 비서'),
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
              if (_voiceStatus != null) _buildVoiceStatus(),
              _buildInputBar(),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildVoiceStatus() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 4),
      child: Text(
        _voiceStatus!,
        style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
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
                '무엇이든 말씀해보세요. 일정 등록/조회, 가게 추천, 오늘 브리핑, '
                '힘들 때 마음 챙김까지 하나의 마이크로 처리해요.',
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
              onTap: () => _playTts(m.text),
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
            if (m.route != null) ...[
              const SizedBox(height: 10),
              buildVoiceIntentCard(context, m.route!),
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
          // 마이크 버튼 — 실제 기기 STT
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
