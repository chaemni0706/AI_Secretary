package com.example.frontend

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import ai.onnxruntime.OnnxJavaType
import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import org.json.JSONObject
import java.io.File
import java.nio.ByteBuffer
import java.nio.FloatBuffer
import java.nio.LongBuffer
import java.nio.charset.StandardCharsets

/**
 * 온디바이스 SmolVLM-500M(q4f16 ONNX Runtime) 1차 evidence 브릿지.
 *
 * Flutter 측 [SmolOndeviceVerifier] (MethodChannel `ai_secretary/smolvlm`) 의 네이티브 대응.
 * **fallback-safe**: 어떤 경로에서도 예외를 Flutter 로 던지지 않고, 실패 시 항상 JSON(success=false / fallback_required=true)
 * 을 반환해 앱이 서버 Qwen2.5-VL-7B fallback 을 타게 한다.
 *
 * 현재 구현 범위(정직히):
 *  - onnxruntime-android 의존성 + OrtEnvironment/OrtSession **로드(warmup)** + 모델 가용성/정보 조회.
 *  - `verifyImage` 는 **추론 경로 spike(Level 1~4)**: 전처리+vision_encoder / embed_tokens / decoder 1-step / 짧은
 *    greedy loop 를 각각 시도해 Level 별 성공/shape/latency 를 보고한다. **완성 인증 아님** — 항상
 *    `fallback_required=true`(서버 fallback). image-merge/anyres/tokenizer/chat_template/detokenize 는 미구현.
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

        // --- spike constants (SmolVLM-500M q4f16 signature) ---
        const val IMG = 512                // preprocessor longest_edge (single-tile spike)
        const val N_LAYERS = 32            // decoder layers (past_key_values.0..31)
        const val N_KV_HEADS = 5L          // KV head 수
        const val HEAD_DIM = 64L           // head dim
        const val EOS_ID = 49279L
        // 고정 프롬프트 "Describe the image." 의 token ids(BOS 포함). tokenizer 미구현 spike 용.
        val PROMPT_IDS = longArrayOf(1L, 37964L, 260L, 2443L, 30L)

        // --- image-text generation 용 (SmolVLM processor 출력, do_image_splitting=false) ---
        const val HIDDEN = 960
        const val IMG_TOKEN_ID = 49190L
        const val IMG_POS_START = 5     // image_token 64개 시작 위치
        const val IMG_FEAT_COUNT = 64   // vision_encoder image_features 토큰 수
        // "<|im_start|>User:<image>×64 Describe the drink briefly.<end_of_utterance>\nAssistant:" 의 input_ids(len 80).
        // (prefix 5) + (image_token 64 @ 위치 5..68) + (suffix 11). image_features 를 이미지 위치 임베딩에 치환 후 no-cache 생성.
        val PROMPT_IMG_IDS: LongArray = run {
            val prefix = longArrayOf(1L, 11126L, 42L, 49189L, 49152L)
            val suffix = longArrayOf(49189L, 37964L, 260L, 5968L, 13099L, 30L, 49279L, 198L, 9519L, 9531L, 42L)
            LongArray(prefix.size + IMG_FEAT_COUNT + suffix.size) { i ->
                when {
                    i < prefix.size -> prefix[i]
                    i < prefix.size + IMG_FEAT_COUNT -> IMG_TOKEN_ID
                    else -> suffix[i - prefix.size - IMG_FEAT_COUNT]
                }
            }
        }
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
     * 이미지 추론 **spike (Level 1~4)** — 온디바이스 ONNX 추론 경로 검증용. 완성 인증 아님.
     *
     * L1 preprocess+vision_encoder / L2 embed_tokens(하드코딩 프롬프트) / L3 decoder 1-step(text-only, 빈 KV prefill)
     * / L4 짧은 greedy loop. 각 Level 개별 try → 부분 성공도 보고. 항상 fallback_required=true(서버 fallback 유지).
     *
     * 단순화(spike caveat): 이미지는 단일 512x512(anyres splitting 미적용), image_features 를 디코더 embed 에 병합하지 않음
     * (text-only), 토크나이저는 고정 프롬프트 token ids 하드코딩. 실제 인증은 서버 fallback 이 담당.
     */
    private fun verifyImage(imagePath: String?, task: String?): HashMap<String, Any?> {
        if (!isModelAvailable()) {
            return hashMapOf(
                "success" to false, "engine" to "smol_ondevice", "status" to "unavailable",
                "fallback_required" to true, "message" to "model not available on device",
            )
        }
        if (imagePath == null || !File(imagePath).exists()) {
            return hashMapOf(
                "success" to false, "engine" to "smol_ondevice", "status" to "no_image",
                "fallback_required" to true, "message" to "image not found: $imagePath",
            )
        }
        val levels = HashMap<String, Any?>()
        val closeables = ArrayList<AutoCloseable>()
        val env = OrtEnvironment.getEnvironment()
        try {
            val opts = OrtSession.SessionOptions()
            // KV-cache 증분 디코딩(L4) 시 merged decoder 의 InsertedPrecisionFreeCast 가 ORT 메모리패턴
            // 버퍼 재사용과 충돌(shape {1,6,960}!={1,1,960}) → memory pattern 비활성화로 회피 시도.
            try { opts.setMemoryPatternOptimization(false) } catch (_: Throwable) {}
            val visionS = env.createSession(File(modelDir(), "vision_encoder_q4f16.onnx").absolutePath, opts)
            val embedS = env.createSession(File(modelDir(), "embed_tokens_q4f16.onnx").absolutePath, opts)
            val decS = env.createSession(File(modelDir(), "decoder_model_merged_q4f16.onnx").absolutePath, opts)
            closeables.add(visionS); closeables.add(embedS); closeables.add(decS)

            // ---- Level 1: preprocess + vision_encoder ------------------------------
            try {
                val t0 = System.currentTimeMillis()
                val (pv, mask) = preprocess(env, imagePath)
                closeables.add(pv); closeables.add(mask)
                val r1 = visionS.run(mapOf("pixel_values" to pv, "pixel_attention_mask" to mask))
                closeables.add(r1)
                val feat = r1.get("image_features").get() as OnnxTensor
                levels["L1_vision_encoder"] = hashMapOf(
                    "ok" to true, "image_features_shape" to feat.info.shape.toList(),
                    "ms" to (System.currentTimeMillis() - t0),
                )
            } catch (e: Throwable) {
                levels["L1_vision_encoder"] = hashMapOf("ok" to false, "error" to errStr(e))
            }

            // ---- Level 2: embed_tokens (hardcoded prompt ids) ----------------------
            var embedsTensor: OnnxTensor? = null
            try {
                val t0 = System.currentTimeMillis()
                val idT = OnnxTensor.createTensor(env, LongBuffer.wrap(PROMPT_IDS), longArrayOf(1, PROMPT_IDS.size.toLong()))
                closeables.add(idT)
                val r2 = embedS.run(mapOf("input_ids" to idT))
                closeables.add(r2)
                embedsTensor = r2.get("inputs_embeds").get() as OnnxTensor
                levels["L2_embed_tokens"] = hashMapOf(
                    "ok" to true, "inputs_embeds_shape" to embedsTensor.info.shape.toList(),
                    "ms" to (System.currentTimeMillis() - t0),
                )
            } catch (e: Throwable) {
                levels["L2_embed_tokens"] = hashMapOf("ok" to false, "error" to errStr(e))
            }

            // ---- Level 3: decoder 1-step (text-only, empty KV prefill) -------------
            var l3ok = false
            if (embedsTensor != null) {
                try {
                    val t0 = System.currentTimeMillis()
                    val seq = PROMPT_IDS.size
                    val inputs = HashMap<String, OnnxTensor>()
                    inputs["inputs_embeds"] = embedsTensor
                    inputs["attention_mask"] = OnnxTensor.createTensor(
                        env, LongBuffer.wrap(LongArray(seq) { 1L }), longArrayOf(1, seq.toLong())
                    ).also { closeables.add(it) }
                    inputs["position_ids"] = OnnxTensor.createTensor(
                        env, LongBuffer.wrap(LongArray(seq) { it.toLong() }), longArrayOf(1, seq.toLong())
                    ).also { closeables.add(it) }
                    addEmptyPast(env, inputs, closeables)
                    val r3 = decS.run(inputs)
                    closeables.add(r3)
                    val logits = r3.get("logits").get() as OnnxTensor
                    val shape = logits.info.shape // [1, seq, vocab]
                    val vocab = shape[2].toInt()
                    val fb = logits.floatBuffer
                    val argmax = argmaxAt(fb, (seq - 1) * vocab, vocab)
                    l3ok = true
                    levels["L3_decoder_step"] = hashMapOf(
                        "ok" to true, "logits_shape" to shape.toList(),
                        "argmax_token_id" to argmax, "ms" to (System.currentTimeMillis() - t0),
                    )
                } catch (e: Throwable) {
                    levels["L3_decoder_step"] = hashMapOf("ok" to false, "error" to errStr(e))
                }
            } else {
                levels["L3_decoder_step"] = hashMapOf("ok" to false, "error" to "skipped (L2 failed)")
            }

            // ---- Level 4: short greedy loop (KV-cache reuse) ----------------------
            if (l3ok) {
                try {
                    levels["L4_generation_loop"] = generationLoop(env, embedS, decS, closeables, maxNew = 5)
                } catch (e: Throwable) {
                    levels["L4_generation_loop"] = hashMapOf("ok" to false, "error" to errStr(e))
                }
            } else {
                levels["L4_generation_loop"] = hashMapOf("ok" to false, "error" to "skipped (L3 failed)")
            }
        } catch (e: Throwable) {
            return hashMapOf(
                "success" to false, "engine" to "smol_ondevice", "status" to "error",
                "fallback_required" to true, "message" to "spike failed: ${errStr(e)}", "levels" to levels,
            )
        } finally {
            for (c in closeables.reversed()) try { c.close() } catch (_: Throwable) {}
        }
        return hashMapOf(
            "success" to false,               // spike: 아직 evidence 미생성 → 서버 fallback
            "engine" to "smol_ondevice",
            "status" to "spike",
            "fallback_required" to true,
            "task" to (task ?: ""),
            "note" to "on-device inference SPIKE (text-only, no image-merge, hardcoded prompt). server fallback for real auth.",
            "levels" to levels,
        )
    }

    // ---- spike helpers ------------------------------------------------------
    private fun preprocess(env: OrtEnvironment, imagePath: String): Pair<OnnxTensor, OnnxTensor> {
        val src = BitmapFactory.decodeFile(imagePath) ?: throw IllegalStateException("decode failed")
        val bmp = Bitmap.createScaledBitmap(src, IMG, IMG, true)
        val n = IMG * IMG
        val px = IntArray(n)
        bmp.getPixels(px, 0, IMG, 0, 0, IMG, IMG)
        val pv = FloatBuffer.allocate(3 * n) // NCHW: [1,1,3,H,W], rescale 1/255 + normalize (x-0.5)/0.5
        for (i in 0 until n) {
            val p = px[i]
            pv.put(i, ((((p shr 16) and 0xFF) / 255f) - 0.5f) / 0.5f)          // R plane
            pv.put(n + i, ((((p shr 8) and 0xFF) / 255f) - 0.5f) / 0.5f)       // G plane
            pv.put(2 * n + i, (((p and 0xFF) / 255f) - 0.5f) / 0.5f)           // B plane
        }
        pv.rewind()
        val pvT = OnnxTensor.createTensor(env, pv, longArrayOf(1, 1, 3, IMG.toLong(), IMG.toLong()))
        val mb = ByteBuffer.allocateDirect(n)
        for (i in 0 until n) mb.put(1.toByte()) // pixel_attention_mask all-true
        mb.rewind()
        val maskT = OnnxTensor.createTensor(env, mb, longArrayOf(1, 1, IMG.toLong(), IMG.toLong()), OnnxJavaType.BOOL)
        return Pair(pvT, maskT)
    }

    /** 32층 past_key_values 를 빈(past_seq=0) fp16 텐서로 채운다. (fp16 = ByteBuffer + OnnxJavaType.FLOAT16) */
    private fun emptyFp16Past(env: OrtEnvironment): OnnxTensor =
        OnnxTensor.createTensor(env, ByteBuffer.allocateDirect(0), longArrayOf(1, N_KV_HEADS, 0, HEAD_DIM), OnnxJavaType.FLOAT16)

    private fun addEmptyPast(env: OrtEnvironment, inputs: HashMap<String, OnnxTensor>, cl: ArrayList<AutoCloseable>) {
        for (i in 0 until N_LAYERS) {
            for (kv in listOf("key", "value")) {
                val t = emptyFp16Past(env)
                cl.add(t)
                inputs["past_key_values.$i.$kv"] = t
            }
        }
    }

    private fun argmaxAt(fb: FloatBuffer, offset: Int, vocab: Int): Int {
        var best = 0; var bestV = Float.NEGATIVE_INFINITY
        for (j in 0 until vocab) {
            val x = fb.get(offset + j)
            if (x > bestV) { bestV = x; best = j }
        }
        return best
    }

    /**
     * Level 4: L3 의 present KV 를 past 로 재사용해 greedy 로 maxNew 토큰 생성.
     * text-only. 실패해도 예외를 던지지 않고 결과 map 반환.
     */
    private fun generationLoop(
        env: OrtEnvironment, embedS: OrtSession, decS: OrtSession,
        cl: ArrayList<AutoCloseable>, maxNew: Int,
    ): HashMap<String, Any?> {
        val t0 = System.currentTimeMillis()
        val generated = ArrayList<Long>()
        // 첫 스텝: 프롬프트 전체 prefill(빈 past) → present 확보
        var seqLen = PROMPT_IDS.size
        var idsForStep = PROMPT_IDS
        var pastKeys: Array<OnnxTensor?> = arrayOfNulls(N_LAYERS * 2) // null → 빈 past
        var step = 0
        while (step < maxNew) {
            // embed step ids
            val idT = OnnxTensor.createTensor(env, LongBuffer.wrap(idsForStep), longArrayOf(1, idsForStep.size.toLong()))
            val er = embedS.run(mapOf("input_ids" to idT))
            val emb = er.get("inputs_embeds").get() as OnnxTensor
            val curLen = idsForStep.size
            val totalLen = seqLen // attention over all seen tokens
            val inputs = HashMap<String, OnnxTensor>()
            inputs["inputs_embeds"] = emb
            val am = OnnxTensor.createTensor(env, LongBuffer.wrap(LongArray(totalLen) { 1L }), longArrayOf(1, totalLen.toLong()))
            val posStart = seqLen - curLen
            val pos = OnnxTensor.createTensor(env, LongBuffer.wrap(LongArray(curLen) { (posStart + it).toLong() }), longArrayOf(1, curLen.toLong()))
            inputs["attention_mask"] = am
            inputs["position_ids"] = pos
            for (i in 0 until N_LAYERS) {
                for ((j, kv) in listOf("key", "value").withIndex()) {
                    val prev = pastKeys[i * 2 + j]
                    inputs["past_key_values.$i.$kv"] = prev ?: emptyFp16Past(env)
                }
            }
            val r = decS.run(inputs)
            val logits = r.get("logits").get() as OnnxTensor
            val shape = logits.info.shape
            val vocab = shape[2].toInt()
            val next = argmaxAt(logits.floatBuffer, (curLen - 1) * vocab, vocab)
            generated.add(next.toLong())
            // 다음 스텝 준비: present → past (이전 past 닫기)
            for (i in 0 until N_LAYERS) {
                for ((j, kv) in listOf("key", "value").withIndex()) {
                    try { pastKeys[i * 2 + j]?.close() } catch (_: Throwable) {}
                    pastKeys[i * 2 + j] = r.get("present.$i.$kv").get() as OnnxTensor
                }
            }
            // r 는 present 텐서를 담고 있으므로 닫지 않는다(다음 스텝 past 로 사용). idT/am/pos/emb/er 정리.
            try { idT.close() } catch (_: Throwable) {}
            try { am.close() } catch (_: Throwable) {}
            try { pos.close() } catch (_: Throwable) {}
            try { er.close() } catch (_: Throwable) {} // emb 는 er 소유 → er.close 로 해제(다음 스텝 새로 생성)
            if (next.toLong() == EOS_ID) break
            idsForStep = longArrayOf(next.toLong())
            seqLen += 1
            step += 1
        }
        // 마지막 past 텐서 정리
        for (t in pastKeys) try { t?.close() } catch (_: Throwable) {}
        return hashMapOf(
            "ok" to true, "generated_token_ids" to generated, "count" to generated.size,
            "ms" to (System.currentTimeMillis() - t0),
            "note" to "text-only greedy; detokenize 는 미구현(token ids 만).",
        )
    }

    private fun errStr(e: Throwable): String = "${e.javaClass.simpleName}: ${(e.message ?: "").take(200)}"

    /**
     * L4 blocker 실험: cached generation loop 을 **decoder OrtSession 의 graph optimization level 별**로 시도.
     * 실패 노드 `InsertedPrecisionFreeCast_...` 는 원본 그래프에 없고 **ORT 최적화가 삽입**한 것이므로,
     * NO_OPT/BASIC 로 내리면 삽입이 사라져 loop 가 될 수 있는지 검증한다. (text-only, 이미지 불필요)
     */
    private fun l4Experiment(): HashMap<String, Any?> {
        if (!isModelAvailable()) {
            return hashMapOf("success" to false, "engine" to "smol_ondevice", "status" to "unavailable", "fallback_required" to true)
        }
        val env = OrtEnvironment.getEnvironment()
        val results = HashMap<String, Any?>()
        var embedS: OrtSession? = null
        try {
            embedS = env.createSession(File(modelDir(), "embed_tokens_q4f16.onnx").absolutePath, OrtSession.SessionOptions())
            val levels = listOf(
                "ALL_OPT" to OrtSession.SessionOptions.OptLevel.ALL_OPT,
                "EXTENDED_OPT" to OrtSession.SessionOptions.OptLevel.EXTENDED_OPT,
                "BASIC_OPT" to OrtSession.SessionOptions.OptLevel.BASIC_OPT,
                "NO_OPT" to OrtSession.SessionOptions.OptLevel.NO_OPT,
            )
            for ((name, lvl) in levels) {
                val cl = ArrayList<AutoCloseable>()
                try {
                    val o = OrtSession.SessionOptions()
                    o.setOptimizationLevel(lvl)
                    try { o.setMemoryPatternOptimization(false) } catch (_: Throwable) {}
                    val decS = env.createSession(File(modelDir(), "decoder_model_merged_q4f16.onnx").absolutePath, o)
                    cl.add(decS)
                    results["cached@$name"] = generationLoop(env, embedS, decS, cl, maxNew = 3)
                } catch (e: Throwable) {
                    results["cached@$name"] = hashMapOf("ok" to false, "error" to errStr(e))
                } finally {
                    for (c in cl.reversed()) try { c.close() } catch (_: Throwable) {}
                }
            }
        } catch (e: Throwable) {
            return hashMapOf("success" to false, "engine" to "smol_ondevice", "status" to "error",
                "fallback_required" to true, "message" to errStr(e), "experiments" to results)
        } finally {
            try { embedS?.close() } catch (_: Throwable) {}
        }
        // Case D: 고정 길이 패딩(no-cache). 모든 decoder.run 을 동일 shape[1,PAD] 로 → 버퍼 재사용 mismatch 회피.
        run {
            val cl = ArrayList<AutoCloseable>()
            var eS: OrtSession? = null; var dS: OrtSession? = null
            try {
                eS = env.createSession(File(modelDir(), "embed_tokens_q4f16.onnx").absolutePath, OrtSession.SessionOptions())
                dS = env.createSession(File(modelDir(), "decoder_model_merged_q4f16.onnx").absolutePath, OrtSession.SessionOptions())
                cl.add(eS); cl.add(dS)
                results["padded_nocache@ALL_OPT(PAD=16)"] = paddedNoCacheLoop(env, eS, dS, padLen = 16, maxNew = 5)
            } catch (e: Throwable) {
                results["padded_nocache@ALL_OPT(PAD=16)"] = hashMapOf("ok" to false, "error" to errStr(e))
            } finally {
                for (c in cl.reversed()) try { c.close() } catch (_: Throwable) {}
            }
        }
        val anyOk = results.values.any { (it as? Map<*, *>)?.get("ok") == true }
        return hashMapOf(
            "success" to false, "engine" to "smol_ondevice", "status" to "l4_experiment",
            "fallback_required" to true, "any_loop_ok" to anyOk, "experiments" to results,
            "note" to "cached(opt-level별) + padded-no-cache. InsertedPrecisionFreeCast 는 opt level 무관(q4 export 내재).",
        )
    }

    /**
     * Case D: **고정 길이 패딩 + no-cache** greedy 생성. 매 스텝 decoder.run 의 입력 shape 를 [1,padLen] 로 고정해
     * (past 는 항상 빈 fp16) ORT 의 버퍼 재사용 shape mismatch(InsertedPrecisionFreeCast)를 회피 시도.
     * 느림(매 스텝 전체 재계산)이나 짧은 생성엔 실용적일 수 있다. text-only.
     */
    private fun paddedNoCacheLoop(
        env: OrtEnvironment, embedS: OrtSession, decS: OrtSession, padLen: Int, maxNew: Int,
    ): HashMap<String, Any?> {
        val t0 = System.currentTimeMillis()
        val PAD_ID = 2L
        val tokens = ArrayList<Long>().apply { PROMPT_IDS.forEach { add(it) } }
        val generated = ArrayList<Long>()
        var steps = 0
        while (steps < maxNew && tokens.size <= padLen) {
            val real = tokens.size
            // pad input_ids to padLen
            val ids = LongArray(padLen) { if (it < real) tokens[it] else PAD_ID }
            val cl = ArrayList<AutoCloseable>()
            try {
                val idT = OnnxTensor.createTensor(env, LongBuffer.wrap(ids), longArrayOf(1, padLen.toLong())); cl.add(idT)
                val er = embedS.run(mapOf("input_ids" to idT)); cl.add(er)
                val emb = er.get("inputs_embeds").get() as OnnxTensor
                val inputs = HashMap<String, OnnxTensor>()
                inputs["inputs_embeds"] = emb
                val am = OnnxTensor.createTensor(env, LongBuffer.wrap(LongArray(padLen) { if (it < real) 1L else 0L }), longArrayOf(1, padLen.toLong())); cl.add(am)
                val pos = OnnxTensor.createTensor(env, LongBuffer.wrap(LongArray(padLen) { it.toLong() }), longArrayOf(1, padLen.toLong())); cl.add(pos)
                inputs["attention_mask"] = am; inputs["position_ids"] = pos
                for (i in 0 until N_LAYERS) for (kv in listOf("key", "value")) {
                    val t = emptyFp16Past(env); cl.add(t); inputs["past_key_values.$i.$kv"] = t
                }
                val r = decS.run(inputs); cl.add(r)
                val logits = r.get("logits").get() as OnnxTensor
                val vocab = logits.info.shape[2].toInt()
                val next = argmaxAt(logits.floatBuffer, (real - 1) * vocab, vocab)
                generated.add(next.toLong()); tokens.add(next.toLong())
                if (next.toLong() == EOS_ID) break
                steps++
            } finally {
                for (c in cl.reversed()) try { c.close() } catch (_: Throwable) {}
            }
        }
        return hashMapOf(
            "ok" to true, "generated_token_ids" to generated, "count" to generated.size,
            "pad_len" to padLen, "ms" to (System.currentTimeMillis() - t0),
            "note" to "fixed-length padded no-cache; detokenize 미구현(token ids only).",
        )
    }

    // ---- image + text generation spike -------------------------------------
    private fun floatsOf(t: OnnxTensor, n: Int): FloatArray {
        val out = FloatArray(n)
        val fb = t.floatBuffer
        fb.rewind()
        fb.get(out, 0, minOf(n, fb.remaining()))
        return out
    }

    /**
     * 이미지+텍스트 짧은 생성 spike: vision_encoder → embed(prompt) → image_features 를 image_token 위치 임베딩에 병합
     * → 고정길이 패딩 no-cache 로 N tokens greedy 생성 → detokenize → [SmolEvidenceParser] 로 task별 evidence 변환.
     * text 는 approximate(하드코딩 프롬프트/단일 512). fallback_required=true 유지(서버 fallback). 완성 인증 아님.
     */
    private fun imageTextGeneration(imagePath: String?, task: String, maxNew: Int, padLen: Int): HashMap<String, Any?> {
        if (!isModelAvailable()) return hashMapOf("success" to false, "status" to "unavailable", "fallback_required" to true, "engine" to "smol_ondevice")
        if (imagePath == null || !File(imagePath).exists()) return hashMapOf("success" to false, "status" to "no_image", "fallback_required" to true, "engine" to "smol_ondevice")
        val env = OrtEnvironment.getEnvironment()
        val levels = HashMap<String, Any?>()
        val cl = ArrayList<AutoCloseable>()
        val t0 = System.currentTimeMillis()
        try {
            val opts = OrtSession.SessionOptions()
            val visionS = env.createSession(File(modelDir(), "vision_encoder_q4f16.onnx").absolutePath, opts); cl.add(visionS)
            val embedS = env.createSession(File(modelDir(), "embed_tokens_q4f16.onnx").absolutePath, opts); cl.add(embedS)
            val decS = env.createSession(File(modelDir(), "decoder_model_merged_q4f16.onnx").absolutePath, opts); cl.add(decS)

            // 1) vision_encoder → image_features [1,64,960]
            val (pv, mask) = preprocess(env, imagePath); cl.add(pv); cl.add(mask)
            val rV = visionS.run(mapOf("pixel_values" to pv, "pixel_attention_mask" to mask)); cl.add(rV)
            val feat = rV.get("image_features").get() as OnnxTensor
            levels["vision_encoder"] = "ok ${feat.info.shape.toList()}"
            val featArr = floatsOf(feat, IMG_FEAT_COUNT * HIDDEN)

            // 2) embed prompt(image placeholder 포함) → [1,80,960]
            val promptIds = PROMPT_IMG_IDS
            val baseLen = promptIds.size
            val idT = OnnxTensor.createTensor(env, LongBuffer.wrap(promptIds), longArrayOf(1, baseLen.toLong())); cl.add(idT)
            val rE = embedS.run(mapOf("input_ids" to idT)); cl.add(rE)
            val embT = rE.get("inputs_embeds").get() as OnnxTensor
            levels["embed_tokens"] = "ok ${embT.info.shape.toList()}"
            val seqEmb = floatsOf(embT, baseLen * HIDDEN)

            // 3) merge: image_token(위치 5..68) 임베딩을 image_features 로 치환
            for (i in 0 until IMG_FEAT_COUNT) {
                System.arraycopy(featArr, i * HIDDEN, seqEmb, (IMG_POS_START + i) * HIDDEN, HIDDEN)
            }
            levels["image_merge"] = "ok (${IMG_FEAT_COUNT} tokens @${IMG_POS_START})"

            if (baseLen + maxNew > padLen) {
                return hashMapOf("success" to false, "status" to "padlen_too_small", "fallback_required" to true,
                    "engine" to "smol_ondevice", "message" to "padLen($padLen) < baseLen($baseLen)+maxNew($maxNew)", "levels" to levels)
            }

            // 4) 고정길이 패딩 no-cache greedy 생성
            val buf = FloatArray(padLen * HIDDEN) // zero-padded
            System.arraycopy(seqEmb, 0, buf, 0, seqEmb.size)
            var curLen = baseLen
            val gen = ArrayList<Long>()
            var loopErr: String? = null
            for (step in 0 until maxNew) {
                val stepCl = ArrayList<AutoCloseable>()
                try {
                    val eT = OnnxTensor.createTensor(env, FloatBuffer.wrap(buf.copyOf()), longArrayOf(1, padLen.toLong(), HIDDEN.toLong())); stepCl.add(eT)
                    val am = OnnxTensor.createTensor(env, LongBuffer.wrap(LongArray(padLen) { if (it < curLen) 1L else 0L }), longArrayOf(1, padLen.toLong())); stepCl.add(am)
                    val pos = OnnxTensor.createTensor(env, LongBuffer.wrap(LongArray(padLen) { it.toLong() }), longArrayOf(1, padLen.toLong())); stepCl.add(pos)
                    val inputs = HashMap<String, OnnxTensor>()
                    inputs["inputs_embeds"] = eT; inputs["attention_mask"] = am; inputs["position_ids"] = pos
                    for (i in 0 until N_LAYERS) for (kv in listOf("key", "value")) {
                        val t = emptyFp16Past(env); stepCl.add(t); inputs["past_key_values.$i.$kv"] = t
                    }
                    val r = decS.run(inputs); stepCl.add(r)
                    val logits = r.get("logits").get() as OnnxTensor
                    val vocab = logits.info.shape[2].toInt()
                    val next = argmaxAt(logits.floatBuffer, (curLen - 1) * vocab, vocab)
                    gen.add(next.toLong())
                    if (next.toLong() == EOS_ID) break
                    // 다음 토큰 임베딩 → buf 에 append
                    val nT = OnnxTensor.createTensor(env, LongBuffer.wrap(longArrayOf(next.toLong())), longArrayOf(1, 1)); stepCl.add(nT)
                    val nr = embedS.run(mapOf("input_ids" to nT)); stepCl.add(nr)
                    val nvec = floatsOf(nr.get("inputs_embeds").get() as OnnxTensor, HIDDEN)
                    if ((curLen + 1) * HIDDEN <= buf.size) System.arraycopy(nvec, 0, buf, curLen * HIDDEN, HIDDEN)
                    curLen++
                } catch (e: Throwable) {
                    loopErr = errStr(e); break
                } finally {
                    for (c in stepCl.reversed()) try { c.close() } catch (_: Throwable) {}
                }
            }
            if (loopErr != null && gen.isEmpty()) {
                levels["generation_loop"] = "blocked: $loopErr"
                return hashMapOf("success" to false, "status" to "generation_blocked", "fallback_required" to true,
                    "engine" to "smol_ondevice", "levels" to levels, "error" to loopErr)
            }
            levels["generation_loop"] = "ok ${gen.size} tokens" + (loopErr?.let { " (stopped: $it)" } ?: "")

            // 5) detokenize
            val text = try { detokenize(gen) } catch (e: Throwable) { null }
            levels["detokenize"] = if (text != null) "ok" else "blocked"

            // 6) evidence 변환(diagnostics-only): generated_text → schema evidence code + Rule Engine 호환 payload.
            //    Smol 결과는 최종 인증으로 채택하지 않는다(fallback_required=true 유지).
            val evidence = try { SmolEvidenceParser.parse(task, text) } catch (e: Throwable) {
                hashMapOf<String, Any?>("parse_status" to "failed", "reason" to "parser error: ${errStr(e)}")
            }
            levels["evidence_parse"] = evidence["parse_status"]

            return hashMapOf(
                "success" to false, "engine" to "smol_ondevice", "status" to "image_text_generation_ok",
                "fallback_required" to true, "task" to task,
                "generated_token_ids" to gen, "generated_text" to (text ?: ""),
                "count" to gen.size, "latency_ms" to (System.currentTimeMillis() - t0),
                "levels" to levels,
                "evidence" to evidence,
                "local_accept_candidate" to (evidence["local_accept_candidate"] ?: false),
                "local_reject_candidate" to (evidence["local_reject_candidate"] ?: false),
                "note" to "image+text no-cache 생성 spike + evidence 변환(diagnostics-only). single-512(anyres 미적용), 프롬프트 하드코딩 → 텍스트 approximate.",
            )
        } catch (e: Throwable) {
            return hashMapOf("success" to false, "engine" to "smol_ondevice", "status" to "error",
                "fallback_required" to true, "message" to errStr(e), "levels" to levels)
        } finally {
            for (c in cl.reversed()) try { c.close() } catch (_: Throwable) {}
        }
    }

    // ---- detokenize (GPT2 byte-level BPE) -----------------------------------
    private var idToToken: HashMap<Int, String>? = null

    private val byteDecoder: HashMap<Char, Int> by lazy {
        val bs = ArrayList<Int>()
        for (i in 0x21..0x7E) bs.add(i)
        for (i in 0xA1..0xAC) bs.add(i)
        for (i in 0xAE..0xFF) bs.add(i)
        val cs = ArrayList<Int>(bs)
        var n = 0
        for (b in 0..255) if (!bs.contains(b)) { bs.add(b); cs.add(256 + n); n++ }
        val m = HashMap<Char, Int>()
        for (i in bs.indices) m[cs[i].toChar()] = bs[i]
        m
    }

    private fun loadIdToToken(): HashMap<Int, String> {
        idToToken?.let { return it }
        val map = HashMap<Int, String>()
        val root = JSONObject(File(modelDir(), "tokenizer.json").readText())
        val vocab = root.getJSONObject("model").getJSONObject("vocab")
        val it = vocab.keys()
        while (it.hasNext()) { val tokn = it.next(); map[vocab.getInt(tokn)] = tokn }
        if (root.has("added_tokens")) {
            val arr = root.getJSONArray("added_tokens")
            for (i in 0 until arr.length()) {
                val o = arr.getJSONObject(i); map[o.getInt("id")] = o.getString("content")
            }
        }
        idToToken = map
        return map
    }

    /** generated token ids → text. 특수토큰(<...>)은 건너뛰고, BPE 토큰은 GPT2 byte-level 디코드. */
    private fun detokenize(ids: List<Long>): String {
        val map = loadIdToToken()
        val bytes = ArrayList<Byte>()
        for (id in ids) {
            val tok = map[id.toInt()] ?: continue
            if (tok.startsWith("<") && tok.endsWith(">")) continue // 특수토큰 skip
            for (ch in tok) {
                val b = byteDecoder[ch]
                if (b != null) bytes.add(b.toByte()) else bytes.add(ch.code.toByte())
            }
        }
        return String(bytes.toByteArray(), StandardCharsets.UTF_8)
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
                        "l4Experiment" -> result.success(l4Experiment())
                        "imageTextGen" -> result.success(
                            imageTextGeneration(call.argument("imagePath"),
                                (call.argument<String>("task")) ?: "water",
                                (call.argument<Int>("maxNew")) ?: 12,
                                (call.argument<Int>("padLen")) ?: 96)
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
