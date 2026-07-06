import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../services/api_client.dart';
import '../services/preference_store.dart';
import '../services/voice_router_api.dart';
import '../services/voice_stt_service.dart';
import '../services/voice_tts_service.dart';
import '../widgets/voice_intent_card.dart';

/// 메인 화면 우측 하단 "AI" 버튼으로 열리는 텍스트/음성 겸용 챗봇 화면.
///
/// `voice_chat_screen.dart` 와 마찬가지로 `POST /api/v1/voice/route` 하나로
/// 발화를 보낸다 — 텍스트로 치든 마이크로 말하든 같은 intent 분류기를 타므로
/// 같은 문장이 화면마다 다르게 처리되는 일이 없다(이전에는 이 화면만
/// `/ai/schedule/parse` 로 직행해 모든 입력이 일정으로 해석됐었음).
class AiChatScreen extends StatefulWidget {
  const AiChatScreen({super.key});

  @override
  State<AiChatScreen> createState() => _AiChatScreenState();
}

class _AiChatScreenState extends State<AiChatScreen> {
  final TextEditingController _inputController = TextEditingController();
  final ScrollController _scrollController = ScrollController();

  final VoiceSttService _stt = VoiceSttService();
  final VoiceTtsService _tts = VoiceTtsService();

  /// 음성 인식 후 바로 전송할지 여부. false 로 두면 입력창에 넣기만 한다.
  static const bool autoSendAfterVoiceInput = true;

  bool _isListening = false;
  bool _sending = false;

  /// 마이크 상태 안내 문구 (null 이면 표시 안 함).
  String? _voiceStatus;

  /// 음성 인식 누적 텍스트.
  String _recognized = '';

  /// 직전 turn 에서 서버가 돌려준 pending context(예: 방금 등록한 일정).
  /// 다음 발화 한 번에만 유효하며, 사용 여부와 무관하게 매 턴 종료 시 비운다.
  Map<String, dynamic>? _pendingContext;

  final List<_ChatMessage> _messages = [
    const _ChatMessage(
      text: '무엇을 도와드릴까요? 일정 등록/조회, 가게 추천, 오늘 브리핑, 감정 코칭까지 뭐든 말씀해보세요.',
      isUser: false,
    ),
  ];

  @override
  void initState() {
    super.initState();
    _tts.init();
  }

