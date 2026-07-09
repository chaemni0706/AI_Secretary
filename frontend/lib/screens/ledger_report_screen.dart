import 'package:flutter/material.dart';
import '../models/ledger_api_models.dart';
import '../models/ledger_mappers.dart';
import '../models/ledger_models.dart';
import '../models/mock_ledger_data.dart';
import '../services/api_client.dart';
import '../services/ledger_api.dart';
import '../theme/app_theme.dart';
import '../theme/ledger_styles.dart';
import '../widgets/ledger_ai_briefing_card.dart';
import '../widgets/ledger_transaction_row.dart';

/// 소비 리포트 — 월간 분석 화면 (API-first).
/// 백엔드 GET /ledger/report 응답 기반으로 렌더링하며, 서버 연결 실패 시에만
/// MockLedgerData 리포트로 fallback 한다.
class LedgerReportScreen extends StatelessWidget {
  const LedgerReportScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: AppTheme.screenBackground,
      child: Scaffold(
        backgroundColor: Colors.transparent,
        appBar: AppBar(
          title: const Text('소비 리포트'),
          leading: const BackButton(),
        ),
        body: const SafeArea(top: false, child: LedgerReportContent()),
      ),
    );
  }
}

class LedgerReportContent extends StatefulWidget {
  final EdgeInsetsGeometry padding;

  /// 부모(탭 컨테이너)가 관리하는 표시 월. null 이면 현재 월(standalone).
  final DateTime? focusedMonth;

  /// 홈에서 거래 mutation이 성공할 때마다 증가. 값이 바뀌면 stale 로 간주한다.
  final int refreshToken;

  /// 이 리포트 탭이 현재 활성(보이는) 상태인지. 비활성일 땐 조용히 stale 마킹만 한다.
  final bool isActive;

  /// 리포트 내부 월 이동 시 부모에 알려 월을 동기화한다(단일 source of truth).
  final ValueChanged<DateTime>? onMonthChanged;

  const LedgerReportContent({
    super.key,
    this.padding = const EdgeInsets.fromLTRB(16, 4, 16, 40),
    this.focusedMonth,
    this.refreshToken = 0,
    this.isActive = true,
    this.onMonthChanged,
  });

  @override
  State<LedgerReportContent> createState() => _LedgerReportContentState();
}

class _LedgerReportContentState extends State<LedgerReportContent> {
  static const _userId = 'local-user';

  bool _loading = true;
  bool _usingFallback = false;
  String? _errorMessage;
  late DateTime _focusedMonth;
  LedgerReportDto? _report;

  bool get _usingApi => !_usingFallback && _report != null;

  /// 마지막으로 로드한 refreshToken(중복/무한 재조회 방지용).
  int? _loadedForToken;

  @override
  void initState() {
    super.initState();
    final base = widget.focusedMonth ?? DateTime.now();
    _focusedMonth = DateTime(base.year, base.month);
    _loadReport();
  }

