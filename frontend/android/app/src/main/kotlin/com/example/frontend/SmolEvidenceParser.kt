package com.example.frontend

/**
 * **Diagnostics-only** rule-based parser: SmolVLM 온디바이스 generated_text →
 * 기존 Rule Engine 이 소비하는 VisionAnalysis 호환 evidence code(schema enum) 로 변환한다.
 *
 * 목적:
 * - 자유형 자연어 생성 텍스트("A glass of yellow liquid.")를 task별 evidence code 로 매핑.
 * - **Smol 결과를 최종 인증으로 채택하지 않는다.** 최종 판정은 서버 fallback / backend Rule Engine.
 * - water 는 colored/yellow/brown/tea/coffee/beer/juice 등이 보이면 강하게 blocker 로 처리하고,
 *   **local_accept_candidate 는 항상 false**(water local accept 금지 정책 유지).
 *
 * 반환 evidence code 는 image_verification_schema.py 의
 * water/study/exercise_visual_evidence enum 과 1:1 호환되므로, rule_engine_payload 는
 * 그대로 backend evaluate_image_verification(task, VisionAnalysis(**payload), ctx) 에 투입 가능하다.
 *
 * 반환은 MethodChannel 직렬화 호환을 위해 Map/List/primitive 만 사용한다(JSONObject 미사용).
 */
object SmolEvidenceParser {

    // task별 (schema code -> 텍스트 트리거 토큰들). 매칭되면 code 채택.
    private data class Vocab(
        val positive: List<Pair<String, List<String>>>,
        val blocker: List<Pair<String, List<String>>>,
        val uncertainCode: String,
    )

    private val UNCERTAIN_TOKENS = listOf(
        "unclear", "unknown", "ambiguous", "maybe", "appears", "seems", "possibly",
        "might be", "hard to tell", "cannot tell", "can't tell", "not sure", "unsure",
        "blurry", "difficult to", "unable to", "no image", "cannot determine",
    )

    // 물이 아닌 색 액체/음료 → non_water_beverage 로 강하게 거절.
    private val WATER = Vocab(
        positive = listOf(
            // visible_clear_liquid 를 먼저 검사(더 구체적) → visible_water.
            "visible_clear_liquid" to listOf(
                "clear liquid", "colorless liquid", "colourless liquid", "transparent liquid",
                "clear water", "clear drinking water",
            ),
            "visible_water" to listOf("water", "plain water", "drinking water", "glass of water", "bottle of water"),
            "filled_container" to listOf("filled", "full of liquid", "contains liquid", "liquid inside", "poured"),
        ),
        blocker = listOf(
            // colored/beverage → non_water_beverage (schema water blocker).
            "non_water_beverage" to listOf(
                "yellow", "brown", "orange", "amber", "golden", "gold ", "red ", "reddish",
                "green", "purple", "pink", "dark liquid", "colored liquid", "coloured liquid", "tinted",
                "tea", "coffee", "espresso", "latte", "juice", "beer", "wine", "soda", "cola",
                "soft drink", "milk", "cocktail", "smoothie", "lemonade", "energy drink", "beverage",
            ),
            "empty_container" to listOf("empty", "no liquid", "nothing inside", "without any liquid"),
            "opaque_closed_container" to listOf("opaque", "closed container", "thermos", "with a lid", "capped"),
            "sealed_water_bottle" to listOf("sealed bottle", "unopened bottle", "sealed water bottle"),
        ),
        uncertainCode = "uncertain_liquid",
    )

