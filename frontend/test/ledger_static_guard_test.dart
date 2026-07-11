import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

/// 정적 회귀 가드(소스 문자열 점검). 실기기/서버 없이 `flutter test` 로 돈다.
///
/// 이력 메모:
/// - m1: _BudgetAlertBanner 하드코딩 문구 제거 → 아래 가드로 회귀 방지(유지).
/// - m2(폐기): 한때 '거래 수정에서 memo 입력/전송 제거'를 가드했으나, 이후 memo 가
///   가계부 정식 필드로 재도입되었다(DB ledger_transactions.memo 컬럼 +
///   ledger_api.updateTransaction 의 memo 파라미터 + ledger_screen 의 메모 입력).
///   더 이상 유효하지 않은 결정을 강제하므로 memo 부재 가드는 제거한다.
void main() {
  test('_BudgetAlertBanner 하드코딩 문구가 활성 화면 코드에 없다', () {
    final src = File('lib/screens/ledger_screen.dart').readAsStringSync();
    expect(src.contains('84%'), isFalse, reason: "84% 하드코딩 잔존");
    expect(src.contains('카페 예산'), isFalse, reason: "'카페 예산' 하드코딩 잔존");
  });
}
