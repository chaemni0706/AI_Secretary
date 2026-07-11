package com.example.frontend

import android.content.Context
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import java.io.File

/**
 * 온디바이스 SmolVLM-500M(q4f16 ONNX Runtime) 1차 evidence 브릿지.
 *
 * Flutter 측 [SmolOndeviceVerifier] (MethodChannel `ai_secretary/smolvlm`) 의 네이티브 대응.
 * **fallback-safe**: 어떤 경로에서도 예외를 Flutter 로 던지지 않고, 실패 시 항상 JSON(success=false / fallback_required=true)
 * 을 반환해 앱이 서버 Qwen2.5-VL-7B fallback 을 타게 한다.
 *
 * 현재 구현 범위(정직히):
 *  - onnxruntime-android 의존성 + OrtEnvironment/OrtSession **로드(warmup)** + 모델 가용성/정보 조회.
 *  - `verifyImage` 의 **실제 추론은 미구현**: SmolVLM 의 이미지 전처리(anyres tiling)/토크나이저/chat template/
 *    디코더 autoregressive(KV-cache) 파이프라인이 방대하고 실기기 검증이 필요해, 여기서는
 *    `status=unsupported_preprocessing`, `fallback_required=true` 를 반환한다(→ 서버 fallback).
 *
 * 모델 파일(git/assets 미포함, ~356MB): 앱 `filesDir/models/smolvlm/` 에서 로드한다.
 *   vision_encoder_q4f16.onnx, embed_tokens_q4f16.onnx, decoder_model_merged_q4f16.onnx,
 *   tokenizer.json, config.json, preprocessor_config.json
 *
 * 주의: Smol 은 final verifier 가 아니다. Smol verified(특히 water)는 로컬 단독 확정 금지.
 */
class SmolVlmBridge(private val context: Context) {
    companion object {
        const val CHANNEL = "ai_secretary/smolvlm"
        val ONNX_FILES = listOf(
            "vision_encoder_q4f16.onnx",
            "embed_tokens_q4f16.onnx",
            "decoder_model_merged_q4f16.onnx",
        )
        val SUPPORT_FILES = listOf("tokenizer.json", "config.json", "preprocessor_config.json")
    }

    private fun modelDir(): File = File(context.filesDir, "models/smolvlm")

    private fun requiredFiles(): List<String> = ONNX_FILES + SUPPORT_FILES

    private fun missingFiles(): List<String> {
        val dir = modelDir()
        return requiredFiles().filter { !File(dir, it).exists() }
    }

    private fun isModelAvailable(): Boolean = missingFiles().isEmpty()

    private fun getModelInfo(): HashMap<String, Any?> {
        val dir = modelDir()
        val found = HashMap<String, Boolean>()
        var totalBytes = 0L
        for (f in requiredFiles()) {
            val file = File(dir, f)
            val exists = file.exists()
            found[f] = exists
            if (exists) totalBytes += file.length()
        }
        return hashMapOf(
            "success" to true,
            "engine" to "smol_ondevice",
            "model_dir" to dir.absolutePath,
            "expected_files" to requiredFiles(),
            "found" to found,
            "available" to isModelAvailable(),
            "total_bytes" to totalBytes,
            "status" to if (isModelAvailable()) "available" else "unavailable",
        )
    }

    /** OrtEnvironment + OrtSession 3종 로드 시도(전처리/추론은 아직 미수행). */
    private fun warmup(): HashMap<String, Any?> {
        val missing = missingFiles()
        if (missing.isNotEmpty()) {
            return hashMapOf(
                "success" to false,
                "engine" to "smol_ondevice",
                "status" to "unavailable",
                "fallback_required" to true,
                "message" to "model files missing: $missing",
            )
        }
        var env: OrtEnvironment? = null
        val sessions = ArrayList<OrtSession>()
        return try {
            env = OrtEnvironment.getEnvironment()
            val opts = OrtSession.SessionOptions()
            val ioNames = HashMap<String, Any?>()
            for (f in ONNX_FILES) {
                val session = env.createSession(File(modelDir(), f).absolutePath, opts)
                sessions.add(session)
                ioNames[f] = hashMapOf(
                    "inputs" to session.inputNames.toList(),
                    "outputs" to session.outputNames.toList(),
                )
            }
            hashMapOf(
                "success" to true,
                "engine" to "smol_ondevice",
                "status" to "loaded",
                "fallback_required" to false,
                "sessions_loaded" to sessions.size,
                "io" to ioNames,
                "message" to "OrtSession(3) loaded",
            )
        } catch (t: Throwable) {
            hashMapOf(
                "success" to false,
                "engine" to "smol_ondevice",
                "status" to "error",
                "fallback_required" to true,
                "message" to "warmup failed: ${t.javaClass.simpleName}: ${t.message}",
            )
        } finally {
            for (s in sessions) {
                try { s.close() } catch (_: Throwable) {}
            }
        }
    }

    /**
     * 이미지 추론. **현재 미구현(전처리/생성 파이프라인)** → unsupported_preprocessing 반환(서버 fallback 유도).
     * 실구현 시: preprocess → vision_encoder → embed_tokens → decoder(autoregressive, use_cache) →
     * detokenize → evidence JSON(서버와 동일 schema, final_result 없음)로 교체.
     */
    private fun verifyImage(imagePath: String?, task: String?): HashMap<String, Any?> {
        if (!isModelAvailable()) {
            return hashMapOf(
                "success" to false, "engine" to "smol_ondevice", "status" to "unavailable",
                "fallback_required" to true, "message" to "model not available on device",
            )
        }
        // 전처리/토크나이저/디코더 루프 미구현 → 안전하게 fallback.
        return hashMapOf(
            "success" to false,
            "engine" to "smol_ondevice",
            "status" to "unsupported_preprocessing",
            "fallback_required" to true,
            "task" to (task ?: ""),
            "uncertainty" to "high",
            "blockers" to emptyList<String>(),
            "parse_status" to "unsupported",
            "message" to "on-device SmolVLM preprocessing/generation not implemented yet; use server fallback",
        )
    }

    fun register(flutterEngine: FlutterEngine) {
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL)
            .setMethodCallHandler { call, result ->
                try {
                    when (call.method) {
                        // 신규 리치 API
                        "isModelAvailable" -> result.success(isModelAvailable())
                        "getModelInfo" -> result.success(getModelInfo())
                        "warmup" -> result.success(warmup())
                        "verifyImage" -> result.success(
                            verifyImage(call.argument("imagePath"), call.argument("task"))
                        )
                        // 하위호환(기존 Dart 오케스트레이터)
                        "isAvailable" -> result.success(isModelAvailable())
                        "inferEvidence" -> {
                            // 미구현 → null 반환(오케스트레이터가 서버 fallback).
                            result.success(null)
                        }
                        else -> result.notImplemented()
                    }
                } catch (t: Throwable) {
                    // 절대 크래시 내지 않는다 — fallback-safe.
                    result.success(
                        hashMapOf(
                            "success" to false, "engine" to "smol_ondevice", "status" to "error",
                            "fallback_required" to true, "message" to (t.message ?: t.javaClass.simpleName),
                        )
                    )
                }
            }
    }
}
