import 'package:flutter/foundation.dart';

import 'schedule_api.dart';

/// 서버 `/ai/schedule/parse` 가 네트워크 오류로 실패했을 때 사용하는
/// 온디바이스 경량 Rule-based 일정 파서(오프라인 fallback).
///
/// 설계 원칙:
///  - 서버 parser 를 **대체하지 않는다**. 서버가 가능하면 서버가 우선이고,
///    이 파서는 오프라인/네트워크 실패에서만 fallback 으로 쓰인다.
///  - 서버와 **동일한 형태의 [ParseResult]**(intent/schedule_draft/missing_fields/
///    tts_text)를 만들어, 화면·저장(ScheduleDraftMapper) 코드를 그대로 재사용한다.
///  - MVP 수준. 정확도는 서버보다 낮으며, 인식 못한 값은 missing_fields 로 알려
///    저장 게이팅/재입력 안내에 맡긴다. 절대 예외를 던지지 않는다.
///  - schedule_draft 키는 서버 스키마를 따른다(title/category/date/start_time/
///    end_time/location/memo/priority/source). 진단용으로 date_expression/
///    time_expression 도 함께 담지만, 저장 시 ScheduleDraftMapper 가 무시한다.
///
/// 지원 예시:
///  - "오늘 6시 운동" / "내일 오후 2시 병원" / "금요일까지 과제 제출"
///  - "다음주 월요일 10시 회의" / "저녁 7시에 약속"
class LocalScheduleParser {
  /// 파싱 결과 출처(계약 필드).
  static const String kSource = 'on_device_rule';

  /// [input] 자연어를 파싱해 서버와 같은 형태의 [ParseResult] 로 돌려준다.
  static ParseResult parse(
    String input,
    {String inputType = 'text', DateTime? now}
  ) {
    final base = now ?? DateTime.now();
    final text = input.trim();

    try {
      final isTodo = _isTodo(text);

      final dateRes = _extractDate(text, base);
      final endDate = _extractEndDate(text, base, dateRes.date);
      final timeRes = _extractStartTime(text);
      final category = _inferCategory(text);
      var title = _extractTitle(text, dateRes.expr, timeRes.expr);
      if (title.isEmpty) title = _defaultTitle(category);

      final draft = <String, dynamic>{
        'title': title,
        'category': category,
        'date': dateRes.date,
        'end_date': endDate,
        'start_time': timeRes.time,
        'end_time': null,
        'location': null,
        'memo': null,
        'priority': 'medium',
        // 저장에는 쓰이지 않지만(mapper 가 무시) 진단/테스트용으로 보존.
        'date_expression': dateRes.expr,
        'time_expression': timeRes.expr,
        // 저장용 source(백엔드가 아는 값). 파싱 출처는 ParseResult.source 로 구분.
        'source': inputType == 'voice' ? 'voice' : 'ai',
      };

      final missing = <String>[];
      if (title.isEmpty) missing.add('title');
      if (!isTodo && dateRes.date == null) missing.add('date');
      // 서버 계약과 동일하게 시간 누락은 'time' 토큰을 쓴다(isRegisterable 호환).
      if (!isTodo && timeRes.time == null) missing.add('time');

      final confidence = _confidence(
        hasTitle: title.isNotEmpty,
        hasDate: dateRes.date != null,
        hasTime: timeRes.time != null,
      );

      final kind = isTodo ? '할 일' : '일정';
      final tts = title.isEmpty
          ? '내용을 잘 이해하지 못했어요. 날짜와 할 일을 포함해 다시 말씀해 주세요.'
          : '오프라인이라 기기에서 "$title"($kind)로 임시 정리했어요. 확인 후 저장하세요.';

      return ParseResult(
        intent: isTodo ? 'create_todo' : 'create_schedule',
        confidence: confidence,
        scheduleDraft: draft,
        missingFields: missing,
        ttsText: tts,
        source: kSource,
      );
    } catch (e) {
      debugPrint('LocalScheduleParser error: $e');
      return ParseResult(
        intent: 'unknown',
        confidence: 0.0,
        scheduleDraft: const {
          'title': '',
          'priority': 'medium',
          'source': 'ai',
        },
        missingFields: const ['title', 'date'],
        ttsText: '오프라인이라 일정을 이해하지 못했어요. 직접 입력해 주세요.',
        source: kSource,
      );
    }
  }

