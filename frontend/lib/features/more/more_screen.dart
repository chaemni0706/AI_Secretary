import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/routing/app_routes.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_dimens.dart';
import '../../core/utils/responsive_utils.dart';

class MoreScreen extends StatelessWidget {
  const MoreScreen({super.key});

  static const String _userName = '도경';

  @override
  Widget build(BuildContext context) {
    final bottomPadding = ResponsiveUtils.tabBottomPadding(context);

    return Scaffold(
      body: SafeArea(
        bottom: false, // 하단 인셋은 스크롤 padding 으로 직접 처리
        child: SingleChildScrollView(
          padding: EdgeInsets.fromLTRB(
            AppDimens.screenPadding,
            AppDimens.screenPadding,
            AppDimens.screenPadding,
            bottomPadding,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _buildHeader(context),
              const SizedBox(height: AppDimens.lg),
              _buildSummaryCard(context),
              const SizedBox(height: AppDimens.lg),
              _buildFeatureGrid(context),
              const SizedBox(height: AppDimens.lg),
              _buildReportAndQuick(context),
              const SizedBox(height: AppDimens.lg),
              _buildBottomMenu(context),
            ],
          ),
        ),
      ),
    );
  }

  // ── 상단 타이틀 + 우측 알림/캐릭터 ──
  Widget _buildHeader(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('전체', style: textTheme.headlineLarge),
              const SizedBox(height: AppDimens.xs),
              Text(
                '$_userName님을 위한 AI 생활 관리',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: textTheme.titleMedium?.copyWith(
                  color: AppColors.textSecondary,
                ),
              ),
            ],
          ),
        ),
        const SizedBox(width: AppDimens.sm),
        // 우측 아이콘 묶음 (고정 크기, 제목 영역과 분리되어 충돌 없음)
        Padding(
          padding: const EdgeInsets.only(top: AppDimens.xs),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(
                Icons.notifications_none_rounded,
                size: 28,
                color: AppColors.textPrimary,
              ),
              const SizedBox(width: AppDimens.sm),
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: AppColors.primarySoft,
                  borderRadius: BorderRadius.circular(AppDimens.radiusMd),
                ),
                alignment: Alignment.center,
                child: const Text('🌤️', style: TextStyle(fontSize: 24)),
              ),
            ],
          ),
        ),
      ],
    );
  }

  // ── 사용자 요약 카드 ──
  Widget _buildSummaryCard(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    return _SoftCard(
      child: Column(
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 72,
                height: 72,
                decoration: BoxDecoration(
                  color: AppColors.primarySoft,
                  borderRadius: BorderRadius.circular(AppDimens.radiusMd),
                ),
                alignment: Alignment.center,
                child: const Text('🌤️', style: TextStyle(fontSize: 38)),
              ),
              const SizedBox(width: AppDimens.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '안녕하세요, $_userName님! 👋',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: textTheme.titleMedium,
                    ),
                    const SizedBox(height: AppDimens.xs),
                    Text(
                      '이번 주 일정이 순조롭게 진행 중이에요.\n'
                      '오늘도 함께 똑똑한 하루를 만들어봐요!',
                      maxLines: 3,
                      overflow: TextOverflow.ellipsis,
                      style: textTheme.bodyMedium?.copyWith(height: 1.4),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const Divider(
            height: AppDimens.xl,
            thickness: 1,
            color: AppColors.divider,
          ),
          _buildSummaryStats(context),
        ],
      ),
    );
  }

  Widget _buildSummaryStats(BuildContext context) {
    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Expanded(
            child: _SummaryStat(
              icon: Icons.calendar_month_rounded,
              iconColor: AppColors.primary,
              value: '12',
              label: '이번 주 일정',
            ),
          ),
          const _StatDivider(),
          Expanded(
            child: _SummaryStat(
              icon: Icons.check_circle,
              iconColor: AppColors.priorityLow,
              value: '9',
              label: '이번 주 할 일',
            ),
          ),
          const _StatDivider(),
          Expanded(
            child: _SummaryStat(
              icon: Icons.star_rounded,
              iconColor: AppColors.primary,
              value: '91%',
              label: '일정 완료율',
            ),
          ),
        ],
      ),
    );
  }

  // ── 기능 카드 그리드 (좁으면 1열, 그 외 2열) ──
  Widget _buildFeatureGrid(BuildContext context) {
    final columns = ResponsiveUtils.responsiveCardColumns(context);

    final cards = <Widget>[
      _FeatureCard(
        icon: Icons.favorite_rounded,
        iconColor: AppColors.priorityHigh,
        title: '감정기반 생활코칭',
        subtitle: '감정 기록 기반 맞춤 코칭',
        onTap: () {},
      ),
      _FeatureCard(
        icon: Icons.account_balance_wallet_rounded,
        iconColor: AppColors.priorityLow,
        title: '소비패턴 분석',
        subtitle: '지출 흐름과 소비 습관 분석',
        onTap: () {},
      ),
      _FeatureCard(
        icon: Icons.chat_bubble_rounded,
        iconColor: AppColors.primary,
        title: '예약 문의 메시지 생성',
        subtitle: '병원 · 식당 · 예약 문의 문구 생성',
        onTap: () => context.push(AppRoutes.reservationMessage),
      ),
      _FeatureCard(
        icon: Icons.notifications_active_rounded,
        iconColor: AppColors.priorityNormal,
        title: '준비물 · 출발 알림',
        subtitle: '일정별 준비물과 출발 시간 안내',
        onTap: () {},
      ),
    ];

    if (columns == 1) {
      return Column(
        children: [
          for (int i = 0; i < cards.length; i++) ...[
            if (i > 0) const SizedBox(height: AppDimens.md),
            cards[i],
          ],
        ],
      );
    }

    return Column(
      children: [
        for (int i = 0; i < cards.length; i += 2) ...[
          if (i > 0) const SizedBox(height: AppDimens.md),
          IntrinsicHeight(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Expanded(child: cards[i]),
                const SizedBox(width: AppDimens.md),
                Expanded(
                  child: (i + 1 < cards.length)
                      ? cards[i + 1]
                      : const SizedBox(),
                ),
              ],
            ),
          ),
        ],
      ],
    );
  }

  // ── 이번 주 AI 리포트 + 자주 쓰는 기능 ──
  // 좁으면 세로 1열, 넓으면 좌우 2열(높이 맞춤)
  Widget _buildReportAndQuick(BuildContext context) {
    final isCompact = ResponsiveUtils.isCompactWidth(context);

    if (isCompact) {
      return Column(
        children: [
          _buildReportCard(context),
          const SizedBox(height: AppDimens.md),
          _buildQuickCard(context),
        ],
      );
    }

    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Expanded(child: _buildReportCard(context)),
          const SizedBox(width: AppDimens.md),
          Expanded(child: _buildQuickCard(context)),
        ],
      ),
    );
  }

  Widget _buildReportCard(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;

    Widget legend(Color color, String text) => Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Container(
                width: 8,
                height: 8,
                decoration:
                    BoxDecoration(color: color, shape: BoxShape.circle),
              ),
            ),
            const SizedBox(width: AppDimens.sm),
            Expanded(
              child: Text(
                text,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: textTheme.bodyMedium,
              ),
            ),
          ],
        );

    return _SoftCard(
      padding: const EdgeInsets.all(AppDimens.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  '이번 주 AI 리포트',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: textTheme.titleMedium,
                ),
              ),
              const Icon(Icons.chevron_right,
                  size: 20, color: AppColors.textSecondary),
            ],
          ),
          const SizedBox(height: AppDimens.md),
          legend(AppColors.primary, '일정 12개'),
          const SizedBox(height: AppDimens.sm),
          legend(AppColors.priorityLow, '할 일 9개'),
          const SizedBox(height: AppDimens.sm),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Padding(
                padding: const EdgeInsets.only(top: 6),
                child: Container(
                  width: 8,
                  height: 8,
                  decoration: const BoxDecoration(
                    color: AppColors.priorityNormal,
                    shape: BoxShape.circle,
                  ),
                ),
              ),
              const SizedBox(width: AppDimens.sm),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '가장 바쁜 날',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: textTheme.bodyMedium,
                    ),
                    Text(
                      '목요일',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: textTheme.bodyMedium?.copyWith(
                        color: AppColors.primary,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildQuickCard(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    return _SoftCard(
      padding: const EdgeInsets.all(AppDimens.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '자주 쓰는 기능',
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: textTheme.titleMedium,
          ),
          const SizedBox(height: AppDimens.md),
          _QuickButton(
            icon: Icons.chat_bubble_rounded,
            label: 'AI 채팅',
            color: AppColors.primary,
            onTap: () => context.go(AppRoutes.aiChat),
          ),
          const SizedBox(height: AppDimens.sm),
          _QuickButton(
            icon: Icons.event_available_rounded,
            label: '예약 후보 추천',
            color: AppColors.priorityLow,
            onTap: () => context.push(AppRoutes.reservationCandidate),
          ),
          const SizedBox(height: AppDimens.sm),
          _QuickButton(
            icon: Icons.chat_rounded,
            label: '메시지 생성',
            color: AppColors.categoryDinner,
            onTap: () => context.push(AppRoutes.reservationMessage),
          ),
        ],
      ),
    );
  }

  // ── 하단 메뉴 리스트 ──
  Widget _buildBottomMenu(BuildContext context) {
    return _SoftCard(
      padding: const EdgeInsets.symmetric(
        horizontal: AppDimens.lg,
        vertical: AppDimens.sm,
      ),
      child: Column(
        children: const [
          _MenuRow(icon: Icons.link_rounded, label: '연동 관리'),
          Divider(height: 1, thickness: 1, color: AppColors.divider),
          _MenuRow(icon: Icons.notifications_none_rounded, label: '알림 설정'),
          Divider(height: 1, thickness: 1, color: AppColors.divider),
          _MenuRow(icon: Icons.person_outline_rounded, label: '개인정보 관리'),
          Divider(height: 1, thickness: 1, color: AppColors.divider),
          _MenuRow(icon: Icons.settings_outlined, label: '앱 설정'),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────
//  내부 위젯
// ─────────────────────────────────────────────────────────────

class _SoftCard extends StatelessWidget {
  const _SoftCard({required this.child, this.padding});
  final Widget child;
  final EdgeInsets? padding;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: padding ?? const EdgeInsets.all(AppDimens.lg),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(AppDimens.radiusCard),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 16,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: child,
    );
  }
}

class _SummaryStat extends StatelessWidget {
  const _SummaryStat({
    required this.icon,
    required this.iconColor,
    required this.value,
    required this.label,
  });
  final IconData icon;
  final Color iconColor;
  final String value;
  final String label;

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Icon(icon, color: iconColor, size: 30),
        const SizedBox(height: AppDimens.sm),
        Text(
          value,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 2),
        Text(
          label,
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
          textAlign: TextAlign.center,
          style: textTheme.bodyMedium,
        ),
      ],
    );
  }
}

