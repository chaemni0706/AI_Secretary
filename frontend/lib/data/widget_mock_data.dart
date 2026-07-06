import 'package:flutter/material.dart';

/// 위젯 대시보드에서 **아직 실제 데이터 소스가 없는** 위젯들의 mock 데이터.
///
/// 화면/위젯 파일 안에 더미 데이터를 직접 쓰지 않고 이 파일로 분리한다.
/// 추후 실제 API/서비스가 준비되면 이 클래스의 getter 를 해당 소스로 교체하면 된다.
class WidgetMockData {
  WidgetMockData._();

  // ── 날씨 (향후 날씨 API 연결 예정) ─────────────────────────────
  static const WeatherNow weatherNow = WeatherNow(
    tempC: 24,
    icon: Icons.wb_sunny_outlined,
    summary: '맑음 · 외출하기 좋아요',
    location: '서울',
  );

  static const List<WeatherDay> weeklyWeather = [
    WeatherDay('월', Icons.wb_sunny_outlined, 25, 17),
    WeatherDay('화', Icons.wb_cloudy_outlined, 23, 16),
    WeatherDay('수', Icons.grain, 20, 15),
    WeatherDay('목', Icons.cloud_outlined, 22, 16),
    WeatherDay('금', Icons.wb_sunny_outlined, 26, 18),
  ];

  // ── 소비 분석 (현재 가계부가 mock 기반) ────────────────────────
  static const SpendingInsight spendingInsight = SpendingInsight(
    periodLabel: '이번 주',
    topCategory: '식비',
    changePercent: 12, // 전월/전주 대비 증가율(+)
    comment: '이번 주 식비 비중이 높아요. 외식을 한 번만 줄여도 예산에 여유가 생겨요.',
  );

  // ── AI 추천 (향후 추천 API 연결 예정) ──────────────────────────
  static const List<String> aiRecommendations = [
    '오후 3시 회의 전 이동시간 20분을 미리 확보해 두는 게 좋아요.',
    '내일 비 예보가 있어요. 우산을 준비물에 추가할까요?',
    '이번 주 여유 시간대에 미뤄둔 병원 예약을 잡아볼까요?',
  ];

  // ── 예약 후보 추천 (BookingRecommendScreen 과 별개의 미리보기) ──
  static const List<String> reservationCandidates = ['14:00', '16:30', '18:00'];
  static const String reservationTitle = '미용실 커트';

  // ── 준비물 (다음 일정 기준, 향후 일정/날씨 연동) ───────────────
  static const List<PreparationItem> preparationItems = [
    PreparationItem('우산', Icons.umbrella_outlined),
    PreparationItem('노트북', Icons.laptop_mac_outlined),
  ];
  static const String preparationContext = '오후 외부 미팅';

  // ── OCR 인증 (향후 OCR API 연결 예정) ──────────────────────────
  static const int ocrPendingCount = 1;
}

class WeatherNow {
  final int tempC;
  final IconData icon;
  final String summary;
  final String location;

  const WeatherNow({
    required this.tempC,
    required this.icon,
    required this.summary,
    required this.location,
  });
}

class WeatherDay {
  final String day;
  final IconData icon;
  final int high;
  final int low;

  const WeatherDay(this.day, this.icon, this.high, this.low);
}

class SpendingInsight {
  final String periodLabel;
  final String topCategory;
  final int changePercent;
  final String comment;

  const SpendingInsight({
    required this.periodLabel,
    required this.topCategory,
    required this.changePercent,
    required this.comment,
  });
}

class PreparationItem {
  final String label;
  final IconData icon;

  const PreparationItem(this.label, this.icon);
}
