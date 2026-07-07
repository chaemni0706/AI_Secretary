import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../widgets/glass_card.dart';
import '../services/api_client.dart';
import '../services/schedule_api.dart';
import '../services/preference_store.dart';
import '../services/todo_api.dart';
import '../services/dashboard_api.dart';
import '../services/voice_stt_service.dart';
import '../services/voice_tts_service.dart';

class AiChatScreen extends StatefulWidget {
  /// true면 화면 진입 직후 마이크 리스닝을 자동으로 시작한다.
  /// (AI 비서 버튼을 길게 눌러 바로 음성 대화로 진입하는 경로에서 사용)
  final bool autoStartVoice;

  const AiChatScreen({super.key, this.autoStartVoice = false});

  @override
  State<AiChatScreen> createState() => _AiChatScreenState();
}

class _AiChatScreenState extends State<AiChatScreen> {
  final TextEditingController _inputController = TextEditingController();
  final ScrollController _scrollController = ScrollController();

  // 음성 입출력 서비스 (기존 서비스 재사용).
  final VoiceSttService _stt = VoiceSttService();
  final VoiceTtsService _tts = VoiceTtsService();

  /// 음성 인식 후 바로 전송할지 여부. false 로 두면 입력창에 넣기만 한다.
  static const bool autoSendAfterVoiceInput = true;

  bool _isListening = false;
  bool _parsing = false;
  bool _saving = false;

  /// 마이크 상태 안내 문구 (null 이면 표시 안 함).
  String? _voiceStatus;

  /// 이번 전송이 음성 입력에서 시작됐는지(응답 TTS 재생 여부 판단).
  bool _fromVoice = false;

  /// 음성 인식 누적 텍스트.
  String _recognized = '';

  /// 마지막 parse 결과 (저장 대상).
  ParseResult? _lastParse;

