import 'package:flutter/material.dart';
import '../models/ledger_models.dart';
import '../models/mock_ledger_data.dart';
import '../theme/app_theme.dart';
import '../theme/ledger_styles.dart';
import '../widgets/ledger_ai_briefing_card.dart';
import '../widgets/ledger_transaction_row.dart';

/// 소비 리포트 — 월간 분석 화면.
/// 카테고리별 지출 / 예산 사용률 / 반복 결제 / AI 분석 문장을 mock 데이터로 보여준다.
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
        body: SafeArea(
          top: false,
          child: ListView(
            physics: const AlwaysScrollableScrollPhysics(
              parent: BouncingScrollPhysics(),
            ),
            padding: const EdgeInsets.fromLTRB(16, 4, 16, 40),
            children: const [
              _ReportHeader(),
              SizedBox(height: 14),
              _PeriodSegment(),
              SizedBox(height: 14),
              _BalanceCard(),
              SizedBox(height: 14),
              _CategorySection(),
              SizedBox(height: 14),
              _BudgetSection(),
              SizedBox(height: 14),
              _RecurringSection(),
              SizedBox(height: 14),
              LedgerAiBriefingCard(
                title: '${MockLedgerData.month}월 AI 소비 브리핑',
                body: MockLedgerData.monthlyBriefing,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ReportHeader extends StatelessWidget {
  const _ReportHeader();

  @override
  Widget build(BuildContext context) {
    return const Padding(
      padding: EdgeInsets.fromLTRB(4, 6, 4, 0),
      child: Row(
        children: [
          Text(
            '${MockLedgerData.year}년 ${MockLedgerData.month}월',
            style: TextStyle(
              fontSize: 24,
              fontWeight: FontWeight.w700,
              letterSpacing: -0.4,
              color: AppTheme.textPrimary,
            ),
          ),
          SizedBox(width: 4),
          Icon(Icons.keyboard_arrow_down, size: 22, color: AppTheme.textPrimary),
        ],
      ),
    );
  }
}

/// 기간 세그먼트 (주간/월간/연간) — 월간 고정 표시.
class _PeriodSegment extends StatelessWidget {
  const _PeriodSegment();

  static const _labels = ['주간', '월간', '연간'];
  static const _selected = 1;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.55),
        borderRadius: BorderRadius.circular(13),
        border: Border.all(color: AppTheme.separator.withValues(alpha: 0.7)),
      ),
      padding: const EdgeInsets.all(4),
      child: Row(
        children: List.generate(3, (i) {
          final active = i == _selected;
          return Expanded(
            child: Container(
              padding: const EdgeInsets.symmetric(vertical: 9),
              decoration: BoxDecoration(
                color: active ? Colors.white : Colors.transparent,
                borderRadius: BorderRadius.circular(10),
                boxShadow: active
                    ? [
                        BoxShadow(
                          color: Colors.black.withValues(alpha: 0.08),
                          blurRadius: 3,
                          offset: const Offset(0, 1),
                        ),
                      ]
                    : null,
              ),
              child: Text(
                _labels[i],
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: active ? FontWeight.w700 : FontWeight.w600,
                  color: active ? AppTheme.textPrimary : AppTheme.textSecondary,
                ),
              ),
            ),
          );
        }),
      ),
    );
  }
}

/// 잔액 요약 카드.
class _BalanceCard extends StatelessWidget {
  const _BalanceCard();

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.72),
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: Colors.white.withValues(alpha: 0.55)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 14,
            offset: const Offset(0, 4),
          ),
        ],
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
                  text: LedgerStyles.formatWon(MockLedgerData.reportBalance),
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
                  value: LedgerStyles.formatWon(MockLedgerData.reportSpend),
                  color: AppTheme.textPrimary,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: _MiniStat(
                  label: '수입',
                  value: LedgerStyles.formatWon(MockLedgerData.reportIncome),
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
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 14,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      padding: const EdgeInsets.all(20),
      child: child,
    );
  }
}

class _CategorySection extends StatelessWidget {
  const _CategorySection();

  @override
  Widget build(BuildContext context) {
    final categories = MockLedgerData.reportCategories;
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
                '총 ${LedgerStyles.formatWon(MockLedgerData.reportCategoryTotal)}원',
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
                      flex: c.pct,
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
            _CategoryRow(
              stat: categories[i],
              last: i == categories.length - 1,
            ),
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
  const _BudgetSection();

  @override
  Widget build(BuildContext context) {
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
          for (final b in MockLedgerData.reportBudgets) _BudgetBar(stat: b),
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
  const _RecurringSection();

  @override
  Widget build(BuildContext context) {
    final recurring = MockLedgerData.recurring;
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
                '월 ${LedgerStyles.formatWon(MockLedgerData.reportRecurringTotal)}원',
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
            _RecurringRow(
              item: recurring[i],
              last: i == recurring.length - 1,
            ),
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
