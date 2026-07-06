// ============================================================================
//  AI 가계부 (AI Ledger) — 단일 파일 실행 데모
//  - 외부 패키지 없이 기본 Flutter 위젯만 사용
//  - Mock 데이터로 화면만 렌더링 (실제 API 연동 없음)
//  - 화면 1: 소비 달력 홈 / 화면 2: 소비 리포트(월간 분석)
//  실행:  이 파일을 lib/main.dart 로 넣고  `flutter run`
// ============================================================================

import 'package:flutter/material.dart';

void main() => runApp(const LedgerApp());

// ----------------------------------------------------------------------------
//  디자인 토큰 (색상 / 간격 / 반경)
// ----------------------------------------------------------------------------
class AppColor {
  static const bg = Color(0xFFFFFFFF);
  static const ink = Color(0xFF191F28); // 기본 텍스트
  static const ink2 = Color(0xFF4E5968);
  static const ink3 = Color(0xFF6B7684);
  static const sub = Color(0xFF8B95A1); // 보조 텍스트
  static const faint = Color(0xFFB0B8C1);
  static const line = Color(0xFFEDF0F3);
  static const line2 = Color(0xFFF2F4F6);
  static const fill = Color(0xFFF5F7FA); // 요약 카드 배경
  static const blue = Color(0xFF3B6EF6); // 포인트 컬러
  static const blueSoft = Color(0xFFEAF0FF);
  static const sunday = Color(0xFFE5686F);

  // 카테고리 컬러
  static const cafe = Color(0xFFE8850C);
  static const food = Color(0xFF1FA463);
  static const trans = Color(0xFF3B6EF6);
  static const sub_ = Color(0xFF8B5CF6);
  static const shop = Color(0xFFE5457E);
  static const cvs = Color(0xFF0EA5A5);
  static const income = Color(0xFF3B6EF6);
  static const tel = Color(0xFF5B6472);

  // 알림/경고
  static const warn = Color(0xFFF2711C);
  static const warnBg = Color(0xFFFFF6F0);
  static const warnBorder = Color(0xFFFCE2D2);
}

Color catColor(String key) {
  switch (key) {
    case 'cafe':
      return AppColor.cafe;
    case 'food':
      return AppColor.food;
    case 'trans':
      return AppColor.trans;
    case 'sub':
      return AppColor.sub_;
    case 'shop':
      return AppColor.shop;
    case 'cvs':
      return AppColor.cvs;
    case 'income':
      return AppColor.income;
    case 'tel':
      return AppColor.tel;
    default:
      return AppColor.food;
  }
}

Color catTagBg(String key) => catColor(key).withOpacity(0.12);

String won(num n) {
  final v = n.abs().round().toString();
  final b = StringBuffer();
  for (int i = 0; i < v.length; i++) {
    if (i > 0 && (v.length - i) % 3 == 0) b.write(',');
    b.write(v[i]);
  }
  return b.toString();
}

// ----------------------------------------------------------------------------
//  모델 (Mock)
// ----------------------------------------------------------------------------
class Tx {
  final String time, merchant, initial, category, catKey, method;
  final int amount; // 음수=지출, 양수=수입
  const Tx(this.time, this.merchant, this.initial, this.amount, this.category,
      this.catKey, this.method);
}

class PendingTx {
  final int id;
  final String merchant, initial, category, catKey, method;
  final int amount;
  final bool review;
  final int confidence;
  const PendingTx(this.id, this.merchant, this.initial, this.amount,
      this.category, this.catKey, this.method, this.review, this.confidence);
}

class DayInfo {
  final int spend, income;
  const DayInfo({this.spend = 0, this.income = 0});
}

class Recurring {
  final String name, initial, cycle, cat, catKey;
  final int amount;
  const Recurring(
      this.name, this.initial, this.amount, this.cycle, this.cat, this.catKey);
}

// ----------------------------------------------------------------------------
//  Mock 데이터 저장소
// ----------------------------------------------------------------------------
class MockData {
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

  static const Map<int, List<Tx>> txByDay = {
    5: [
      Tx('08:00', '급여 입금', '급', 500000, '수입', 'income', '입금 알림'),
      Tx('20:10', '롯데마트 서초점', '롯', -52000, '식비', 'food', '장소 검색'),
    ],
    17: [
      Tx('21:30', '쿠팡', '쿠', -63000, '쇼핑', 'shop', '룰베이스'),
      Tx('19:10', '배달의민족', '배', -35400, '식비', 'food', 'AI 판단'),
    ],
    20: [
      Tx('14:20', '스타벅스 강남역점', '스', -5800, '카페', 'cafe', '룰베이스'),
      Tx('12:30', '홍콩반점0410 강남역점', '홍', -9500, '식비', 'food', '장소 검색'),
      Tx('09:10', '카카오T', 'K', -12000, '교통', 'trans', '룰베이스'),
    ],
    26: [
      Tx('18:00', '이마트 트레이더스', '이', -110000, '쇼핑', 'shop', '장소 검색'),
    ],
  };

