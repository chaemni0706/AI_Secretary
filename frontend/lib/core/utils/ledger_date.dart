/// AI 가계부 공용 날짜 헬퍼.
///
/// 화면은 DateTime.now() 기준으로 동작하고, 여기서 표시/전송 포맷을 일관되게 만든다.
library;

/// 'YYYY-MM-DD' (백엔드 date / selected_date 규약).
String yyyyMmDd(DateTime d) =>
    '${d.year.toString().padLeft(4, '0')}-'
    '${d.month.toString().padLeft(2, '0')}-'
    '${d.day.toString().padLeft(2, '0')}';

/// 'YYYY년 M월' 표시 라벨.
String monthLabel(DateTime d) => '${d.year}년 ${d.month}월';

/// 연·월·일이 같은 날짜인지.
bool sameDate(DateTime a, DateTime b) =>
    a.year == b.year && a.month == b.month && a.day == b.day;

/// 해당 월의 마지막 일(day). 예: 2월 → 28/29.
int lastDayOfMonth(int year, int month) => DateTime(year, month + 1, 0).day;
