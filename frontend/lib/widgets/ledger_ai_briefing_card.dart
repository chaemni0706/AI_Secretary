import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../theme/ledger_styles.dart';

/// 시그니처 AI 브리핑 카드 (딥네이비/블루 그라디언트).
/// "단순 가계부가 아닌 AI 비서"라는 정체성을 표현한다. 홈·리포트에서 공유.
class LedgerAiBriefingCard extends StatelessWidget {
  final String title;
  final String trailing;
  final String body;

  const LedgerAiBriefingCard({
    super.key,
    required this.title,
    this.trailing = '',
    required this.body,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        gradient: LedgerStyles.briefingGradient,
        boxShadow: [
          BoxShadow(
            color: TossColors.blue700.withValues(alpha: 0.25),
            blurRadius: 20,
            offset: const Offset(0, 6),
          ),
        ],
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
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.14),
                  borderRadius: BorderRadius.circular(7),
                ),
                child: const Icon(
                  Icons.auto_awesome,
                  size: 13,
                  color: LedgerStyles.briefingIcon,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  title,
                  style: const TextStyle(
                    fontSize: 12.5,
                    fontWeight: FontWeight.w700,
                    color: LedgerStyles.briefingTitle,
                  ),
                ),
              ),
              if (trailing.isNotEmpty)
                Text(
                  trailing,
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    color: Colors.white.withValues(alpha: 0.55),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            body,
            style: const TextStyle(
              fontSize: 14.5,
              height: 1.55,
              fontWeight: FontWeight.w500,
              color: LedgerStyles.briefingBody,
            ),
          ),
        ],
      ),
    );
  }
}
