import 'package:flutter/material.dart';
import '../../data/widget_catalog.dart';
import '../../models/dashboard_widget_model.dart';
import '../../models/ledger_api_models.dart';
import '../../models/ledger_mappers.dart';
import '../../models/ledger_models.dart';
import '../../models/mock_ledger_data.dart';
import '../../services/ledger_api.dart';
import '../../theme/app_theme.dart';
import '../../theme/ledger_styles.dart';
import 'dashboard_widget_card.dart';

/// 가계부 위젯 (Medium).
///
/// 이번 달 지출·대표 예산 사용률·상위 카테고리를 실제 `ledgerApi.report` 에서
/// 가져온다. 캐시가 있으면 즉시 그리고, 조회 실패/빈 달이면 mock 으로 폴백해
/// 위젯이 항상 무언가를 보여준다(레이아웃 점프 방지).
class BudgetWidget extends StatefulWidget {
  const BudgetWidget({super.key});

  @override
  State<BudgetWidget> createState() => _BudgetWidgetState();
}

class _BudgetWidgetState extends State<BudgetWidget> {
  // 폴백 기본값(mock). 실데이터가 오면 덮어쓴다.
  int _spend = MockLedgerData.monthSpend;
  BudgetStat _budget = MockLedgerData.reportBudgets.first;
  List<CategoryStat> _topCategories =
      MockLedgerData.reportCategories.take(2).toList();

  @override
  void initState() {
    super.initState();
    final now = DateTime.now();
    // 캐시가 있으면 즉시 반영.
    final cached = ledgerApi.cachedReport(year: now.year, month: now.month);
    if (cached != null) _apply(cached);
    // 서버 최신값으로 갱신(실패해도 폴백 유지).
    ledgerApi
        .report(year: now.year, month: now.month)
        .then(_apply)
        .catchError((_) {});
  }

  void _apply(LedgerReportDto report) {
    if (!mounted) return;
    final budgets = report.budgetStats();
    final cats = report.categoryStats();
    setState(() {
      if (report.totalExpense != 0) _spend = report.totalExpense;
      if (budgets.isNotEmpty) _budget = budgets.first;
      if (cats.isNotEmpty) _topCategories = cats.take(2).toList();
    });
  }

  @override
  Widget build(BuildContext context) {
    final spec = WidgetCatalog.of(DashboardWidgetType.budget);
    final budget = _budget;
    final topCategories = _topCategories;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        WidgetCardHeader(
          icon: spec.icon,
          accent: spec.accent,
          title: spec.title,
          showChevron: true,
        ),
        const SizedBox(height: 10),
        Text.rich(
          TextSpan(
            children: [
              const TextSpan(
                text: '이번 달 지출  ',
                style: TextStyle(
                  fontSize: 11.5,
                  fontWeight: FontWeight.w500,
                  color: AppTheme.textSecondary,
                ),
              ),
              TextSpan(
                text: '${LedgerStyles.formatWon(_spend)}원',
                style: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w700,
                  letterSpacing: -0.3,
                  color: AppTheme.textPrimary,
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 8),
        Row(
          children: [
            Expanded(
              child: ClipRRect(
                borderRadius: BorderRadius.circular(5),
                child: LinearProgressIndicator(
                  value: (budget.pct / 100).clamp(0.0, 1.0),
                  minHeight: 7,
                  backgroundColor: AppTheme.separator,
                  valueColor: AlwaysStoppedAnimation(
                    budget.over ? AppTheme.orange : spec.accent,
                  ),
                ),
              ),
            ),
            const SizedBox(width: 8),
            Text(
              '${budget.name} ${budget.pct}%',
              style: TextStyle(
                fontSize: 11.5,
                fontWeight: FontWeight.w700,
                color: budget.over ? AppTheme.orange : AppTheme.textPrimary,
              ),
            ),
          ],
        ),
        const Spacer(),
        Row(
          children: [
            for (final c in topCategories) ...[
              Container(
                width: 8,
                height: 8,
                decoration: BoxDecoration(
                  color: LedgerStyles.categoryColor(c.catKey),
                  borderRadius: BorderRadius.circular(2.5),
                ),
              ),
              const SizedBox(width: 5),
              Text(
                '${c.name} ${c.pct}%',
                style: const TextStyle(
                  fontSize: 11.5,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.textTertiary,
                ),
              ),
              const SizedBox(width: 12),
            ],
          ],
        ),
      ],
    );
  }
}
