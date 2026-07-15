import 'package:shared_preferences/shared_preferences.dart';

/// 인증(운동 등) 연속 달성(스트릭) 로컬 저장소.
///
/// 성공한 인증 날짜(yyyy-MM-dd)를 task 별로 [SharedPreferences] 에 보관하고,
/// "오늘까지 며칠 연속인지"를 계산한다. 백엔드에 인증 이력 테이블이 없는
/// 현재 구조에서 기기 로컬로 동작하는 최소 구현이다(서버 이관 시 이 파일만 교체).
class StreakStore {
  StreakStore._();
  static final StreakStore instance = StreakStore._();

  static const _keyPrefix = 'verification_success_dates_';

  String _key(String task) => '$_keyPrefix$task';

  String _fmt(DateTime d) =>
      '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

  /// 오늘 성공을 기록하고, 오늘까지의 연속 일수를 반환한다.
  /// 같은 날 중복 인증은 한 번만 센다.
  Future<int> recordSuccess(String task, {DateTime? when}) async {
    final prefs = await SharedPreferences.getInstance();
    final dates = (prefs.getStringList(_key(task)) ?? <String>[]).toSet();
    dates.add(_fmt(when ?? DateTime.now()));
    // 오래된 기록은 최근 60일만 유지(무한 증가 방지).
    final cutoff = DateTime.now().subtract(const Duration(days: 60));
    final kept = dates.where((s) {
      final d = DateTime.tryParse(s);
      return d != null && !d.isBefore(cutoff);
    }).toList()
      ..sort();
    await prefs.setStringList(_key(task), kept);
    return currentStreakFrom(kept.toSet(), when ?? DateTime.now());
  }

  /// 저장된 기록 기준, [today] 까지의 연속 일수.
  Future<int> currentStreak(String task, {DateTime? today}) async {
    final prefs = await SharedPreferences.getInstance();
    final dates = (prefs.getStringList(_key(task)) ?? <String>[]).toSet();
    return currentStreakFrom(dates, today ?? DateTime.now());
  }

  /// [dates](yyyy-MM-dd 집합)에서 [today] 부터 거꾸로 세는 연속 일수.
  int currentStreakFrom(Set<String> dates, DateTime today) {
    var streak = 0;
    var cursor = DateTime(today.year, today.month, today.day);
    while (dates.contains(_fmt(cursor))) {
      streak += 1;
      cursor = cursor.subtract(const Duration(days: 1));
    }
    return streak;
  }

  /// 시연용: 오늘 이전 [days]일을 성공 처리해 스트릭을 만들어 둔다.
  /// (예: days=6 → 오늘 인증 성공 시 7일 연속)
  Future<void> seedDemo(String task, int days) async {
    final prefs = await SharedPreferences.getInstance();
    final dates = (prefs.getStringList(_key(task)) ?? <String>[]).toSet();
    final today = DateTime.now();
    for (var i = 1; i <= days; i++) {
      dates.add(_fmt(today.subtract(Duration(days: i))));
    }
    final list = dates.toList()..sort();
    await prefs.setStringList(_key(task), list);
  }

  /// 시연/테스트용: 해당 task 기록 초기화.
  Future<void> reset(String task) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_key(task));
  }
}

final streakStore = StreakStore.instance;
