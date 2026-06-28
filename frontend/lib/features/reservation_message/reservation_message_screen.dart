import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';

import '../../core/theme/app_colors.dart';
import '../../core/theme/app_dimens.dart';

// ─────────────────────────────────────────────────────────────
//  임시 mock 모델 (다음 단계에서 data/models 로 분리 예정)
// ─────────────────────────────────────────────────────────────

enum _Tone { polite, friendly, simple }

extension _ToneLabel on _Tone {
  String get label => switch (this) {
        _Tone.polite => '정중하게',
        _Tone.friendly => '친근하게',
        _Tone.simple => '간단하게',
      };
}

class _ReservationInfo {
  const _ReservationInfo({
    required this.place,
    required this.people,
    required this.date,
    required this.time,
  });
  final String place;
  final String people;
  final String date;
  final String time;
}

class ReservationMessageScreen extends StatefulWidget {
  const ReservationMessageScreen({super.key});

  @override
  State<ReservationMessageScreen> createState() =>
      _ReservationMessageScreenState();
}

class _ReservationMessageScreenState extends State<ReservationMessageScreen> {
  // ── mock 예약 정보 ──
  static const _info = _ReservationInfo(
    place: '강남역 파스타집',
    people: '3명',
    date: '6월 26일 수요일',
    time: '오후 7시',
  );

  _Tone _selectedTone = _Tone.polite;

  // 말투별 생성 메시지 (mock)
  String get _generatedMessage => switch (_selectedTone) {
        _Tone.polite =>
          '안녕하세요. 6월 26일 수요일 오후 7시에 3명 예약 가능할까요? '
              '가능하시다면 예약 부탁드립니다. 감사합니다.',
        _Tone.friendly =>
          '안녕하세요! 6월 26일 수요일 저녁 7시에 3명 자리 있을까요? '
              '있으면 예약하고 싶어요. 감사합니다!',
        _Tone.simple => '6월 26일(수) 오후 7시 3명 예약 가능한가요?',
      };