    private val STUDY = Vocab(
        positive = listOf(
            "open_textbook" to listOf("textbook", "open book", "opened book", "reading a book"),
            "open_workbook" to listOf("workbook", "worksheet", "exercise book"),
            "handwritten_notes" to listOf("handwritten", "notebook", "notes", "writing notes", "taking notes"),
            "problem_solving_material" to listOf("problem", "math problem", "solving", "equations", "homework"),
            "code_editor" to listOf("code editor", "programming", "source code", "ide ", "writing code"),
            "study_content_on_screen" to listOf("lecture on screen", "study material on screen", "online course", "study on a laptop"),
            "lecture_video" to listOf("lecture video", "online lecture", "lecture", "course video"),
            "educational_document" to listOf("document", "pdf", "article", "study material", "educational"),
        ),
        blocker = listOf(
            "gaming_content" to listOf("game", "gaming", "video game", "playing a game"),
            "entertainment_video" to listOf("movie", "youtube", "netflix", "tv show", "entertainment", "watching a video"),
            "social_media" to listOf("social media", "instagram", "facebook", "twitter", "tiktok", "chatting"),
            "shopping_content" to listOf("shopping", "amazon", "online store", "product page"),
            "closed_study_materials" to listOf("closed book", "closed textbook", "books are closed"),
            "non_study_screen" to listOf("empty desk", "unrelated screen"),
        ),
        uncertainCode = "uncertain_screen_content",
    )

    private val EXERCISE = Vocab(
        positive = listOf(
            "exercise_pose_visible" to listOf(
                "exercising", "working out", "doing exercise", "push-up", "pushup", "push up",
                "squat", "lunge", "stretching", "lifting weights", "doing yoga", "running", "jogging",
            ),
            "gym_environment" to listOf("gym", "fitness center", "fitness club"),
            "treadmill_present" to listOf("treadmill"),
            "dumbbell_present" to listOf("dumbbell", "dumbbells"),
            "barbell_present" to listOf("barbell"),
            "yoga_mat_present" to listOf("yoga mat", "exercise mat"),
            "exercise_bike_present" to listOf("exercise bike", "stationary bike", "spin bike"),
            "running_environment" to listOf("running track", "track", "treadmill running"),
            "exercise_equipment_present" to listOf("kettlebell", "resistance band", "weight machine", "workout equipment"),
        ),
        blocker = listOf(
            "unrelated_environment" to listOf(
                "bedroom", "sitting", "resting", "selfie", "sofa", "couch", "lying down",
                "sleeping", "in bed", "relaxing", "eating",
            ),
            "insufficient_exercise_evidence" to listOf("only clothes", "just clothes", "clothes only", "no exercise"),
        ),
        uncertainCode = "uncertain_exercise_environment",
    )

    private fun vocabFor(task: String): Vocab? = when (task) {
        "water" -> WATER
        "study" -> STUDY
        "exercise" -> EXERCISE
        else -> null
    }