  @override
  void didUpdateWidget(covariant LedgerReportContent oldWidget) {
    super.didUpdateWidget(oldWidget);

    // 1) 부모 월 동기화(달라졌을 때만). _focusedMonth 는 즉시 갱신해 재진입 시 중복 판정.
    final incoming = widget.focusedMonth;
    final monthChanged = incoming != null &&
        (incoming.year != _focusedMonth.year ||
            incoming.month != _focusedMonth.month);
    if (monthChanged) {
      _focusedMonth = DateTime(incoming.year, incoming.month);
    }

    // 2) refreshToken 변경 또는 비활성→활성 전환 시, stale(마지막 로드 토큰과 다름)일 때만 재조회.
    final becameActive = widget.isActive && !oldWidget.isActive;
    final tokenChanged = widget.refreshToken != oldWidget.refreshToken;
    final needTokenRefresh = widget.isActive &&
        (tokenChanged || becameActive) &&
        widget.refreshToken != _loadedForToken;

    // build/업데이트 도중 setState 를 피하기 위해 프레임 이후에 로드한다(무한 루프 방지:
    // _focusedMonth/_loadedForToken 을 이미 갱신 기준으로 비교하므로 동일 상태면 재호출 안 됨).
    if (monthChanged || needTokenRefresh) {
      final silent = !monthChanged; // 월 변경은 로더 표시, 토큰/활성 전환만이면 silent
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _loadReport(silent: silent);
      });
    }
  }

  Future<void> _loadReport({bool silent = false}) async {
    // 이번 로드가 커버하는 refreshToken 을 먼저 기록해 중복 호출을 막는다.
    _loadedForToken = widget.refreshToken;
    setState(() {
      if (!silent) _loading = true;
      _errorMessage = null;
    });
    try {
      final dto = await ledgerApi.report(
        userId: _userId,
        year: _focusedMonth.year,
        month: _focusedMonth.month,
      );
      if (!mounted) return;
      setState(() {
        _report = dto;
        _usingFallback = false;
        _errorMessage = null;
        _loading = false;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      if (e.isNetworkError) {
        setState(() {
          _usingFallback = true;
          _report = null;
          _errorMessage = null;
          _loading = false;
        });
      } else {
        setState(() {
          _errorMessage = e.message;
          _loading = false;
        });
      }
    } on FormatException catch (e) {
      if (!mounted) return;
      setState(() {
        _errorMessage = '응답 형식 오류: ${e.message}';
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _errorMessage = '알 수 없는 오류가 발생했어요.';
        _loading = false;
      });
    }
  }

  void _onChangeMonth(int delta) {
    final next = DateTime(_focusedMonth.year, _focusedMonth.month + delta);
    setState(() => _focusedMonth = next);
    // 부모(홈)와 월을 동기화. 부모가 같은 월을 되돌려줘도 didUpdateWidget 가
    // 월 동일로 판단해 중복 재조회하지 않는다.
    widget.onMonthChanged?.call(next);
    _loadReport();
  }

  /// API DTO 또는 Mock 에서 화면에 필요한 값 묶음을 만든다.
  _ReportVM _vm() {
    final year = _focusedMonth.year;
    final month = _focusedMonth.month;
    if (_usingApi) {
      final r = _report!;
      final body = r.briefingBody ?? '$month월 소비 리포트예요.';
      return _ReportVM(
        year: year,
        month: month,
        balance: r.balance,
        spend: r.totalExpense,
        income: r.totalIncome,
        categories: r.categoryStats(),
        categoryTotal: r.categoryTotal,
        budgets: r.budgetStats(),
        recurring: r.recurringItems(),
        recurringTotal: r.recurringTotal,
        briefingTitle: '$month월 AI 소비 브리핑',
        briefingBody: body,
      );
    }
    // 오프라인 fallback: 라벨은 현재 월, 수치는 demo 데이터셋을 사용한다.
    return _ReportVM(
      year: year,
      month: month,
      balance: MockLedgerData.reportBalance,
      spend: MockLedgerData.reportSpend,
      income: MockLedgerData.reportIncome,
      categories: MockLedgerData.reportCategories,
      categoryTotal: MockLedgerData.reportCategoryTotal,
      budgets: MockLedgerData.reportBudgets,
      recurring: MockLedgerData.recurring,
      recurringTotal: MockLedgerData.reportRecurringTotal,
      briefingTitle: '$month월 AI 소비 브리핑',
      briefingBody: MockLedgerData.monthlyBriefing,
    );
  }

  @override
  Widget build(BuildContext context) {
    if (_loading && _report == null && !_usingFallback) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_errorMessage != null && _report == null && !_usingFallback) {
      return _buildErrorView();
    }

    final vm = _vm();
    return RefreshIndicator(
      onRefresh: _loadReport,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(
          parent: BouncingScrollPhysics(),
        ),
        padding: widget.padding,
        children: [
          if (_usingFallback) const _FallbackBadge(),
          if (_usingFallback) const SizedBox(height: 12),
          _ReportHeader(
            year: vm.year,
            month: vm.month,
            onPrev: () => _onChangeMonth(-1),
            onNext: () => _onChangeMonth(1),
          ),
          const SizedBox(height: 14),
          _BalanceCard(balance: vm.balance, spend: vm.spend, income: vm.income),
          const SizedBox(height: 14),
          _CategorySection(categories: vm.categories, total: vm.categoryTotal),
          const SizedBox(height: 14),
          _BudgetSection(budgets: vm.budgets),
          const SizedBox(height: 14),
          _RecurringSection(
              recurring: vm.recurring, total: vm.recurringTotal),
          const SizedBox(height: 14),
          LedgerAiBriefingCard(
            title: vm.briefingTitle,
            body: vm.briefingBody,
          ),
        ],
      ),
    );
  }

  Widget _buildErrorView() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.cloud_off_rounded,
                size: 40, color: AppTheme.textSecondary),
            const SizedBox(height: 12),
            Text(
              _errorMessage ?? '리포트를 불러오지 못했어요.',
              textAlign: TextAlign.center,
              style: const TextStyle(
                  fontSize: 14, color: AppTheme.textSecondary),
            ),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: _loadReport,
              child: const Text('다시 시도'),
            ),
          ],
        ),
      ),
    );
  }
}

