import 'package:flutter/material.dart';

/// 토스(TDS) 스타일 디자인 토큰 — 앱 전체 스타일의 단일 진실 소스.
///
/// 색·타이포·radius·spacing·그림자는 반드시 이 토큰만 참조한다.
/// 화면/위젯 코드에 hex, 픽셀 값을 직접 쓰지 말 것.
class TossColors {
  TossColors._();

  // Grey scale (토스 공개 값)
  static const Color grey50 = Color(0xFFF9FAFB);
  static const Color grey100 = Color(0xFFF2F4F6);
  static const Color grey200 = Color(0xFFE5E8EB);
  static const Color grey300 = Color(0xFFD1D6DB);
  static const Color grey400 = Color(0xFFB0B8C1);
  static const Color grey500 = Color(0xFF8B95A1);
  static const Color grey600 = Color(0xFF6B7684);
  static const Color grey700 = Color(0xFF4E5968);
  static const Color grey800 = Color(0xFF333D4B);
  static const Color grey900 = Color(0xFF191F28);

  // Brand
  static const Color blue500 = Color(0xFF3182F6); // primary
  static const Color blue600 = Color(0xFF1B64DA);
  static const Color blue700 = Color(0xFF1957C2);
  static const Color blueWeak = Color(0xFFE8F3FF); // primary-weak 배경

  // Semantic
  static const Color red = Color(0xFFF04452); // error / 지출
  static const Color redWeak = Color(0xFFFDEDEE);
  static const Color green = Color(0xFF02B33A); // positive / 수입
  static const Color greenWeak = Color(0xFFE6F6EC);
  static const Color orange = Color(0xFFFF9E00);
  static const Color orangeWeak = Color(0xFFFFF4E0);
  static const Color purple = Color(0xFF7048E8);
  static const Color purpleWeak = Color(0xFFF1EDFD);
  static const Color teal = Color(0xFF00B8B0);
  static const Color tealWeak = Color(0xFFE2F8F7);

  // Text 시맨틱
  static const Color textPrimary = grey900;
  static const Color textSecondary = grey600;
  static const Color textAssistive = grey400;
  static const Color textOnPrimary = Colors.white;

  // Background 시맨틱
  static const Color bgWhite = Color(0xFFFFFFFF);
  static const Color bgGrey = grey100;
  static const Color bgFloated = Color(0xFFFFFFFF);
  static const Color dim = Color(0x66191F28); // 모달 뒤 딤 (grey900 40%)

  // 누름 상태 오버레이
  static const Color pressedGrey = Color(0x0F191F28); // grey900 6%
}

class TossRadius {
  TossRadius._();

  static const double sm = 8;
  static const double md = 12;
  static const double lg = 16;
  static const double xl = 20;
  static const double full = 999;
}

class TossSpacing {
  TossSpacing._();

  static const double xs = 4;
  static const double sm = 8;
  static const double md = 12;
  static const double lg = 16;
  static const double xl = 20;
  static const double xxl = 24;
  static const double xxxl = 32;

  /// 화면 좌우 기본 여백.
  static const double screen = 20;
}

class TossShadow {
  TossShadow._();

  /// 칩/작은 표면 — 아주 옅게.
  static const List<BoxShadow> tiny = [
    BoxShadow(
      color: Color(0x08191F28),
      blurRadius: 8,
      offset: Offset(0, 2),
    ),
  ];

  /// 카드 기본.
  static const List<BoxShadow> weak = [
    BoxShadow(
      color: Color(0x0A191F28),
      blurRadius: 20,
      offset: Offset(0, 4),
    ),
  ];

  /// Floated 표면 / 강조 카드.
  static const List<BoxShadow> medium = [
    BoxShadow(
      color: Color(0x14191F28),
      blurRadius: 28,
      offset: Offset(0, 8),
    ),
  ];
}

class TossTypography {
  TossTypography._();

  static const String fontFamily = 'Pretendard';

  /// 큰 금액/화면 타이틀 (Bold 28)
  static const TextStyle display = TextStyle(
    fontFamily: fontFamily,
    fontSize: 28,
    fontWeight: FontWeight.w700,
    height: 1.3,
    letterSpacing: -0.4,
    color: TossColors.textPrimary,
  );

  /// 섹션 큰 타이틀 (Bold 22)
  static const TextStyle title1 = TextStyle(
    fontFamily: fontFamily,
    fontSize: 22,
    fontWeight: FontWeight.w700,
    height: 1.35,
    letterSpacing: -0.3,
    color: TossColors.textPrimary,
  );

  /// 카드/섹션 타이틀 (Semibold 19)
  static const TextStyle title2 = TextStyle(
    fontFamily: fontFamily,
    fontSize: 19,
    fontWeight: FontWeight.w600,
    height: 1.4,
    letterSpacing: -0.2,
    color: TossColors.textPrimary,
  );

  /// 리스트 행 타이틀 (Semibold 17)
  static const TextStyle title3 = TextStyle(
    fontFamily: fontFamily,
    fontSize: 17,
    fontWeight: FontWeight.w600,
    height: 1.4,
    color: TossColors.textPrimary,
  );

  /// 본문 (Regular 15)
  static const TextStyle body = TextStyle(
    fontFamily: fontFamily,
    fontSize: 15,
    fontWeight: FontWeight.w400,
    height: 1.45,
    color: TossColors.textPrimary,
  );

  /// 버튼/강조 라벨 (Medium 15)
  static const TextStyle label = TextStyle(
    fontFamily: fontFamily,
    fontSize: 15,
    fontWeight: FontWeight.w500,
    height: 1.4,
    color: TossColors.textPrimary,
  );

  /// 보조 설명 (Regular 13, grey600)
  static const TextStyle caption = TextStyle(
    fontFamily: fontFamily,
    fontSize: 13,
    fontWeight: FontWeight.w400,
    height: 1.4,
    color: TossColors.textSecondary,
  );

  /// 아주 작은 뱃지/메타 (Medium 11)
  static const TextStyle small = TextStyle(
    fontFamily: fontFamily,
    fontSize: 11,
    fontWeight: FontWeight.w500,
    height: 1.35,
    color: TossColors.textSecondary,
  );
}

class TossMotion {
  TossMotion._();

  /// 마이크로 인터랙션 (누름 피드백 등)
  static const Duration fast = Duration(milliseconds: 150);

  /// 기본 전환
  static const Duration normal = Duration(milliseconds: 250);

  /// 등장 모션
  static const Duration slow = Duration(milliseconds: 350);

  static const Curve easeOut = Curves.easeOutCubic;

  /// 약간의 오버슈트가 있는 스프링 느낌.
  static const Curve spring = Curves.easeOutBack;

  /// 누름 시 스케일.
  static const double pressedScale = 0.96;
}
