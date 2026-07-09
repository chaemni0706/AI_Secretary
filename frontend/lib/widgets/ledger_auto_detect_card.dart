import 'package:flutter/material.dart';
import '../models/ledger_models.dart';
import '../theme/app_theme.dart';
import '../theme/ledger_styles.dart';
import 'ledger_transaction_row.dart';

/// 결제 알림 자동 감지 카드. "시뮬레이션" 버튼으로 mock 결제를 추가하고,
/// 각 대기 거래를 [확정]/[수정]/[삭제] 할 수 있다.
class LedgerAutoDetectCard extends StatelessWidget {
  final List<PendingTx> pending;

  /// "금융 알림 보내기" 버튼 콜백(작성 다이얼로그 열기).
  final VoidCallback onSimulate;

  /// 등록 진행 중이면 버튼을 비활성화(중복 클릭 방지).
  final bool submitting;

  /// 콜백은 백엔드 transactionId 접근을 위해 PendingTx 전체를 넘긴다.
  final ValueChanged<PendingTx> onConfirm;
  final ValueChanged<PendingTx> onEdit;
  final ValueChanged<PendingTx> onRemove;

  const LedgerAutoDetectCard({
    super.key,
    required this.pending,
    required this.onSimulate,
    required this.onConfirm,
    required this.onEdit,
    required this.onRemove,
    this.submitting = false,
  });

  @override
  Widget build(BuildContext context) {
    // status 기반 안내 문구: 확인 필요 거래가 하나라도 있으면 그 문구를 우선한다.
    final hasReview = pending.any((p) => p.isNeedsReview);
    final statusMessage = pending.isEmpty
        ? null
        : (hasReview ? '확인이 필요한 거래예요' : '새 결제 내역을 감지했어요');

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
                onTap: submitting ? null : onSimulate,
                behavior: HitTestBehavior.opaque,
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                  decoration: BoxDecoration(
                    color: AppTheme.blue.withValues(alpha: submitting ? 0.4 : 1),
                    borderRadius: BorderRadius.circular(9),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      if (submitting)
                        const SizedBox(
                          width: 13,
                          height: 13,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            valueColor:
                                AlwaysStoppedAnimation<Color>(Colors.white),
                          ),
                        )
                      else
                        const Icon(Icons.bolt, size: 14, color: Colors.white),
                      const SizedBox(width: 4),
                      const Text(
                        '알림 보내기',
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
          else ...[
            if (statusMessage != null)
              Padding(
                padding: const EdgeInsets.only(top: 10),
                child: Align(
                  alignment: Alignment.centerLeft,
                  child: Text(
                    statusMessage,
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color: hasReview ? AppTheme.orange : AppTheme.blue,
                    ),
                  ),
                ),
              ),
            for (final p in pending)
              _PendingRow(
                pending: p,
                enabled: !submitting,
                onConfirm: () => onConfirm(p),
                onEdit: () => onEdit(p),
                onRemove: () => onRemove(p),
              ),
          ],
        ],
      ),
    );
  }
}

class _PendingRow extends StatelessWidget {
  final PendingTx pending;
  final bool enabled;
  final VoidCallback onConfirm;
  final VoidCallback onEdit;
  final VoidCallback onRemove;

  const _PendingRow({
    required this.pending,
    required this.onConfirm,
    required this.onEdit,
    required this.onRemove,
    this.enabled = true,
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
                  _MiniButton(
                      label: '확정',
                      filled: true,
                      enabled: enabled,
                      onTap: onConfirm),
                  const SizedBox(width: 5),
                  _MiniButton(label: '수정', enabled: enabled, onTap: onEdit),
                  const SizedBox(width: 5),
                  _MiniButton(
                      label: '삭제',
                      muted: true,
                      enabled: enabled,
                      onTap: onRemove),
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
  final bool enabled;
  final VoidCallback onTap;

  const _MiniButton({
    required this.label,
    this.filled = false,
    this.muted = false,
    this.enabled = true,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Opacity(
      opacity: enabled ? 1 : 0.45,
      child: GestureDetector(
        onTap: enabled ? onTap : null,
        behavior: HitTestBehavior.opaque,
        child: Container(
          padding:
              EdgeInsets.symmetric(horizontal: filled ? 11 : 9, vertical: 5),
          decoration: BoxDecoration(
            color: filled ? AppTheme.blue : Colors.white,
            borderRadius: BorderRadius.circular(8),
            border: filled ? null : Border.all(color: AppTheme.separator),
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
      ),
    );
  }
}
