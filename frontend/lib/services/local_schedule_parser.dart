import 'package:flutter/foundation.dart';

import 'schedule_api.dart';

/// 서버 `/ai/schedule/parse` 가 네트워크 오류로 실패했을 때 사용하는
/// 온디바이스 경량 일정 파서(오프라인 fallback).
///
/// 설계 원칙:
///  - 서버와 **동일한 형태의 [ParseResult]**(intent/schedule_draft/missing_fields/
///    tts_text)를 만들어, 화면·저장(ScheduleDraftMapper) 코드를 그대로 재사용한다.
///  - 정확도는 서버보다 낮다. 인식 못한 값은 missing_fields 로 알려 저장 게이팅에
///    맡긴다. 절대 예외를 던지지 않는다.
///  - 서버 스키마/키 이름을 그대로 따른다(title/category/date/start_time/...).
///
/// 지원 범위(간단 규칙):
///  - 날짜: 오늘/내일/모레/글피, 요일(다음 해당 요일), "M월 D일", "M/D".
///  - 시간: "오전/오후 N시(반)?(M분)?", "N시", 아침/점심/저녁(대략).
///  - 종류: 제출/과제/마감/장보기/작성/사기 → 할 일, 그 외 → 일정.
class LocalScheduleParser {
  /// [input] 자연어를 파싱해 서버와 같은 형태의 [ParseResult] 로 돌려준다.
  static ParseResult parse(
    String input, {
    String inputType = 'text',
    DateTime? now,
  }) {
    final base = now ?? DateTime.now();
    final text = input.trim();

    try {
      final isTodo = _isTodo(text);
      final date = _extractDate(text, base);
      final time = _extractStartTime(text);
      final category = _inferCategory(text);
      final title = _extractTitle(text);

      final draft = <String, dynamic>{
        'title': title,
        'category': category,
        'date': date,
        'start_time': time,
        'end_time': null,
        'location': null,
        'memo': null,
        'priority': 'medium',
        'source': inputType == 'voice' ? 'voice' : 'ai',
      };

      final missing = <String>[];
      if (title.isEmpty) missing.add('title');
      if (!isTodo && date == null) missing.add('date');
      if (!isTodo && time == null) missing.add('time');

      final kind = isTodo ? '할 일' : '일정';
      final tts = title.isEmpty
          ? '내용을 잘 이해하지 못했어요. 날짜와 할 일을 포함해 다시 말씀해 주세요.'
          : '오프라인이라 기기에서 "$title"($kind)로 임시 정리했어요. 확인 후 저장하세요.';

      return ParseResult(
        intent: isTodo ? 'create_todo' : 'create_schedule',
        confidence: 0.5,
        scheduleDraft: draft,
        missingFields: missing,
        ttsText: tts,
        source: 'on_device',
      );
    } catch (e) {
      debugPrint('LocalScheduleParser error: $e');
      // 어떤 경우에도 안전한 결과를 반환(앱 미크래시).
      return ParseResult(
        intent: 'unknown',
        confidence: 0.0,
        scheduleDraft: const {'title': '', 'priority': 'medium', 'source': 'ai'},
        missingFields: const ['title', 'date'],
        ttsText: '오프라인이라 일정을 이해하지 못했어요. 직접 입력해 주세요.',
        source: 'on_device',
      );
    }
  }

  // ------------------------------------------------------------------ //
  static const _todoSignals = ['제출', '과제', '마감', '장보기', '작성', '사기', '사와', '정리'];
  static const _todoOverride = ['예약', '회의', '약속', '병원', '진료', '수업', '미팅'];

  static bool _isTodo(String t) {
    final hasTodo = _todoSignals.any(t.contains);
    final hasOverride = _todoOverride.any(t.contains);
    return hasTodo && !hasOverride;
  }

  static const _weekdays = {
    '월': DateTime.monday,
    '화': DateTime.tuesday,
    '수': DateTime.wednesday,
    '목': DateTime.thursday,
    '금': DateTime.friday,
    '토': DateTime.saturday,
    '일': DateTime.sunday,
  };

