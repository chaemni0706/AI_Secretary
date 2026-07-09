import 'package:flutter/material.dart';

import 'toss_tokens.dart';

export 'toss_tokens.dart';

/// 앱 전역 테마 — 토스(TDS) 토큰([TossColors] 등)을 단일 진실 소스로 사용한다.
///
/// 기존 화면들이 참조하던 `AppTheme.*` 이름은 하위 호환을 위해 유지하고,
/// 값만 토스 토큰으로 매핑했다. 새 코드는 가급적 Toss* 토큰을 직접 참조할 것.
class AppTheme {
  static const Color blue = TossColors.blue500;
  static const Color background = TossColors.bgGrey;
  static const Color textPrimary = TossColors.textPrimary;
  static const Color textSecondary = TossColors.textAssistive;
  static const Color textTertiary = TossColors.textSecondary;
  static const Color teal = TossColors.teal;
  static const Color purple = TossColors.purple;
  static const Color orange = TossColors.orange;
  static const Color green = TossColors.green;
  static const Color red = TossColors.red;
  static const Color separator = TossColors.grey200;
  static const Color dark = TossColors.grey900;

  static const Color cardBg = TossColors.bgWhite;

  static ThemeData get lightTheme => ThemeData(
        useMaterial3: true,
        fontFamily: TossTypography.fontFamily,
        scaffoldBackgroundColor: background,
        colorScheme: const ColorScheme.light(
          primary: blue,
          secondary: teal,
          surface: TossColors.bgWhite,
          error: red,
        ),
        splashFactory: NoSplash.splashFactory,
        highlightColor: TossColors.pressedGrey,
        appBarTheme: const AppBarTheme(
          backgroundColor: Colors.transparent,
          elevation: 0,
          scrolledUnderElevation: 0,
          foregroundColor: textPrimary,
          titleTextStyle: TextStyle(
            fontFamily: TossTypography.fontFamily,
            color: textPrimary,
            fontSize: 17,
            fontWeight: FontWeight.w600,
          ),
        ),
        textTheme: const TextTheme(
          displaySmall: TossTypography.display,
          titleLarge: TossTypography.title1,
          titleMedium: TossTypography.title3,
          titleSmall: TextStyle(
            fontFamily: TossTypography.fontFamily,
            color: textPrimary,
            fontSize: 15,
            fontWeight: FontWeight.w600,
          ),
          bodyLarge: TossTypography.body,
          bodyMedium: TextStyle(
            fontFamily: TossTypography.fontFamily,
            color: TossColors.textSecondary,
            fontSize: 14,
            height: 1.45,
          ),
          bodySmall: TossTypography.caption,
        ),
        bottomSheetTheme: const BottomSheetThemeData(
          backgroundColor: TossColors.bgWhite,
          modalBackgroundColor: TossColors.bgWhite,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.vertical(
              top: Radius.circular(TossRadius.xl),
            ),
          ),
        ),
        dialogTheme: const DialogThemeData(
          backgroundColor: TossColors.bgWhite,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.all(Radius.circular(TossRadius.xl)),
          ),
        ),
      );

  /// 화면 배경 — 토스식 단색 연회색.
  /// (과거 그라데이션 API 호환을 위해 LinearGradient 형태 유지)
  static LinearGradient get screenGradient => const LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: [TossColors.bgGrey, TossColors.bgGrey],
      );

  static BoxDecoration get screenBackground => const BoxDecoration(
        color: TossColors.bgGrey,
      );
}
