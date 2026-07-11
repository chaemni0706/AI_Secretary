import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/models/schedule_model.dart';

/// ScheduleModel.fromJson 단위 테스트.
/// 실행: `flutter test test/schedule_model_test.dart`
///
/// 하루 종일(is_all_day) 파싱, id 문자열 보존, priority 기본값, memo 기반
/// 종료일(end_date) 추출 등 화면/캘린더 렌더가 의존하는 계약을 고정한다.
void main() {
  group('ScheduleModel.fromJson', () {
    test('is_all_day 를 파싱하고 없으면 false', () {
      final allDay = ScheduleModel.fromJson({
        'id': 'a1',
        'title': '워크숍',
        'date': '2026-07-12',
        'is_all_day': true,
      });
      expect(allDay.isAllDay, isTrue);

      final timed = ScheduleModel.fromJson({
        'id': 'a2',
        'title': '치과',
        'date': '2026-07-12',
        'start_time': '14:00',
      });
      expect(timed.isAllDay, isFalse);
      expect(timed.startTime, '14:00');
    });

    test('id 는 어떤 타입이 와도 문자열로 보존, priority 기본값은 medium', () {
      final m = ScheduleModel.fromJson({'id': 123, 'title': 'x'});
      expect(m.id, '123');
      expect(m.priority, 'medium');
      expect(m.status, 'scheduled');
    });

    test('effectiveEndDate 는 memo 의 end_date 토큰에서 읽고 isMultiDay 판정', () {
      final m = ScheduleModel.fromJson({
        'id': '1',
        'title': '휴가',
        'date': '2026-07-10',
        'memo': '가족 여행\nend_date: 2026-07-12',
      });
      expect(m.effectiveEndDate, '2026-07-12');
      expect(m.isMultiDay, isTrue);
    });

    test('종료일이 없으면 단일 일정(isMultiDay=false)', () {
      final m = ScheduleModel.fromJson({
        'id': '2',
        'title': '회의',
        'date': '2026-07-10',
      });
      expect(m.effectiveEndDate, isNull);
      expect(m.isMultiDay, isFalse);
    });
  });
}