class _StatDivider extends StatelessWidget {
  const _StatDivider();
  @override
  Widget build(BuildContext context) {
    return const VerticalDivider(
      width: AppDimens.md,
      thickness: 1,
      color: AppColors.divider,
    );
  }
}

class _CircleIcon extends StatelessWidget {
  const _CircleIcon({required this.icon, required this.color, this.size = 44});
  final IconData icon;
  final Color color;
  final double size;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(color: color, shape: BoxShape.circle),
      alignment: Alignment.center,
      child: Icon(icon, color: Colors.white, size: size * 0.5),
    );
  }
}

/// 기능 카드 (탭 가능, 2열/1열 공용)
class _FeatureCard extends StatelessWidget {
  const _FeatureCard({
    required this.icon,
    required this.iconColor,
    required this.title,
    required this.subtitle,
    required this.onTap,
  });

  final IconData icon;
  final Color iconColor;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(AppDimens.radiusCard),
      child: _SoftCard(
        padding: const EdgeInsets.all(AppDimens.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _CircleIcon(icon: icon, color: iconColor),
                const Spacer(),
                const Icon(Icons.chevron_right,
                    size: 20, color: AppColors.textSecondary),
              ],
            ),
            const SizedBox(height: AppDimens.md),
            Text(
              title,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: textTheme.titleMedium,
            ),
            const SizedBox(height: AppDimens.xs),
            Text(
              subtitle,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: textTheme.bodyMedium,
            ),
          ],
        ),
      ),
    );
  }
}