  static const Map<int, String> briefingByDay = {
    5: '12월 5일에 급여 500,000원이 입금됐어요. 같은 날 마트 지출이 있었으니 이번 주 예산을 미리 나눠두면 좋아요 💡',
    17: '12월 17일은 이번 달 지출이 가장 많은 날이에요. 쇼핑과 배달로 98,400원을 사용했어요. 큰 지출이 몰린 날이니 다음 주는 조금 여유를 둬볼까요?',
    20: '12월 20일에는 총 27,300원을 사용했어요. 카페와 교통비 지출이 평소보다 조금 많아요. 커피 한 잔만 줄여도 목표에 가까워져요 ☕',
    26: '12월 26일에는 이마트에서 110,000원을 사용했어요. 대형 지출이 있던 날이라 이번 달 식비·쇼핑 예산을 다시 확인해볼게요.',
  };

  static const List<PendingTx> initialPending = [
    PendingTx(1, '무신사', '무', -42000, '쇼핑', 'shop', 'AI 판단', true, 71),
  ];

  static const List<PendingTx> simPool = [
    PendingTx(0, '이디야커피 역삼점', '이', -4500, '카페', 'cafe', '룰베이스', false, 96),
    PendingTx(0, 'CU 강남중앙점', 'C', -2800, '편의점', 'cvs', '룰베이스', false, 94),
    PendingTx(0, '배달의민족', '배', -18500, '식비', 'food', 'AI 판단', true, 68),
    PendingTx(0, '쿠팡', '쿠', -33900, '쇼핑', 'shop', '장소 검색', false, 88),
    PendingTx(0, '지하철 (교통카드)', '지', -1400, '교통', 'trans', '룰베이스', false, 97),
  ];

  static const List<Recurring> recurring = [
    Recurring('NETFLIX', 'N', -17000, '매월 1일', '구독', 'sub'),
    Recurring('KT 통신비', 'KT', -69000, '매월 15일', '통신', 'tel'),
  ];
}

// ----------------------------------------------------------------------------
//  앱 루트
// ----------------------------------------------------------------------------
class LedgerApp extends StatelessWidget {
  const LedgerApp({super.key});
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'AI 가계부',
      theme: ThemeData(
        scaffoldBackgroundColor: AppColor.bg,
        fontFamily: 'Pretendard', // 없으면 기본 폰트로 폴백
        colorScheme: ColorScheme.fromSeed(seedColor: AppColor.blue),
        useMaterial3: true,
      ),
      home: const RootShell(),
    );
  }
}

/// 하단 내비게이션 — AI 가계부 탭이 선택된 상태
class RootShell extends StatefulWidget {
  const RootShell({super.key});
  @override
  State<RootShell> createState() => _RootShellState();
}

class _RootShellState extends State<RootShell> {
  int _tab = 2; // 0 홈 · 1 일정 · 2 AI 가계부(선택) · 3 마이

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(bottom: false, child: const CalendarHomeScreen()),
      bottomNavigationBar: _BottomNav(
        current: _tab,
        onTap: (i) => setState(() => _tab = i),
      ),
    );
  }
}

class _BottomNav extends StatelessWidget {
  final int current;
  final ValueChanged<int> onTap;
  const _BottomNav({required this.current, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final items = [
      (Icons.home_outlined, '홈'),
      (Icons.calendar_today_outlined, '일정'),
      (Icons.account_balance_wallet_outlined, 'AI 가계부'),
      (Icons.person_outline, '마이'),
    ];
    return Container(
      decoration: const BoxDecoration(
        color: Colors.white,
        border: Border(top: BorderSide(color: Color(0xFFEEF1F4))),
      ),
      padding: const EdgeInsets.only(top: 8, bottom: 22, left: 8, right: 8),
      child: Row(
        children: List.generate(items.length, (i) {
          final active = i == current;
          final color = active ? AppColor.blue : AppColor.faint;
          return Expanded(
            child: GestureDetector(
              behavior: HitTestBehavior.opaque,
              onTap: () => onTap(i),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(items[i].$1, size: 24, color: color),
                  const SizedBox(height: 5),
                  Text(items[i].$2,
                      style: TextStyle(
                          fontSize: 10.5,
                          height: 1,
                          fontWeight:
                              active ? FontWeight.w700 : FontWeight.w500,
                          color: color)),
                ],
              ),
            ),
          );
        }),
      ),
    );
  }
}

// ============================================================================
//  화면 1 — 소비 달력 홈
// ============================================================================
class CalendarHomeScreen extends StatefulWidget {
  const CalendarHomeScreen({super.key});
  @override
  State<CalendarHomeScreen> createState() => _CalendarHomeScreenState();
}