  @override
  void dispose() {
    _stt.cancel();
    _tts.dispose();
    _inputController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  // ---------------------------------------------------------------------- //
  // 음성 입력 (STT)  —  마이크 → 인식 → 입력창 → 자동 전송
  // ---------------------------------------------------------------------- //
  Future<void> _handleMicPressed() async {
    // 이미 듣는 중이면 정지(수동 종료).
    if (_isListening) {
      await _stt.stop();
      await _finishListening();
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
        // 인식이 끝나면(done/notListening) 자동으로 마무리.
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

    setState(() {
      _isListening = true;
      _recognized = '';
      _voiceStatus = '듣는 중...';
    });

    await _stt.listen(
      onResult: (r) {
        _recognized = r.text;
        if (mounted) {
          setState(() => _inputController.text = r.text);
        }
      },
      localeId: 'ko_KR',
    );
  }

  /// 인식 종료 처리: 결과가 있으면 입력창 반영 + (옵션) 자동 전송.
  Future<void> _finishListening() async {
    if (!_isListening) return;
    if (!mounted) return;
    setState(() => _isListening = false);

    final text = _recognized.trim();
    if (text.isEmpty) {
      setState(() => _voiceStatus = '음성을 인식하지 못했어요. 다시 말해주세요.');
      return;
    }

    setState(() {
      _inputController.text = text;
      _voiceStatus = '인식 완료';
    });

    if (autoSendAfterVoiceInput) {
      await _send(fromVoice: true);
    }
  }

  void _addMessage(String text, {required bool isUser, VoiceRouteResult? route}) {
    setState(() => _messages.add(_ChatMessage(text: text, isUser: isUser, route: route)));
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 250),
          curve: Curves.easeOut,
        );
      }
    });
  }

  /// 발화 전송 → 통합 라우팅(`/voice/route`) → 응답 표시 (+음성 입력이면 TTS)
  ///
  /// TTS 정책(기존 그대로 유지): 마이크로 말한 경우만 자동 재생하고, 키보드
  /// 입력은 화면에만 표시한다(조용한 상황에서 타이핑했는데 갑자기 말이 나오는
  /// 것을 막기 위함).
  Future<void> _send({bool fromVoice = false}) async {
    final text = _inputController.text.trim();
    if (text.isEmpty || _sending) return;

    final contextToSend = _pendingContext;
    _pendingContext = null;

    _inputController.clear();
    _addMessage(text, isUser: true);
    setState(() {
      _sending = true;
      _voiceStatus = fromVoice ? '답변 생성 중...' : null;
    });

    try {
      await preferenceStore.ensureLoaded();
      final result = await voiceRouterApi.route(
        text,
        currentDatetime: DateTime.now().toIso8601String(),
        context: contextToSend,
        assistantTone: preferenceStore.assistantTone,
        responseLength: preferenceStore.responseLength,
        reminderStrength: preferenceStore.reminderStrength,
      );
      if (!mounted) return;
      setState(() {
        _pendingContext = result.context;
        _sending = false;
        _voiceStatus = null;
      });
      _addMessage(
        result.ttsText.isNotEmpty ? result.ttsText : '확인했어요.',
        isUser: false,
        route: result,
      );
      handleVoiceSideEffects(result);
      if (mounted) handleVoiceScreenAction(context, result);

      if (fromVoice) await _speak(result.ttsText);
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _sending = false;
        _voiceStatus = null;
      });
      final msg = (e.statusCode == null)
          ? '서버에 연결할 수 없어요. 백엔드가 실행 중인지 확인해주세요.'
          : '요청을 처리하지 못했어요: ${e.message}';
      _addMessage(msg, isUser: false);
      if (fromVoice) await _speak('요청을 처리하지 못했어요. 다시 시도해주세요.');
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _sending = false;
        _voiceStatus = null;
      });
      _addMessage('오류가 발생했어요: $e', isUser: false);
    }
  }

  /// AI 응답을 Flutter TTS 로 읽는다. (빈 문자열/오류는 서비스에서 안전 처리)
  Future<void> _speak(String text) async {
    try {
      await _tts.speak(text);
    } catch (e) {
      debugPrint('AiChat TTS error: $e');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: AppTheme.screenBackground,
      child: Scaffold(
        backgroundColor: Colors.transparent,
        body: SafeArea(
          child: Column(
            children: [
              _buildHeader(),
              Expanded(child: _buildChatArea()),
              if (_sending)
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 8),
                  child: SizedBox(
                    height: 18,
                    width: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                ),
              if (_voiceStatus != null) _buildVoiceStatus(_voiceStatus!),
              _buildInputArea(),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 8),
      child: Row(
        children: [
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [AppTheme.purple, AppTheme.blue],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              borderRadius: BorderRadius.circular(12),
            ),
            child: const Icon(
              Icons.auto_awesome,
              color: Colors.white,
              size: 20,
            ),
          ),
          const SizedBox(width: 10),
          const Text(
            'AI 비서',
            style: TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.w700,
              color: AppTheme.textPrimary,
              letterSpacing: -0.4,
            ),
          ),
          const Spacer(),
          GestureDetector(
            onTap: () {},
            child: Container(
              width: 32,
              height: 32,
              decoration: BoxDecoration(
                color: Colors.white.withOpacity(0.6),
                shape: BoxShape.circle,
                border: Border.all(color: AppTheme.separator.withOpacity(0.7)),
              ),
              child: const Icon(
                Icons.more_horiz,
                color: AppTheme.textSecondary,
                size: 18,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildChatArea() {
    return ListView.builder(
      controller: _scrollController,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      itemCount: _messages.length,
      itemBuilder: (context, i) {
        final msg = _messages[i];
        return _ChatBubble(message: msg);
      },
    );
  }

  Widget _buildVoiceStatus(String status) {
    final listening = _isListening;
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 6),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            listening ? Icons.mic : Icons.info_outline,
            size: 14,
            color: listening ? AppTheme.red : AppTheme.textSecondary,
          ),
          const SizedBox(width: 6),
          Text(
            status,
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: listening ? AppTheme.red : AppTheme.textSecondary,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildInputArea() {
    return Container(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.85),
        border: Border(
          top: BorderSide(color: AppTheme.separator.withOpacity(0.5)),
        ),
      ),
      child: Row(
        children: [
          Expanded(
            child: Container(
              decoration: BoxDecoration(
                color: AppTheme.background,
                borderRadius: BorderRadius.circular(24),
                border: Border.all(color: AppTheme.separator),
              ),
              child: Row(
                children: [
                  const SizedBox(width: 16),
                  Expanded(
                    child: TextField(
                      controller: _inputController,
                      onSubmitted: (_) => _send(),
                      textInputAction: TextInputAction.send,
                      style: const TextStyle(
                        fontSize: 14,
                        color: AppTheme.textPrimary,
                      ),
                      decoration: const InputDecoration(
                        hintText: '말하거나 입력하세요',
                        hintStyle: TextStyle(
                          fontSize: 14,
                          color: AppTheme.textSecondary,
                        ),
                        border: InputBorder.none,
                        isDense: true,
                        contentPadding: EdgeInsets.symmetric(vertical: 10),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  GestureDetector(
                    onTap: _sending ? null : _handleMicPressed,
                    child: Container(
                      width: 34,
                      height: 34,
                      margin: const EdgeInsets.all(4),
                      decoration: BoxDecoration(
                        color: _isListening
                            ? AppTheme.red
                            : AppTheme.blue.withOpacity(0.12),
                        shape: BoxShape.circle,
                      ),
                      child: Icon(
                        _isListening ? Icons.stop : Icons.mic,
                        color: _isListening ? Colors.white : AppTheme.blue,
                        size: 18,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(width: 10),
          GestureDetector(
            onTap: _sending ? null : () => _send(),
            child: Container(
              width: 42,
              height: 42,
              decoration: BoxDecoration(
                color: AppTheme.blue,
                shape: BoxShape.circle,
                boxShadow: [
                  BoxShadow(
                    color: AppTheme.blue.withOpacity(0.3),
                    blurRadius: 8,
                    offset: const Offset(0, 3),
                  ),
                ],
              ),
              child: const Icon(Icons.send, color: Colors.white, size: 18),
            ),
          ),
        ],
      ),
    );
  }
}

class _ChatMessage {
  final String text;
  final bool isUser;

  /// AI 메시지에 한해 `/voice/route` 결과 전체를 담는다(사용자 메시지는 null).
  final VoiceRouteResult? route;

  const _ChatMessage({required this.text, required this.isUser, this.route});
}

class _ChatBubble extends StatelessWidget {
  final _ChatMessage message;

  const _ChatBubble({required this.message});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Column(
        crossAxisAlignment:
            message.isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: message.isUser
                ? MainAxisAlignment.end
                : MainAxisAlignment.start,
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              if (!message.isUser) ...[
                Container(
                  width: 28,
                  height: 28,
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(
                      colors: [AppTheme.purple, AppTheme.blue],
                    ),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Icon(
                    Icons.auto_awesome,
                    color: Colors.white,
                    size: 14,
                  ),
                ),
                const SizedBox(width: 8),
              ],
              Flexible(
                child: Container(
                  constraints: BoxConstraints(
                    maxWidth: MediaQuery.of(context).size.width * 0.7,
                  ),
                  padding:
                      const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                  decoration: BoxDecoration(
                    color: message.isUser
                        ? AppTheme.blue
                        : Colors.white.withOpacity(0.85),
                    borderRadius: BorderRadius.only(
                      topLeft: const Radius.circular(16),
                      topRight: const Radius.circular(16),
                      bottomLeft: Radius.circular(message.isUser ? 16 : 4),
                      bottomRight: Radius.circular(message.isUser ? 4 : 16),
                    ),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withOpacity(0.06),
                        blurRadius: 8,
                        offset: const Offset(0, 2),
                      ),
                    ],
                  ),
                  child: Text(
                    message.text,
                    style: TextStyle(
                      fontSize: 14,
                      color: message.isUser ? Colors.white : AppTheme.textPrimary,
                      height: 1.4,
                    ),
                  ),
                ),
              ),
              if (message.isUser) const SizedBox(width: 4),
            ],
          ),
          if (!message.isUser && message.route != null) ...[
            const SizedBox(height: 6),
            Padding(
              padding: const EdgeInsets.only(left: 36, right: 32),
              child: buildVoiceIntentCard(context, message.route!),
            ),
          ],
        ],
      ),
    );
  }
}