/// 화면 렌더링에 필요한 값 묶음(뷰모델).
class _ReportVM {
  final int year;
  final int month;
  final int balance;
  final int spend;
  final int income;
  final List<CategoryStat> categories;
  final int categoryTotal;
  final List<BudgetStat> budgets;
  final List<RecurringPayment> recurring;
  final int recurringTotal;
  final String briefingTitle;
  final String briefingBody;

  const _ReportVM({
    required this.year,
    required this.month,
    required this.balance,
    required this.spend,
    required this.income,
    required this.categories,
    required this.categoryTotal,
    required this.budgets,
    required this.recurring,
    required this.recurringTotal,
    required this.briefingTitle,
    required this.briefingBody,
  });
}

class _FallbackBadge extends StatelessWidget {
  const _FallbackBadge();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
      decoration: BoxDecoration(
        color: TossColors.orangeWeak,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: const [
          Icon(Icons.wifi_off_rounded, size: 14, color: AppTheme.orange),
          SizedBox(width: 6),
          Expanded(
            child: Text(
              '오프라인 데모 리포트 · 서버 연결 시 실제 데이터로 전환돼요',
              style: TextStyle(
                fontSize: 11.5,
                fontWeight: FontWeight.w600,
                color: AppTheme.orange,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ReportHeader extends StatelessWidget {
  final int year;
  final int month;
  final VoidCallback onPrev;
  final VoidCallback onNext;

  const _ReportHeader({
    required this.year,
    required this.month,
    required this.onPrev,
    required this.onNext,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(4, 6, 4, 0),
      child: Row(
        children: [
          GestureDetector(
            onTap: onPrev,
            behavior: HitTestBehavior.opaque,
            child: const Icon(Icons.chevron_left,
                size: 24, color: AppTheme.textSecondary),
          ),
          const SizedBox(width: 4),
          Text(
            '$year년 $month월',
            style: const TextStyle(
              fontSize: 24,
              fontWeight: FontWeight.w700,
              letterSpacing: -0.4,
              color: AppTheme.textPrimary,
            ),
          ),
          const SizedBox(width: 4),
          GestureDetector(
            onTap: onNext,
            behavior: HitTestBehavior.opaque,
            child: const Icon(Icons.chevron_right,
                size: 24, color: AppTheme.textSecondary),
          ),
        ],
      ),
    );
  }
}

/// 잔액 요약 카드.
class _BalanceCard extends StatelessWidget {
  final int balance;
  final int spend;
  final int income;

  const _BalanceCard({
    required this.balance,
    required this.spend,
    required this.income,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.72),
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: Colors.white.withValues(alpha: 0.55)),
        boxShadow: TossShadow.weak,
      ),
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '이번 달 잔액',
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w600,
              color: AppTheme.textTertiary,
            ),
          ),
          const SizedBox(height: 16),
          Text.rich(
            TextSpan(
              children: [
                TextSpan(
                  text: LedgerStyles.formatWon(balance),
                  style: const TextStyle(
                    fontSize: 32,
                    fontWeight: FontWeight.w700,
                    letterSpacing: -0.6,
                    color: AppTheme.textPrimary,
                  ),
                ),
                const TextSpan(
                  text: ' 원',
                  style: TextStyle(
                    fontSize: 19,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.textPrimary,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 18),
          Row(
            children: [
              Expanded(
                child: _MiniStat(
                  label: '지출',
                  value: LedgerStyles.formatWon(spend),
                  color: AppTheme.textPrimary,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: _MiniStat(
                  label: '수입',
                  value: LedgerStyles.formatWon(income),
                  color: AppTheme.blue,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _MiniStat extends StatelessWidget {
  final String label;
  final String value;
  final Color color;

  const _MiniStat({
    required this.label,
    required this.value,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 13),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: const TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w500,
              color: AppTheme.textSecondary,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            value,
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w700,
              letterSpacing: -0.3,
              color: color,
            ),
          ),
        ],
      ),
    );
  }
}

/// 흰 섹션 카드 컨테이너.
class _SectionCard extends StatelessWidget {
  final Widget child;

  const _SectionCard({required this.child});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.72),
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: Colors.white.withValues(alpha: 0.55)),
        boxShadow: TossShadow.weak,
      ),
      padding: const EdgeInsets.all(20),
      child: child,
    );
  }
}

class _CategorySection extends StatelessWidget {
  final List<CategoryStat> categories;
  final int total;

  const _CategorySection({required this.categories, required this.total});

  @override
  Widget build(BuildContext context) {
    if (categories.isEmpty) {
      return const _SectionCard(
        child: Text(
          '이번 달 카테고리별 소비 내역이 아직 없어요.',
          style: TextStyle(fontSize: 13, color: AppTheme.textSecondary),
        ),
      );
    }
    return _SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Text(
                '카테고리별 소비',
                style: TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w700,
                  color: AppTheme.textPrimary,
                ),
              ),
              const Spacer(),
              Text(
                '총 ${LedgerStyles.formatWon(total)}원',
                style: const TextStyle(
                  fontSize: 12.5,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.textSecondary,
                ),
              ),
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
                    Expanded(
                      flex: c.pct <= 0 ? 1 : c.pct,
                      child: Container(
                        color: LedgerStyles.categoryColor(c.catKey),
                      ),
                    ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 20),
          for (int i = 0; i < categories.length; i++)
            _CategoryRow(stat: categories[i], last: i == categories.length - 1),
        ],
      ),
    );
  }
}