    /**
     * generated_text → evidence Map(diagnostics). 예외를 던지지 않는다.
     *
     * 반환 필드:
     *  parse_status: clean|repaired|weak|failed
     *  evidence_codes / blockers / uncertainty(low|medium|high)
     *  raw_text / task
     *  local_accept_candidate(진단 표시용; water 는 항상 false) / local_reject_candidate / reason
     *  rule_engine_compatible / rule_engine_payload(VisionAnalysis 호환 dict)
     */
    fun parse(task: String, generatedText: String?): HashMap<String, Any?> {
        val out = HashMap<String, Any?>()
        val raw = (generatedText ?: "").trim()
        out["task"] = task
        out["raw_text"] = raw
        out["fallback_required"] = true            // 이 spike 는 항상 서버 fallback 유지
        out["local_accept_candidate"] = false      // 기본 false; study/exercise 만 조건부 true
        out["local_reject_candidate"] = false
        out["rule_engine_compatible"] = false
        out["evidence_codes"] = ArrayList<String>()
        out["blockers"] = ArrayList<String>()

        val vocab = vocabFor(task)
        if (vocab == null) {
            out["parse_status"] = "failed"; out["uncertainty"] = "high"
            out["reason"] = "unsupported task: $task"
            return out
        }
        if (raw.isEmpty()) {
            out["parse_status"] = "failed"; out["uncertainty"] = "high"
            out["reason"] = "empty generated_text"
            return out
        }

        // 정규화: 소문자 + 200자 초과 시 첫 문장 위주로 절단(repaired).
        var repaired = false
        var text = raw.lowercase()
        if (text.length > 200) {
            val cut = text.indexOf('.')
            text = if (cut in 1..199) text.substring(0, cut + 1) else text.substring(0, 200)
            repaired = true
        }

        val positives = LinkedHashSet<String>()
        for ((code, tokens) in vocab.positive) if (tokens.any { text.contains(it) }) positives.add(code)
        val blockers = LinkedHashSet<String>()
        for ((code, tokens) in vocab.blocker) if (tokens.any { text.contains(it) }) blockers.add(code)

        // water 특례: colored/yellow 등이 있으면 visible_water/visible_clear_liquid positive 취소.
        // ("yellow water" 같은 모순 문구가 mandatory pass 로 새는 것을 방지)
        if (task == "water" && blockers.contains("non_water_beverage")) {
            positives.remove("visible_water"); positives.remove("visible_clear_liquid")
        }
        val hasUncertainToken = UNCERTAIN_TOKENS.any { text.contains(it) }

        val allCodes = LinkedHashSet<String>()
        allCodes.addAll(positives); allCodes.addAll(blockers)

        val uncertainty: String = when {
            hasUncertainToken || (positives.isEmpty() && blockers.isEmpty()) -> {
                allCodes.add(vocab.uncertainCode)   // schema uncertain code 도 payload 에 포함
                "high"
            }
            positives.isNotEmpty() && blockers.isNotEmpty() -> "medium"  // 신호 충돌
            else -> "low"
        }

        val parseStatus = when {
            positives.isEmpty() && blockers.isEmpty() -> "weak"   // 매핑 실패(텍스트는 있음)
            repaired -> "repaired"
            else -> "clean"
        }

        // 후보 판정(진단 표시용, 실제 인증 아님).
        val hasBlocker = blockers.isNotEmpty()
        val localReject = hasBlocker
        val localAccept: Boolean
        val reason: String
        when (task) {
            "water" -> {
                localAccept = false     // water local accept 금지 정책 유지
                reason = when {
                    hasBlocker && blockers.contains("non_water_beverage") -> "water: colored/non-water beverage blocker → reject 후보"
                    hasBlocker -> "water: blocker(${blockers.joinToString(",")}) → reject 후보"
                    positives.isNotEmpty() -> "water: 물 근거 있으나 local accept 금지 정책 → fallback"
                    else -> "water: 근거 약함 → fallback"
                }
            }
            else -> {
                localAccept = positives.isNotEmpty() && !hasBlocker && uncertainty != "high"
                reason = when {
                    hasBlocker -> "$task: blocker(${blockers.joinToString(",")}) → reject 후보"
                    localAccept -> "$task: positive(${positives.joinToString(",")}) → accept 후보(단, 채택 안 함)"
                    else -> "$task: 근거 약함/불확실 → fallback"
                }
            }
        }

        out["parse_status"] = parseStatus
        out["evidence_codes"] = ArrayList(allCodes)
        out["blockers"] = ArrayList(blockers)
        out["uncertainty"] = uncertainty
        out["local_accept_candidate"] = localAccept
        out["local_reject_candidate"] = localReject
        out["reason"] = reason

        // Rule Engine 호환 payload(VisionAnalysis dict). backend evaluate_image_verification 투입 가능.
        val quality = HashMap<String, Any?>()
        quality["brightness"] = "normal"; quality["blur"] = "low"; quality["usable"] = true
        val payload = HashMap<String, Any?>()
        payload["quality"] = quality
        payload["scene"] = null
        payload["objects"] = ArrayList<Any?>()
        payload["visible_text"] = ArrayList<Any?>()
        payload["visual_evidence"] = arrayListOf(raw)
        payload["${task}_visual_evidence"] = ArrayList(allCodes)
        out["rule_engine_payload"] = payload
        out["rule_engine_compatible"] = true

        return out
    }
}
