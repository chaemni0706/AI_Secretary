import 'package:flutter/material.dart';

import 'toss_tokens.dart';

/// 하위 호환용 상수 — 값은 토스 토큰([TossSpacing] 등)을 따른다.
/// 새 코드는 Toss* 토큰을 직접 참조할 것.
class AppSpacing {
  static const double screenPadding = TossSpacing.screen;
  static const double sectionGap = TossSpacing.lg;
  static const double cardGap = TossSpacing.sm;
  static const double iconButton = 40;
  static const double compactIconButton = 36;
}

class AppRadii {
  static const double card = TossRadius.lg;
  static const double control = TossRadius.md;
  static const double small = TossRadius.sm;
}

class AppTextStyles {
  static const TextStyle screenTitle = TossTypography.display;

  static const TextStyle sectionTitle = TextStyle(
    fontFamily: TossTypography.fontFamily,
    fontSize: 17,
    fontWeight: FontWeight.w700,
    color: TossColors.textPrimary,
  );

  static const TextStyle cardTitle = TextStyle(
    fontFamily: TossTypography.fontFamily,
    fontSize: 14,
    fontWeight: FontWeight.w600,
    color: TossColors.textPrimary,
  );

  static const TextStyle meta = TossTypography.small;
}