class _CategoryRow extends StatelessWidget {
  final CategoryStat stat;
  final bool last;

  const _CategoryRow({required this.stat, required this.last});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: last
          ? null
          : BoxDecoration(
              border: Border(
                bottom: BorderSide(
                  color: AppTheme.separator.withValues(alpha: 0.6),
                ),
              ),
            ),
      padding: const EdgeInsets.symmetric(vertical: 9),
      child: Row(
        children: [
          Container(
            width: 10,
            height: 10,
            decoration: BoxDecoration(
              color: LedgerStyles.categoryColor(stat.catKey),
              borderRadius: BorderRadius.circular(3),
            ),
          ),
          const SizedBox(width: 11),
          Expanded(
            child: Text(
              stat.name,
              style: const TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w600,
                color: AppTheme.textPrimary,
              ),
            ),
          ),
          Text(
            '${stat.pct}%',
            style: const TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w600,
              color: AppTheme.textSecondary,
            ),
          ),
          const SizedBox(width: 12),
          SizedBox(
            width: 70,
            child: Text(
              '${LedgerStyles.formatWon(stat.amount)}원',
              textAlign: TextAlign.right,
              style: const TextStyle(
                fontSize: 14.5,
                fontWeight: FontWeight.w700,
                letterSpacing: -0.3,
                color: AppTheme.textPrimary,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _BudgetSection extends StatelessWidget {
  final List<BudgetStat> budgets;

  const _BudgetSection({required this.budgets});

  @override
  Widget build(BuildContext context) {
    if (budgets.isEmpty) {
      return const _SectionCard(
        child: Text(
          '설정된 예산이 아직 없어요.',
          style: TextStyle(fontSize: 13, color: AppTheme.textSecondary),
        ),
      );
    }
    return _SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '예산 사용률',
            style: TextStyle(
              fontSize: 15,
              fontWeight: FontWeight.w700,
              color: AppTheme.textPrimary,
            ),
          ),
          const SizedBox(height: 16),
          for (final b in budgets) _BudgetBar(stat: b),
        ],
      ),
    );
  }
}