  // ------------------------------------------------------------------ //
  // intent (일정 vs 할 일)
  // ------------------------------------------------------------------ //
  static const _todoSignals = [
    '제출', '과제', '마감', '까지', '장보기', '작성', '사기', '사와', '정리', '시험',
  ];
  static const _todoOverride = [
    '예약', '회의', '미팅', '약속', '병원', '진료', '수업', '운동',
  ];

  static bool _isTodo(String t) {
    final hasTodo = _todoSignals.any(t.contains);
    final hasOverride = _todoOverride.any(t.contains);
    return hasTodo && !hasOverride;
  }

  // ------------------------------------------------------------------ //
  // 날짜
  // ------------------------------------------------------------------ //
  static const _weekdays = {
    '월': DateTime.monday,
    '화': DateTime.tuesday,
    '수': DateTime.wednesday,
    '목': DateTime.thursday,
    '금': DateTime.friday,
    '토': DateTime.saturday,
    '일': DateTime.sunday,
  };

  static _DateResult _extractDate(String t, DateTime base) {
    // 1) ISO: YYYY-MM-DD
    final iso = RegExp(r'(\d{4})-(\d{1,2})-(\d{1,2})').firstMatch(t);
    if (iso != null) {
      final dt = _safeDate(
          int.parse(iso.group(1)!), int.parse(iso.group(2)!), int.parse(iso.group(3)!));
      if (dt != null) return _DateResult(_fmt(dt), iso.group(0)!);
    }

    // 2) 다음 주 X요일
    final nextW = RegExp(r'다음\s*주\s*([월화수목금토일])\s*요일').firstMatch(t);
    if (nextW != null) {
      final wd = _weekdays[nextW.group(1)!]!;
      final thisMon = base.subtract(Duration(days: base.weekday - 1));
      final target = thisMon.add(Duration(days: 7 + (wd - 1)));
      return _DateResult(_fmt(target), nextW.group(0)!);
    }

    // 3) 이번 주 X요일
    final thisW = RegExp(r'이번\s*주\s*([월화수목금토일])\s*요일').firstMatch(t);
    if (thisW != null) {
      final wd = _weekdays[thisW.group(1)!]!;
      final thisMon = base.subtract(Duration(days: base.weekday - 1));
      final target = thisMon.add(Duration(days: wd - 1));
      return _DateResult(_fmt(target), thisW.group(0)!);
    }

    // 4) 상대 표현
    if (t.contains('모레') || t.contains('내일모레')) {
      return _DateResult(_fmt(base.add(const Duration(days: 2))),
          t.contains('내일모레') ? '내일모레' : '모레');
    }
    if (t.contains('글피')) return _DateResult(_fmt(base.add(const Duration(days: 3))), '글피');
    if (t.contains('내일')) return _DateResult(_fmt(base.add(const Duration(days: 1))), '내일');
    if (t.contains('오늘')) return _DateResult(_fmt(base), '오늘');

    // 5) 단독 요일(까지 포함) → 다가오는 해당 요일(오늘 제외).
    final wdOnly = RegExp(r'([월화수목금토일])\s*요일').firstMatch(t);
    if (wdOnly != null) {
      final wd = _weekdays[wdOnly.group(1)!]!;
      var day = base;
      do {
        day = day.add(const Duration(days: 1));
      } while (day.weekday != wd);
      return _DateResult(_fmt(day), wdOnly.group(0)!);
    }

    // 6) N월 M일
    final md = RegExp(r'(\d{1,2})\s*월\s*(\d{1,2})\s*일').firstMatch(t);
    if (md != null) {
      final m = int.parse(md.group(1)!);
      final d = int.parse(md.group(2)!);
      final year = (m < base.month) ? base.year + 1 : base.year;
      final dt = _safeDate(year, m, d);
      if (dt != null) return _DateResult(_fmt(dt), md.group(0)!);
    }

    // 7) M/D
    final slash = RegExp(r'(?<!\d)(\d{1,2})\s*/\s*(\d{1,2})(?!\d)').firstMatch(t);
    if (slash != null) {
      final m = int.parse(slash.group(1)!);
      final d = int.parse(slash.group(2)!);
      final year = (m < base.month) ? base.year + 1 : base.year;
      final dt = _safeDate(year, m, d);
      if (dt != null) return _DateResult(_fmt(dt), slash.group(0)!);
    }

    return const _DateResult(null, null);
  }

