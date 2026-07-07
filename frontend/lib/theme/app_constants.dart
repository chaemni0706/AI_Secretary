import 'package:flutter/material.dart';

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

class AppSpacing {
  static const double screenPadding = 20;
  static const double sectionGap = 16;
  static const double cardGap = 8;
  static const double iconButton = 40;
  static const double compactIconButton = 36;
}

class AppRadii {
  static const double card = 18;
  static const double control = 12;
  static const double small = 10;
}

class AppTextStyles {
  static const TextStyle screenTitle = TextStyle(
    fontSize: 26,
    fontWeight: FontWeight.w700,
    letterSpacing: -0.5,
  );

  static const TextStyle sectionTitle = TextStyle(
    fontSize: 17,
    fontWeight: FontWeight.w700,
  );

  static const TextStyle cardTitle = TextStyle(
    fontSize: 14,
    fontWeight: FontWeight.w600,
  );

  static const TextStyle meta = TextStyle(fontSize: 12);
}
