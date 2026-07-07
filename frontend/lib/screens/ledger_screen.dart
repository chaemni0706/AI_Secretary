import 'package:flutter/material.dart';
import '../models/ledger_models.dart';
import '../models/mock_ledger_data.dart';
import '../theme/app_constants.dart';
import '../theme/app_theme.dart';
import '../theme/ledger_styles.dart';
import '../widgets/app_top_actions.dart';
import '../widgets/budget_segmented_control.dart';
import '../widgets/glass_card.dart';
import '../widgets/ledger_ai_briefing_card.dart';
import '../widgets/ledger_auto_detect_card.dart';
import '../widgets/ledger_calendar_grid.dart';
import '../widgets/ledger_transaction_row.dart';
import 'ledger_report_screen.dart';

/// AI 가계부 메인 화면 — 소비 달력 홈.
/// 결제 알림 자동 감지 + AI 소비 브리핑을 mock 데이터 기반으로 보여준다.
class LedgerScreen extends StatefulWidget {
  const LedgerScreen({super.key});

  @override
  State<LedgerScreen> createState() => _LedgerScreenState();
}

class _LedgerScreenState extends State<LedgerScreen> {
  static const _dow = ['일', '월', '화', '수', '목', '금', '토'];

  int _selectedDay = MockLedgerData.defaultSelectedDay;
  int _topTab = 0;
  int _simIndex = 0;
  int _nextPendingId = 100;
  late final List<PendingTx> _pending = List.of(MockLedgerData.initialPending);
  late final PageController _pageController;

  @override
  void initState() {
    super.initState();
    _pageController = PageController(initialPage: _topTab);
  }

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  void _selectDay(int day) => setState(() => _selectedDay = day);

  void _simulate() {
    final template =
        MockLedgerData.simPool[_simIndex % MockLedgerData.simPool.length];
    setState(() {
      _simIndex++;
      _pending.insert(
        0,
        PendingTx(
          _nextPendingId++,
          template.merchant,
          template.initial,
          template.amount,
          template.category,
          template.catKey,
          template.method,
          template.review,
          template.confidence,
        ),
      );
    });
    _snack('${template.merchant} 결제 알림을 감지했어요.');
  }

  void _confirmPending(int id) {
    final tx = _pending.firstWhere((p) => p.id == id);
    setState(() => _pending.removeWhere((p) => p.id == id));
    _snack('${tx.merchant} 거래를 기록했어요.');
  }

  void _removePending(int id) {
    setState(() => _pending.removeWhere((p) => p.id == id));
  }

  void _editPending(int id) {
    setState(() {
      final i = _pending.indexWhere((p) => p.id == id);
      if (i >= 0) {
        _pending[i] = _pending[i].copyWith(
          method: '직접 수정',
          review: false,
          confidence: 100,
        );
      }
    });
  }

  void _openReport() => _onTabTap(2);

