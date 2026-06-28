import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/theme/app_colors.dart';
import '../../core/theme/app_dimens.dart';
import '../../core/utils/responsive_utils.dart';

// ─────────────────────────────────────────────────────────────
//  임시 mock 모델 (다음 단계에서 data/models 로 분리 예정)
// ─────────────────────────────────────────────────────────────

class _ChatMessage {
  const _ChatMessage({required this.text, required this.isUser});
  final String text;
  final bool isUser;
}

class AiChatScreen extends StatefulWidget {
  const AiChatScreen({super.key});

  @override
  State<AiChatScreen> createState() => _AiChatScreenState();
}

class _AiChatScreenState extends State<AiChatScreen> {
  final TextEditingController _controller = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final List<_ChatMessage> _messages = [];

  @override
  void dispose() {
    _controller.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _send([String? preset]) {
    final text = preset ?? _controller.text.trim();
    if (text.isEmpty) return;

    setState(() {
      _messages.add(_ChatMessage(text: text, isUser: true));
      _messages.add(
        _ChatMessage(
          text: '"$text" 요청을 확인했어요. 잠시만 기다려 주세요.',
          isUser: false,
        ),
      );
      _controller.clear();
    });

    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('메시지를 전송했어요.'),
        duration: Duration(seconds: 2),
      ),
    );

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
    final hasMessages = _messages.isNotEmpty;

