import 'package:flutter/material.dart';
import '../models/ledger_models.dart';
import '../theme/app_theme.dart';
import '../theme/ledger_styles.dart';

/// 거래 카테고리를 보여주는 세로 컬러 바.
class TransactionCategoryBar extends StatelessWidget {
  final Color color;
  final double height;

  const TransactionCategoryBar({
    super.key,
    required this.color,
    this.height = 48,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 4,
      height: height,
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(999),
      ),
    );
  }
}

/// 카테고리 색 배경 + 한글 이니셜 아바타. 대기 거래/반복 결제에서 사용한다.
class LedgerInitialAvatar extends StatelessWidget {
  final String text;
  final Color color;
  final double size;

  const LedgerInitialAvatar({
    super.key,
    required this.text,
    required this.color,
    this.size = 38,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(size * 0.3),
      ),
      child: Text(
        text,
        style: TextStyle(
          fontSize: size * 0.34,
          fontWeight: FontWeight.w700,
          color: Colors.white,
        ),
      ),
    );
  }
}

/// 카테고리 태그 pill.
class LedgerCategoryTag extends StatelessWidget {
  final String label;
  final String catKey;

  const LedgerCategoryTag({
    super.key,
    required this.label,
    required this.catKey,
  });

  @override
  Widget build(BuildContext context) {
    final color = LedgerStyles.categoryColor(catKey);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
      decoration: BoxDecoration(
        color: LedgerStyles.categoryTagBg(catKey),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w600,
          color: color,
        ),
      ),
    );
  }
}

/// 확정 거래 한 줄 (카테고리 바 + 상호명 + 메타 + 금액).
class LedgerTransactionRow extends StatelessWidget {
  final LedgerTx tx;
  final bool showDivider;

  const LedgerTransactionRow({
    super.key,
    required this.tx,
    this.showDivider = true,
  });

  @override
  Widget build(BuildContext context) {
    final color = LedgerStyles.categoryColor(tx.catKey);
    return Container(
      decoration: showDivider
          ? BoxDecoration(
              border: Border(
                bottom: BorderSide(
                  color: AppTheme.separator.withValues(alpha: 0.7),
                ),
              ),
            )
          : null,
      padding: const EdgeInsets.symmetric(vertical: 13),
      child: Row(
        children: [
          TransactionCategoryBar(color: color),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  tx.merchant,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    fontSize: 14.5,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.textPrimary,
                  ),
                ),
                const SizedBox(height: 4),
                Row(
                  children: [
                    Text(
                      tx.time,
                      style: const TextStyle(
                        fontSize: 11.5,
                        fontWeight: FontWeight.w500,
                        color: AppTheme.textSecondary,
                      ),
                    ),
                    const SizedBox(width: 6),
                    LedgerCategoryTag(label: tx.category, catKey: tx.catKey),
                    const SizedBox(width: 6),
                    Flexible(
                      child: Text(
                        tx.method,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          fontSize: 10.5,
                          fontWeight: FontWeight.w500,
                          color: AppTheme.textSecondary,
                        ),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          Text(
            LedgerStyles.signedWon(tx.amount),
            style: TextStyle(
              fontSize: 15.5,
              fontWeight: FontWeight.w700,
              letterSpacing: -0.3,
              color: tx.isExpense ? AppTheme.textPrimary : AppTheme.blue,
            ),
          ),
        ],
      ),
    );
  }
}