/// 자주 쓰는 기능 버튼 (알약 형태)
class _QuickButton extends StatelessWidget {
  const _QuickButton({
    required this.icon,
    required this.label,
    required this.color,
    required this.onTap,
  });

  final IconData icon;
  final String label;
  final Color color;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(AppDimens.radiusFull),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(
          horizontal: AppDimens.md,
          vertical: AppDimens.md,
        ),
        decoration: BoxDecoration(
          color: color,
          borderRadius: BorderRadius.circular(AppDimens.radiusFull),
        ),
        child: Row(
          children: [
            Icon(icon, size: 18, color: Colors.white),
            const SizedBox(width: AppDimens.sm),
            Expanded(
              child: Text(
                label,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  color: Colors.white,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// 하단 메뉴 한 줄
class _MenuRow extends StatelessWidget {
  const _MenuRow({required this.icon, required this.label});
  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    return InkWell(
      onTap: () {},
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: AppDimens.md),
        child: Row(
          children: [
            Icon(icon, size: 22, color: AppColors.textSecondary),
            const SizedBox(width: AppDimens.md),
            Expanded(
              child: Text(
                label,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: textTheme.titleMedium,
              ),
            ),
            const Icon(Icons.chevron_right,
                size: 20, color: AppColors.textSecondary),
          ],
        ),
      ),
    );
  }
}