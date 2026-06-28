import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/theme/app_colors.dart';
import '../../core/theme/app_dimens.dart';
import '../../core/utils/responsive_utils.dart';
import '../../data/models/todo_model.dart';
import '../../data/repositories/todo_repository.dart';
import 'todo_view_model.dart';

class TodoScreen extends StatelessWidget {
  const TodoScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider(
      create: (_) => TodoViewModel(repository: MockTodoRepository()),
      child: const _TodoView(),
    );
  }
}

class _TodoView extends StatelessWidget {
  const _TodoView();

  @override
  Widget build(BuildContext context) {
    final bottomPadding = ResponsiveUtils.tabBottomPadding(context);
    final vm = context.watch<TodoViewModel>();

    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: vm.isLoading
            ? const Center(child: CircularProgressIndicator())
            : SingleChildScrollView(
                padding: EdgeInsets.fromLTRB(
                  AppDimens.screenPadding,
                  AppDimens.screenPadding,
                  AppDimens.screenPadding,
                  bottomPadding,
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _buildHeader(context, vm.userName),
                    const SizedBox(height: AppDimens.lg),
                    _buildSummaryCard(context, vm.summary!),
                    const SizedBox(height: AppDimens.lg),
                    _buildFeatureGrid(context, vm.summary!),
                    const SizedBox(height: AppDimens.lg),
                    _buildTodoListCard(context, vm),
                    const SizedBox(height: AppDimens.lg),
                    _buildMenuCard(context),
                  ],
                ),
              ),
      ),
    );
  }

  Widget _buildHeader(BuildContext context, String userName) {
    final textTheme = Theme.of(context).textTheme;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('할 일', style: textTheme.headlineLarge),
        const SizedBox(height: AppDimens.xs),
        Text(
          '$userName님을 위한 AI 할 일 관리',
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: textTheme.titleMedium?.copyWith(
            color: AppColors.textSecondary,
          ),
        ),
      ],
    );
  }

  Widget _buildSummaryCard(BuildContext context, TodoSummary summary) {
    final textTheme = Theme.of(context).textTheme;

    return _SoftCard(
      child: Column(
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 64,
                height: 64,
                decoration: BoxDecoration(
                  color: AppColors.primarySoft,
                  borderRadius: BorderRadius.circular(AppDimens.radiusMd),
                ),
                alignment: Alignment.center,
                child: const Text('🌤️', style: TextStyle(fontSize: 34)),
              ),
              const SizedBox(width: AppDimens.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '오늘 할 일도 차근차근 진행 중이에요.',
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: textTheme.titleMedium,
                    ),
                    const SizedBox(height: AppDimens.xs),
                    Text(
                      '마감 전에 필요한 준비물까지 챙겨드릴게요!',
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: textTheme.bodyMedium,
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
          _buildSummaryStats(context, summary),
        ],
      ),
    );
  }

  Widget _buildSummaryStats(BuildContext context, TodoSummary summary) {
    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Expanded(
            child: _SummaryStat(
              leading: _MiniProgressRing(percent: summary.progressPercent),
              label: '진행률',
              value: '${summary.progressPercent}%',
            ),
          ),
          const _StatDivider(),
          Expanded(
            child: _SummaryStat(
              leading: const _CircleIcon(
                icon: Icons.check_circle,
                color: AppColors.priorityLow,
              ),
              label: '완료',
              value: '${summary.completedCount}',
            ),
          ),
          const _StatDivider(),
          Expanded(
            child: _SummaryStat(
              leading: const _CircleIcon(
                icon: Icons.assignment_outlined,
                color: AppColors.primary,
              ),
              label: '남은 할 일',
              value: '${summary.remainingCount}',
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFeatureGrid(BuildContext context, TodoSummary summary) {
    final columns = ResponsiveUtils.responsiveCardColumns(context);

    final cards = <Widget>[
      _FeatureCard(
        icon: Icons.bar_chart_rounded,
        iconColor: AppColors.primary,
        title: '진행률',
        subtitle: '오늘 완료율과\n남은 일 확인',
        trailing: _MiniProgressRing(percent: summary.progressPercent, size: 36),
      ),
      const _FeatureCard(
        icon: Icons.star_rounded,
        iconColor: AppColors.priorityLow,
        title: '완료 통계',
        subtitle: '이번 주\n완료 9개',
      ),
      const _FeatureCard(
        icon: Icons.backpack_rounded,
        iconColor: AppColors.priorityNormal,
        title: '준비물',
        subtitle: '우산 · 노트북 · 충전기',
      ),
      const _FeatureCard(
        icon: Icons.format_list_bulleted_rounded,
        iconColor: AppColors.priorityHigh,
        title: '우선순위',
        subtitle: '높음 2 · 보통 3 · 낮음 4',
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
                  child: i + 1 < cards.length ? cards[i + 1] : const SizedBox(),
                ),
              ],
            ),
          ),
        ],
      ],
    );
  }

  Widget _buildTodoListCard(BuildContext context, TodoViewModel vm) {
    final textTheme = Theme.of(context).textTheme;
    final todos = vm.todos;

    return _SoftCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('오늘의 할 일', style: textTheme.titleLarge),
          const SizedBox(height: AppDimens.md),
          ...List.generate(todos.length, (index) {
            final isLast = index == todos.length - 1;
            final todo = todos[index];

            return Column(
              children: [
                _TodoRow(
                  item: todo,
                  onToggle: () => vm.toggleDone(todo.id),
                ),
                if (!isLast)
                  const Divider(
                    height: AppDimens.lg,
                    thickness: 1,
                    color: AppColors.divider,
                  ),
              ],
            );
          }),
        ],
      ),
    );
  }

  Widget _buildMenuCard(BuildContext context) {
    return _SoftCard(
      padding: const EdgeInsets.symmetric(
        horizontal: AppDimens.lg,
        vertical: AppDimens.sm,
      ),
      child: const Column(
        children: [
          _MenuRow(icon: Icons.event_outlined, label: '마감일 관리'),
          Divider(height: 1, thickness: 1, color: AppColors.divider),
          _MenuRow(icon: Icons.notifications_none_rounded, label: '알림 설정'),
          Divider(height: 1, thickness: 1, color: AppColors.divider),
          _MenuRow(icon: Icons.repeat_rounded, label: '반복 할 일'),
        ],
      ),
    );
  }
}

