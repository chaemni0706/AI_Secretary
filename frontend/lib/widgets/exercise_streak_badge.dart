import 'package:flutter/material.dart';

/// 운동 인증 성공 시 보여주는 연속 달성(스트릭) 배지.
///
/// 동그라미 7개가 왼쪽부터 순차적으로 그린으로 채워지는 애니메이션(시연 하이라이트).
/// [streak] 이 7을 넘으면 7개 모두 채우고 텍스트로 "N일 연속"을 보여준다.
class ExerciseStreakBadge extends StatefulWidget {
  final int streak;

  const ExerciseStreakBadge({super.key, required this.streak});

  @override
  State<ExerciseStreakBadge> createState() => _ExerciseStreakBadgeState();
}

class _ExerciseStreakBadgeState extends State<ExerciseStreakBadge>
    with SingleTickerProviderStateMixin {
  static const _slots = 7;
  static const _green = Color(0xFF2E7D32);

  late final AnimationController _controller;

  int get _filled => widget.streak.clamp(0, _slots);

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      // 채워질 개수에 비례한 총 길이(개당 ~0.18초, 톡톡톡 느낌).
      duration: Duration(milliseconds: 300 + 180 * (_filled == 0 ? 1 : _filled)),
    )..forward();
  }

  @override
  void didUpdateWidget(covariant ExerciseStreakBadge oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.streak != widget.streak) {
      _controller
        ..duration = Duration(milliseconds: 300 + 180 * (_filled == 0 ? 1 : _filled))
        ..forward(from: 0);
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  /// i번째 동그라미의 채움 진행도(0~1). 왼쪽부터 순차 시작.
  Animation<double> _circleAnim(int i) {
    if (i >= _filled) return const AlwaysStoppedAnimation(0);
    final start = i / _slots;
    final end = ((i + 1) / _slots).clamp(0.0, 1.0);
    return CurvedAnimation(
      parent: _controller,
      curve: Interval(start, end, curve: Curves.easeOutBack),
    );
  }

  @override
  Widget build(BuildContext context) {
    final encouragement = widget.streak >= 7
        ? '정말 잘하고 있어요'
        : (widget.streak >= 3 ? '좋은 흐름이에요' : '내일도 이어가 봐요');
    return Card(
      color: const Color(0xFFF0F7F0),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Text('🔥', style: TextStyle(fontSize: 18)),
                const SizedBox(width: 8),
                Text(
                  '${widget.streak}일 연속 운동',
                  style: const TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w700,
                    color: _green,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            AnimatedBuilder(
              animation: _controller,
              builder: (context, _) => Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  for (var i = 0; i < _slots; i++) _circle(i),
                ],
              ),
            ),
            const SizedBox(height: 10),
            Text(
              '${widget.streak}일 연속 · $encouragement',
              style: const TextStyle(fontSize: 13, color: Color(0xFF4E6B4E)),
            ),
          ],
        ),
      ),
    );
  }

  Widget _circle(int i) {
    final t = _circleAnim(i).value.clamp(0.0, 1.0);
    final filled = t > 0;
    return Transform.scale(
      // easeOutBack 으로 살짝 통통 튀는 팝 효과.
      scale: filled ? 0.8 + 0.2 * t : 1.0,
      child: Container(
        width: 34,
        height: 34,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: Color.lerp(Colors.transparent, _green, t),
          border: Border.all(
            color: filled ? _green : const Color(0xFFBFD4BF),
            width: 2,
          ),
        ),
        child: filled && t > 0.6
            ? const Icon(Icons.check_rounded, size: 18, color: Colors.white)
            : null,
      ),
    );
  }
}
