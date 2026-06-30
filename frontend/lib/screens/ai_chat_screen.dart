import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

class AiChatScreen extends StatefulWidget {
  const AiChatScreen({super.key});

  @override
  State<AiChatScreen> createState() => _AiChatScreenState();
}

class _AiChatScreenState extends State<AiChatScreen> {
  final TextEditingController _inputController = TextEditingController();
  bool _isListening = false;

  @override
  void dispose() {
    _inputController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: AppTheme.screenBackground,
      child: SafeArea(
        child: Column(
          children: [
            _buildHeader(),
            Expanded(child: _buildConversation()),
            _buildSuggestionChips(),
            _buildSiriArea(),
            _buildInputBar(),
          ],
        ),
      ),
    );
  }

  // ─── 헤더 ───────────────────────────────
  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 0),
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
        ],
      ),
    );
  }

  // ─── 대화 영역 ──────────────────────────
  Widget _buildConversation() {
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
      physics: const BouncingScrollPhysics(),
      children: [
        // 사용자 메시지
        _userBubble('내일 오후 2시에 병원 예약 잡아줘'),
        const SizedBox(height: 12),

        // AI 텍스트 응답
        _aiBubble('내일 오후 2시 병원 예약으로 인식했어요. 캘린더에 추가할까요?'),
        const SizedBox(height: 8),

        // AI 카드 응답 (말풍선 스타일로 AI 응답 아래에)
        _aiCardBubble(),
      ],
    );
  }

  Widget _userBubble(String text) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.end,
      children: [
        Flexible(
          child: Container(
            constraints: BoxConstraints(
              maxWidth: MediaQuery.of(context).size.width * 0.72,
            ),
            padding:
                const EdgeInsets.symmetric(horizontal: 16, vertical: 11),
            decoration: BoxDecoration(
              color: AppTheme.blue,
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(18),
                topRight: Radius.circular(18),
                bottomLeft: Radius.circular(18),
                bottomRight: Radius.circular(4),
              ),
              boxShadow: [
                BoxShadow(
                  color: AppTheme.blue.withOpacity(0.25),
                  blurRadius: 10,
                  offset: const Offset(0, 3),
                ),
              ],
            ),
            child: Text(text,
                style: const TextStyle(
                    fontSize: 14, color: Colors.white, height: 1.4)),
          ),
        ),
      ],
    );
  }

  Widget _aiBubble(String text) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        // AI 아바타
        Container(
          width: 30,
          height: 30,
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              colors: [AppTheme.purple, AppTheme.blue],
            ),
            borderRadius: BorderRadius.circular(9),
          ),
          child:
              const Icon(Icons.auto_awesome, color: Colors.white, size: 15),
        ),
        const SizedBox(width: 8),
        Flexible(
          child: Container(
            constraints: BoxConstraints(
              maxWidth: MediaQuery.of(context).size.width * 0.72,
            ),
            padding:
                const EdgeInsets.symmetric(horizontal: 16, vertical: 11),
            decoration: BoxDecoration(
              color: Colors.white.withOpacity(0.88),
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(4),
                topRight: Radius.circular(18),
                bottomLeft: Radius.circular(18),
                bottomRight: Radius.circular(18),
              ),
              border:
                  Border.all(color: AppTheme.separator.withOpacity(0.5)),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withOpacity(0.05),
                  blurRadius: 8,
                  offset: const Offset(0, 2),
                ),
              ],
            ),
            child: Text(text,
                style: const TextStyle(
                    fontSize: 14,
                    color: AppTheme.textPrimary,
                    height: 1.4)),
          ),
        ),
      ],
    );
  }

  // 카드형 AI 응답 (말풍선 안에 담긴 예약 정보 카드)
  Widget _aiCardBubble() {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SizedBox(width: 38), // AI 아바타 자리 맞춤
        Flexible(
          child: Container(
            constraints: BoxConstraints(
              maxWidth: MediaQuery.of(context).size.width * 0.82,
            ),
            decoration: BoxDecoration(
              color: Colors.white.withOpacity(0.92),
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(4),
                topRight: Radius.circular(18),
                bottomLeft: Radius.circular(18),
                bottomRight: Radius.circular(18),
              ),
              border: Border.all(
                  color: AppTheme.separator.withOpacity(0.5)),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withOpacity(0.05),
                  blurRadius: 8,
                  offset: const Offset(0, 2),
                ),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // 카드 상단
                Container(
                  padding: const EdgeInsets.fromLTRB(14, 12, 14, 10),
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      colors: [
                        AppTheme.teal.withOpacity(0.12),
                        AppTheme.blue.withOpacity(0.06),
                      ],
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    ),
                    borderRadius: const BorderRadius.only(
                      topLeft: Radius.circular(4),
                      topRight: Radius.circular(18),
                    ),
                  ),
                  child: Row(
                    children: [
                      Container(
                        width: 32,
                        height: 32,
                        decoration: BoxDecoration(
                          color: AppTheme.teal.withOpacity(0.18),
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: const Icon(Icons.local_hospital_outlined,
                            color: AppTheme.teal, size: 18),
                      ),
                      const SizedBox(width: 10),
                      const Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('병원 예약',
                              style: TextStyle(
                                fontSize: 14,
                                fontWeight: FontWeight.w700,
                                color: AppTheme.textPrimary,
                              )),
                          Text('카테고리 · 병원',
                              style: TextStyle(
                                  fontSize: 11,
                                  color: AppTheme.textSecondary)),
                        ],
                      ),
                    ],
                  ),
                ),
                // 카드 내용
                Padding(
                  padding: const EdgeInsets.fromLTRB(14, 10, 14, 0),
                  child: Column(
                    children: [
                      _infoRow(Icons.calendar_today_outlined, '날짜',
                          '6월 30일 (월)'),
                      const SizedBox(height: 7),
                      _infoRow(Icons.access_time_outlined, '시간',
                          '오후 2:00 – 3:00'),
                      const SizedBox(height: 7),
                      _infoRow(Icons.notifications_outlined, '알림',
                          '30분 전'),
                    ],
                  ),
                ),
                // 버튼
                Padding(
                  padding: const EdgeInsets.all(12),
                  child: Row(
                    children: [
                      Expanded(
                        child: GestureDetector(
                          onTap: () {},
                          child: Container(
                            padding:
                                const EdgeInsets.symmetric(vertical: 10),
                            decoration: BoxDecoration(
                              color: AppTheme.blue,
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: const Text('저장하기',
                                textAlign: TextAlign.center,
                                style: TextStyle(
                                    fontSize: 13,
                                    fontWeight: FontWeight.w700,
                                    color: Colors.white)),
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: GestureDetector(
                          onTap: () {},
                          child: Container(
                            padding:
                                const EdgeInsets.symmetric(vertical: 10),
                            decoration: BoxDecoration(
                              color: AppTheme.separator,
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: const Text('수정하기',
                                textAlign: TextAlign.center,
                                style: TextStyle(
                                    fontSize: 13,
                                    fontWeight: FontWeight.w700,
                                    color: AppTheme.textPrimary)),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _infoRow(IconData icon, String label, String value) {
    return Row(
      children: [
        Icon(icon, size: 14, color: AppTheme.textSecondary),
        const SizedBox(width: 6),
        SizedBox(
          width: 36,
          child: Text(label,
              style: const TextStyle(
                  fontSize: 12, color: AppTheme.textSecondary)),
        ),
        Text(value,
            style: const TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w600,
              color: AppTheme.textPrimary,
            )),
      ],
    );
  }

  // ─── 제안 칩 ────────────────────────────
  Widget _buildSuggestionChips() {
    final chips = ['준비물 알려줘', '출발 시간은?', '취소하기'];
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: Row(
          children: chips.map((c) {
            return Padding(
              padding: const EdgeInsets.only(right: 8),
              child: GestureDetector(
                onTap: () {},
                child: Container(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 14, vertical: 8),
                  decoration: BoxDecoration(
                    color: Colors.white.withOpacity(0.7),
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(color: AppTheme.separator),
                  ),
                  child: Text(c,
                      style: const TextStyle(
                          fontSize: 13, color: AppTheme.textPrimary)),
                ),
              ),
            );
          }).toList(),
        ),
      ),
    );
  }

  // ─── Siri 오브 영역 ─────────────────────
  Widget _buildSiriArea() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(0, 16, 0, 4),
      child: Center(
        child: _SiriOrb(isListening: _isListening),
      ),
    );
  }

  // ─── 입력 바 ─────────────────────────────
  Widget _buildInputBar() {
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
                  GestureDetector(
                    onTap: () =>
                        setState(() => _isListening = !_isListening),
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
                      child: Icon(Icons.graphic_eq,
                          color: _isListening
                              ? Colors.white
                              : AppTheme.blue,
                          size: 18),
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(width: 10),
          GestureDetector(
            onTap: () {},
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

// ─────────────────────────────────────────
//  iOS 26 스타일 AI 오브 (오로라 + 반투명 유리)
// ─────────────────────────────────────────
class _SiriOrb extends StatefulWidget {
  final bool isListening;
  const _SiriOrb({required this.isListening});

  @override
  State<_SiriOrb> createState() => _SiriOrbState();
}

class _SiriOrbState extends State<_SiriOrb> with TickerProviderStateMixin {
  late AnimationController _pulse;
  late AnimationController _rotate;
  late Animation<double> _scaleAnim;
  late Animation<double> _opacityAnim;

  @override
  void initState() {
    super.initState();
    _pulse = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 2200),
    )..repeat(reverse: true);
    _rotate = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 8),
    )..repeat();
    _scaleAnim = Tween<double>(begin: 0.95, end: 1.05).animate(
      CurvedAnimation(parent: _pulse, curve: Curves.easeInOut),
    );
    _opacityAnim = Tween<double>(begin: 0.55, end: 0.85).animate(
      CurvedAnimation(parent: _pulse, curve: Curves.easeInOut),
    );
  }

  @override
  void dispose() {
    _pulse.dispose();
    _rotate.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: Listenable.merge([_pulse, _rotate]),
      builder: (_, __) {
        final isActive = widget.isListening;
        final scale = isActive ? _scaleAnim.value : 1.0;
        const orbSize = 110.0;
        const glassSize = 72.0;

        return Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Transform.scale(
              scale: scale,
              child: SizedBox(
                width: orbSize,
                height: orbSize,
                child: Stack(
                  alignment: Alignment.center,
                  children: [
                    // 오로라 배경 (펴져나가는 그라데이션)
                    CustomPaint(
                      size: const Size(orbSize, orbSize),
                      painter: _AuroraPainter(
                        rotation: _rotate.value,
                        intensity: isActive ? _opacityAnim.value : 0.4,
                      ),
                    ),

                    // 반투명 유리 구체 (iOS 26 liquid glass)
                    Container(
                      width: glassSize,
                      height: glassSize,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        gradient: RadialGradient(
                          center: const Alignment(-0.3, -0.4),
                          radius: 1.0,
                          colors: [
                            Colors.white.withOpacity(0.75),
                            Colors.white.withOpacity(0.35),
                            AppTheme.blue.withOpacity(0.12),
                          ],
                          stops: const [0.0, 0.5, 1.0],
                        ),
                        border: Border.all(
                          color: Colors.white.withOpacity(0.6),
                          width: 1.5,
                        ),
                        boxShadow: [
                          BoxShadow(
                            color: AppTheme.blue.withOpacity(
                                isActive ? 0.3 : 0.15),
                            blurRadius: isActive ? 24 : 14,
                            spreadRadius: isActive ? 4 : 0,
                          ),
                          BoxShadow(
                            color: AppTheme.purple.withOpacity(0.1),
                            blurRadius: 20,
                            offset: const Offset(0, 4),
                          ),
                        ],
                      ),
                      child: Center(
                        child: Icon(
                          Icons.auto_awesome,
                          color: AppTheme.blue.withOpacity(0.65),
                          size: 26,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        );
      },
    );
  }
}

// ─────────────────────────────────────────
//  오로라 배경 페인터 (iOS 26 gradient rays)
// ─────────────────────────────────────────
class _AuroraPainter extends CustomPainter {
  final double rotation; // 0.0–1.0
  final double intensity;

  const _AuroraPainter({required this.rotation, required this.intensity});

  @override
  void paint(Canvas canvas, Size size) {
    final c = Offset(size.width / 2, size.height / 2);
    final maxR = size.width / 2;

    // 세 가지 색상 블롭이 회전하며 펴져나감
    final blobs = [
      (AppTheme.blue, 0.0),
      (AppTheme.purple, 2 * math.pi / 3),
      (AppTheme.teal, 4 * math.pi / 3),
    ];

    for (final (color, baseAngle) in blobs) {
      final angle = baseAngle + rotation * 2 * math.pi;
      final blobX = c.dx + maxR * 0.28 * math.cos(angle);
      final blobY = c.dy + maxR * 0.28 * math.sin(angle);
      final blobCenter = Offset(blobX, blobY);

      final paint = Paint()
        ..shader = RadialGradient(
          colors: [
            color.withOpacity(intensity * 0.55),
            color.withOpacity(intensity * 0.18),
            color.withOpacity(0.0),
          ],
          stops: const [0.0, 0.5, 1.0],
        ).createShader(
            Rect.fromCircle(center: blobCenter, radius: maxR * 0.85));

      canvas.drawCircle(blobCenter, maxR * 0.85, paint);
    }

    // 중심 소프트 화이트 글로우
    canvas.drawCircle(
        c,
        maxR * 0.45,
        Paint()
          ..shader = RadialGradient(
            colors: [
              Colors.white.withOpacity(0.18),
              Colors.white.withOpacity(0.0),
            ],
          ).createShader(Rect.fromCircle(center: c, radius: maxR * 0.45)));
  }

  @override
  bool shouldRepaint(covariant _AuroraPainter old) =>
      old.rotation != rotation || old.intensity != intensity;
}