  /// 날짜 추출 → "YYYY-MM-DD" 또는 null.
  static String? _extractDate(String t, DateTime base) {
    // 상대 표현.
    if (t.contains('모레') || t.contains('내일모레')) return _fmt(base.add(const Duration(days: 2)));
    if (t.contains('글피')) return _fmt(base.add(const Duration(days: 3)));
    if (t.contains('내일')) return _fmt(base.add(const Duration(days: 1)));
    if (t.contains('오늘')) return _fmt(base);

    // "M월 D일"
    final md = RegExp(r'(\d{1,2})\s*월\s*(\d{1,2})\s*일').firstMatch(t);
    if (md != null) {
      final m = int.parse(md.group(1)!);
      final d = int.parse(md.group(2)!);
      final year = (m < base.month) ? base.year + 1 : base.year;
      final dt = _safeDate(year, m, d);
      if (dt != null) return _fmt(dt);
    }

    // "M/D"
    final slash = RegExp(r'(?<!\d)(\d{1,2})\s*/\s*(\d{1,2})(?!\d)').firstMatch(t);
    if (slash != null) {
      final m = int.parse(slash.group(1)!);
      final d = int.parse(slash.group(2)!);
      final year = (m < base.month) ? base.year + 1 : base.year;
      final dt = _safeDate(year, m, d);
      if (dt != null) return _fmt(dt);
    }

    // 요일 → 다음 해당 요일(오늘 포함 안 함).
    for (final entry in _weekdays.entries) {
      if (t.contains('${entry.key}요일')) {
        var day = base;
        do {
          day = day.add(const Duration(days: 1));
        } while (day.weekday != entry.value);
        return _fmt(day);
      }
    }
    return null;
  }

  /// 시작 시간 추출 → "HH:mm" 또는 null.
  static String? _extractStartTime(String t) {
    final pm = t.contains('오후') || t.contains('저녁') || t.contains('밤');
    final am = t.contains('오전') || t.contains('아침');

    final hm = RegExp(r'(\d{1,2})\s*시(?:\s*(\d{1,2})\s*분)?').firstMatch(t);
    if (hm != null) {
      var h = int.parse(hm.group(1)!);
      final min = hm.group(2) != null ? int.parse(hm.group(2)!) : 0;
      if (t.contains('반') && hm.group(2) == null) {
        // "N시 반"
      }
      final half = (hm.group(2) == null && t.contains('반')) ? 30 : min;
      if (pm && h < 12) h += 12;
      if (am && h == 12) h = 0;
      if (h < 0 || h > 23) return null;
      return '${h.toString().padLeft(2, '0')}:${half.toString().padLeft(2, '0')}';
    }

    // 시각 숫자 없이 대략적 표현만 있을 때(선택적 기본값).
    if (t.contains('점심')) return '12:00';
    if (t.contains('아침')) return '08:00';
    if (t.contains('저녁')) return '18:00';
    return null;
  }

  static const Map<String, String> _categoryKeywords = {
    '병원': 'hospital',
    '진료': 'hospital',
    '치과': 'hospital',
    '회의': 'meeting',
    '미팅': 'meeting',
    '수업': 'school',
    '강의': 'school',
    '운동': 'exercise',
    '헬스': 'exercise',
    '식당': 'restaurant',
    '점심': 'meal',
    '저녁': 'meal',
    '장보기': 'shopping',
  };

  static String? _inferCategory(String t) {
    for (final e in _categoryKeywords.entries) {
      if (t.contains(e.key)) return e.value;
    }
    return null;
  }

  static final _stripPatterns = <RegExp>[
    RegExp(r'\d{1,2}\s*월\s*\d{1,2}\s*일'),
    RegExp(r'(?<!\d)\d{1,2}\s*/\s*\d{1,2}(?!\d)'),
    RegExp(r'\d{1,2}\s*시(?:\s*\d{1,2}\s*분)?'),
    RegExp(r'(오늘|내일|모레|글피|내일모레|오전|오후|아침|점심|저녁|밤|반)'),
    RegExp(r'[월화수목금토일]요일'),
    RegExp(r'(잡아\s*줘|잡아줘|추가해\s*줘|추가해줘|등록해\s*줘|등록해줘|저장해\s*줘|저장해줘|알려\s*줘|알려줘|해\s*줘|해줘|넣어\s*줘|넣어줘)'),
    RegExp(r'(일정|스케줄|해야\s*해|할\s*일로|일정으로)'),
  ];

  /// 날짜/시간/명령어/불용어를 제거해 제목만 남긴다.
  static String _extractTitle(String t) {
    var s = t;
    for (final p in _stripPatterns) {
      s = s.replaceAll(p, ' ');
    }
    s = s.replaceAll(RegExp(r'\s+'), ' ').trim();
    // 조사 꼬리 정리(에/에서/으로/로 끝나면 제거).
    s = s.replaceAll(RegExp(r'(에서|에|으로|로|을|를)$'), '').trim();
    return s;
  }

  // ------------------------------------------------------------------ //
  static String _fmt(DateTime d) =>
      '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

  static DateTime? _safeDate(int y, int m, int d) {
    if (m < 1 || m > 12 || d < 1 || d > 31) return null;
    try {
      final dt = DateTime(y, m, d);
      if (dt.month != m || dt.day != d) return null; // 2/30 등 무효
      return dt;
    } catch (_) {
      return null;
    }
  }
}
