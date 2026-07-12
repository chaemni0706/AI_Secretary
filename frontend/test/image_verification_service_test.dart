import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/models/verification_result.dart';
import 'package:frontend/services/image_verification_service.dart';
import 'package:frontend/services/smol_ondevice_verifier.dart';
import 'package:frontend/services/verification_api.dart';

/// Smol blocker 또는 null 을 돌려주는 가짜 온디바이스 verifier.
/// (실제 inferBlocker 는 내부 try/catch 로 오류 시 null 을 반환하는 fallback-safe 계약.)
class _FakeSmol extends SmolOndeviceVerifier {
  final Map<String, dynamic>? blocker;
  const _FakeSmol({this.blocker});

  @override
  Future<Map<String, dynamic>?> inferBlocker({required File imageFile, required String task}) async {
    return blocker; // null = 명백한 blocker 없음(positive/약함/오류) → 서버 fallback
  }

  // positive local accept 경로는 항상 닫힘(서버로).
  @override
  Future<Map<String, dynamic>?> inferEvidence(
          {required File imageFile, required String task, String? activityType}) async =>
      null;
}

/// 서버 호출 여부를 기록하고 고정 결과를 돌려주는 가짜 API.
class _FakeApi extends VerificationApi {
  final VerificationResult result;
  final List<String> calls;
  const _FakeApi(this.result, this.calls);

  @override
  Future<VerificationResult> submitImageVerification(
      {required String verificationType, required File imageFile, String? activityType}) async {
    calls.add(verificationType);
    return result;
  }
}

VerificationResult _server(String task, String result, {bool review = false}) =>
    VerificationResult.fromData({
      'verification_type': task,
      'result': result,
      'review_required': review,
      'rule_evidence': [
        {'message': 'server reason'}
      ],
      'score': 70,
    });

void main() {
  final img = File('dummy.jpg');

  test('Smol 명백한 blocker → 로컬 retake_required, 서버 호출 안 함', () async {
    final calls = <String>[];
    final svc = ImageVerificationService(
      smol: const _FakeSmol(blocker: {
        'local_blocker_detected': true,
        'blockers': ['non_water_beverage'],
        'evidence_codes': ['non_water_beverage'],
        'reason': 'water: colored/non-water beverage blocker',
        'generated_text': 'Orange juice.',
      }),
      api: _FakeApi(_server('water', 'verified'), calls),
    );
    final r = await svc.verify(imageFile: img, task: 'water');
    expect(r.finalResult, 'retake_required');
    expect(r.engineUsed, 'smol_ondevice');
    expect(r.fallbackUsed, isFalse);
    expect(r.smolBlockerDetected, isTrue);
    expect(r.isVerified, isFalse); // local accept 없음
    expect(calls, isEmpty); // 서버 호출 skip
  });

  test('Smol blocker 없음(null) → 서버 fallback 호출', () async {
    final calls = <String>[];
    final svc = ImageVerificationService(
      smol: const _FakeSmol(blocker: null),
      api: _FakeApi(_server('study', 'verified'), calls),
    );
    final r = await svc.verify(imageFile: img, task: 'study');
    expect(r.engineUsed, 'server_fallback');
    expect(r.fallbackUsed, isTrue);
    expect(calls, ['study']); // 서버가 호출됨
  });

  test('water 서버 verified → review_required(재촬영), 로컬 accept 아님', () async {
    final calls = <String>[];
    final svc = ImageVerificationService(
      smol: const _FakeSmol(blocker: null),
      api: _FakeApi(_server('water', 'verified'), calls),
    );
    final r = await svc.verify(imageFile: img, task: 'water');
    expect(r.reviewRequired, isTrue); // water verified → review(재촬영)
    expect(r.needsRetake, isTrue);
    expect(r.isVerified, isFalse);
    expect(calls, ['water']);
  });

  test('Smol 실패/오류(inferBlocker null 계약) → 서버 fallback, 로컬 accept 없음', () async {
    final calls = <String>[];
    final svc = ImageVerificationService(
      smol: const _FakeSmol(blocker: null), // 오류/약함 → null 로 정규화됨
      api: _FakeApi(_server('exercise', 'rejected'), calls),
    );
    final r = await svc.verify(imageFile: img, task: 'exercise', activityType: 'gym');
    expect(r.engineUsed, 'server_fallback');
    expect(r.finalResult, 'rejected');
    expect(calls, ['exercise']);
  });
}
