import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

/// 1차 수정 회귀 가드(정적 점검).
/// - m2: 거래 수정에서 memo 입력/전송 제거
/// - m1: _BudgetAlertBanner 하드코딩 문구 제거
///
/// 소스 파일 내용을 검사하는 정적 테스트라 실기기/서버 없이 `flutter test` 로 돈다.
void main() {
  test('ledgerApi.updateTransaction 은 memo 를 파라미터/‌body 로 전송하지 않는다', () {
    final src = File('lib/services/ledger_api.dart').readAsStringSync();
    expect(src.contains("body['memo']"), isFalse,
        reason: "PATCH body 에 memo 가 들어가면 안 됨");
    expect(src.contains('String? memo'), isFalse,
        reason: "updateTransaction 시그니처에 memo 파라미터가 남아 있으면 안 됨");
  });

  test('거래 수정 다이얼로그에 memo 입력 필드가 없다', () {
    final src = File('lib/screens/ledger_screen.dart').readAsStringSync();
    expect(src.contains('memoCtl'), isFalse, reason: "memo 컨트롤러 잔존");
    expect(RegExp(r"labelText:\s*'메모").hasMatch(src), isFalse,
        reason: "memo TextField labelText 잔존");
  });

  test('_BudgetAlertBanner 하드코딩 문구가 활성 화면 코드에 없다', () {
    final src = File('lib/screens/ledger_screen.dart').readAsStringSync();
    expect(src.contains('84%'), isFalse, reason: "84% 하드코딩 잔존");
    expect(src.contains('카페 예산'), isFalse, reason: "'카페 예산' 하드코딩 잔존");
  });
}
