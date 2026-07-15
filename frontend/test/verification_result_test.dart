// VerificationResult getter 로직: review_required 는 "자동 확정 불가 → 재촬영" 을 의미한다.
// water verified 는 자동 성공(isVerified)이 아니라 needsRetake 로 처리되어야 한다.
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/models/verification_result.dart';

void main() {
  VerificationResult fromData(Map<String, dynamic> data) =>
      VerificationResult.fromData(data);

  test('water verified 는 자동 성공이 아니라 재촬영 안내(needsRetake)', () {
    final r = fromData({'verification_type': 'water', 'result': 'verified', 'score': 65});
    expect(r.reviewRequired, isTrue);
    expect(r.isVerified, isFalse); // 자동 확정 아님
    expect(r.needsRetake, isTrue);
    expect(r.needsSecondaryReview, isTrue); // 하위호환 별칭
    expect(r.displayMessage.contains('다시 촬영'), isTrue);
  });

  test('review_required=true 는 자동 성공(isVerified)로 처리되지 않는다', () {
    final r = fromData({
      'verification_type': 'water', 'result': 'verified', 'review_required': true,
    });
    expect(r.isVerified, isFalse);
    expect(r.needsRetake, isTrue);
  });

  test('exercise verified 는 기존처럼 자동 성공', () {
    final r = fromData({'verification_type': 'exercise', 'result': 'verified', 'score': 70});
    expect(r.reviewRequired, isFalse);
    expect(r.isVerified, isTrue);
    expect(r.needsRetake, isFalse);
    expect(r.displayMessage.contains('성공'), isTrue);
  });

  test('study verified 는 기존처럼 자동 성공', () {
    final r = fromData({'verification_type': 'study', 'result': 'verified'});
    expect(r.isVerified, isTrue);
    expect(r.needsRetake, isFalse);
  });

  test('water rejected 는 재촬영 대상 아님(거절)', () {
    final r = fromData({'verification_type': 'water', 'result': 'rejected'});
    expect(r.needsRetake, isFalse);
    expect(r.isRejected, isTrue);
  });
}