  // ------------------------------------------------------------------ //
  // 기간(종료일)
  // ------------------------------------------------------------------ //
  /// "A부터 B까지" / "A~B" / "A-B" 형태에서 종료일을 뽑는다(없으면 null).
  /// [startDate] 는 이미 해석된 시작일("YYYY-MM-DD")로, "N일" 단독 종료 표현의
  /// 연·월을 물려받는 데 쓴다. 종료일이 시작일보다 뒤일 때만 반환한다.
  static String? _extractEndDate(String t, DateTime base, String? startDate) {
    if (startDate == null) return null;

    String? rightExpr;
    final buteo = RegExp(r'(.+?)\s*부터\s*(.+?)\s*까지').firstMatch(t);
    if (buteo != null) {
      rightExpr = buteo.group(2);
    } else {
      const tok =
          r'(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}\s*월\s*\d{1,2}\s*일|\d{1,2}\s*/\s*\d{1,2}|\d{1,2}\s*일)';
      final tilde =
          RegExp('($tok)\\s*[~∼〜–—-]\\s*($tok)').firstMatch(t);
      if (tilde != null) rightExpr = tilde.group(2);
    }
    if (rightExpr == null) return null;

    final end = _resolveEndExpr(rightExpr.trim(), base, startDate);
    if (end == null || end.compareTo(startDate) <= 0) return null;
    return end;
  }

  static String? _resolveEndExpr(String expr, DateTime base, String startDate) {
    // "9일" / "9" → 시작일의 연·월 사용.
    final dOnly = RegExp(r'^(\d{1,2})\s*일?$').firstMatch(expr);
    if (dOnly != null) {
      final y = int.parse(startDate.substring(0, 4));
      final m = int.parse(startDate.substring(5, 7));
      final d = int.parse(dOnly.group(1)!);
      final dt = _safeDate(y, m, d);
      return dt == null ? null : _fmt(dt);
    }
    return _extractDate(expr, base).date;
  }

  // ------------------------------------------------------------------ //
  // 시간
  // ------------------------------------------------------------------ //
  static _TimeResult _extractStartTime(String t) {
    final pm = t.contains('오후') || t.contains('저녁') || t.contains('밤');
    final am = t.contains('오전') || t.contains('아침') || t.contains('새벽');

    // 1) HH:mm
    final colon = RegExp(r'(\d{1,2}):(\d{2})').firstMatch(t);
    if (colon != null) {
      var h = int.parse(colon.group(1)!);
      final m = int.parse(colon.group(2)!);
      if (h >= 0 && h <= 23 && m >= 0 && m <= 59) {
        return _TimeResult(_hhmm(h, m), colon.group(0)!);
      }
    }

    // 2) N시 (M분)? / N시 반
    final hm = RegExp(r'(\d{1,2})\s*시(?:\s*(\d{1,2})\s*분)?').firstMatch(t);
    if (hm != null) {
      var h = int.parse(hm.group(1)!);
      var min = hm.group(2) != null ? int.parse(hm.group(2)!) : 0;
      final hasBan = hm.group(2) == null && _nearBan(t, hm.end);
      if (hasBan) min = 30;
      if (pm && h < 12) h += 12;
      if (am && h == 12) h = 0;
      if (h >= 0 && h <= 23 && min >= 0 && min <= 59) {
        return _TimeResult(_hhmm(h, min), hm.group(0)!);
      }
    }

    // 3) 시각 숫자 없이 시간대 표현만.
    if (t.contains('점심')) return const _TimeResult('12:00', '점심');
    if (t.contains('새벽')) return const _TimeResult('06:00', '새벽');
    if (t.contains('아침')) return const _TimeResult('08:00', '아침');
    if (t.contains('저녁')) return const _TimeResult('18:00', '저녁');
    if (t.contains('밤')) return const _TimeResult('20:00', '밤');

    return const _TimeResult(null, null);
  }

  /// "N시" 뒤에 곧바로 '반'이 오는지(예: "7시 반").
  static bool _nearBan(String t, int fromIndex) {
    final tail = t.substring(fromIndex).trimLeft();
    return tail.startsWith('반');
  }

  // ------------------------------------------------------------------ //
  // 카테고리
  // ------------------------------------------------------------------ //
  // 순서 중요: 상위 항목 먼저 매칭(예: '약속'(personal)을 '저녁'(food)보다 먼저).
  static const List<MapEntry<String, List<String>>> _categoryRules = [
    MapEntry('hospital', ['병원', '진료', '치과', '의원', '검진']),
    MapEntry('beauty', ['미용실', '미용', '네일', '헤어', '피부과']),
    MapEntry('meeting', ['회의', '미팅', '회식']),
    MapEntry('study', ['과제', '공부', '시험', '스터디', '강의', '수업']),
    MapEntry('exercise', ['운동', '헬스', '요가', '러닝', 'pt', 'PT']),
    MapEntry('personal', ['약속', '친구', '데이트']),
    MapEntry('food', ['식당', '맛집', '식사', '밥', '점심', '저녁', '아침']),
  ];

