import 'package:flutter/material.dart';
import '../../data/widget_catalog.dart';
import '../../models/dashboard_widget_model.dart';
import '../../theme/app_theme.dart';

typedef AddWidgetResult = ({DashboardWidgetType type, WidgetSize size});

/// "위젯 추가" 바텀시트. 추가 가능한 위젯 목록과 지원 크기를 보여준다.
/// 크기 배지를 누르면 해당 크기로, 행을 누르면 기본 크기로 추가된다.
Future<AddWidgetResult?> showAddWidgetSheet(BuildContext context) {
  return showModalBottomSheet<AddWidgetResult>(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (_) => const _AddWidgetSheet(),
  );
}

class _AddWidgetSheet extends StatelessWidget {
  const _AddWidgetSheet();

  @override
  Widget build(BuildContext context) {
    final maxHeight = MediaQuery.of(context).size.height * 0.82;
    return Container(
      constraints: BoxConstraints(maxHeight: maxHeight),
      decoration: const BoxDecoration(
        color: TossColors.bgWhite,
        borderRadius: BorderRadius.vertical(
          top: Radius.circular(TossRadius.xl),
        ),
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
                  '위젯 추가',
                  style: TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.w700,
                    color: AppTheme.textPrimary,
                  ),
                ),
              ),
            ),
            Flexible(
              child: ListView.separated(
                padding: const EdgeInsets.fromLTRB(16, 6, 16, 16),
                itemCount: WidgetCatalog.catalogOrder.length,
                separatorBuilder: (_, _) => const SizedBox(height: 10),
                itemBuilder: (context, i) {
                  final spec = WidgetCatalog.of(WidgetCatalog.catalogOrder[i]);
                  return _CatalogTile(spec: spec);
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _CatalogTile extends StatelessWidget {
  final DashboardWidgetSpec spec;

  const _CatalogTile({required this.spec});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () =>
          Navigator.of(context).pop((type: spec.type, size: spec.defaultSize)),
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
                color: spec.accent.withValues(alpha: 0.14),
                borderRadius: BorderRadius.circular(13),
              ),
              child: Icon(spec.icon, color: spec.accent, size: 22),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    spec.title,
                    style: const TextStyle(
                      fontSize: 14.5,
                      fontWeight: FontWeight.w700,
                      color: AppTheme.textPrimary,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    spec.description,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w500,
                      color: AppTheme.textSecondary,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 8),
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                for (final size in spec.supportedSizes)
                  Padding(
                    padding: const EdgeInsets.only(left: 5),
                    child: _SizeBadge(
                      size: size,
                      accent: spec.accent,
                      onTap: () => Navigator.of(
                        context,
                      ).pop((type: spec.type, size: size)),
                    ),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _SizeBadge extends StatelessWidget {
  final WidgetSize size;
  final Color accent;
  final VoidCallback onTap;

  const _SizeBadge({
    required this.size,
    required this.accent,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: Container(
        width: 26,
        height: 26,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: accent.withValues(alpha: 0.12),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Text(
          size.label,
          style: TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w700,
            color: accent,
          ),
        ),
      ),
    );
  }
}