class _BudgetBar extends StatelessWidget {
  final BudgetStat stat;

  const _BudgetBar({required this.stat});

  @override
  Widget build(BuildContext context) {
    final barColor = stat.over ? AppTheme.orange : AppTheme.blue;
    return Padding(
      padding: const EdgeInsets.only(bottom: 18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.baseline,
            textBaseline: TextBaseline.alphabetic,
            children: [
              Text(
                stat.name,
                style: const TextStyle(
                  fontSize: 13.5,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.textPrimary,
                ),
              ),
              const Spacer(),
              Text(
                '${stat.pct}%',
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w700,
                  color: stat.over ? AppTheme.orange : AppTheme.textPrimary,
                ),
              ),
              const SizedBox(width: 6),
              Text(
                stat.detail,
                style: const TextStyle(
                  fontSize: 11.5,
                  fontWeight: FontWeight.w500,
                  color: AppTheme.textSecondary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          ClipRRect(
            borderRadius: BorderRadius.circular(5),
            child: LinearProgressIndicator(
              value: (stat.pct / 100).clamp(0.0, 1.0),
              minHeight: 8,
              backgroundColor: AppTheme.separator,
              valueColor: AlwaysStoppedAnimation(barColor),
            ),
          ),
        ],
      ),
    );
  }
}

class _RecurringSection extends StatelessWidget {
  final List<RecurringPayment> recurring;
  final int total;

  const _RecurringSection({required this.recurring, required this.total});

  @override
  Widget build(BuildContext context) {
    if (recurring.isEmpty) {
      return const _SectionCard(
        child: Text(
          '감지된 반복 결제가 아직 없어요.',
          style: TextStyle(fontSize: 13, color: AppTheme.textSecondary),
        ),
      );
    }
    return _SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Text(
                '반복 결제 · 고정지출',
                style: TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w700,
                  color: AppTheme.textPrimary,
                ),
              ),
              const Spacer(),
              Text(
                '월 ${LedgerStyles.formatWon(total)}원',
                style: const TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w700,
                  color: AppTheme.textPrimary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          for (int i = 0; i < recurring.length; i++)
            _RecurringRow(item: recurring[i], last: i == recurring.length - 1),
        ],
      ),
    );
  }
}

class _RecurringRow extends StatelessWidget {
  final RecurringPayment item;
  final bool last;

  const _RecurringRow({required this.item, required this.last});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: last
          ? null
          : BoxDecoration(
              border: Border(
                bottom: BorderSide(
                  color: AppTheme.separator.withValues(alpha: 0.6),
                ),
              ),
            ),
      padding: const EdgeInsets.symmetric(vertical: 13),
      child: Row(
        children: [
          LedgerInitialAvatar(
            text: item.initial,
            color: LedgerStyles.categoryColor(item.catKey),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  item.name,
                  style: const TextStyle(
                    fontSize: 14.5,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.textPrimary,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  '${item.cycle} · ${item.category}',
                  style: const TextStyle(
                    fontSize: 11.5,
                    fontWeight: FontWeight.w500,
                    color: AppTheme.textSecondary,
                  ),
                ),
              ],
            ),
          ),
          Text(
            '${LedgerStyles.formatWon(item.amount)}원',
            style: const TextStyle(
              fontSize: 15,
              fontWeight: FontWeight.w700,
              letterSpacing: -0.3,
              color: AppTheme.textPrimary,
            ),
          ),
        ],
      ),
    );
  }
}
