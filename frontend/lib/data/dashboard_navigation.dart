import 'package:flutter/foundation.dart';

/// 위젯 대시보드 → 하단 탭 전환 요청용 전역 notifier.
///
/// 위젯을 누르면 [requestTab] 을 호출하고, [MainNavigator] 가 이 값을 listen 하여
/// 실제 하단 탭을 전환한다. (service/model 계층은 건드리지 않는 UI 전용 신호)
///
/// 하단 탭 인덱스: 0 캘린더 · 1 할 일 · 2 위젯 · 3 가계부 · 4 마이페이지
class DashboardTabIndex {
  DashboardTabIndex._();
  static const int calendar = 0;
  static const int todo = 1;
  static const int widget = 2;
  static const int ledger = 3;
  static const int myPage = 4;
}

/// 마지막으로 요청된 탭 인덱스. -1 은 "요청 없음"(초기/처리 완료 상태).
final ValueNotifier<int> requestedTabIndex = ValueNotifier<int>(-1);

void requestTab(int index) {
  requestedTabIndex.value = index;
}

/// 리스너가 처리한 뒤 호출하여 신호를 초기화한다.
void clearTabRequest() {
  requestedTabIndex.value = -1;
}