class _CalendarHomeScreenState extends State<CalendarHomeScreen> {
  int selectedDay = 20;
  int topTab = 0; // 0 달력 · 1 거래내역 · 2 소비분석
  int _simIdx = 0;
  int _nextId = 100;
  final List<PendingTx> pending = List.of(MockData.initialPending);

  void _selectDay(int d) => setState(() => selectedDay = d);

  void _simulate() {
    final tpl = MockData.simPool[_simIdx % MockData.simPool.length];
    setState(() {
      _simIdx++;
      pending.insert(
          0,
          PendingTx(_nextId++, tpl.merchant, tpl.initial, tpl.amount,
              tpl.category, tpl.catKey, tpl.method, tpl.review, tpl.confidence));
    });
  }

  void _confirm(int id) => setState(() => pending.removeWhere((p) => p.id == id));
  void _remove(int id) => setState(() => pending.removeWhere((p) => p.id == id));
  void _edit(int id) {
    setState(() {
      final i = pending.indexWhere((p) => p.id == id);
      if (i >= 0) {
        final p = pending[i];
        pending[i] = PendingTx(p.id, p.merchant, p.initial, p.amount,
            p.category, p.catKey, '직접 수정', false, 100);
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    const dow = ['일', '월', '화', '수', '목', '금', '토'];
    final info = MockData.dayData[selectedDay] ?? const DayInfo();
    final txs = MockData.txByDay[selectedDay] ?? const [];
    final wdSel = DateTime(2025, 12, selectedDay).weekday % 7; // 0=일
    final selectedLabel = '12월 $selectedDay일 · ${dow[wdSel]}요일';

    String dayTotal;
    Color dayTotalColor;
    if (info.spend > 0) {
      dayTotal = '지출 ${won(info.spend)}원';
      dayTotalColor = AppColor.ink2;
    } else if (info.income > 0) {
      dayTotal = '수입 ${won(info.income)}원';
      dayTotalColor = AppColor.blue;
    } else {
      dayTotal = '소비 없음';
      dayTotalColor = AppColor.faint;
    }

    final briefing = MockData.briefingByDay[selectedDay] ??
        (info.spend > 0
            ? '12월 $selectedDay일에는 총 ${won(info.spend)}원을 사용했어요. 소비가 크지 않은 하루였어요 👍'
            : '12월 $selectedDay일에는 기록된 소비가 없어요. 여유로운 하루였네요 :)');

    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 28),
      children: [
        // 헤더
        Padding(
          padding: const EdgeInsets.fromLTRB(4, 6, 4, 14),
          child: Row(
            children: [
              const Text('12월 내 소비',
                  style: TextStyle(
                      fontSize: 23,
                      height: 1,
                      fontWeight: FontWeight.w700,
                      letterSpacing: -0.4,
                      color: AppColor.ink)),
              const SizedBox(width: 4),
              const Icon(Icons.keyboard_arrow_down, size: 22, color: AppColor.ink),
              const Spacer(),
              _NotifBell(),
            ],
          ),
        ),

        // 탭
        _TopTabs(
          current: topTab,
          onTap: (i) {
            if (i == 2) {
              Navigator.of(context).push(
                  MaterialPageRoute(builder: (_) => const ReportScreen()));
            } else {
              setState(() => topTab = i);
            }
          },
        ),
        const SizedBox(height: 18),

        // 월 요약
        Padding(
          padding: const EdgeInsets.fromLTRB(6, 2, 6, 18),
          child: Row(
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: const [
                  _SummaryLine(label: '지출', value: '1,625,560', color: AppColor.ink),
                  SizedBox(height: 9),
                  _SummaryLine(label: '수입', value: '2,746,059', color: AppColor.blue),
                ],
              ),
              const Spacer(),
              const Icon(Icons.chevron_right, color: AppColor.faint),
            ],
          ),
        ),

        // 달력 (핵심 영역)
        _CalendarGrid(selectedDay: selectedDay, onSelect: _selectDay),
        const SizedBox(height: 16),

        // 선택 날짜 AI 브리핑
        _AiBriefingCard(
          title: 'AI 소비 브리핑',
          trailing: '12월 $selectedDay일',
          body: briefing,
        ),
        const SizedBox(height: 14),

        // 선택 날짜 거래 내역
        Padding(
          padding: const EdgeInsets.fromLTRB(4, 2, 4, 10),
          child: Row(
            children: [
              Text(selectedLabel,
                  style: const TextStyle(
                      fontSize: 15, fontWeight: FontWeight.w700, color: AppColor.ink)),
              const Spacer(),
              Text(dayTotal,
                  style: TextStyle(
                      fontSize: 13, fontWeight: FontWeight.w600, color: dayTotalColor)),
            ],
          ),
        ),
        if (txs.isEmpty)
          Container(
            decoration: BoxDecoration(
              color: const Color(0xFFF8FAFB),
              borderRadius: BorderRadius.circular(18),
              border: Border.all(color: AppColor.line),
            ),
            padding: const EdgeInsets.symmetric(vertical: 24, horizontal: 16),
            alignment: Alignment.center,
            child: const Text('이 날은 기록된 소비가 없어요',
                style: TextStyle(fontSize: 13, color: AppColor.sub)),
          )
        else
          _CardList(
            children: [
              for (int i = 0; i < txs.length; i++)
                _TxRow(tx: txs[i], last: i == txs.length - 1),
            ],
          ),
        const SizedBox(height: 14),

        // 자동 감지 (축소형)
        _AutoDetectCompact(
          pending: pending,
          onSimulate: _simulate,
          onConfirm: _confirm,
          onEdit: _edit,
          onRemove: _remove,
        ),
        const SizedBox(height: 12),

        // 예산 초과 (한 줄 알림)
        _BudgetAlertBanner(),
      ],
    );
  }
}

