import 'package:flutter/material.dart';

class AppTheme {
  static const Color blue = Color(0xFF007AFF);
  static const Color background = Color(0xFFEEF0FB);
  static const Color textPrimary = Color(0xFF1C1C1E);
  static const Color textSecondary = Color(0xFF8A8F97);
  static const Color textTertiary = Color(0xFF6B6F76);
  static const Color teal = Color(0xFF30B0C7);
  static const Color purple = Color(0xFF5E5CE6);
  static const Color orange = Color(0xFFFF9F0A);
  static const Color green = Color(0xFF34C759);
  static const Color red = Color(0xFFFF3B30);
  static const Color separator = Color(0xFFE6E9F1);
  static const Color dark = Color(0xFF1A1A1C);

  static final Color cardBg = Colors.white.withOpacity(0.75);

  static ThemeData get lightTheme => ThemeData(
        useMaterial3: true,
        scaffoldBackgroundColor: background,
        colorScheme: const ColorScheme.light(
          primary: blue,
          secondary: teal,
          surface: Colors.white,
        ),
        appBarTheme: const AppBarTheme(
          backgroundColor: Colors.transparent,
          elevation: 0,
          scrolledUnderElevation: 0,
          foregroundColor: textPrimary,
          titleTextStyle: TextStyle(
            color: textPrimary,
            fontSize: 17,
            fontWeight: FontWeight.w600,
          ),
        ),
        textTheme: const TextTheme(
          displaySmall: TextStyle(
            color: textPrimary,
            fontSize: 28,
            fontWeight: FontWeight.w700,
            letterSpacing: -0.5,
          ),
          titleLarge: TextStyle(
            color: textPrimary,
            fontSize: 22,
            fontWeight: FontWeight.w700,
            letterSpacing: -0.4,
          ),
          titleMedium: TextStyle(
            color: textPrimary,
            fontSize: 17,
            fontWeight: FontWeight.w600,
          ),
          titleSmall: TextStyle(
            color: textPrimary,
            fontSize: 15,
            fontWeight: FontWeight.w600,
          ),
          bodyLarge: TextStyle(color: textPrimary, fontSize: 16),
          bodyMedium: TextStyle(color: textTertiary, fontSize: 14),
          bodySmall: TextStyle(color: textSecondary, fontSize: 12),
        ),
      );

  static LinearGradient get screenGradient => const LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: [Color(0xFFE9F2FF), Color(0xFFEEF0FB), Color(0xFFFCEEF4)],
        stops: [0.0, 0.5, 1.0],
      );

  static BoxDecoration get screenBackground => BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            const Color(0xFFE9F2FF),
            const Color(0xFFEEF0FB),
            const Color(0xFFFCEEF4).withOpacity(0.8),
          ],
          stops: const [0.0, 0.5, 1.0],
        ),
      );
}
