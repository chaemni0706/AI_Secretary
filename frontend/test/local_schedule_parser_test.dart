import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/services/local_schedule_parser.dart';
import 'package:frontend/services/schedule_api.dart';

/// LocalScheduleParser 단위 테스트.
///
/// 기준일(now)을 2026-07-06(월요일)로 고정해 요일/상대날짜 계산을 결정적으로 만든다.
/// 실행: `flutter test test/local_schedule_parser_test.dart`
void main() {
  final base = DateTime(2026, 7, 6); // Monday

  ParseResult run(String s) => LocalScheduleParser.parse(s, now: base);

  String? draft(ParseResult r, String k) => r.scheduleDraft[k] as String?;

  group('LocalScheduleParser - source/기본', () {
    test('source 는 on_device_rule', () {
      expect(run('오늘 6시 운동').source, 'on_device_rule');
    });
  });

  group('LocalScheduleParser - 날짜/시간/카테고리/제목', () {
    test('오늘 6시 운동', () {
      final r = run('오늘 6시 운동');
      expect(r.intent, 'create_schedule');
      expect(draft(r, 'title'), '운동');
      expect(draft(r, 'date'), '2026-07-06');
      expect(draft(r, 'start_time'), '06:00');
      expect(draft(r, 'category'), 'exercise');
      expect(r.missingFields, isEmpty);
    });

    test('내일 오후 2시 병원', () {
      final r = run('내일 오후 2시 병원');
      expect(draft(r, 'title'), '병원');
      expect(draft(r, 'date'), '2026-07-07');
      expect(draft(r, 'start_time'), '14:00');
      expect(draft(r, 'category'), 'hospital');
      expect(r.missingFields, isEmpty);
    });

    test('금요일까지 과제 제출 → 할 일', () {
      final r = run('금요일까지 과제 제출');
      expect(r.intent, 'create_todo');
      expect(draft(r, 'title'), '과제 제출');
      expect(draft(r, 'date'), '2026-07-10');
      expect(draft(r, 'category'), 'study');
    });

    test('다음주 월요일 10시 회의', () {
      final r = run('다음주 월요일 10시 회의');
      expect(draft(r, 'title'), '회의');
      expect(draft(r, 'date'), '2026-07-13');
      expect(draft(r, 'start_time'), '10:00');
      expect(draft(r, 'category'), 'meeting');
    });

    test('저녁 7시에 약속 (조사 제거, 날짜 누락)', () {
      final r = run('저녁 7시에 약속');
      expect(draft(r, 'title'), '약속');
      expect(draft(r, 'start_time'), '19:00');
      expect(draft(r, 'category'), 'personal');
      expect(draft(r, 'date'), isNull);
      expect(r.missingFields, contains('date'));
    });

    test('내일 병원 예약 (시간 누락)', () {
      final r = run('내일 병원 예약');
      expect(draft(r, 'title'), '병원 예약');
      expect(draft(r, 'date'), '2026-07-07');
      expect(draft(r, 'start_time'), isNull);
      expect(draft(r, 'category'), 'hospital');
      expect(r.missingFields, contains('time'));
    });

    test('이번주 금요일 3시 미팅', () {
      final r = run('이번주 금요일 3시 미팅');
      expect(draft(r, 'title'), '미팅');
      expect(draft(r, 'date'), '2026-07-10');
      expect(draft(r, 'start_time'), '03:00'); // 오전/오후 없으면 그대로(MVP 한계)
      expect(draft(r, 'category'), 'meeting');
    });

    test('2026-07-10 14:00 치과 (ISO)', () {
      final r = run('2026-07-10 14:00 치과');
      expect(draft(r, 'title'), '치과');
      expect(draft(r, 'date'), '2026-07-10');
      expect(draft(r, 'start_time'), '14:00');
      expect(draft(r, 'category'), 'hospital');
    });

    test('7/10 미용실 (M/D, 시간 누락)', () {
      final r = run('7/10 미용실');
      expect(draft(r, 'title'), '미용실');
      expect(draft(r, 'date'), '2026-07-10');
      expect(draft(r, 'category'), 'beauty');
      expect(r.missingFields, contains('time'));
    });

    test('모레 오전 9시 시험 공부 → 할 일', () {
      final r = run('모레 오전 9시 시험 공부');
      expect(r.intent, 'create_todo');
      expect(draft(r, 'title'), '시험 공부');
      expect(draft(r, 'date'), '2026-07-08');
      expect(draft(r, 'start_time'), '09:00');
      expect(draft(r, 'category'), 'study');
    });

    test('다음주 화요일 헬스 (시간 누락)', () {
      final r = run('다음주 화요일 헬스');
      expect(draft(r, 'title'), '헬스');
      expect(draft(r, 'date'), '2026-07-14');
      expect(draft(r, 'category'), 'exercise');
      expect(r.missingFields, contains('time'));
    });

    test('점심 약속 (시간대→12:00, 날짜 누락)', () {
      final r = run('점심 약속');
      expect(draft(r, 'title'), '약속');
      expect(draft(r, 'start_time'), '12:00');
      expect(draft(r, 'category'), 'personal');
      expect(r.missingFields, contains('date'));
    });

    test('3시 회의 잡아줘 (명령형 제거, 날짜 누락)', () {
      final r = run('3시 회의 잡아줘');
      expect(draft(r, 'title'), '회의');
      expect(draft(r, 'start_time'), '03:00');
      expect(draft(r, 'category'), 'meeting');
      expect(r.missingFields, contains('date'));
    });

    test('밤 11시 마감 → 할 일', () {
      final r = run('밤 11시 마감');
      expect(r.intent, 'create_todo');
      expect(draft(r, 'title'), '마감');
      expect(draft(r, 'start_time'), '23:00');
    });

    test('오늘 미용실 예약 (시간 누락)', () {
      final r = run('오늘 미용실 예약');
      expect(draft(r, 'title'), '미용실 예약');
      expect(draft(r, 'date'), '2026-07-06');
      expect(draft(r, 'category'), 'beauty');
      expect(r.missingFields, contains('time'));
    });

    test('다음주 목요일 저녁 6시 식당', () {
      final r = run('다음주 목요일 저녁 6시 식당');
      expect(draft(r, 'title'), '식당');
      expect(draft(r, 'date'), '2026-07-16');
      expect(draft(r, 'start_time'), '18:00');
      expect(draft(r, 'category'), 'food');
    });

    test('빈 입력 → title/date 누락', () {
      final r = run('');
      expect(draft(r, 'title'), '');
      expect(r.missingFields, contains('title'));
      expect(r.missingFields, contains('date'));
    });
  });

  group('LocalScheduleParser - 안전성', () {
    test('예외 없이 항상 ParseResult 반환', () {
      expect(() => run('!!!@@@###'), returnsNormally);
      expect(run('!!!@@@###').source, 'on_device_rule');
    });
  });
}