  void _snack(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: AppTheme.screenBackground,
      child: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
              child: _buildHeader(),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 14, 16, 0),
              child: BudgetSegmentedControl(
                selectedIndex: _topTab,
                labels: const ['달력', '거래내역', '소비 리포트'],
                onChanged: _onTabTap,
              ),
            ),
            const SizedBox(height: 10),
            Expanded(
              child: PageView(
                controller: _pageController,
                onPageChanged: (index) => setState(() => _topTab = index),
                children: [
                  _LedgerPage(children: _buildCalendarView()),
                  _LedgerPage(children: _buildListView()),
                  const LedgerReportContent(
                    padding: EdgeInsets.fromLTRB(16, 4, 16, 28),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _onTabTap(int index) {
    setState(() => _topTab = index);
    _pageController.animateToPage(
      index,
      duration: const Duration(milliseconds: 240),
      curve: Curves.easeOutCubic,
    );
  }

  Widget _buildHeader() {
    return Row(
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '가계부',
                style: AppTextStyles.screenTitle.copyWith(
                  color: AppTheme.textPrimary,
                ),
              ),
              Text(
                '${MockLedgerData.month}월 소비 흐름 · AI 자동 기록',
                style: AppTextStyles.meta.copyWith(
                  color: AppTheme.textSecondary,
                ),
              ),
            ],
          ),
        ),
        const AppTopActions(),
      ],
    );
  }

  Widget _buildMonthSummary() {
    return GlassCard(
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 16),
      onTap: _openReport,
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _SummaryLine(
                  label: '지출',
                  value: LedgerStyles.formatWon(MockLedgerData.monthSpend),
                  color: AppTheme.textPrimary,
                ),
                const SizedBox(height: 9),
                _SummaryLine(
                  label: '수입',
                  value: LedgerStyles.formatWon(MockLedgerData.monthIncome),
                  color: AppTheme.blue,
                ),
              ],
            ),
          ),
          const Icon(Icons.chevron_right, color: AppTheme.textSecondary),
        ],
      ),
    );
  }

  List<Widget> _buildCalendarView() {
    final info = MockLedgerData.dayData[_selectedDay] ?? const DayInfo();
    final txs = MockLedgerData.txByDay[_selectedDay] ?? const <LedgerTx>[];
    final weekday =
        DateTime(
          MockLedgerData.year,
          MockLedgerData.month,
          _selectedDay,
        ).weekday %
        7;
    final selectedLabel =
        '${MockLedgerData.month}월 $_selectedDay일 · ${_dow[weekday]}요일';
    final briefing =
        MockLedgerData.briefingByDay[_selectedDay] ??
        MockLedgerData.fallbackBriefing(_selectedDay, info);

    return [
      LedgerAiBriefingCard(
        title: 'AI 소비 브리핑',
        trailing: '${MockLedgerData.month}월 $_selectedDay일',
        body: briefing,
      ),
      const SizedBox(height: 14),
      GlassCard(
        padding: const EdgeInsets.fromLTRB(14, 16, 14, 12),
        child: LedgerCalendarGrid(
          selectedDay: _selectedDay,
          onSelect: _selectDay,
        ),
      ),
      const SizedBox(height: 14),
      _buildMonthSummary(),
      const SizedBox(height: 14),
      Padding(
        padding: const EdgeInsets.symmetric(horizontal: 4),
        child: Row(
          children: [
            Text(
              selectedLabel,
              style: const TextStyle(
                fontSize: 15,
                fontWeight: FontWeight.w700,
                color: AppTheme.textPrimary,
              ),
            ),
            const Spacer(),
            Text(
              _dayTotalLabel(info),
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w600,
                color: _dayTotalColor(info),
              ),
            ),
          ],
        ),
      ),
      const SizedBox(height: 10),
      if (txs.isEmpty)
        const GlassCard(
          padding: EdgeInsets.symmetric(vertical: 24, horizontal: 16),
          child: Center(
            child: Text(
              '이 날은 기록된 소비가 없어요',
              style: TextStyle(fontSize: 13, color: AppTheme.textSecondary),
            ),
          ),
        )
      else
        GlassCard(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Column(
            children: [
              for (int i = 0; i < txs.length; i++)
                LedgerTransactionRow(
                  tx: txs[i],
                  showDivider: i != txs.length - 1,
                ),
            ],
          ),
        ),
      const SizedBox(height: 14),
      LedgerAutoDetectCard(
        pending: _pending,
        onSimulate: _simulate,
        onConfirm: _confirmPending,
        onEdit: _editPending,
        onRemove: _removePending,
      ),
      const SizedBox(height: 12),
      _BudgetAlertBanner(onTap: _openReport),
    ];
  }

  List<Widget> _buildListView() {
    final days = MockLedgerData.txByDay.keys.toList()
      ..sort((a, b) => b.compareTo(a));

    return [
      LedgerAutoDetectCard(
        pending: _pending,
        onSimulate: _simulate,
        onConfirm: _confirmPending,
        onEdit: _editPending,
        onRemove: _removePending,
      ),
      const SizedBox(height: 14),
      for (final day in days) ...[
        Padding(
          padding: const EdgeInsets.fromLTRB(4, 6, 4, 8),
          child: Text(
            '${MockLedgerData.month}월 $day일',
            style: const TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w700,
              color: AppTheme.textPrimary,
            ),
          ),
        ),
        GlassCard(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Column(
            children: [
              for (int i = 0; i < MockLedgerData.txByDay[day]!.length; i++)
                LedgerTransactionRow(
                  tx: MockLedgerData.txByDay[day]![i],
                  showDivider: i != MockLedgerData.txByDay[day]!.length - 1,
                ),
            ],
          ),
        ),
        const SizedBox(height: 12),
      ],
    ];
  }

  String _dayTotalLabel(DayInfo info) {
    if (info.spend > 0) return '지출 ${LedgerStyles.formatWon(info.spend)}원';
    if (info.income > 0) return '수입 ${LedgerStyles.formatWon(info.income)}원';
    return '소비 없음';
  }

  Color _dayTotalColor(DayInfo info) {
    if (info.spend > 0) return AppTheme.textPrimary;
    if (info.income > 0) return AppTheme.blue;
    return AppTheme.textSecondary;
  }
}