class _SummaryLine extends StatelessWidget {
  final String label, value;
  final Color color;
  const _SummaryLine({required this.label, required this.value, required this.color});
  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.baseline,
      textBaseline: TextBaseline.alphabetic,
      children: [
        SizedBox(
          width: 30,
          child: Text(label,
              style: const TextStyle(
                  fontSize: 13.5, fontWeight: FontWeight.w600, color: AppColor.ink3)),
        ),
        const SizedBox(width: 12),
        Text.rich(TextSpan(children: [
          TextSpan(
              text: value,
              style: TextStyle(
                  fontSize: 17,
                  fontWeight: FontWeight.w700,
                  letterSpacing: -0.3,
                  color: color)),
          const TextSpan(
              text: ' 원',
              style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
        ])),
      ],
    );
  }
}

class _NotifBell extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container(
      width: 40,
      height: 40,
      decoration: const BoxDecoration(color: AppColor.line2, shape: BoxShape.circle),
      child: Stack(
        alignment: Alignment.center,
        children: [
          const Icon(Icons.notifications_none, size: 22, color: AppColor.ink2),
          Positioned(
            top: 7,
            right: 8,
            child: Container(
              width: 8,
              height: 8,
              decoration: BoxDecoration(
                color: const Color(0xFFF04452),
                shape: BoxShape.circle,
                border: Border.all(color: AppColor.line2, width: 2),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _TopTabs extends StatelessWidget {
  final int current;
  final ValueChanged<int> onTap;
  const _TopTabs({required this.current, required this.onTap});
  @override
  Widget build(BuildContext context) {
    const labels = ['달력', '거래 내역', '소비 분석'];
    return Container(
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: Color(0xFFEEF1F4))),
      ),
      child: Row(
        children: List.generate(3, (i) {
          final active = i == current;
          return Expanded(
            child: GestureDetector(
              behavior: HitTestBehavior.opaque,
              onTap: () => onTap(i),
              child: Container(
                padding: const EdgeInsets.only(top: 12, bottom: 13),
                decoration: BoxDecoration(
                  border: Border(
                    bottom: BorderSide(
                        color: active ? AppColor.blue : Colors.transparent,
                        width: 2.5),
                  ),
                ),
                child: Text(labels[i],
                    textAlign: TextAlign.center,
                    style: TextStyle(
                        fontSize: 14.5,
                        fontWeight: active ? FontWeight.w700 : FontWeight.w600,
                        color: active ? AppColor.ink : AppColor.faint)),
              ),
            ),
          );
        }),
      ),
    );
  }
}

class _CalendarGrid extends StatelessWidget {
  final int selectedDay;
  final ValueChanged<int> onSelect;
  const _CalendarGrid({required this.selectedDay, required this.onSelect});

  @override
  Widget build(BuildContext context) {
    const dowLabels = ['일', '월', '화', '수', '목', '금', '토'];
    final firstDow = DateTime(2025, 12, 1).weekday % 7; // 0=일
    final daysIn = DateTime(2025, 12 + 1, 0).day; // 31

    final cells = <Widget>[];
    for (int i = 0; i < firstDow; i++) {
      cells.add(const SizedBox.shrink());
    }
    for (int d = 1; d <= daysIn; d++) {
      final info = MockData.dayData[d];
      final sel = d == selectedDay;
      final wd = (firstDow + d - 1) % 7;
      Color numColor = AppColor.ink;
      if (wd == 0) numColor = AppColor.sunday;
      if (sel) numColor = AppColor.blue;

      cells.add(GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: () => onSelect(d),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 27,
              height: 27,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: sel ? AppColor.blueSoft : Colors.transparent,
                shape: BoxShape.circle,
              ),
              child: Text('$d',
                  style: TextStyle(
                      fontSize: 13.5, fontWeight: FontWeight.w600, color: numColor)),
            ),
            const SizedBox(height: 2),
            SizedBox(
              height: 9,
              child: Text(info?.spend != null && info!.spend > 0 ? '-${won(info.spend)}' : '',
                  style: const TextStyle(
                      fontSize: 8, height: 1.15, fontWeight: FontWeight.w600, color: AppColor.sub)),
            ),
            SizedBox(
              height: 9,
              child: Text(info?.income != null && info!.income > 0 ? '+${won(info.income)}' : '',
                  style: const TextStyle(
                      fontSize: 8, height: 1.15, fontWeight: FontWeight.w600, color: AppColor.blue)),
            ),
          ],
        ),
      ));
    }

    return Column(
      children: [
        // 요일 헤더
        Row(
          children: List.generate(7, (i) {
            Color c = AppColor.faint;
            if (i == 0) c = AppColor.sunday;
            if (i == 6) c = const Color(0xFF7BA0E8);
            return Expanded(
              child: Text(dowLabels[i],
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 12, fontWeight: FontWeight.w500, color: c)),
            );
          }),
        ),
        const SizedBox(height: 8),
        // 날짜 그리드
        GridView.count(
          crossAxisCount: 7,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          childAspectRatio: 0.72,
          mainAxisSpacing: 4,
          children: cells,
        ),
      ],
    );
  }
}

