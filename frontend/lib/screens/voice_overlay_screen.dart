import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../models/voice_chat_message.dart';
import '../theme/app_theme.dart';

/// "포비" 음성 비서 Siri 스타일 오버레이.
///
/// 핫워드 서비스([hotwordService])가 백그라운드에서 트리거될 때 이 오버레이를
/// 띄우고, 진행 상황(인식한 말/응답/단계)을 [voiceOverlay] 컨트롤러로 밀어넣는다.
/// 화면 구성: 뒷화면이 비치는 어두운 반투명 배경 + 위에서부터 대화 말풍선
/// (AI 챗 화면과 같은 스타일) + 하단에 맥동하는 구체(떠다니는 AI 비서 버튼과
/// 같은 생김새).

/// 오버레이 진행 단계 — 구체 애니메이션과 상태 라벨이 이 값을 따라간다.
enum VoicePhase { idle, listening, thinking, speaking }

/// 오버레이 상태 컨트롤러(전역 싱글턴 [voiceOverlay]).
///
/// 서비스 코드(context 없음)에서 화면을 띄울 수 있도록
/// [rootNavigatorKey] 를 [attachNavigator] 로 주입받는다
/// (briefing_scheduler_service 와 동일한 패턴).
class VoiceOverlayController extends ChangeNotifier {
  GlobalKey<NavigatorState>? _navigatorKey;
  Route<void>? _route;

  final List<VoiceChatMessage> messages = [];
  VoicePhase phase = VoicePhase.idle;

  bool get isVisible => _route != null;

  void attachNavigator(GlobalKey<NavigatorState> key) => _navigatorKey = key;

  /// 오버레이를 띄운다(이미 떠 있으면 그대로 재사용해 대화를 이어간다).
  void show() {
    if (isVisible) return;
    final nav = _navigatorKey?.currentState;
    if (nav == null) return;

    messages.clear();
    phase = VoicePhase.idle;

    final route = PageRouteBuilder<void>(
      opaque: false,
      fullscreenDialog: true,
      transitionDuration: const Duration(milliseconds: 220),
      reverseTransitionDuration: const Duration(milliseconds: 180),
      pageBuilder: (_, _, _) => const VoiceOverlayScreen(),
      transitionsBuilder: (_, animation, _, child) =>
          FadeTransition(opacity: animation, child: child),
    );
    _route = route;
    nav.push(route).then((_) {
      _route = null;
      phase = VoicePhase.idle;
    });
    notifyListeners();
  }

  /// 오버레이를 닫는다(핫워드 흐름에서는 자동으로 닫지 않고 사용자가 닫는다).
  void dismiss() {
    final nav = _navigatorKey?.currentState;
    final route = _route;
    if (nav == null || route == null) return;
    if (route.isActive) nav.removeRoute(route);
    _route = null;
  }

  void addUser(String text) => _add(ChatRole.user, text);

  void addAssistant(String text) => _add(ChatRole.assistant, text);

  void _add(ChatRole role, String text) {
    final trimmed = text.trim();
    if (trimmed.isEmpty) return;
    messages.add(VoiceChatMessage(role: role, text: trimmed));
    notifyListeners();
  }

  void setPhase(VoicePhase next) {
    if (phase == next) return;
    phase = next;
    notifyListeners();
  }
}

/// 전역 인스턴스(기존 `*_service` 싱글턴 패턴과 동일).
final voiceOverlay = VoiceOverlayController();

class VoiceOverlayScreen extends StatefulWidget {
  const VoiceOverlayScreen({super.key});

  @override
  State<VoiceOverlayScreen> createState() => _VoiceOverlayScreenState();
}

class _VoiceOverlayScreenState extends State<VoiceOverlayScreen> {
  final _scrollController = ScrollController();

  @override
  void initState() {
    super.initState();
    voiceOverlay.addListener(_onChanged);
  }

  @override
  void dispose() {
    voiceOverlay.removeListener(_onChanged);
    _scrollController.dispose();
    super.dispose();
  }

