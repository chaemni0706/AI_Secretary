import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/theme/app_colors.dart';
import '../../core/theme/app_dimens.dart';

// ─────────────────────────────────────────────────────────────
//  임시 mock 모델 (다음 단계에서 data/models 로 분리 예정)
// ─────────────────────────────────────────────────────────────

class _DateChipData {
  const _DateChipData({required this.weekday, required this.day});
  final String weekday; // 월
  final int day; // 24
}

enum _Fit { best, good, tight }

extension _FitStyle on _Fit {
  Color get color => switch (this) {
        _Fit.best => AppColors.fitBest,
        _Fit.good => AppColors.fitGood,
        _Fit.tight => AppColors.fitTight,
      };

  IconData get icon => switch (this) {
        _Fit.best => Icons.check_circle,
        _Fit.good => Icons.schedule,
        _Fit.tight => Icons.error_outline,
      };
}

class _Candidate {
  const _Candidate({
    required this.dateLabel,
    required this.timeRange,
    required this.note,
    required this.fit,
  });
  final String dateLabel; // "6월 26일 수요일"
  final String timeRange; // "14:00 - 15:00"
  final String note; // "겹치는 일정 없음"
  final _Fit fit;
}

class ReservationCandidateScreen extends StatefulWidget {
  const ReservationCandidateScreen({super.key});

  @override
  State<ReservationCandidateScreen> createState() =>
      _ReservationCandidateScreenState();
}