  @override
  void initState() {
    super.initState();
    _tts.init();
    if (widget.autoStartVoice) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _handleMicPressed();
      });
    }
  }

  final List<_ChatMessage> _messages = [
    const _ChatMessage(
      text: '무엇을 도와드릴까요? 예: "내일 오후 2시에 치과 예약 잡아줘"',
      isUser: false,
    ),
  ];

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
    if (_parsing || _saving) return;

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

  void _addMessage(String text, {required bool isUser}) {
    setState(() => _messages.add(_ChatMessage(text: text, isUser: isUser)));
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

  /// 1) 자연어 → parse
  ///
  /// TTS 정책(의도된 동작):
  /// - 마이크로 말한 경우([fromVoice]==true): input_type="voice" 로 보내고
  ///   AI 응답을 TTS 로 자동 재생한다.
  /// - 키보드로 입력한 경우([fromVoice]==false): 화면에만 표시하고 소리는 내지 않는다.
  ///   (조용한 상황에서 타이핑했는데 갑자기 말이 나오는 것을 막기 위함)
  Future<void> _send({bool fromVoice = false}) async {
    final text = _inputController.text.trim();
    if (text.isEmpty || _parsing) return;
    _fromVoice = fromVoice;
    _inputController.clear();
    _addMessage(text, isUser: true);
    setState(() {
      _parsing = true;
      _voiceStatus = fromVoice ? '답변 생성 중...' : null;
    });

    try {
      await preferenceStore.ensureLoaded();
      final result = await scheduleApi.parse(
        text,
        currentDatetime: DateTime.now().toIso8601String(),
        inputType: fromVoice ? 'voice' : 'text',
        assistantTone: preferenceStore.assistantTone,
        responseLength: preferenceStore.responseLength,
        reminderStrength: preferenceStore.reminderStrength,
      );
      if (!mounted) return;
      setState(() {
        _lastParse = result;
        _parsing = false;
        _voiceStatus = null;
      });
      final draft = result.scheduleDraft;
      final kind = result.isTodo ? '할 일' : '일정';
      final reply =
          '"${draft['title'] ?? text}"($kind)로 인식했어요. 아래에서 확인 후 저장하세요.';
      _addMessage(reply, isUser: false);

      // 음성 입력이었으면 AI 응답을 읽어준다. tts_text 우선, 없으면 화면 문구.
      if (_fromVoice) {
        final speakText =
            (result.ttsText != null && result.ttsText!.trim().isNotEmpty)
            ? result.ttsText!
            : reply;
        await _speak(speakText);
      }
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _parsing = false;
        _voiceStatus = null;
      });
      final msg = (e.statusCode == null)
          ? '서버에 연결할 수 없어요. 백엔드가 실행 중인지 확인해주세요.'
          : '인식에 실패했어요: ${e.message}';
      _addMessage(msg, isUser: false);
      if (_fromVoice) await _speak('요청을 처리하지 못했어요. 다시 시도해주세요.');
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _parsing = false;
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

  /// 2) parse 결과 저장 → 3) 대시보드 새로고침 트리거
  Future<void> _save() async {
    final parse = _lastParse;
    if (parse == null || _saving) return;

    final draft = Map<String, dynamic>.from(parse.scheduleDraft);

    // 일정 저장은 date 가 필수다. 파서가 날짜를 인식하지 못했으면(예: 날짜 표현이
    // 없는 문장) 임의로 오늘로 저장하지 않고, 사용자에게 날짜를 알려달라고 안내한다.
    // (일정만 해당. To-do 는 마감일이 없어도 저장 가능.)
    final rawDate = draft['date'];
    final dateMissing = rawDate == null || rawDate.toString().trim().isEmpty;
    if (!parse.isTodo && dateMissing) {
      _addMessage(
        '날짜를 인식하지 못했어요. "7월 3일", "7/3", "내일"처럼 날짜를 포함해 다시 말씀해 주세요.',
        isUser: false,
      );
      return;
    }

    final rawTitle = draft['title'];
    if (rawTitle == null || rawTitle.toString().trim().isEmpty) {
      draft['title'] = '새 일정';
    }

    setState(() => _saving = true);
    try {
      final String savedTitle;
      if (parse.isTodo) {
        final todo = await todoApi.createFromDraft(draft);
        savedTitle = todo.title;
      } else {
        final sch = await scheduleApi.createFromDraft(
          draft,
          intent: parse.intent,
        );
        savedTitle = sch.title;
      }
      // 홈 대시보드 새로고침 트리거.
      triggerDashboardRefresh();
      setState(() {
        _saving = false;
        _lastParse = null;
      });
      _addMessage('"$savedTitle" 저장 완료! 홈 화면에 반영됩니다.', isUser: false);
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text('저장되었습니다.')));
      }
    } on ApiException catch (e) {
      setState(() => _saving = false);
      _addMessage('저장 실패: ${e.message}', isUser: false);
    } catch (e) {
      setState(() => _saving = false);
      _addMessage('저장 중 오류: $e', isUser: false);
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
              if (_parsing)
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 8),
                  child: SizedBox(
                    height: 18,
                    width: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                ),
              if (_lastParse != null) _buildResultCard(_lastParse!),
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

  Widget _buildResultCard(ParseResult parse) {
    final draft = parse.scheduleDraft;
    final title = (draft['title'] ?? '(제목 없음)').toString();
    final category = (draft['category'] ?? '기타').toString();
    final date = (draft['date'] ?? '-').toString();
    final start = (draft['start_time'] ?? '').toString();
    final end = (draft['end_time'] ?? '').toString();
    final timeText = start.isEmpty
        ? '-'
        : (end.isEmpty ? start : '$start – $end');
    final isTodo = parse.isTodo;

    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
      child: GlassCard(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  width: 32,
                  height: 32,
                  decoration: BoxDecoration(
                    color: AppTheme.teal.withOpacity(0.15),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Icon(
                    isTodo ? Icons.check_circle_outline : Icons.event_outlined,
                    color: AppTheme.teal,
                    size: 18,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        title,
                        style: const TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w700,
                          color: AppTheme.textPrimary,
                        ),
                      ),
                      Text(
                        '${isTodo ? "할 일" : "일정"} · $category',
                        style: const TextStyle(
                          fontSize: 12,
                          color: AppTheme.textSecondary,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            const Divider(color: AppTheme.separator, height: 1),
            const SizedBox(height: 10),
            _resultRow(isTodo ? '마감일' : '날짜', date),
            if (!isTodo) ...[
              const SizedBox(height: 6),
              _resultRow('시간', timeText),
            ],
            if (parse.missingFields.isNotEmpty) ...[
              const SizedBox(height: 6),
              _resultRow('누락', parse.missingFields.join(', ')),
            ],
            const SizedBox(height: 14),
            Row(
              children: [
                Expanded(
                  child: FilledButton(
                    onPressed: _saving ? null : _save,
                    style: FilledButton.styleFrom(
                      backgroundColor: AppTheme.blue,
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                    child: _saving
                        ? const SizedBox(
                            height: 18,
                            width: 18,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Colors.white,
                            ),
                          )
                        : const Text(
                            '저장하기',
                            style: TextStyle(
                              fontSize: 14,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: OutlinedButton(
                    onPressed: _saving
                        ? null
                        : () => setState(() => _lastParse = null),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: AppTheme.textPrimary,
                      side: const BorderSide(color: AppTheme.separator),
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                    child: const Text(
                      '취소',
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _resultRow(String label, String value) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: 48,
          child: Text(
            label,
            style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary),
          ),
        ),
        Expanded(
          child: Text(
            value,
            style: const TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w600,
              color: AppTheme.textPrimary,
            ),
          ),
        ),
      ],
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
                    onTap: (_parsing || _saving) ? null : _handleMicPressed,
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
            onTap: _send,
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

  const _ChatMessage({required this.text, required this.isUser});
}

class _ChatBubble extends StatelessWidget {
  final _ChatMessage message;

  const _ChatBubble({required this.message});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
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
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
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
    );
  }
}