  void _onChanged() {
    if (!mounted) return;
    setState(() {});
    // 새 말풍선이 추가되면 맨 아래로 스크롤(AI 챗 화면과 동일한 패턴).
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scrollController.hasClients) return;
      _scrollController.animateTo(
        _scrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 250),
        curve: Curves.easeOut,
      );
    });
  }

  String get _statusLabel {
    switch (voiceOverlay.phase) {
      case VoicePhase.listening:
        return '듣고 있어요…';
      case VoicePhase.thinking:
        return '생각하는 중…';
      case VoicePhase.speaking:
        return '말하는 중…';
      case VoicePhase.idle:
        return '"포비 브리핑" 이라고 불러보세요';
    }
  }

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: GestureDetector(
        // Siri 처럼 아무 곳이나 탭하면 닫힌다(스크롤 드래그는 그대로 동작).
        onTap: () => Navigator.of(context).pop(),
        behavior: HitTestBehavior.opaque,
        child: Container(
          color: Colors.black.withValues(alpha: 0.78),
          child: SafeArea(
            child: Column(
              children: [
                Align(
                  alignment: Alignment.centerRight,
                  child: IconButton(
                    onPressed: () => Navigator.of(context).pop(),
                    icon: Icon(
                      Icons.close,
                      color: Colors.white.withValues(alpha: 0.7),
                    ),
                    tooltip: '닫기',
                  ),
                ),
                Expanded(
                  child: ListView.builder(
                    controller: _scrollController,
                    physics: const BouncingScrollPhysics(),
                    padding: const EdgeInsets.fromLTRB(16, 4, 16, 16),
                    itemCount: voiceOverlay.messages.length,
                    itemBuilder: (context, index) =>
                        _OverlayChatBubble(message: voiceOverlay.messages[index]),
                  ),
                ),
                Padding(
                  padding: const EdgeInsets.only(bottom: 40),
                  child: Column(
                    children: [
                      Text(
                        _statusLabel,
                        style: TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w600,
                          color: Colors.white.withValues(alpha: 0.75),
                        ),
                      ),
                      const SizedBox(height: 18),
                      _SiriOrb(phase: voiceOverlay.phase),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// AI 챗 화면(_ChatBubble)과 같은 말풍선 스타일 — 사용자=오른쪽 파랑,
/// AI=왼쪽 흰색 + 보라→파랑 그라데이션 아바타. 어두운 배경 위에서도 동일하게
/// 잘 보이므로 색은 그대로 쓴다.
class _OverlayChatBubble extends StatelessWidget {
  final VoiceChatMessage message;

  const _OverlayChatBubble({required this.message});

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
                    : Colors.white.withValues(alpha: 0.9),
                borderRadius: BorderRadius.only(
                  topLeft: const Radius.circular(16),
                  topRight: const Radius.circular(16),
                  bottomLeft: Radius.circular(message.isUser ? 16 : 4),
                  bottomRight: Radius.circular(message.isUser ? 4 : 16),
                ),
                boxShadow: TossShadow.tiny,
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

/// Siri 스타일 반응 구체 — 떠다니는 AI 비서 버튼(_AssistantMainButton)과 같은
/// 아이덴티티(blue500 원 + auto_awesome + 글로우)를 키운 것.
/// 단계별로 숨쉬기/맥동/파문 애니메이션이 달라진다.
class _SiriOrb extends StatefulWidget {
  final VoicePhase phase;

  const _SiriOrb({required this.phase});

  @override
  State<_SiriOrb> createState() => _SiriOrbState();
}

class _SiriOrbState extends State<_SiriOrb>
    with SingleTickerProviderStateMixin {
  static const double _orbSize = 84;

  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(vsync: this, duration: _phaseDuration());
    _syncAnimation();
  }

  @override
  void didUpdateWidget(covariant _SiriOrb oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.phase != widget.phase) {
      _controller.duration = _phaseDuration();
      _syncAnimation();
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Duration _phaseDuration() {
    switch (widget.phase) {
      case VoicePhase.listening:
        return const Duration(milliseconds: 1600);
      case VoicePhase.speaking:
        return const Duration(milliseconds: 700);
      case VoicePhase.thinking:
        return const Duration(milliseconds: 2200);
      case VoicePhase.idle:
        return const Duration(milliseconds: 1600);
    }
  }

  void _syncAnimation() {
    if (widget.phase == VoicePhase.idle) {
      _controller.stop();
      _controller.value = 0;
    } else if (!_controller.isAnimating) {
      _controller.repeat();
    }
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, _) {
        final t = _controller.value;
        // 0→1→0 으로 부드럽게 오가는 맥동 값.
        final pulse = 0.5 - 0.5 * math.cos(2 * math.pi * t);

        double scale = 1.0;
        double orbOpacity = 1.0;
        double glowAlpha = 0.28;
        double glowBlur = 24;
        switch (widget.phase) {
          case VoicePhase.listening:
            scale = 1.0 + 0.10 * pulse;
            glowAlpha = 0.28 + 0.14 * pulse;
            glowBlur = 24 + 10 * pulse;
          case VoicePhase.speaking:
            scale = 1.0 + 0.06 * pulse;
            glowAlpha = 0.36 + 0.16 * pulse;
            glowBlur = 28 + 12 * pulse;
          case VoicePhase.thinking:
            orbOpacity = 0.72 + 0.28 * pulse;
          case VoicePhase.idle:
            break;
        }

        return SizedBox(
          width: _orbSize * 2.4,
          height: _orbSize * 2.4,
          child: Stack(
            alignment: Alignment.center,
            children: [
              if (widget.phase == VoicePhase.listening)
                CustomPaint(
                  size: const Size.square(_orbSize * 2.4),
                  painter: _RipplePainter(progress: t, color: AppTheme.blue),
                ),
              Transform.scale(
                scale: scale,
                child: Opacity(
                  opacity: orbOpacity,
                  child: Container(
                    width: _orbSize,
                    height: _orbSize,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: TossColors.blue500,
                      boxShadow: TossShadow.glow(
                        TossColors.blue500,
                        alpha: glowAlpha,
                        blur: glowBlur,
                      ),
                    ),
                    child: const Icon(
                      Icons.auto_awesome,
                      color: Colors.white,
                      size: 36,
                    ),
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

/// 듣는 중일 때 구체 밖으로 퍼져나가는 파문 링 2개.
class _RipplePainter extends CustomPainter {
  final double progress;
  final Color color;

  const _RipplePainter({required this.progress, required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    final center = size.center(Offset.zero);
    final baseRadius = _SiriOrbState._orbSize / 2;
    final maxSpread = size.width / 2 - baseRadius;

    // 반 주기 간격으로 어긋난 링 2개(항상 하나는 퍼지는 중).
    for (final phaseOffset in const [0.0, 0.5]) {
      final p = (progress + phaseOffset) % 1.0;
      final radius = baseRadius + maxSpread * p;
      final opacity = (1 - p) * 0.35;
      if (opacity <= 0.01) continue;
      canvas.drawCircle(
        center,
        radius,
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2
          ..color = color.withValues(alpha: opacity),
      );
    }
  }

  @override
  bool shouldRepaint(covariant _RipplePainter oldDelegate) =>
      oldDelegate.progress != progress || oldDelegate.color != color;
}