class _ReservationCandidateScreenState
    extends State<ReservationCandidateScreen> {
  // ── mock 날짜 칩 ──
  static const List<_DateChipData> _dates = [
    _DateChipData(weekday: '월', day: 24),
    _DateChipData(weekday: '화', day: 25),
    _DateChipData(weekday: '수', day: 26),
    _DateChipData(weekday: '목', day: 27),
    _DateChipData(weekday: '금', day: 28),
  ];

  int _selectedDay = 26; // 기본 선택: 수 26

  // ── mock 추천 후보 ──
  static const List<_Candidate> _candidates = [
    _Candidate(
      dateLabel: '6월 26일 수요일',
      timeRange: '14:00 - 15:00',
      note: '겹치는 일정 없음',
      fit: _Fit.best,
    ),
    _Candidate(
      dateLabel: '6월 27일 목요일',
      timeRange: '10:30 - 11:30',
      note: '이동시간 여유 있음',
      fit: _Fit.good,
    ),
    _Candidate(
      dateLabel: '6월 28일 금요일',
      timeRange: '16:00 - 17:00',
      note: '조금 빠듯해요',
      fit: _Fit.tight,
    ),
  ];

  int _selectedCandidate = 0; // 기본 선택: BEST

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.pop(),
        ),
        title: const Text('예약 후보 추천'),
      ),
      // ── 하단 고정 CTA (Message 와 동일 방식) ──
      bottomNavigationBar: _buildCtaBar(context),
      body: SafeArea(
        bottom: false, // 하단은 CTA(bottomNavigationBar)가 SafeArea 처리
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(
            AppDimens.screenPadding,
            AppDimens.screenPadding,
            AppDimens.screenPadding,
            AppDimens.md,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _buildSpeechBubble(context),
              const SizedBox(height: AppDimens.lg),
              _buildConditionCard(context),
              const SizedBox(height: AppDimens.lg),
              _buildDateChips(context),
              const SizedBox(height: AppDimens.lg),
              _buildCandidateSection(context),
            ],
          ),
        ),
      ),
    );
  }

  // ── AI 말풍선 + 캐릭터 ──
  Widget _buildSpeechBubble(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          child: Container(
            padding: const EdgeInsets.all(AppDimens.md),
            decoration: BoxDecoration(
              color: AppColors.primarySoft,
              borderRadius: BorderRadius.circular(AppDimens.radiusMd),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '가능한 시간을 찾아봤어요',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: textTheme.titleMedium,
                ),
                const SizedBox(height: AppDimens.xs),
                Text(
                  '겹치는 일정과 이동 시간을 확인했어요.',
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: textTheme.bodyMedium,
                ),
              ],
            ),
          ),
        ),
        const SizedBox(width: AppDimens.sm),
        const Text('🌤️', style: TextStyle(fontSize: 44)),
      ],
    );
  }

  // ── 예약 조건 카드 ──
  Widget _buildConditionCard(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    return _SoftCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '예약 조건',
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: textTheme.titleMedium?.copyWith(color: AppColors.primary),
          ),
          const SizedBox(height: AppDimens.md),
          _ConditionRow(icon: Icons.access_time, label: '미팅 1시간'),
          const _RowDivider(),
          _ConditionRow(icon: Icons.location_on_outlined, label: '강남역 근처'),
          const _RowDivider(),
          _ConditionRow(icon: Icons.people_outline, label: '참석자 3명'),
        ],
      ),
    );
  }

  // ── 날짜 선택 칩 (가로 스크롤: 좁은 화면 overflow 방지) ──
  Widget _buildDateChips(BuildContext context) {
    return SizedBox(
      height: 72,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        physics: const BouncingScrollPhysics(),
        padding: EdgeInsets.zero,
        itemCount: _dates.length,
        separatorBuilder: (_, __) => const SizedBox(width: AppDimens.sm),
        itemBuilder: (context, i) {
          final data = _dates[i];
          return _DateChip(
            data: data,
            selected: data.day == _selectedDay,
            onTap: () => setState(() => _selectedDay = data.day),
          );
        },
      ),
    );
  }

  // ── 추천 시간 후보 ──
  Widget _buildCandidateSection(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('추천 시간 후보', style: textTheme.titleLarge),
        const SizedBox(height: AppDimens.md),
        ...List.generate(_candidates.length, (i) {
          return Padding(
            padding: const EdgeInsets.only(bottom: AppDimens.md),
            child: _CandidateCard(
              candidate: _candidates[i],
              isBest: i == 0,
              selected: i == _selectedCandidate,
              onTap: () => setState(() => _selectedCandidate = i),
            ),
          );
        }),
      ],
    );
  }

  // ── 하단 고정 CTA ──
  Widget _buildCtaBar(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 16,
            offset: const Offset(0, -4),
          ),
        ],
      ),
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.all(AppDimens.screenPadding),
          child: SizedBox(
            width: double.infinity,
            height: 56,
            child: FilledButton(
              onPressed: () {
                final c = _candidates[_selectedCandidate];
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content:
                        Text('${c.dateLabel} ${c.timeRange}로 예약을 진행해요.'),
                  ),
                );
              },
              child: const Text(
                '선택한 시간으로 예약',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────
//  내부 위젯
// ─────────────────────────────────────────────────────────────

class _SoftCard extends StatelessWidget {
  const _SoftCard({required this.child});
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppDimens.lg),
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

class _ConditionRow extends StatelessWidget {
  const _ConditionRow({required this.icon, required this.label});
  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    return Row(
      children: [
        Container(
          width: 36,
          height: 36,
          decoration: const BoxDecoration(
            color: AppColors.primarySoft,
            shape: BoxShape.circle,
          ),
          alignment: Alignment.center,
          child: Icon(icon, size: 20, color: AppColors.primary),
        ),
        const SizedBox(width: AppDimens.md),
        Expanded(
          child: Text(
            label,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: textTheme.bodyLarge,
          ),
        ),
      ],
    );
  }
}

class _RowDivider extends StatelessWidget {
  const _RowDivider();
  @override
  Widget build(BuildContext context) {
    return const Divider(
      height: AppDimens.lg,
      thickness: 1,
      color: AppColors.divider,
    );
  }
}

