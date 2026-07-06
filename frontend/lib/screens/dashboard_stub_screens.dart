import 'package:flutter/material.dart';
import '../data/widget_mock_data.dart';
import '../theme/app_theme.dart';
import '../widgets/glass_card.dart';

/// 위젯에서 진입하지만 아직 전용 화면이 없는 기능들의 임시 상세 화면.
/// 추후 실제 화면이 준비되면 위젯의 onTap 대상만 교체하면 된다.

/// 준비물 / 출발 알림 임시 화면.
class PreparationDetailScreen extends StatelessWidget {
  const PreparationDetailScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return _StubScaffold(
      title: '준비물 · 출발 알림',
      icon: Icons.backpack_outlined,
      accent: AppTheme.green,
      description: '다음 일정 기준으로 챙길 준비물과 출발 시각을 안내하는 화면입니다. (준비 중)',
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 4, 16, 0),
          child: GlassCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  WidgetMockData.preparationContext,
                  style: const TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                    color: AppTheme.textPrimary,
                  ),
                ),
                const SizedBox(height: 12),
                for (final item in WidgetMockData.preparationItems)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: Row(
                      children: [
                        Icon(item.icon, size: 20, color: AppTheme.green),
                        const SizedBox(width: 12),
                        Text(
                          item.label,
                          style: const TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.w600,
                            color: AppTheme.textPrimary,
                          ),
                        ),
                      ],
                    ),
                  ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

/// OCR 인증 임시 화면. 실제 OCR API 는 연결하지 않는다.
class OcrVerificationDetailScreen extends StatelessWidget {
  const OcrVerificationDetailScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return _StubScaffold(
      title: 'OCR 인증',
      icon: Icons.document_scanner_outlined,
      accent: AppTheme.purple,
      description:
          '영수증·서류를 촬영해 일정/할 일을 자동 인증하는 화면입니다. 실제 인식 기능은 추후 연결 예정입니다.',
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 4, 16, 0),
          child: GlassCard(
            child: Row(
              children: [
                Container(
                  width: 44,
                  height: 44,
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    color: AppTheme.purple.withValues(alpha: 0.14),
                    borderRadius: BorderRadius.circular(13),
                  ),
                  child: const Icon(Icons.photo_camera_outlined,
                      color: AppTheme.purple),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Text(
                    '오늘 인증이 필요한 항목 ${WidgetMockData.ocrPendingCount}건',
                    style: const TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      color: AppTheme.textPrimary,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
          child: FilledButton.icon(
            onPressed: () {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('카메라/OCR 인식은 준비 중입니다.')),
              );
            },
            style: FilledButton.styleFrom(
              backgroundColor: AppTheme.purple,
              minimumSize: const Size.fromHeight(48),
            ),
            icon: const Icon(Icons.photo_camera_outlined),
            label: const Text('촬영하여 인증'),
          ),
        ),
      ],
    );
  }
}

class _StubScaffold extends StatelessWidget {
  final String title;
  final IconData icon;
  final Color accent;
  final String description;
  final List<Widget> children;

  const _StubScaffold({
    required this.title,
    required this.icon,
    required this.accent,
    required this.description,
    required this.children,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: AppTheme.screenBackground,
      child: Scaffold(
        backgroundColor: Colors.transparent,
        appBar: AppBar(
          title: Text(title),
          leading: const BackButton(),
        ),
        body: SafeArea(
          top: false,
          child: ListView(
            physics: const AlwaysScrollableScrollPhysics(
              parent: BouncingScrollPhysics(),
            ),
            padding: const EdgeInsets.fromLTRB(0, 8, 0, 32),
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
                child: GlassCard(
                  padding: const EdgeInsets.all(16),
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
                        child: Text(
                          description,
                          style: const TextStyle(
                            fontSize: 13,
                            height: 1.4,
                            fontWeight: FontWeight.w500,
                            color: AppTheme.textTertiary,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              ...children,
            ],
          ),
        ),
      ),
    );
  }
}