// AI 브리핑 카드 (딥네이비 그라디언트)
class _AiBriefingCard extends StatelessWidget {
  final String title, trailing, body;
  const _AiBriefingCard(
      {required this.title, required this.trailing, required this.body});
  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFF1E2A54), Color(0xFF2E3E7E), Color(0xFF3A4FA0)],
          stops: [0.0, 0.55, 1.0],
        ),
      ),
      padding: const EdgeInsets.fromLTRB(18, 17, 18, 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 22,
                height: 22,
                decoration: BoxDecoration(
                    color: Colors.white.withOpacity(0.14),
                    borderRadius: BorderRadius.circular(7)),
                child: const Icon(Icons.auto_awesome, size: 13, color: Color(0xFFBFD0FF)),
              ),
              const SizedBox(width: 8),
              Text(title,
                  style: const TextStyle(
                      fontSize: 12.5, fontWeight: FontWeight.w700, color: Color(0xFFEAF0FF))),
              const Spacer(),
              Text(trailing,
                  style: TextStyle(
                      fontSize: 11, fontWeight: FontWeight.w600, color: Colors.white.withOpacity(0.55))),
            ],
          ),
          const SizedBox(height: 10),
          Text(body,
              style: const TextStyle(
                  fontSize: 14.5, height: 1.55, fontWeight: FontWeight.w500, color: Color(0xFFF4F7FF))),
        ],
      ),
    );
  }
}

// 흰 카드 컨테이너 + 내부 리스트
class _CardList extends StatelessWidget {
  final List<Widget> children;
  const _CardList({required this.children});
  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: AppColor.line),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Column(children: children),
    );
  }
}

// 거래 한 줄 (타임라인 아이템)
class _TxRow extends StatelessWidget {
  final Tx tx;
  final bool last;
  const _TxRow({required this.tx, required this.last});
  @override
  Widget build(BuildContext context) {
    final c = catColor(tx.catKey);
    final expense = tx.amount < 0;
    return Container(
      decoration: BoxDecoration(
        border: last ? null : const Border(bottom: BorderSide(color: AppColor.line2)),
      ),
      padding: const EdgeInsets.symmetric(vertical: 13),
      child: Row(
        children: [
          _InitialBox(text: tx.initial, color: c),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(tx.merchant,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                        fontSize: 14.5, fontWeight: FontWeight.w600, color: AppColor.ink)),
                const SizedBox(height: 4),
                Row(
                  children: [
                    Text(tx.time,
                        style: const TextStyle(
                            fontSize: 11.5, fontWeight: FontWeight.w500, color: AppColor.sub)),
                    const SizedBox(width: 6),
                    Container(width: 2, height: 2, decoration: const BoxDecoration(color: Color(0xFFC6CDD5), shape: BoxShape.circle)),
                    const SizedBox(width: 6),
                    _Tag(text: tx.category, color: c, bg: catTagBg(tx.catKey)),
                    const SizedBox(width: 6),
                    Text(tx.method,
                        style: const TextStyle(
                            fontSize: 10.5, fontWeight: FontWeight.w500, color: AppColor.faint)),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          Text('${expense ? '-' : '+'}${won(tx.amount)}원',
              style: TextStyle(
                  fontSize: 15.5,
                  fontWeight: FontWeight.w700,
                  letterSpacing: -0.3,
                  color: expense ? AppColor.ink : AppColor.blue)),
        ],
      ),
    );
  }
}

class _InitialBox extends StatelessWidget {
  final String text;
  final Color color;
  final double size;
  const _InitialBox({required this.text, required this.color, this.size = 38});
  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      alignment: Alignment.center,
      decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(size * 0.3)),
      child: Text(text,
          style: TextStyle(
              fontSize: size * 0.34, fontWeight: FontWeight.w700, color: Colors.white)),
    );
  }
}

class _Tag extends StatelessWidget {
  final String text;
  final Color color, bg;
  const _Tag({required this.text, required this.color, required this.bg});
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(5)),
      child: Text(text,
          style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: color)),
    );
  }
}

