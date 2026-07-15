import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/services/streak_store.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  final store = StreakStore.instance;
  final today = DateTime(2026, 7, 13);

  String fmt(DateTime d) =>
      '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

  group('currentStreakFrom (순수 계산)', () {
    test('기록 없음 → 0', () {
      expect(store.currentStreakFrom({}, today), 0);
    });

    test('오늘만 성공 → 1', () {
      expect(store.currentStreakFrom({fmt(today)}, today), 1);
    });

    test('7일 연속 → 7', () {
      final dates = {
        for (var i = 0; i < 7; i++) fmt(today.subtract(Duration(days: i))),
      };
      expect(store.currentStreakFrom(dates, today), 7);
    });

    test('중간 하루 빠지면 그 앞에서 끊김', () {
      // 오늘, 어제, (그제 없음), 3일 전 → 2
      final dates = {
        fmt(today),
        fmt(today.subtract(const Duration(days: 1))),
        fmt(today.subtract(const Duration(days: 3))),
      };
      expect(store.currentStreakFrom(dates, today), 2);
    });

    test('오늘 기록이 없으면 0 (어제까지 연속이어도)', () {
      final dates = {
        fmt(today.subtract(const Duration(days: 1))),
        fmt(today.subtract(const Duration(days: 2))),
      };
      expect(store.currentStreakFrom(dates, today), 0);
    });
  });

  group('recordSuccess / seedDemo (SharedPreferences 연동)', () {
    setUp(() {
      SharedPreferences.setMockInitialValues({});
    });

    test('같은 날 중복 인증은 한 번만 센다', () async {
      final s1 = await store.recordSuccess('exercise', when: today);
      final s2 = await store.recordSuccess('exercise', when: today);
      expect(s1, 1);
      expect(s2, 1);
    });

    test('seedDemo(6) 후 오늘 성공 → 7일 연속', () async {
      // seedDemo 는 DateTime.now() 기준이므로 now 기준으로 검증한다.
      await store.seedDemo('exercise', 6);
      final streak = await store.recordSuccess('exercise');
      expect(streak, 7);
    });
  });
}
