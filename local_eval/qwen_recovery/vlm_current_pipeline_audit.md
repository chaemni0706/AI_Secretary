# Current VLM Verification Pipeline — Audit (read-code, no inference run)

Scope: this audits what `POST /image-verifications` and `POST
/verification/image/{type}` actually execute **today**, on the currently
checked-out branch (`qwen`, a descendant of
`feature/vlm-image-verification-stabilization` — contains all of that
branch's commits plus later merges: `Feature_0712`, `Feature_UI`, ledger
work). Working tree is clean (`git status --short` empty).

**Headline finding**: the architecture described in
`VLM_FALLBACK_STABILIZATION_REPORT.md` ("SmolVLM local blocker-first →
Qwen2.5-VL-7B server fallback → Rule Engine → `vlm_fp_guard`", full171
recall=0.481, FP=6) is **not the code path either backend endpoint actually
calls**. That architecture lives entirely in `local_eval/vlm_baseline/`
(`vlm_fallback_verifier.py`) as a **standalone, validated-but-unintegrated
evaluation harness**. It has never been imported by `backend/`. The real,
currently-wired default is materially weaker and differently shaped — see §1-3.

## 1. What the two API endpoints actually call

Two endpoints exist, and **both resolve to the exact same underlying
function** — confirmed by reading the code, not assumed:

- `POST /image-verifications` (`backend/api/image_verification.py`) →
  `image_verification_service.verify_image_upload(...)` directly.
- `POST /verification/image/{verification_type}` (`backend/api/verification.py`)
  → `verification_orchestrator.verify_image(...)` → also calls
  `image_verification_service.verify_image_upload(...)` (confirmed in
  `backend/services/verification_orchestrator.py`: `verify_image()` is a thin
  wrapper with no extra logic).

So there is exactly one real verification code path today, in
`backend/services/image_verification_service.py`:

```
image + task
  -> get_default_vision_analyzer()      # config default: provider="smolvlm"
       -> LocalVLMVisionAnalyzer("smolvlm")   # SmolVLM-500M, runs server-side
                                                # in the Python backend process
  -> evaluate_image_verification(type, analysis, context)   # real Rule Engine
  -> IF task == "study" AND result != "verified" AND _should_study_fallback(...):
         get_study_fallback_analyzer()   # config default: "qwen_awq"
              -> LocalVLMVisionAnalyzer("qwen_awq")   # Qwen2.5-VL-3B-AWQ,
                                                          # also server-side
         -> re-run evaluate_image_verification with the fallback's VisionAnalysis
  -> apply_secondary_review_policy(result)   # water verified -> review_required=true
  -> final ImageVerificationData
```

Config defaults (`backend/core/config.py` lines 51-56, not overridden anywhere
found in this repo):
```
IMAGE_VERIFICATION_VLM_PROVIDER: str = "smolvlm"
IMAGE_VERIFICATION_STUDY_FALLBACK: str | None = "qwen_awq"
IMAGE_VERIFICATION_USE_OPENAI: bool = False
```

## 2. Does a "SmolVLM not loaded → final failure" path exist?

Two separate SmolVLM code paths exist and must not be confused:

- **Backend server-side** (`backend/services/local_vlm_analyzer.py`,
  `LocalVLMVisionAnalyzer`): if the adapter/weights fail to load,
  `get_default_vision_analyzer()`'s `try/except` falls back to
  `OpenAIVisionAnalyzer()` (which itself returns `_unavailable_analysis(...)`
  — `quality.usable=False` — if no `OPENAI_API_KEY` is configured, which per
  `IMAGE_VERIFICATION_USE_OPENAI=False`/no key found in this repo's config is
  the likely real state). An unusable analysis fails the Rule Engine's
  `quality_usable` mandatory check → `retake_required`, never a crash and
  never a silent `verified`.
- **Flutter on-device** (`frontend/lib/services/smol_ondevice_verifier.dart`):
  this is a **client-side, separate** SmolVLM attempt (native ONNX Runtime
  Android bridge) that the Flutter `ImageVerificationService` tries **before**
  ever calling the server API. Per that file's own doc-comment: "네이티브는
  OrtSession 로드(warmup)까지 구현. 실제 이미지 추론... 미구현 →
  `verifyImage`는 `fallback_required=true`를 반환" — i.e., **on-device
  inference is not implemented yet**, so `inferBlocker`/`inferEvidence` always
  return null in practice today, and every request currently falls through to
  the server API call (`api.submitImageVerification`) regardless of device
  capability. So today, "Smol not loaded" on the client just means "always
  goes to the server" — never a terminal failure, but also means the
  client-side blocker-first optimization described in the Flutter comments is
  not actually active yet.

