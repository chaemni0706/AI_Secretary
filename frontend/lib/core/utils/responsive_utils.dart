import 'package:flutter/material.dart';

import '../theme/app_dimens.dart';

/// 모바일 반응형 공통 helper.
/// 화면 폭/인셋 기반의 단순 분기만 제공한다. (과한 추상화 지양)
class ResponsiveUtils {
  ResponsiveUtils._();

  /// 좁은 화면 기준 폭. 이 값 미만이면 compact 로 간주한다.
  static const double compactBreakpoint = 340.0;

  /// 현재 화면이 좁은 폭(compact)인지 여부.
  /// - true 이면 2열 그리드를 1열로 떨어뜨리는 등의 처리에 사용.
  static bool isCompactWidth(BuildContext context) {
    return MediaQuery.sizeOf(context).width < compactBreakpoint;
  }

  /// 2열 카드 그리드의 열 개수.
  /// - 좁은 화면: 1열, 그 외: 2열
  static int responsiveCardColumns(BuildContext context) {
    return isCompactWidth(context) ? 1 : 2;
  }

  /// 탭 화면(스크롤형)의 하단 padding.
  /// BottomNavigationBar 높이 + Android gesture/system inset 을 함께 고려해
  /// 마지막 콘텐츠가 하단 바에 가려지지 않게 한다.
  static double tabBottomPadding(BuildContext context) {
    // NavigationBar 표준 높이(약 80) + 시스템 하단 인셋
    const navBarHeight = 80.0;
    final systemInset = MediaQuery.viewPaddingOf(context).bottom;
    return navBarHeight + systemInset + AppDimens.md;
  }
}