/// 날짜 선택 칩 (가로 스크롤 안에서 고정 폭 사용)
class _DateChip extends StatelessWidget {
  const _DateChip({
    required this.data,
    required this.selected,
    required this.onTap,
  });
  final _DateChipData data;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(AppDimens.radiusMd),
      child: Container(
        width: 64,
        padding: const EdgeInsets.symmetric(vertical: AppDimens.md),
        decoration: BoxDecoration(
          color: selected ? AppColors.primarySoft : AppColors.surface,
          borderRadius: BorderRadius.circular(AppDimens.radiusMd),
          border: Border.all(
            color: selected ? AppColors.primary : AppColors.divider,
            width: selected ? 1.5 : 1,
          ),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              data.weekday,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                fontSize: 13,
                color:
                    selected ? AppColors.primary : AppColors.textSecondary,
              ),
            ),
            const SizedBox(height: AppDimens.xs),
            Text(
              '${data.day}',
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.bold,
                color: selected ? AppColors.primary : AppColors.textPrimary,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// 추천 후보 카드
class _CandidateCard extends StatelessWidget {
  const _CandidateCard({
    required this.candidate,
    required this.isBest,
    required this.selected,
    required this.onTap,
  });
  final _Candidate candidate;
  final bool isBest;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    final borderColor = selected ? AppColors.primary : AppColors.divider;

    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(AppDimens.radiusCard),
      child: Container(
        padding: const EdgeInsets.all(AppDimens.md),
        decoration: BoxDecoration(
          color: selected ? AppColors.primarySoft : AppColors.surface,
          borderRadius: BorderRadius.circular(AppDimens.radiusCard),
          border: Border.all(
            color: borderColor,
            width: selected ? 1.5 : 1,
          ),
        ),
        child: Row(
          children: [
            _buildLeading(),
            const SizedBox(width: AppDimens.md),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (isBest)
                    Padding(
                      padding: const EdgeInsets.only(bottom: AppDimens.xs),
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: AppDimens.sm,
                          vertical: 2,
                        ),
                        decoration: BoxDecoration(
                          color: AppColors.primary,
                          borderRadius:
                              BorderRadius.circular(AppDimens.radiusFull),
                        ),
                        child: const Text(
                          'BEST',
                          style: TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.bold,
                            color: Colors.white,
                          ),
                        ),
                      ),
                    ),
                  Text(
                    '${candidate.dateLabel} ${candidate.timeRange}',
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: textTheme.titleMedium,
                  ),
                  const SizedBox(height: AppDimens.xs),
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Padding(
                        padding: const EdgeInsets.only(top: 1),
                        child: Icon(candidate.fit.icon,
                            size: 16, color: candidate.fit.color),
                      ),
                      const SizedBox(width: AppDimens.xs),
                      Expanded(
                        child: Text(
                          candidate.note,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: textTheme.bodyMedium?.copyWith(
                            color: candidate.fit.color,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(width: AppDimens.sm),
            const Icon(Icons.chevron_right,
                size: 22, color: AppColors.textSecondary),
          ],
        ),
      ),
    );
  }

  Widget _buildLeading() {
    if (isBest) {
      return Container(
        width: 44,
        height: 44,
        decoration: BoxDecoration(
          color: AppColors.primary.withValues(alpha: 0.12),
          shape: BoxShape.circle,
        ),
        alignment: Alignment.center,
        child: const Icon(Icons.check, color: AppColors.primary, size: 24),
      );
    }
    final bg = candidate.fit == _Fit.tight
        ? AppColors.fitTight.withValues(alpha: 0.12)
        : AppColors.primarySoft;
    final fg =
        candidate.fit == _Fit.tight ? AppColors.fitTight : AppColors.primary;
    return Container(
      width: 44,
      height: 44,
      decoration: BoxDecoration(color: bg, shape: BoxShape.circle),
      alignment: Alignment.center,
      child: Icon(candidate.fit.icon, color: fg, size: 22),
    );
  }
}