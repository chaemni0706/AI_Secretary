import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../widgets/glass_card.dart';
import '../services/api_client.dart';
import '../services/schedule_api.dart';
import '../services/todo_api.dart';
import '../services/dashboard_api.dart';

class AiChatScreen extends StatefulWidget {
  const AiChatScreen({super.key});

  @override
  State<AiChatScreen> createState() => _AiChatScreenState();
}

class _AiChatScreenState extends State<AiChatScreen> {
  final TextEditingController _inputController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  bool _isListening = false;
  bool _parsing = false;
  bool _saving = false;

  /// 마지막 parse 결과 (저장 대상).
  ParseResult? _lastParse;

  final List<_ChatMessage> _messages = [
    const _ChatMessage(
      text: '무엇을 도와드릴까요? 예: "내일 오후 2시에 치과 예약 잡아줘"',
      isUser: false,
    ),
  ];

  @override
  void dispose() {
    _inputController.dispose();
    _scrollController.dispose();
    super.dispose();
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
  Future<void> _send() async {
    final text = _inputController.text.trim();
    if (text.isEmpty || _parsing) return;
    _inputController.clear();
    _addMessage(text, isUser: true);
    setState(() => _parsing = true);

    try {
      final result = await scheduleApi.parse(
        text,
        currentDatetime: DateTime.now().toIso8601String(),
      );
      setState(() {
        _lastParse = result;
        _parsing = false;
      });
      final draft = result.scheduleDraft;
      final kind = result.isTodo ? '할 일' : '일정';
      _addMessage(
        '"${draft['title'] ?? text}"($kind)로 인식했어요. 아래에서 확인 후 저장하세요.',
        isUser: false,
      );
    } on ApiException catch (e) {
      setState(() => _parsing = false);
      _addMessage('인식에 실패했어요: ${e.message}', isUser: false);
    } catch (e) {
      setState(() => _parsing = false);
      _addMessage('오류가 발생했어요: $e', isUser: false);
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
    final dateMissing =
        rawDate == null || rawDate.toString().trim().isEmpty;
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
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('저장되었습니다.')),
        );
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
      child: SafeArea(
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
            _buildInputArea(),
          ],
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
            child:
                const Icon(Icons.auto_awesome, color: Colors.white, size: 20),
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
                border:
                    Border.all(color: AppTheme.separator.withOpacity(0.7)),
              ),
              child: const Icon(Icons.more_horiz,
                  color: AppTheme.textSecondary, size: 18),
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
                      Text(title,
                          style: const TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w700,
                            color: AppTheme.textPrimary,
                          )),
                      Text('${isTodo ? "할 일" : "일정"} · $category',
                          style: const TextStyle(
                            fontSize: 12,
                            color: AppTheme.textSecondary,
                          )),
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
                        : const Text('저장하기',
                            style: TextStyle(
                                fontSize: 14, fontWeight: FontWeight.w600)),
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
                    child: const Text('취소',
                        style: TextStyle(
                            fontSize: 14, fontWeight: FontWeight.w600)),
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
          child: Text(label,
              style: const TextStyle(
                  fontSize: 13, color: AppTheme.textSecondary)),
        ),
        Expanded(
          child: Text(value,
              style: const TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w600,
                color: AppTheme.textPrimary,
              )),
        ),
      ],
    );
  }

  Widget _buildInputArea() {
    return Container(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.85),
        border: Border(
            top: BorderSide(color: AppTheme.separator.withOpacity(0.5))),
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
                          fontSize: 14, color: AppTheme.textPrimary),
                      decoration: const InputDecoration(
                        hintText: '말하거나 입력하세요',
                        hintStyle: TextStyle(
                            fontSize: 14, color: AppTheme.textSecondary),
                        border: InputBorder.none,
                        isDense: true,
                        contentPadding:
                            EdgeInsets.symmetric(vertical: 10),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  GestureDetector(
                    onTap: () => setState(() => _isListening = !_isListening),
                    child: Container(
                      width: 34,
                      height: 34,
                      margin: const EdgeInsets.all(4),
                      decoration: BoxDecoration(
                        color: _isListening
                            ? AppTheme.blue
                            : AppTheme.blue.withOpacity(0.12),
                        shape: BoxShape.circle,
                      ),
                      child: Icon(
                        Icons.graphic_eq,
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
        mainAxisAlignment:
            message.isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
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
              child: const Icon(Icons.auto_awesome,
                  color: Colors.white, size: 14),
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
                  color:
                      message.isUser ? Colors.white : AppTheme.textPrimary,
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