  void _onCopy() {
    Clipboard.setData(ClipboardData(text: _generatedMessage));
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('메시지를 복사했어요.'),
        duration: Duration(seconds: 2),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.pop(),
        ),
        title: const Text('예약 문의 메시지 생성'),
        actions: [
          IconButton(
            icon: const Icon(Icons.info_outline,
                color: AppColors.textSecondary),
            onPressed: () {},
          ),
        ],
      ),
      // ── 하단 고정 CTA (Candidate 와 통일) ──
      bottomNavigationBar: _buildCtaBar(context),
      body: SafeArea(
        bottom: false, // 하단은 CTA(bottomNavigationBar)가 SafeArea 처리
        child: SingleChildScrollView(
          // CTA 에 마지막 콘텐츠가 가리지 않도록 충분한 하단 padding
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
              _buildInfoCard(context),
              const SizedBox(height: AppDimens.lg),
              _buildToneSection(context),
              const SizedBox(height: AppDimens.lg),
              _buildMessageSection(context),
              const SizedBox(height: AppDimens.lg),
              _buildActionButtons(context),
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
                  '예약 문의 메시지를',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: textTheme.titleMedium,
                ),
                const SizedBox(height: AppDimens.xs),
                Text(
                  '상황에 맞게 정중한 문장으로 정리했어요.',
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

  // ── 예약 정보 카드 ──
  Widget _buildInfoCard(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    return _SoftCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('예약 정보', style: textTheme.titleLarge),
          const SizedBox(height: AppDimens.md),
          _InfoRow(
              icon: Icons.location_on_outlined,
              label: '장소',
              value: _info.place),
          const _RowDivider(),
          _InfoRow(
              icon: Icons.people_outline, label: '인원', value: _info.people),
          const _RowDivider(),
          _InfoRow(
              icon: Icons.event_outlined, label: '날짜', value: _info.date),
          const _RowDivider(),
          _InfoRow(icon: Icons.access_time, label: '시간', value: _info.time),
        ],
      ),
    );
  }

  // ── 말투 선택 ──
  Widget _buildToneSection(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('말투 선택', style: textTheme.titleLarge),
        const SizedBox(height: AppDimens.md),
        Row(
          children: _Tone.values.map((tone) {
            final isFirst = tone == _Tone.values.first;
            return Expanded(
              child: Padding(
                padding: EdgeInsets.only(left: isFirst ? 0 : AppDimens.sm),
                child: _ToneChip(
                  label: tone.label,
                  selected: tone == _selectedTone,
                  onTap: () => setState(() => _selectedTone = tone),
                ),
              ),
            );
          }).toList(),
        ),
      ],
    );
  }

  // ── 생성된 메시지 ──
  Widget _buildMessageSection(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('생성된 메시지', style: textTheme.titleLarge),
        const SizedBox(height: AppDimens.md),
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(AppDimens.lg),
          decoration: BoxDecoration(
            color: AppColors.primarySoft,
            borderRadius: BorderRadius.circular(AppDimens.radiusMd),
          ),
          child: Text(
            _generatedMessage,
            style: textTheme.bodyLarge?.copyWith(height: 1.5),
          ),
        ),
      ],
    );
  }

  // ── 액션 버튼 3개 ──
  Widget _buildActionButtons(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: _ActionButton(
            icon: Icons.refresh,
            label: '다시 생성',
            onTap: () => setState(() {}),
          ),
        ),
        const SizedBox(width: AppDimens.sm),
        Expanded(
          child: _ActionButton(
            icon: Icons.edit_outlined,
            label: '수정하기',
            onTap: () {},
          ),
        ),
        const SizedBox(width: AppDimens.sm),
        Expanded(
          child: _ActionButton(
            icon: Icons.copy_outlined,
            label: '복사하기',
            onTap: _onCopy,
          ),
        ),
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
            child: FilledButton.icon(
              onPressed: () {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('메시지를 보냈어요.')),
                );
              },
              icon: const Icon(Icons.send, size: 20),
              label: const Text(
                '메시지 보내기',
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

class _InfoRow extends StatelessWidget {
  const _InfoRow({
    required this.icon,
    required this.label,
    required this.value,
  });
  final IconData icon;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        Icon(icon, size: 22, color: AppColors.primary),
        const SizedBox(width: AppDimens.md),
        // label: 고정폭 대신 내용 크기 (짧은 2글자라 폭 차지 적음)
        Text(
          label,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600),
        ),
        const SizedBox(width: AppDimens.md),
        // value: 남는 폭을 차지하고 길면 말줄임
        Expanded(
          child: Text(
            value,
            maxLines: 2,
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

/// 말투 선택 칩 (좁은 화면에서도 텍스트 overflow 방지)
class _ToneChip extends StatelessWidget {
  const _ToneChip({
    required this.label,
    required this.selected,
    required this.onTap,
  });
  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(AppDimens.radiusMd),
      child: Container(
        padding: const EdgeInsets.symmetric(
          horizontal: AppDimens.sm,
          vertical: AppDimens.md,
        ),
        decoration: BoxDecoration(
          color: selected ? AppColors.primarySoft : AppColors.surface,
          borderRadius: BorderRadius.circular(AppDimens.radiusMd),
          border: Border.all(
            color: selected ? AppColors.primary : AppColors.divider,
            width: selected ? 1.5 : 1,
          ),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            if (selected) ...[
              const Icon(Icons.check_circle,
                  size: 18, color: AppColors.primary),
              const SizedBox(width: AppDimens.xs),
            ],
            Flexible(
              child: Text(
                label,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  color:
                      selected ? AppColors.primary : AppColors.textPrimary,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// 테두리 액션 버튼 (다시 생성 / 수정하기 / 복사하기)
class _ActionButton extends StatelessWidget {
  const _ActionButton({
    required this.icon,
    required this.label,
    required this.onTap,
  });
  final IconData icon;
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(AppDimens.radiusMd),
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: AppDimens.md),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(AppDimens.radiusMd),
          border: Border.all(color: AppColors.divider, width: 1),
        ),
        child: Column(
          children: [
            Icon(icon, size: 20, color: AppColors.primary),
            const SizedBox(height: AppDimens.xs),
            Text(
              label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w600,
                color: AppColors.textPrimary,
              ),
            ),
          ],
        ),
      ),
    );
  }
}