// 자동 감지 (축소형)
class _AutoDetectCompact extends StatelessWidget {
  final List<PendingTx> pending;
  final VoidCallback onSimulate;
  final ValueChanged<int> onConfirm, onEdit, onRemove;
  const _AutoDetectCompact({
    required this.pending,
    required this.onSimulate,
    required this.onConfirm,
    required this.onEdit,
    required this.onRemove,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: const Color(0xFFF7F9FF),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFFE3EAFB)),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      child: Column(
        children: [
          Row(
            children: [
              Container(width: 8, height: 8, decoration: const BoxDecoration(color: AppColor.blue, shape: BoxShape.circle)),
              const SizedBox(width: 8),
              const Text('결제 알림 자동 감지',
                  style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: AppColor.ink)),
              const SizedBox(width: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(color: AppColor.blueSoft, borderRadius: BorderRadius.circular(20)),
                child: Text('${pending.length}건',
                    style: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.w600, color: AppColor.blue)),
              ),
              const Spacer(),
              GestureDetector(
                onTap: onSimulate,
                child: Row(
                  children: const [
                    Text('시뮬레이션',
                        style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: AppColor.sub)),
                    Icon(Icons.chevron_right, size: 14, color: AppColor.faint),
                  ],
                ),
              ),
            ],
          ),
          for (final p in pending) _PendingRow(
            p: p,
            onConfirm: () => onConfirm(p.id),
            onEdit: () => onEdit(p.id),
            onRemove: () => onRemove(p.id),
          ),
        ],
      ),
    );
  }
}

class _PendingRow extends StatelessWidget {
  final PendingTx p;
  final VoidCallback onConfirm, onEdit, onRemove;
  const _PendingRow({required this.p, required this.onConfirm, required this.onEdit, required this.onRemove});

  @override
  Widget build(BuildContext context) {
    final c = catColor(p.catKey);
    final badge = p.review
        ? '확인 필요'
        : (p.confidence >= 95 ? '자동 분류' : 'AI ${p.confidence}%');
    final badgeColor = p.review ? AppColor.warn : const Color(0xFF1FA463);
    final badgeBg = p.review ? const Color(0xFFFFF1E8) : const Color(0xFF1FA463).withOpacity(0.10);
    return Container(
      margin: const EdgeInsets.only(top: 11),
      padding: const EdgeInsets.only(top: 11),
      decoration: const BoxDecoration(
        border: Border(top: BorderSide(color: Color(0xFFE7EDFA))),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InitialBox(text: p.initial, color: c, size: 30),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(p.merchant,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w600, color: AppColor.ink)),
                const SizedBox(height: 4),
                Row(
                  children: [
                    _Tag(text: p.category, color: c, bg: catTagBg(p.catKey)),
                    const SizedBox(width: 5),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
                      decoration: BoxDecoration(color: badgeBg, borderRadius: BorderRadius.circular(5)),
                      child: Text(badge,
                          style: TextStyle(fontSize: 10.5, fontWeight: FontWeight.w600, color: badgeColor)),
                    ),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text('-${won(p.amount)}원',
                  style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: AppColor.ink)),
              const SizedBox(height: 6),
              Row(
                children: [
                  _MiniBtn(label: '확정', filled: true, onTap: onConfirm),
                  const SizedBox(width: 5),
                  _MiniBtn(label: '수정', onTap: onEdit),
                  const SizedBox(width: 5),
                  _MiniBtn(label: '삭제', muted: true, onTap: onRemove),
                ],
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _MiniBtn extends StatelessWidget {
  final String label;
  final bool filled, muted;
  final VoidCallback onTap;
  const _MiniBtn({required this.label, this.filled = false, this.muted = false, required this.onTap});
  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: EdgeInsets.symmetric(horizontal: filled ? 11 : 9, vertical: 5),
        decoration: BoxDecoration(
          color: filled ? AppColor.blue : Colors.white,
          borderRadius: BorderRadius.circular(8),
          border: filled ? null : Border.all(color: const Color(0xFFDCE3EC)),
        ),
        child: Text(label,
            style: TextStyle(
                fontSize: 11.5,
                fontWeight: filled ? FontWeight.w700 : FontWeight.w600,
                color: filled ? Colors.white : (muted ? AppColor.sub : AppColor.ink2))),
      ),
    );
  }
}

class _BudgetAlertBanner extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppColor.warnBg,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColor.warnBorder),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      child: Row(
        children: [
          Container(
            width: 32,
            height: 32,
            decoration: BoxDecoration(color: const Color(0xFFFFEADD), borderRadius: BorderRadius.circular(9)),
            child: const Icon(Icons.warning_amber_rounded, size: 18, color: AppColor.warn),
          ),
          const SizedBox(width: 11),
          Expanded(
            child: Text.rich(TextSpan(
              style: const TextStyle(fontSize: 12.5, height: 1.35, fontWeight: FontWeight.w600, color: AppColor.ink),
              children: const [
                TextSpan(text: '이번 달 '),
                TextSpan(text: '카페', style: TextStyle(fontWeight: FontWeight.w700)),
                TextSpan(text: ' 예산의 '),
                TextSpan(text: '84%', style: TextStyle(fontWeight: FontWeight.w700, color: AppColor.warn)),
                TextSpan(text: '를 사용했어요'),
              ],
            )),
          ),
          const Icon(Icons.chevron_right, size: 18, color: Color(0xFFE0B79A)),
        ],
      ),
    );
  }
}

