import 'package:flutter/material.dart';
import 'app_theme.dart';

/// AI 가계부 전용 색상 · 포맷 헬퍼.
/// 앱 팔레트([AppTheme])와 조화를 이루도록 카테고리 색을 정의한다.
class LedgerStyles {
  LedgerStyles._();

  /// 시그니처 AI 브리핑 카드 그라디언트 (토스 블루 톤).
  static const LinearGradient briefingGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [TossColors.blue700, TossColors.blue600, TossColors.blue500],
    stops: [0.0, 0.55, 1.0],
  );

  static const Color briefingTitle = Colors.white;
  static const Color briefingBody = Color(0xFFEFF5FF);
  static const Color briefingIcon = Color(0xFFBFDBFF);

  /// 카테고리 키 → 대표 색.
  static const Map<String, Color> _categoryColors = {
    'cafe': Color(0xFFE8850C),
    'food': AppTheme.green,
    'trans': AppTheme.blue,
    'sub': AppTheme.purple,
    'shop': Color(0xFFE5457E),
    'cvs': AppTheme.teal,
    'income': AppTheme.blue,
    'tel': Color(0xFF5B6472),
  };

  static Color categoryColor(String catKey) =>
      _categoryColors[catKey] ?? AppTheme.green;

  /// 카테고리 태그 배경색.
  static Color categoryTagBg(String catKey) =>
      categoryColor(catKey).withValues(alpha: 0.12);

  /// 대기 거래 상태 배지 라벨.
  static String pendingBadgeLabel({required bool review, required int confidence}) {
    if (review) return '확인 필요';
    return confidence >= 95 ? '자동 분류' : 'AI $confidence%';
  }

  static Color pendingBadgeColor(bool review) =>
      review ? AppTheme.orange : AppTheme.green;

  /// 금액을 천 단위 콤마 문자열로 변환 (부호 제외, 절대값 기준).
  static String formatWon(num n) {
    final v = n.abs().round().toString();
    final b = StringBuffer();
    for (int i = 0; i < v.length; i++) {
      if (i > 0 && (v.length - i) % 3 == 0) b.write(',');
      b.write(v[i]);
    }
    return b.toString();
  }

  /// 부호가 붙은 금액 문자열 (예: '-5,800원', '+500,000원').
  static String signedWon(int amount) {
    final sign = amount < 0 ? '-' : '+';
    return '$sign${formatWon(amount)}원';
  }
}
