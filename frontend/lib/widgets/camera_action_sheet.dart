import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

/// 어시스턴트 FAB의 "카메라" 액션을 눌렀을 때 보여줄 선택지.
enum CameraActionChoice {
  /// 약봉투 촬영 -> 복약 루틴 생성 (MedicineOcrScreen)
  medicineRoutine,

  /// 물/운동/공부 등 활동 사진 인증 (ImageVerificationScreen)
  verificationPhoto,
}

/// "카메라" 액션 바텀시트. `dashboard_widgets/add_widget_sheet.dart`와 동일한
/// 기존 바텀시트 패턴(둥근 상단 시트 + 드래그 핸들 + 아이콘/제목/설명 행)을 재사용한다.
Future<CameraActionChoice?> showCameraActionSheet(BuildContext context) {
  return showModalBottomSheet<CameraActionChoice>(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (_) => const _CameraActionSheet(),
  );
}

class _CameraActionSheet extends StatelessWidget {
  const _CameraActionSheet();

  @override
  Widget build(BuildContext context) {
    final maxHeight = MediaQuery.of(context).size.height * 0.82;
    return Container(
      constraints: BoxConstraints(maxHeight: maxHeight),
      decoration: const BoxDecoration(
        color: TossColors.bgWhite,
        borderRadius: BorderRadius.vertical(top: Radius.circular(TossRadius.xl)),
      ),
      child: SafeArea(
        top: false,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const SizedBox(height: 10),
            Container(
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: AppTheme.separator,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            const Padding(
              padding: EdgeInsets.fromLTRB(20, 16, 20, 8),
              child: Align(
                alignment: Alignment.centerLeft,
                child: Text(
                  '카메라',
                  style: TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.w700,
                    color: AppTheme.textPrimary,
                  ),
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 6, 16, 16),
              child: Column(
                children: [
                  _ActionTile(
                    icon: Icons.medication_outlined,
                    accent: AppTheme.blue,
                    title: '루틴 추가',
                    description: '약봉투를 촬영해 복약 루틴을 생성합니다.',
                    onTap: () => Navigator.of(
                      context,
                    ).pop(CameraActionChoice.medicineRoutine),
                  ),
                  const SizedBox(height: 10),
                  _ActionTile(
                    icon: Icons.photo_camera_outlined,
                    accent: AppTheme.purple,
                    title: '인증 사진',
                    description: '물, 약, 운동, 공부 등의 활동 사진을 인증합니다.',
                    onTap: () => Navigator.of(
                      context,
                    ).pop(CameraActionChoice.verificationPhoto),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ActionTile extends StatelessWidget {
  final IconData icon;
  final Color accent;
  final String title;
  final String description;
  final VoidCallback onTap;

  const _ActionTile({
    required this.icon,
    required this.accent,
    required this.title,
    required this.description,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: TossColors.grey50,
          borderRadius: BorderRadius.circular(TossRadius.lg),
        ),
        child: Row(
          children: [
            Container(
              width: 42,
              height: 42,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: accent.withValues(alpha: 0.14),
                borderRadius: BorderRadius.circular(13),
              ),
              child: Icon(icon, color: accent, size: 22),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: const TextStyle(
                      fontSize: 14.5,
                      fontWeight: FontWeight.w700,
                      color: AppTheme.textPrimary,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    description,
                    style: const TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w500,
                      color: AppTheme.textSecondary,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