class _SoftCard extends StatelessWidget {
  const _SoftCard({
    required this.child,
    this.padding,
  });

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
            color: Colors.black.withOpacity(0.05),
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
    required this.leading,
    required this.label,
    required this.value,
  });

  final Widget leading;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;

    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        leading,
        const SizedBox(height: AppDimens.sm),
        Text(
          label,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          textAlign: TextAlign.center,
          style: textTheme.bodyMedium,
        ),
        const SizedBox(height: 2),
        Text(
          value,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold),
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
  const _CircleIcon({
    required this.icon,
    required this.color,
    this.size = 40,
  });

  final IconData icon;
  final Color color;
  final double size;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: color,
        shape: BoxShape.circle,
      ),
      alignment: Alignment.center,
      child: Icon(icon, color: Colors.white, size: size * 0.55),
    );
  }
}

class _MiniProgressRing extends StatelessWidget {
  const _MiniProgressRing({
    required this.percent,
    this.size = 40,
  });

  final int percent;
  final double size;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: size,
      height: size,
      child: CustomPaint(
        painter: _RingPainter(percent: percent),
        child: Center(
          child: Text(
            '$percent%',
            maxLines: 1,
            overflow: TextOverflow.clip,
            style: TextStyle(
              fontSize: size * 0.26,
              fontWeight: FontWeight.bold,
              color: AppColors.primary,
            ),
          ),
        ),
      ),
    );
  }
}

class _RingPainter extends CustomPainter {
  _RingPainter({required this.percent});

  final int percent;

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = (math.min(size.width, size.height) - 5) / 2;
    final stroke = size.width * 0.11;

    final trackPaint = Paint()
      ..color = AppColors.primarySoft
      ..style = PaintingStyle.stroke
      ..strokeWidth = stroke;

