package com.example.frontend

import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

/**
 * 온디바이스 SmolVLM-500M(ONNX Runtime) 추론 브릿지 **스켈레톤**.
 *
 * Flutter 측 [SmolOndeviceVerifier] (MethodChannel `ai_secretary/smolvlm`) 의 네이티브 대응.
 * 현재는 **stub**: `isAvailable` = false 를 반환해 앱이 서버 Qwen2.5-VL-7B fallback 을 타게 한다.
 *
 * 실동작시키려면(루트 SMOL_ONDEVICE_STATUS.md 참조):
 *  1. build.gradle 에 `implementation("com.microsoft.onnxruntime:onnxruntime-android:<ver>")` 추가.
 *  2. assets/models/smolvlm/ 에 q4f16 ONNX(vision_encoder/embed_tokens/decoder_merged) +
 *     tokenizer/merges/chat_template/preprocessor 동봉(**git 미포함**, release 시 주입).
 *  3. onLoad(): OrtEnvironment + OrtSession 3개 로드 → isAvailable=true.
 *  4. inferEvidence(): image preprocess → vision_encoder → embed_tokens → decoder(autoregressive, use_cache)
 *     → detokenize → evidence JSON(서버와 동일 schema) 반환.
 *
 * 주의: Smol 은 final verifier 가 아니다. Smol verified(특히 water)는 로컬 단독 확정 금지.
 *
 * MainActivity 에는 아직 배선하지 않았다. 활성화하려면 MainActivity.configureFlutterEngine 에서
 * `SmolVlmBridge().register(flutterEngine)` 를 호출한다.
 */
class SmolVlmBridge {
    companion object {
        const val CHANNEL = "ai_secretary/smolvlm"
    }

    // TODO: OrtSession 3종(vision/embed/decoder) 로드 후 true 로 전환.
    private val modelLoaded: Boolean = false

    fun register(flutterEngine: FlutterEngine) {
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL)
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "isAvailable" -> result.success(isAvailable())
                    "inferEvidence" -> {
                        // stub: 미구현 → null 반환하여 Flutter 오케스트레이터가 서버 fallback 을 타게 함.
                        // 실구현 시 evidence JSON(Map) 을 result.success(map) 로 반환.
                        result.success(null)
                    }
                    else -> result.notImplemented()
                }
            }
    }

    private fun isAvailable(): Boolean = modelLoaded
}
