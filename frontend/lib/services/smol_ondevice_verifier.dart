import 'dart:io';

import 'package:flutter/services.dart';

/// 온디바이스 SmolVLM-500M(q4f16 ONNX Runtime) 1차 evidence 인터페이스.
///
/// 네이티브 [SmolVlmBridge] (MethodChannel `ai_secretary/smolvlm`) 와 연결된다.
/// **fallback-safe**: 네이티브 미등록/모델 미존재/추론 미지원/예외 등 어떤 경우에도 예외를 던지지 않고,
/// 사용 불가로 판단해 오케스트레이터([ImageVerificationService])가 서버 Qwen2.5-VL-7B fallback 을 타게 한다.
///
/// 현재 상태(정직히): 네이티브는 OrtSession **로드(warmup)** 까지 구현. 실제 이미지 추론
/// (전처리/토크나이저/디코더 생성)은 미구현 → `verifyImage` 는 `fallback_required=true` 를 반환한다.
///
/// 모델 파일(git/assets 미포함, ~356MB)은 앱 `filesDir/models/smolvlm/` 에 배치. 자세한 건 `SMOL_ONDEVICE_STATUS.md`.
///
/// 주의: Smol 은 final verifier 가 아니다. Smol `verified`(특히 water)는 로컬 단독 확정 금지.
class SmolOndeviceVerifier {
  static const MethodChannel _channel = MethodChannel('ai_secretary/smolvlm');

  const SmolOndeviceVerifier();

  /// 온디바이스 모델 파일 존재 여부(빠른 확인).
  Future<bool> isModelAvailable() async {
    try {
      final ok = await _channel.invokeMethod<bool>('isModelAvailable');
      return ok ?? false;
    } on MissingPluginException {
      return false; // 네이티브 브릿지 미등록(예: iOS/데스크톱)
    } on PlatformException {
      return false;
    }
  }

  /// (하위호환) isModelAvailable 과 동일.
  Future<bool> isAvailable() => isModelAvailable();

  /// 모델 자산 정보(경로/파일별 존재/총 크기/상태).
  Future<Map<String, dynamic>?> getModelInfo() async {
    try {
      return await _channel.invokeMapMethod<String, dynamic>('getModelInfo');
    } on MissingPluginException {
      return null;
    } on PlatformException {
      return null;
    }
  }

  /// OrtSession 로드 시도(모델 input/output 이름 반환). 실패해도 예외 없이 map 반환.
  Future<Map<String, dynamic>?> warmup() async {
    try {
      return await _channel.invokeMapMethod<String, dynamic>('warmup');
    } on MissingPluginException {
      return {'success': false, 'status': 'unavailable', 'fallback_required': true};
    } on PlatformException catch (e) {
      return {'success': false, 'status': 'error', 'fallback_required': true, 'message': e.message};
    }
  }

  /// 온디바이스 추론 시도. 현재는 미지원(unsupported_preprocessing) → fallback_required=true.
  Future<Map<String, dynamic>?> verifyImage({
    required File imageFile,
    required String task,
    String? activityType,
  }) async {
    try {
      return await _channel.invokeMapMethod<String, dynamic>('verifyImage', {
        'imagePath': imageFile.path,
        'task': task,
        if (activityType != null) 'activityType': activityType,
      });
    } on MissingPluginException {
      return {'success': false, 'status': 'unavailable', 'fallback_required': true};
    } on PlatformException catch (e) {
      return {'success': false, 'status': 'error', 'fallback_required': true, 'message': e.message};
    }
  }

  /// L4 blocker 실험(dev): cached generation loop 을 decoder opt-level 별로 시도. fallback-safe.
  Future<Map<String, dynamic>?> l4Experiment() async {
    try {
      return await _channel.invokeMapMethod<String, dynamic>('l4Experiment');
    } on MissingPluginException {
      return {'success': false, 'status': 'unavailable', 'fallback_required': true};
    } on PlatformException catch (e) {
      return {'success': false, 'status': 'error', 'fallback_required': true, 'message': e.message};
    }
  }

  /// image+text 짧은 생성 spike(dev): vision→embed→image merge→no-cache 생성→detokenize. fallback-safe.
  Future<Map<String, dynamic>?> imageTextGen({required File imageFile, int maxNew = 12, int padLen = 96}) async {
    try {
      return await _channel.invokeMapMethod<String, dynamic>('imageTextGen', {
        'imagePath': imageFile.path,
        'maxNew': maxNew,
        'padLen': padLen,
      });
    } on MissingPluginException {
      return {'success': false, 'status': 'unavailable', 'fallback_required': true};
    } on PlatformException catch (e) {
      return {'success': false, 'status': 'error', 'fallback_required': true, 'message': e.message};
    }
  }

  /// 오케스트레이터용: **로컬 채택 가능한 evidence** 가 나오면 map 을, 아니면 null 을 반환(→ 서버 fallback).
  /// 현재 네이티브 추론이 미구현이라 항상 null(fallback) — 온디바이스 추론이 붙으면 evidence map 반환.
  Future<Map<String, dynamic>?> inferEvidence({
    required File imageFile,
    required String task,
    String? activityType,
  }) async {
    if (!await isModelAvailable()) return null;
    final res = await verifyImage(imageFile: imageFile, task: task, activityType: activityType);
    if (res == null) return null;
    // fallback 이 필요하거나 성공하지 못했으면 서버로.
    if (res['fallback_required'] == true || res['success'] != true) return null;
    return res; // 서버와 동일 evidence schema 로 정규화된 결과(향후 네이티브 구현 시)
  }
}

const smolOndeviceVerifier = SmolOndeviceVerifier();
