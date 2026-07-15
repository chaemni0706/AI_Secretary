import 'package:flutter/material.dart';
import '../../data/widget_catalog.dart';
import '../../data/widget_mock_data.dart';
import '../../models/dashboard_widget_model.dart';
import '../../models/ledger_api_models.dart';
import '../../models/ledger_mappers.dart';
import '../../services/ledger_api.dart';
import '../../theme/app_theme.dart';
import 'dashboard_widget_card.dart';

/// 소비 분석 위젯 (Medium).
///
/// 최다 카테고리·AI 코멘트는 `ledgerApi.report`, 전월 대비 증감은 이번 달/지난 달
/// 지출을 비교해 계산한다. 캐시가 있으면 즉시 그리고, 실패/빈 달이면 mock 으로
/// 폴백한다.
class SpendingAnalysisWidget extends StatefulWidget {
  const SpendingAnalysisWidget({super.key});

  @override
  State<SpendingAnalysisWidget> createState() => _SpendingAnalysisWidgetState();
}

class _SpendingAnalysisWidgetState extends State<SpendingAnalysisWidget> {
  late String _topCategory = WidgetMockData.spendingInsight.topCategory;
  late num _changePercent = WidgetMockData.spendingInsight.changePercent;
  late String _comment = WidgetMockData.spendingInsight.comment;

  @override
  void initState() {
    super.initState();
    final now = DateTime.now();
    final prev = DateTime(now.year, now.month - 1);
    final cached = ledgerApi.cachedReport(year: now.year, month: now.month);
    if (cached != null) _applyThisMonth(cached);
    ledgerApi
        .report(year: now.year, month: now.month)
        .then((r) {
          _applyThisMonth(r);
          // 전월 대비: 지난 달 지출과 비교(캐시/dedup 재사용).
          ledgerApi
              .report(year: prev.year, month: prev.month)
              .then((p) => _applyDelta(r.totalExpense, p.totalExpense))
              .catchError((_) {});
        })
        .catchError((_) {});
  }

  void _applyThisMonth(LedgerReportDto r) {
    if (!mounted) return;
    final cats = r.categoryStats();
    setState(() {
      if (cats.isNotEmpty) _topCategory = cats.first.name;
      final b = r.briefingBody;
      if (b != null && b.trim().isNotEmpty) _comment = b;
    });
  }

  void _applyDelta(int thisExpense, int prevExpense) {
    if (!mounted || prevExpense <= 0) return;
    setState(() {
      _changePercent =
          (((thisExpense - prevExpense) / prevExpense) * 100).round();
    });
  }

  @override
  Widget build(BuildContext context) {
    final spec = WidgetCatalog.of(DashboardWidgetType.spendingAnalysis);
    final topCategory = _topCategory;
    final changePercent = _changePercent;
    final comment = _comment;
    final up = changePercent >= 0;

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
        Row(
          children: [
            _Chip(label: '최다 $topCategory', color: spec.accent),
            const SizedBox(width: 6),
            _Chip(
              label: '전월 대비 ${up ? '+' : '-'}${changePercent.abs()}%',
              color: up ? AppTheme.red : AppTheme.green,
              icon: up ? Icons.trending_up : Icons.trending_down,
            ),
          ],
        ),
        const Spacer(),
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(Icons.auto_awesome, size: 14, color: spec.accent),
            const SizedBox(width: 6),
            Expanded(
              child: Text(
                comment,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  fontSize: 12,
                  height: 1.35,
                  fontWeight: FontWeight.w500,
                  color: AppTheme.textTertiary,
                ),
              ),
            ),
          ],
        ),
      ],
    );
  }
}

class _Chip extends StatelessWidget {
  final String label;
  final Color color;
  final IconData? icon;

  const _Chip({required this.label, required this.color, this.icon});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(9),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, size: 13, color: color),
            const SizedBox(width: 4),
          ],
          Text(
            label,
            style: TextStyle(
              fontSize: 11.5,
              fontWeight: FontWeight.w700,
              color: color,
            ),
          ),
        ],
      ),
    );
  }
}