  static String? _inferCategory(String t) {
    for (final rule in _categoryRules) {
      if (rule.value.any(t.contains)) return rule.key;
    }
    return null;
  }

  static const Map<String, String> _defaultTitles = {
    'hospital': '병원 예약',
    'beauty': '미용실',
    'meeting': '회의',
    'study': '공부',
    'exercise': '운동',
    'personal': '약속',
    'food': '식사',
  };

  static String _defaultTitle(String? category) =>
      category == null ? '' : (_defaultTitles[category] ?? '');

  // ------------------------------------------------------------------ //
  // 제목 정제
  // ------------------------------------------------------------------ //
  static final _commandPatterns = <RegExp>[
    RegExp(r'(잡아\s*줘|잡아줘|추가해\s*줘|추가해줘|등록해\s*줘|등록해줘|저장해\s*줘|저장해줘|알려\s*줘|알려줘|넣어\s*줘|넣어줘|해\s*줘|해줘|부탁해?|해야\s*해|해야지|하기)'),
  ];
  static final _fillerPatterns = <RegExp>[
    RegExp(r'(다음\s*주|이번\s*주)'),
    RegExp(r'[월화수목금토일]\s*요일'),
    RegExp(r'(오늘|내일모레|내일|모레|글피|까지)'),
    RegExp(r'\d{4}-\d{1,2}-\d{1,2}'),
    RegExp(r'\d{1,2}\s*월\s*\d{1,2}\s*일'),
    RegExp(r'(?<!\d)\d{1,2}\s*/\s*\d{1,2}(?!\d)'),
    RegExp(r'\d{1,2}:\d{2}'),
    RegExp(r'\d{1,2}\s*시(?:\s*\d{1,2}\s*분)?'),
    RegExp(r'(오전|오후|저녁|아침|점심|밤|새벽|낮|반)'),
    RegExp(r'(일정으로|할\s*일로|일정|스케줄|좀)'),
  ];

  static String _extractTitle(String t, String? dateExpr, String? timeExpr) {
    var s = t;
    // 매칭된 날짜/시간 표현을 우선 제거.
    if (dateExpr != null && dateExpr.isNotEmpty) s = s.replaceAll(dateExpr, ' ');
    if (timeExpr != null && timeExpr.isNotEmpty) s = s.replaceAll(timeExpr, ' ');
    for (final p in _commandPatterns) {
      s = s.replaceAll(p, ' ');
    }
    for (final p in _fillerPatterns) {
      s = s.replaceAll(p, ' ');
    }
    s = s.replaceAll(RegExp(r'\s+'), ' ').trim();
    // 홀로 남은 조사 토큰 제거(예: "7시에" 제거 후 남은 "에").
    const particles = {'에', '에서', '로', '으로', '을', '를', '이', '가', '는', '은', '도', '만'};
    final tokens =
        s.split(' ').where((w) => w.isNotEmpty && !particles.contains(w)).toList();
    s = tokens.join(' ').trim();
    // 조사 꼬리 정리(에서/에/으로/로/을/를/이/가 로 끝나면 제거).
    s = s.replaceAll(RegExp(r'(에서|에|으로|로|을|를|이|가)$'), '').trim();
    return s;
  }

  // ------------------------------------------------------------------ //
  static double _confidence({
    required bool hasTitle,
    required bool hasDate,
    required bool hasTime,
  }) {
    if (!hasTitle) return 0.1;
    if (hasDate && hasTime) return 0.7;
    if (hasDate || hasTime) return 0.5;
    return 0.3;
  }

  static String _hhmm(int h, int m) =>
      '${h.toString().padLeft(2, '0')}:${m.toString().padLeft(2, '0')}';

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

/// 날짜 추출 결과(정규화 날짜 + 매칭된 원문 표현).
class _DateResult {
  final String? date; // 'YYYY-MM-DD' 또는 null
  final String? expr; // 매칭된 날짜 표현 원문
  const _DateResult(this.date, this.expr);
}

/// 시간 추출 결과(정규화 시각 + 매칭된 원문 표현).
class _TimeResult {
  final String? time; // 'HH:mm' 또는 null
  final String? expr; // 매칭된 시간 표현 원문
  const _TimeResult(this.time, this.expr);
}
