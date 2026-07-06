import 'package:flutter/material.dart';
import '../../data/widget_catalog.dart';
import '../../models/dashboard_widget_model.dart';
import '../../models/mock_ledger_data.dart';
import '../../theme/app_theme.dart';
import '../../theme/ledger_styles.dart';
import 'dashboard_widget_card.dart';

/// 가계부 위젯 (Medium).
/// 현재 가계부가 mock 기반이므로 [MockLedgerData] 를 재사용한다.
/// 가계부 데이터가 실데이터로 바뀌면 동일 소스를 그대로 참조하면 반영됨.
class BudgetWidget extends StatelessWidget {
  const BudgetWidget({super.key});

  @override
  Widget build(BuildContext context) {
    final spec = WidgetCatalog.of(DashboardWidgetType.budget);
    // 대표 예산(카페) 사용률 + 상위 카테고리 2개.
    final budget = MockLedgerData.reportBudgets.first;
    final topCategories = MockLedgerData.reportCategories.take(2).toList();

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
                text: '${LedgerStyles.formatWon(MockLedgerData.monthSpend)}원',
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
