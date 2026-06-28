import 'package:flutter/material.dart';

/// Raw 팔레트. 화면에서 직접 쓰지 말고 의미색(아래 AppColors)을 통해 사용한다.
class _Palette {
  _Palette._();

  static const blue500 = Color(0xFF2563FF);
  static const blue50 = Color(0xFFEAF1FF);
  static const green500 = Color(0xFF22C55E);
  static const orange500 = Color(0xFFF59E0B);
  static const purple500 = Color(0xFF7C3AED);
  static const red500 = Color(0xFFEF4444);

  static const white = Color(0xFFFFFFFF);
  static const gray50 = Color(0xFFF7F8FA);
  static const gray100 = Color(0xFFF1F3F6);
  static const gray200 = Color(0xFFE5E8EC);
  static const gray400 = Color(0xFF9AA1AC);
  static const gray900 = Color(0xFF1A1D26);
}

/// 의미 기반 색상 토큰.
class AppColors {
  AppColors._();

  static const background = _Palette.gray50;
  static const surface = _Palette.white;
  static const primary = _Palette.blue500;
  static const primarySoft = _Palette.blue50;
  static const onPrimary = _Palette.white;
  static const textPrimary = _Palette.gray900;
  static const textSecondary = _Palette.gray400;
  static const divider = _Palette.gray200;

  static const categoryMeeting = _Palette.blue500;
  static const categoryMedical = _Palette.green500;
  static const categoryStudy = _Palette.orange500;
  static const categoryDinner = _Palette.purple500;

  static const priorityHigh = _Palette.red500;
  static const priorityNormal = _Palette.orange500;
  static const priorityLow = _Palette.green500;

  static const fitBest = _Palette.blue500;
  static const fitGood = _Palette.green500;
  static const fitTight = _Palette.orange500;
}