    canvas.drawCircle(center, radius, trackPaint);

    final progressPaint = Paint()
      ..color = AppColors.primary
      ..style = PaintingStyle.stroke
      ..strokeWidth = stroke
      ..strokeCap = StrokeCap.round;

    final sweep = (percent / 100.0) * 2 * math.pi;

    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius),
      -math.pi / 2,
      sweep,
      false,
      progressPaint,
    );
  }

  @override
  bool shouldRepaint(covariant _RingPainter oldDelegate) {
    return oldDelegate.percent != percent;
  }
}

class _FeatureCard extends StatelessWidget {
  const _FeatureCard({
    required this.icon,
    required this.iconColor,
    required this.title,
    required this.subtitle,
    this.trailing,
  });

  final IconData icon;
  final Color iconColor;
  final String title;
  final String subtitle;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;

    return _SoftCard(
      padding: const EdgeInsets.all(AppDimens.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              _CircleIcon(icon: icon, color: iconColor, size: 44),
              const Spacer(),
              const Icon(
                Icons.chevron_right,
                size: 20,
                color: AppColors.textSecondary,
              ),
            ],
          ),
          const SizedBox(height: AppDimens.md),
          Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
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
              if (trailing != null) ...[
                const SizedBox(width: AppDimens.sm),
                trailing!,
              ],
            ],
          ),
        ],
      ),
    );
  }
}

class _TodoRow extends StatelessWidget {
  const _TodoRow({
    required this.item,
    required this.onToggle,
  });

  final TodoItem item;
  final VoidCallback onToggle;

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;

    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.only(top: 2),
          child: GestureDetector(
            onTap: onToggle,
            child: Container(
              width: 24,
              height: 24,
              decoration: BoxDecoration(
                color: item.isDone ? AppColors.primary : Colors.transparent,
                borderRadius: BorderRadius.circular(AppDimens.radiusSm),
                border: Border.all(
                  color: item.isDone ? AppColors.primary : AppColors.divider,
                  width: 2,
                ),
              ),
              child: item.isDone
                  ? const Icon(Icons.check, size: 16, color: Colors.white)
                  : null,
            ),
          ),
        ),
        const SizedBox(width: AppDimens.md),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Text(
                      item.title,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: textTheme.titleMedium?.copyWith(
                        decoration:
                            item.isDone ? TextDecoration.lineThrough : null,
                        color: item.isDone
                            ? AppColors.textSecondary
                            : AppColors.textPrimary,
                      ),
                    ),
                  ),
                  const SizedBox(width: AppDimens.sm),
                  _PriorityBadge(priority: item.priority),
                ],
              ),
              const SizedBox(height: AppDimens.xs),
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Padding(
                    padding: EdgeInsets.only(top: 2),
                    child: Icon(
                      Icons.notifications_none_rounded,
                      size: 14,
                      color: AppColors.textSecondary,
                    ),
                  ),
                  const SizedBox(width: AppDimens.xs),
                  Expanded(
                    child: Text(
                      item.reminder,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: textTheme.bodyMedium,
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(width: AppDimens.sm),
        const Padding(
          padding: EdgeInsets.only(top: 2),
          child: Icon(
            Icons.chevron_right,
            size: 20,
            color: AppColors.textSecondary,
          ),
        ),
      ],
    );
  }
}

class _PriorityBadge extends StatelessWidget {
  const _PriorityBadge({required this.priority});

  final TodoPriority priority;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppDimens.sm,
        vertical: 3,
      ),
      decoration: BoxDecoration(
        color: priority.color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(AppDimens.radiusSm),
      ),
      child: Text(
        priority.label,
        maxLines: 1,
        overflow: TextOverflow.clip,
        style: TextStyle(
          fontSize: 12,
          fontWeight: FontWeight.w600,
          color: priority.color,
        ),
      ),
    );
  }
}

class _MenuRow extends StatelessWidget {
  const _MenuRow({
    required this.icon,
    required this.label,
  });

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
            const Icon(
              Icons.chevron_right,
              size: 20,
              color: AppColors.textSecondary,
            ),
          ],
        ),
      ),
    );
  }
}