// ============================================================================
//  화면 2 — 소비 리포트 (월간 분석)
// ============================================================================
class ReportScreen extends StatelessWidget {
  const ReportScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final categories = [
      ('식비', 81000, 34, 'food'),
      ('쇼핑', 50000, 21, 'shop'),
      ('카페', 43000, 18, 'cafe'),
      ('교통', 29000, 12, 'trans'),
      ('구독', 17000, 7, 'sub'),
    ];
    final budgets = [
      ('카페', 84, '42,000 / 50,000', true),
      ('식비', 62, '81,000 / 130,000', false),
      ('쇼핑', 48, '50,000 / 105,000', false),
    ];

    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        scrolledUnderElevation: 0,
        foregroundColor: AppColor.ink,
        title: const Text('소비 리포트',
            style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: AppColor.ink)),
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(20, 4, 20, 40),
        children: [
          // 헤더
          Padding(
            padding: const EdgeInsets.fromLTRB(4, 6, 4, 16),
            child: Row(
              children: const [
                Text('2025년 12월',
                    style: TextStyle(fontSize: 24, fontWeight: FontWeight.w700, letterSpacing: -0.4, color: AppColor.ink)),
                SizedBox(width: 4),
                Icon(Icons.keyboard_arrow_down, size: 22, color: AppColor.ink),
              ],
            ),
          ),

          // 기간 세그먼트
          _Segmented(),
          const SizedBox(height: 16),

          // 잔액 요약
          Container(
            decoration: BoxDecoration(color: AppColor.fill, borderRadius: BorderRadius.circular(22)),
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('이번 달 잔액',
                    style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppColor.ink3)),
                const SizedBox(height: 16),
                Text.rich(TextSpan(children: const [
                  TextSpan(text: '261,500', style: TextStyle(fontSize: 32, fontWeight: FontWeight.w700, letterSpacing: -0.6, color: AppColor.ink)),
                  TextSpan(text: ' 원', style: TextStyle(fontSize: 19, fontWeight: FontWeight.w600, color: AppColor.ink)),
                ])),
                const SizedBox(height: 18),
                Row(
                  children: const [
                    Expanded(child: _MiniStat(label: '지출', value: '238,500', color: AppColor.ink)),
                    SizedBox(width: 10),
                    Expanded(child: _MiniStat(label: '수입', value: '500,000', color: AppColor.blue)),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 14),

          // 카테고리별 소비
          _Section(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: const [
                    Text('카테고리별 소비', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: AppColor.ink)),
                    Spacer(),
                    Text('총 220,000원', style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600, color: AppColor.sub)),
                  ],
                ),
                const SizedBox(height: 16),
                ClipRRect(
                  borderRadius: BorderRadius.circular(7),
                  child: SizedBox(
                    height: 12,
                    child: Row(
                      children: [
                        for (final c in categories)
                          Expanded(flex: c.$3, child: Container(color: catColor(c.$4))),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 20),
                for (int i = 0; i < categories.length; i++)
                  _CategoryRow(
                    name: categories[i].$1,
                    amount: categories[i].$2,
                    pct: categories[i].$3,
                    catKey: categories[i].$4,
                    last: i == categories.length - 1,
                  ),
              ],
            ),
          ),
          const SizedBox(height: 14),

          // 예산 사용률
          _Section(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('예산 사용률', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: AppColor.ink)),
                const SizedBox(height: 16),
                for (final b in budgets)
                  _BudgetBar(name: b.$1, pct: b.$2, detail: b.$3, over: b.$4),
              ],
            ),
          ),
          const SizedBox(height: 14),

          // 반복 결제 상세
          _Section(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: const [
                    Text('반복 결제 · 고정지출', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: AppColor.ink)),
                    Spacer(),
                    Text('월 86,000원', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: AppColor.ink)),
                  ],
                ),
                const SizedBox(height: 4),
                for (int i = 0; i < MockData.recurring.length; i++)
                  _RecurringRow(r: MockData.recurring[i], last: i == MockData.recurring.length - 1),
              ],
            ),
          ),
          const SizedBox(height: 14),

          // 월간 AI 브리핑
          const _AiBriefingCard(
            title: '12월 AI 소비 브리핑',
            trailing: '',
            body: '이번 달은 식비와 카페 소비가 가장 많았어요. 특히 일정이 많은 날 교통비와 카페 지출이 함께 늘어나는 패턴이 보여요. 바쁜 주에는 미리 커피 쿠폰을 챙겨두면 도움이 될 거예요.',
          ),
        ],
      ),
    );
  }
}