    return Scaffold(
      backgroundColor: AppColors.surface,
      resizeToAvoidBottomInset: true,
      appBar: AppBar(
        backgroundColor: AppColors.surface,
        leading: TextButton(
          onPressed: () => context.go('/today'),
          child: const Text(
            '취소',
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w600,
              color: AppColors.primary,
            ),
          ),
        ),
        leadingWidth: 72,
        title: const Text('AI 채팅'),
        actions: [
          IconButton(
            icon: const Icon(Icons.more_horiz, color: AppColors.textPrimary),
            onPressed: () {},
          ),
        ],
      ),
      body: SafeArea(
        bottom: false, // 입력창에서 하단 인셋을 직접 처리
        child: Column(
          children: [
            Expanded(
              child: hasMessages
                  ? _buildMessageList(context)
                  : _buildEmptyState(context),
            ),
            _buildInputBar(context),
          ],
        ),
      ),
    );
  }

  // ── 빈 상태 (시안 화면) ──
  Widget _buildEmptyState(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    final width = MediaQuery.sizeOf(context).width;
    final orbSize = math.min(width * 0.5, 200.0);

    return SingleChildScrollView(
      padding: const EdgeInsets.symmetric(horizontal: AppDimens.lg),
      child: Column(
        children: [
          const SizedBox(height: AppDimens.xl),
          _AiOrb(size: orbSize),
          const SizedBox(height: AppDimens.xl),
          Text(
            'AI 비서에게 말해보세요.',
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: textTheme.titleLarge,
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: AppDimens.sm),
          Text(
            '“오늘 일정 정리해줘”',
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: textTheme.headlineMedium?.copyWith(
              fontWeight: FontWeight.bold,
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: AppDimens.md),
          Text(
            '일정, 예약, 준비물, 메시지를 한 번에 도와드릴게요.',
            maxLines: 3,
            overflow: TextOverflow.ellipsis,
            style: textTheme.bodyMedium,
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: AppDimens.xl),
          _buildQuickActions(context),
          const SizedBox(height: AppDimens.lg),
        ],
      ),
    );
  }

  // ── 빠른 실행 버튼 (Wrap: 좁은 화면에서 자동 줄바꿈) ──
  Widget _buildQuickActions(BuildContext context) {
    return Wrap(
      alignment: WrapAlignment.center,
      spacing: AppDimens.sm,
      runSpacing: AppDimens.sm,
      children: [
        _QuickPill(
          icon: Icons.calendar_today_outlined,
          label: '오늘 브리핑',
          onTap: () => _send('오늘 브리핑 해줘'),
        ),
        _QuickPill(
          icon: Icons.chat_bubble_outline,
          label: '예약 메시지 생성',
          onTap: () => _send('예약 메시지 생성해줘'),
        ),
        _QuickPill(
          icon: Icons.check_box_outlined,
          label: '준비물 알려줘',
          onTap: () => _send('오늘 준비물 알려줘'),
        ),
      ],
    );
  }

  // ── 메시지 리스트 (전송 후) ──
  Widget _buildMessageList(BuildContext context) {
    return ListView.builder(
      controller: _scrollController,
      padding: const EdgeInsets.all(AppDimens.lg),
      itemCount: _messages.length,
      itemBuilder: (context, i) => _MessageBubble(message: _messages[i]),
    );
  }

  // ── 하단 입력창 ──
  Widget _buildInputBar(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;

    // 키보드가 떠 있으면 그 높이를, 아니면 BottomNav + 시스템 인셋을 확보.
    final keyboardInset = MediaQuery.viewInsetsOf(context).bottom;
    final bottomInset = keyboardInset > 0
        ? keyboardInset + AppDimens.md
        : ResponsiveUtils.tabBottomPadding(context);

    return Padding(
      padding: EdgeInsets.fromLTRB(
        AppDimens.lg,
        AppDimens.sm,
        AppDimens.lg,
        bottomInset,
      ),
      child: Container(
        padding: const EdgeInsets.only(left: AppDimens.lg, right: AppDimens.xs),
        decoration: BoxDecoration(
          color: AppColors.background,
          borderRadius: BorderRadius.circular(AppDimens.radiusFull),
          border: Border.all(color: AppColors.divider),
        ),
        child: Row(
          children: [
            // TextField: 남는 폭 모두 차지 (버튼과 밀리지 않게 Expanded)
            Expanded(
              child: TextField(
                controller: _controller,
                textInputAction: TextInputAction.send,
                onSubmitted: (_) => _send(),
                style: textTheme.bodyLarge,
                decoration: const InputDecoration(
                  hintText: 'AI 비서에게 물어보기',
                  border: InputBorder.none,
                  isCollapsed: true,
                ),
              ),
            ),
            // 마이크 + 전송: 고정 크기 묶음
            IconButton(
              icon: const Icon(Icons.mic_none_rounded,
                  color: AppColors.textSecondary),
              onPressed: () {},
              constraints: const BoxConstraints(),
              padding: const EdgeInsets.all(AppDimens.sm),
            ),
            const SizedBox(width: AppDimens.xs),
            Container(
              decoration: const BoxDecoration(
                color: AppColors.primary,
                shape: BoxShape.circle,
              ),
              child: IconButton(
                icon: const Icon(Icons.send, color: Colors.white, size: 20),
                onPressed: () => _send(),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────
//  AI Orb (이미지 없이 gradient + glow, 크기 비례)
// ─────────────────────────────────────────────────────────────

class _AiOrb extends StatelessWidget {
  const _AiOrb({required this.size});
  final double size;

  @override
  Widget build(BuildContext context) {
    // 내부 요소들을 orb 크기에 비례 계산
    final coreSize = size * 0.75;
    final blob1 = size * 0.4;
    final blob2 = size * 0.3;
    final highlight = size * 0.2;

    return SizedBox(
      width: size,
      height: size,
      child: Stack(
        alignment: Alignment.center,
        children: [
          // 바깥 glow
          Container(
            width: size,
            height: size,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: RadialGradient(
                colors: [
                  AppColors.primary.withValues(alpha: 0.25),
                  AppColors.primary.withValues(alpha: 0.0),
                ],
              ),
            ),
          ),
          // 메인 구체
          Container(
            width: coreSize,
            height: coreSize,
            decoration: const BoxDecoration(
              shape: BoxShape.circle,
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [
                  Color(0xFF7C3AED), // purple
                  Color(0xFF2563FF), // blue
                  Color(0xFF22D3EE), // cyan
                ],
              ),
            ),
          ),
          // 반투명 겹침 원 1 (좌상단)
          Positioned(
            left: size * 0.2,
            top: size * 0.18,
            child: Container(
              width: blob1,
              height: blob1,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: Colors.white.withValues(alpha: 0.25),
              ),
            ),
          ),
          // 반투명 겹침 원 2 (우하단)
          Positioned(
            right: size * 0.22,
            bottom: size * 0.2,
            child: Container(
              width: blob2,
              height: blob2,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: const Color(0xFF22D3EE).withValues(alpha: 0.4),
              ),
            ),
          ),
          // 중앙 하이라이트
          Container(
            width: highlight,
            height: highlight,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: RadialGradient(
                colors: [
                  Colors.white.withValues(alpha: 0.9),
                  Colors.white.withValues(alpha: 0.0),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────
//  내부 위젯
// ─────────────────────────────────────────────────────────────

/// 빠른 실행 pill 버튼
class _QuickPill extends StatelessWidget {
  const _QuickPill({
    required this.icon,
    required this.label,
    required this.onTap,
  });
  final IconData icon;
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(AppDimens.radiusFull),
      child: Container(
        padding: const EdgeInsets.symmetric(
          horizontal: AppDimens.md,
          vertical: AppDimens.sm + 2,
        ),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(AppDimens.radiusFull),
          border: Border.all(color: AppColors.primary.withValues(alpha: 0.4)),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 18, color: AppColors.primary),
            const SizedBox(width: AppDimens.sm),
            // Wrap 안의 pill 이라 텍스트는 내용 크기 유지 (줄바꿈은 Wrap 이 처리)
            Text(
              label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w600,
                color: AppColors.textPrimary,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// 채팅 말풍선
class _MessageBubble extends StatelessWidget {
  const _MessageBubble({required this.message});
  final _ChatMessage message;

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    final isUser = message.isUser;
    final maxBubbleWidth = MediaQuery.sizeOf(context).width * 0.78;

    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(bottom: AppDimens.md),
        padding: const EdgeInsets.symmetric(
          horizontal: AppDimens.md,
          vertical: AppDimens.sm + 2,
        ),
        constraints: BoxConstraints(maxWidth: maxBubbleWidth),
        decoration: BoxDecoration(
          color: isUser ? AppColors.primary : AppColors.background,
          borderRadius: BorderRadius.only(
            topLeft: const Radius.circular(AppDimens.radiusMd),
            topRight: const Radius.circular(AppDimens.radiusMd),
            bottomLeft: Radius.circular(isUser ? AppDimens.radiusMd : 4),
            bottomRight: Radius.circular(isUser ? 4 : AppDimens.radiusMd),
          ),
        ),
        child: Text(
          message.text,
          // 줄바꿈 자연 처리, 길이 제한 없음(말풍선 폭 안에서 여러 줄)
          style: textTheme.bodyLarge?.copyWith(
            color: isUser ? Colors.white : AppColors.textPrimary,
            height: 1.4,
          ),
        ),
      ),
    );
  }
}