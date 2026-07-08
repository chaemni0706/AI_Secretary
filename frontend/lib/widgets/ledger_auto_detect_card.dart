import 'package:flutter/material.dart';
import '../models/ledger_models.dart';
import '../theme/app_theme.dart';
import '../theme/ledger_styles.dart';
import 'ledger_transaction_row.dart';

/// 결제 알림 자동 감지 카드. "시뮬레이션" 버튼으로 mock 결제를 추가하고,
/// 각 대기 거래를 [확정]/[수정]/[삭제] 할 수 있다.
class LedgerAutoDetectCard extends StatelessWidget {
  final List<PendingTx> pending;
  final VoidCallback onSimulate;
  final ValueChanged<int> onConfirm;
  final ValueChanged<int> onEdit;
  final ValueChanged<int> onRemove;

  const LedgerAutoDetectCard({
    super.key,
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
        color: AppTheme.blue.withValues(alpha: 0.06),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.blue.withValues(alpha: 0.18)),
        boxShadow: TossShadow.tiny,
      ),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      child: Column(
        children: [
          Row(
            children: [
              Container(
                width: 8,
                height: 8,
                decoration: const BoxDecoration(
                  color: AppTheme.blue,
                  shape: BoxShape.circle,
                ),
              ),
              const SizedBox(width: 8),
              const Text(
                '결제 알림 자동 감지',
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w700,
                  color: AppTheme.textPrimary,
                ),
              ),
              const SizedBox(width: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: AppTheme.blue.withValues(alpha: 0.14),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Text(
                  '${pending.length}건',
                  style: const TextStyle(
                    fontSize: 11.5,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.blue,
                  ),
                ),
              ),
              const Spacer(),
              GestureDetector(
                onTap: onSimulate,
                behavior: HitTestBehavior.opaque,
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                  decoration: BoxDecoration(
                    color: AppTheme.blue,
                    borderRadius: BorderRadius.circular(9),
                  ),
                  child: const Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.bolt, size: 14, color: Colors.white),
                      SizedBox(width: 3),
                      Text(
                        '시뮬레이션',
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w700,
                          color: Colors.white,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
          if (pending.isEmpty)
            const Padding(
              padding: EdgeInsets.only(top: 14),
              child: Text(
                '대기 중인 결제 알림이 없어요. 시뮬레이션으로 새 결제를 감지해보세요.',
                style: TextStyle(
                  fontSize: 12.5,
                  fontWeight: FontWeight.w500,
                  color: AppTheme.textSecondary,
                ),
              ),
            )
          else
            for (final p in pending)
              _PendingRow(
                pending: p,
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
  final PendingTx pending;
  final VoidCallback onConfirm;
  final VoidCallback onEdit;
  final VoidCallback onRemove;

  const _PendingRow({
    required this.pending,
    required this.onConfirm,
    required this.onEdit,
    required this.onRemove,
  });

  @override
  Widget build(BuildContext context) {
    final color = LedgerStyles.categoryColor(pending.catKey);
    final badge = LedgerStyles.pendingBadgeLabel(
      review: pending.review,
      confidence: pending.confidence,
    );
    final badgeColor = LedgerStyles.pendingBadgeColor(pending.review);

    return Container(
      margin: const EdgeInsets.only(top: 11),
      padding: const EdgeInsets.only(top: 11),
      decoration: BoxDecoration(
        border: Border(
          top: BorderSide(color: AppTheme.blue.withValues(alpha: 0.12)),
        ),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          LedgerInitialAvatar(text: pending.initial, color: color, size: 30),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  pending.merchant,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    fontSize: 13.5,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.textPrimary,
                  ),
                ),
                const SizedBox(height: 4),
                Row(
                  children: [
                    LedgerCategoryTag(
                      label: pending.category,
                      catKey: pending.catKey,
                    ),
                    const SizedBox(width: 5),
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 6,
                        vertical: 3,
                      ),
                      decoration: BoxDecoration(
                        color: badgeColor.withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        badge,
                        style: TextStyle(
                          fontSize: 10.5,
                          fontWeight: FontWeight.w600,
                          color: badgeColor,
                        ),
                      ),
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
              Text(
                LedgerStyles.signedWon(pending.amount),
                style: const TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w700,
                  color: AppTheme.textPrimary,
                ),
              ),
              const SizedBox(height: 6),
              Row(
                children: [
                  _MiniButton(label: '확정', filled: true, onTap: onConfirm),
                  const SizedBox(width: 5),
                  _MiniButton(label: '수정', onTap: onEdit),
                  const SizedBox(width: 5),
                  _MiniButton(label: '삭제', muted: true, onTap: onRemove),
                ],
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _MiniButton extends StatelessWidget {
  final String label;
  final bool filled;
  final bool muted;
  final VoidCallback onTap;

  const _MiniButton({
    required this.label,
    this.filled = false,
    this.muted = false,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: Container(
        padding: EdgeInsets.symmetric(horizontal: filled ? 11 : 9, vertical: 5),
        decoration: BoxDecoration(
          color: filled ? AppTheme.blue : Colors.white,
          borderRadius: BorderRadius.circular(8),
          border: filled
              ? null
              : Border.all(color: AppTheme.separator),
        ),
        child: Text(
          label,
          style: TextStyle(
            fontSize: 11.5,
            fontWeight: filled ? FontWeight.w700 : FontWeight.w600,
            color: filled
                ? Colors.white
                : (muted ? AppTheme.textSecondary : AppTheme.textPrimary),
          ),
        ),
      ),
    );
  }
}