class _Segmented extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    const labels = ['주간', '월간', '연간'];
    const selected = 1;
    return Container(
      decoration: BoxDecoration(color: AppColor.line2, borderRadius: BorderRadius.circular(13)),
      padding: const EdgeInsets.all(4),
      child: Row(
        children: List.generate(3, (i) {
          final active = i == selected;
          return Expanded(
            child: Container(
              padding: const EdgeInsets.symmetric(vertical: 9),
              decoration: BoxDecoration(
                color: active ? Colors.white : Colors.transparent,
                borderRadius: BorderRadius.circular(10),
                boxShadow: active
                    ? [BoxShadow(color: Colors.black.withOpacity(0.08), blurRadius: 3, offset: const Offset(0, 1))]
                    : null,
              ),
              child: Text(labels[i],
                  textAlign: TextAlign.center,
                  style: TextStyle(
                      fontSize: 13,
                      fontWeight: active ? FontWeight.w700 : FontWeight.w600,
                      color: active ? AppColor.ink : AppColor.sub)),
            ),
          );
        }),
      ),
    );
  }
}

class _MiniStat extends StatelessWidget {
  final String label, value;
  final Color color;
  const _MiniStat({required this.label, required this.value, required this.color});
  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(14)),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 13),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w500, color: AppColor.sub)),
          const SizedBox(height: 6),
          Text(value, style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, letterSpacing: -0.3, color: color)),
        ],
      ),
    );
  }
}

class _Section extends StatelessWidget {
  final Widget child;
  const _Section({required this.child});
  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: AppColor.line),
      ),
      padding: const EdgeInsets.all(20),
      child: child,
    );
  }
}

class _CategoryRow extends StatelessWidget {
  final String name, catKey;
  final int amount, pct;
  final bool last;
  const _CategoryRow({required this.name, required this.amount, required this.pct, required this.catKey, required this.last});
  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        border: last ? null : const Border(bottom: BorderSide(color: Color(0xFFF5F7FA))),
      ),
      padding: const EdgeInsets.symmetric(vertical: 9),
      child: Row(
        children: [
          Container(width: 10, height: 10, decoration: BoxDecoration(color: catColor(catKey), borderRadius: BorderRadius.circular(3))),
          const SizedBox(width: 11),
          Expanded(child: Text(name, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: Color(0xFF333D4B)))),
          Text('$pct%', style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppColor.sub)),
          const SizedBox(width: 12),
          SizedBox(
            width: 66,
            child: Text('${won(amount)}원',
                textAlign: TextAlign.right,
                style: const TextStyle(fontSize: 14.5, fontWeight: FontWeight.w700, letterSpacing: -0.3, color: AppColor.ink)),
          ),
        ],
      ),
    );
  }
}

class _BudgetBar extends StatelessWidget {
  final String name, detail;
  final int pct;
  final bool over;
  const _BudgetBar({required this.name, required this.pct, required this.detail, required this.over});
  @override
  Widget build(BuildContext context) {
    final barColor = over ? AppColor.warn : AppColor.blue;
    return Padding(
      padding: const EdgeInsets.only(bottom: 18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.baseline,
            textBaseline: TextBaseline.alphabetic,
            children: [
              Text(name, style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w600, color: Color(0xFF333D4B))),
              const Spacer(),
              Text('$pct%', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: over ? AppColor.warn : AppColor.ink)),
              const SizedBox(width: 6),
              Text(detail, style: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.w500, color: AppColor.faint)),
            ],
          ),
          const SizedBox(height: 8),
          ClipRRect(
            borderRadius: BorderRadius.circular(5),
            child: LinearProgressIndicator(
              value: pct / 100,
              minHeight: 8,
              backgroundColor: AppColor.line2,
              valueColor: AlwaysStoppedAnimation(barColor),
            ),
          ),
        ],
      ),
    );
  }
}

class _RecurringRow extends StatelessWidget {
  final Recurring r;
  final bool last;
  const _RecurringRow({required this.r, required this.last});
  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        border: last ? null : const Border(bottom: BorderSide(color: Color(0xFFF5F7FA))),
      ),
      padding: const EdgeInsets.symmetric(vertical: 13),
      child: Row(
        children: [
          _InitialBox(text: r.initial, color: catColor(r.catKey)),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(r.name, style: const TextStyle(fontSize: 14.5, fontWeight: FontWeight.w600, color: AppColor.ink)),
                const SizedBox(height: 4),
                Text('${r.cycle} · ${r.cat}', style: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.w500, color: AppColor.sub)),
              ],
            ),
          ),
          Text('${won(r.amount)}원', style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700, letterSpacing: -0.3, color: AppColor.ink)),
        ],
      ),
    );
  }
}
