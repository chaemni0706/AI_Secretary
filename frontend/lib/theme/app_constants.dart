import 'package:flutter/material.dart';

import 'toss_tokens.dart';

/// 앱 전역에서 쓰는 고정 문자열. 특히 AI 비서의 표시 이름은 화면·알림·TTS
/// 문구에 반복 등장하므로, 하드코딩을 없애고 이 한 곳에서만 관리한다.
/// 명칭을 바꾸려면 [assistantName] 값 하나만 수정하면 전체에 반영된다.
class AppStrings {
  /// AI 비서의 공식 표시 이름(프로젝트 공식 명칭).
  static const String assistantName = 'AI 비서';

  /// "{이름}가 알려드려요." 처럼 조사(가/이)가 붙는 안내 접두 문구.
  static String assistantNotifiesPrefix() => '$assistantName가 알려드려요.';

  /// mock_call/알림 등에서 쓰는 "{이름} 전화 알림" 제목.
  static String callAlertTitle() => '$assistantName 전화 알림';
}

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
