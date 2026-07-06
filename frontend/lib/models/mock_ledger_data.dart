import 'ledger_models.dart';

/// AI 가계부 프로토타입에서 사용하는 모든 mock 데이터.
/// 실제 금융 연동은 없으며, 시뮬레이션 버튼이 [simPool] 에서 거래를 순환 추가한다.
class MockLedgerData {
  MockLedgerData._();

  /// 기준 연/월 (달력 · 리포트 공통).
  static const int year = 2025;
  static const int month = 12;

  /// 기본 선택 날짜.
  static const int defaultSelectedDay = 20;

  /// 월 요약 합계.
  static const int monthSpend = 1625560;
  static const int monthIncome = 2746059;

  /// 달력 셀 표시용 일별 지출/수입 합계.
  static const Map<int, DayInfo> dayData = {
    1: DayInfo(spend: 3200),
    2: DayInfo(spend: 18500),
    4: DayInfo(spend: 9800),
    5: DayInfo(spend: 52000, income: 500000),
    6: DayInfo(spend: 4500),
    8: DayInfo(spend: 12300),
    9: DayInfo(income: 32000),
    11: DayInfo(spend: 33900),
    13: DayInfo(spend: 8400),
    14: DayInfo(spend: 22400),
    15: DayInfo(spend: 15600),
    17: DayInfo(spend: 98400),
    18: DayInfo(spend: 2800),
    19: DayInfo(spend: 54800, income: 12000),
    20: DayInfo(spend: 27300),
    22: DayInfo(spend: 14000),
    23: DayInfo(spend: 9500),
    24: DayInfo(spend: 48000),
    26: DayInfo(spend: 110000),
    27: DayInfo(spend: 49390),
    28: DayInfo(income: 9500),
    29: DayInfo(spend: 2900),
    31: DayInfo(spend: 5300),
  };

  /// 날짜별 상세 거래 리스트.
  static const Map<int, List<LedgerTx>> txByDay = {
    5: [
      LedgerTx('08:00', '급여 입금', '급', 500000, '수입', 'income', '입금 알림'),
      LedgerTx('20:10', '롯데마트 서초점', '롯', -52000, '식비', 'food', '장소 검색'),
    ],
    17: [
      LedgerTx('21:30', '쿠팡', '쿠', -63000, '쇼핑', 'shop', '룰베이스'),
      LedgerTx('19:10', '배달의민족', '배', -35400, '식비', 'food', 'AI 판단'),
    ],
    19: [
      LedgerTx('12:00', '점심 정산 입금', '정', 12000, '수입', 'income', '입금 알림'),
      LedgerTx('22:40', '올리브영 강남', '올', -54800, '쇼핑', 'shop', '장소 검색'),
    ],
    20: [
      LedgerTx('14:20', '스타벅스 강남역점', '스', -5800, '카페', 'cafe', '룰베이스'),
      LedgerTx('12:30', '홍콩반점0410 강남역점', '홍', -9500, '식비', 'food', '장소 검색'),
      LedgerTx('09:10', '카카오T', 'K', -12000, '교통', 'trans', '룰베이스'),
    ],
    26: [
      LedgerTx('18:00', '이마트 트레이더스', '이', -110000, '쇼핑', 'shop', '장소 검색'),
    ],
  };

  /// 날짜별 AI 브리핑 문구.
  static const Map<int, String> briefingByDay = {
    5: '12월 5일에 급여 500,000원이 입금됐어요. 같은 날 마트 지출이 있었으니 이번 주 예산을 미리 나눠두면 좋아요 💡',
    17: '12월 17일은 이번 달 지출이 가장 많은 날이에요. 쇼핑과 배달로 98,400원을 사용했어요. 큰 지출이 몰린 날이니 다음 주는 조금 여유를 둬볼까요?',
    19: '12월 19일에는 쇼핑 지출이 조금 컸어요. 소소한 입금도 있었으니 남은 예산을 확인해볼게요.',
    20: '12월 20일에는 총 27,300원을 사용했어요. 카페와 교통비 지출이 평소보다 조금 많아요. 커피 한 잔만 줄여도 목표에 가까워져요 ☕',
    26: '12월 26일에는 이마트에서 110,000원을 사용했어요. 대형 지출이 있던 날이라 이번 달 식비·쇼핑 예산을 다시 확인해볼게요.',
  };

  /// 자동 감지 초기 대기 목록.
  static const List<PendingTx> initialPending = [
    PendingTx(1, '무신사', '무', -42000, '쇼핑', 'shop', 'AI 판단', true, 71),
  ];

  /// 시뮬레이션 버튼이 순환하며 추가하는 mock 결제 풀.
  static const List<PendingTx> simPool = [
    PendingTx(0, '이디야커피 역삼점', '이', -4500, '카페', 'cafe', '룰베이스', false, 96),
    PendingTx(0, 'CU 강남중앙점', 'C', -2800, '편의점', 'cvs', '룰베이스', false, 94),
    PendingTx(0, '배달의민족', '배', -18500, '식비', 'food', 'AI 판단', true, 68),
    PendingTx(0, '쿠팡', '쿠', -33900, '쇼핑', 'shop', '장소 검색', false, 88),
    PendingTx(0, '지하철 (교통카드)', '지', -1400, '교통', 'trans', '룰베이스', false, 97),
  ];

  /// 리포트: 반복 결제 · 고정지출.
  static const List<RecurringPayment> recurring = [
    RecurringPayment('NETFLIX', 'N', -17000, '매월 1일', '구독', 'sub'),
    RecurringPayment('KT 통신비', 'KT', -69000, '매월 15일', '통신', 'tel'),
  ];

  /// 리포트: 카테고리별 소비.
  static const List<CategoryStat> reportCategories = [
    CategoryStat('식비', 81000, 34, 'food'),
    CategoryStat('쇼핑', 50000, 21, 'shop'),
    CategoryStat('카페', 43000, 18, 'cafe'),
    CategoryStat('교통', 29000, 12, 'trans'),
    CategoryStat('구독', 17000, 7, 'sub'),
  ];

  /// 리포트: 예산 사용률.
  static const List<BudgetStat> reportBudgets = [
    BudgetStat('카페', 84, '42,000 / 50,000', true),
    BudgetStat('식비', 62, '81,000 / 130,000', false),
    BudgetStat('쇼핑', 48, '50,000 / 105,000', false),
  ];

  /// 리포트 요약.
  static const int reportBalance = 261500;
  static const int reportSpend = 238500;
  static const int reportIncome = 500000;
  static const int reportCategoryTotal = 220000;
  static const int reportRecurringTotal = 86000;

  static const String monthlyBriefing =
      '이번 달은 식비와 카페 소비가 가장 많았어요. 특히 일정이 많은 날 교통비와 카페 지출이 함께 늘어나는 패턴이 보여요. 바쁜 주에는 미리 커피 쿠폰을 챙겨두면 도움이 될 거예요.';

  /// 상세 데이터가 없는 날의 기본 브리핑 문구.
  static String fallbackBriefing(int day, DayInfo info) {
    if (info.spend > 0) {
      return '12월 $day일에는 총 ${_won(info.spend)}원을 사용했어요. 소비가 크지 않은 하루였어요 👍';
    }
    return '12월 $day일에는 기록된 소비가 없어요. 여유로운 하루였네요 :)';
  }

  static String _won(num n) {
    final v = n.abs().round().toString();
    final b = StringBuffer();
    for (int i = 0; i < v.length; i++) {
      if (i > 0 && (v.length - i) % 3 == 0) b.write(',');
      b.write(v[i]);
    }
    return b.toString();
  }
}