## 3. Is Qwen2.5-VL-7B fallback connected to the real endpoint?

**No.** The only Qwen model wired into `backend/services/image_verification_service.py`
is via `get_study_fallback_analyzer()`, which defaults to provider key
`"qwen_awq"` — per `local_eval/ondevice_vlm_eval/model_candidates.yaml`, that
adapter key maps to **Qwen2.5-VL-3B-AWQ** (`Qwen/Qwen2.5-VL-3B-Instruct-AWQ`),
not the 7B bf16 model. And it is **study-only** — `verify_image_upload` never
invokes any Qwen fallback for water or exercise; those two tasks get exactly
one SmolVLM-500M pass, full stop.

The Flutter client's own code comment
(`frontend/lib/services/image_verification_service.dart` line 7, 85) claims
"서버 fallback (Qwen2.5-VL-7B + guard + Rule Engine)" — **this comment does
not match the backend it actually calls.** It describes the
`local_eval/vlm_baseline` harness's architecture, not
`image_verification_service.py`'s real behavior. This is a documentation/code
drift, not a currently-functioning 7B fallback.

## 4. Is the Rule Engine the final decision maker?

**Yes**, for the actual decision enum. Every code path — SmolVLM-only, or
SmolVLM+qwen_awq-fallback — ends by calling
`evaluate_image_verification(...)`, which is the sole place
`verified`/`rejected`/`retake_required` is produced (`image_verification_rule_engine.py`,
unmodified by any fallback logic — confirmed identical function reused in
every call site found: `image_verification_service.py`,
`run_smolvlm_final_inference.py`, `evaluate_validation_dataset.py`). No VLM
output is ever returned directly as a final result.

## 5. When is `vlm_fp_guard` applied?

**Never, in the real backend path.** `rg` for `vlm_fp_guard` shows it is
imported and called only inside `local_eval/vlm_baseline/vlm_fallback_verifier.py`
and `run_server_vlm_candidate_eval.py`/`run_vlm_fallback_full_eval.py` — all
`local_eval` harness files. `backend/services/image_verification_service.py`
has no import of it. The only post-decision adjustment that IS live in
`backend/` is `apply_secondary_review_policy` (§6).

## 6. Does the water `verified` → `review_required` policy still hold?

**Yes, confirmed live** in `backend/services/image_verification_service.py`:
```python
_REVIEW_TASKS = frozenset({"water"})

def apply_secondary_review_policy(data):
    if data.result == "verified" and data.verification_type in _REVIEW_TASKS:
        return data.model_copy(update={"review_required": True,
                                        "review_reason": "water_non_visual_context_risk"})
    return data
```
This runs unconditionally after every water verification (SmolVLM-only or
SmolVLM+fallback path — study/exercise never touch this fallback since
`_REVIEW_TASKS` is water-only). It is called at the end of
`verify_image_upload`, so it is not bypassable via either API endpoint.

## 7. CLIP/SigLIP re-confirmation

Re-confirmed (no new findings beyond the prior `clip_siglip_usage_check.md`
in the YOLO project): zero genuine CLIP/SigLIP calls in `backend/`,
`frontend/lib/`, or `tests/`. Not used anywhere in this real pipeline.

## 8. Practical implication for the recovery-ablation framework

Because the real default path is SmolVLM-500M-primary for **all three
tasks**, with only a conditional, 3B-AWQ, study-only escalation and no
post-decision guard, the actually-relevant "baseline to beat" for a
recovery-ablation framework is **not** the 0.481-recall/FP=6 harness number
from `VLM_FALLBACK_STABILIZATION_REPORT.md` — that number describes a
different, more capable (and unintegrated) architecture. The real current
default's own partial full171 measurement (SmolVLM-500M alone, all 3 tasks,
via `run_smolvlm_final_inference.py`) is **recall 0.247, FP=9**
(`local_eval/real_validation_dataset/results/smolvlm500_final/metrics_summary.json`,
dated 2026-07-09) — see `qwen_baseline_artifact_inventory.md` §2 for the full
breakdown and the gap in coverage (no full171 run exists yet that combines
SmolVLM-primary + the live qwen_awq study-fallback trigger logic together).

This changes the recovery framing: recovering recall toward 0.80 while
keeping FP flat is not "improve on the already-good 7B+guard harness" — it
is "either (a) actually wire the validated 7B+guard harness into
`backend/`, which is a bigger integration change out of this task's scope, or
(b) build the crop/OCR/recovery ablations against whichever fallback model is
actually reachable from this pipeline, while treating the 7B+guard harness
numbers as an upper-bound reference, not the live baseline." §7 of the
ablation plan documents both harness numbers side by side for this reason.