class _LedgerPage extends StatelessWidget {
  final List<Widget> children;

  const _LedgerPage({required this.children});

  @override
  Widget build(BuildContext context) {
    return ListView(
      physics: const AlwaysScrollableScrollPhysics(
        parent: BouncingScrollPhysics(),
      ),
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 28),
      children: children,
    );
  }
}

class _SummaryLine extends StatelessWidget {
  final String label;
  final String value;
  final Color color;

  const _SummaryLine({
    required this.label,
    required this.value,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.baseline,
      textBaseline: TextBaseline.alphabetic,
      children: [
        SizedBox(
          width: 30,
          child: Text(
            label,
            style: const TextStyle(
              fontSize: 13.5,
              fontWeight: FontWeight.w600,
              color: AppTheme.textTertiary,
            ),
          ),
        ),
        const SizedBox(width: 12),
        Text.rich(
          TextSpan(
            children: [
              TextSpan(
                text: value,
                style: TextStyle(
                  fontSize: 17,
                  fontWeight: FontWeight.w700,
                  letterSpacing: -0.3,
                  color: color,
                ),
              ),
              TextSpan(
                text: ' 원',
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  color: color,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _BudgetAlertBanner extends StatelessWidget {
  final VoidCallback onTap;

  const _BudgetAlertBanner({required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: Container(
        decoration: BoxDecoration(
          color: AppTheme.orange.withValues(alpha: 0.10),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: AppTheme.orange.withValues(alpha: 0.28)),
        ),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        child: Row(
          children: [
            Container(
              width: 32,
              height: 32,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: AppTheme.orange.withValues(alpha: 0.18),
                borderRadius: BorderRadius.circular(9),
              ),
              child: const Icon(
                Icons.warning_amber_rounded,
                size: 18,
                color: AppTheme.orange,
              ),
            ),
            const SizedBox(width: 11),
            const Expanded(
              child: Text.rich(
                TextSpan(
                  style: TextStyle(
                    fontSize: 12.5,
                    height: 1.35,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.textPrimary,
                  ),
                  children: [
                    TextSpan(text: '이번 달 '),
                    TextSpan(
                      text: '카페',
                      style: TextStyle(fontWeight: FontWeight.w700),
                    ),
                    TextSpan(text: ' 예산의 '),
                    TextSpan(
                      text: '84%',
                      style: TextStyle(
                        fontWeight: FontWeight.w700,
                        color: AppTheme.orange,
                      ),
                    ),
                    TextSpan(text: '를 사용했어요'),
                  ],
                ),
              ),
            ),
            Icon(
              Icons.chevron_right,
              size: 18,
              color: AppTheme.orange.withValues(alpha: 0.7),
            ),
          ],
        ),
      ),
    );
  }
}
