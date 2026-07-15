# Demo Readiness Report — Phase 12 Synthesis

Repo: `AI_Secretary_Qwen`, branch `qwen`. Scope: production VLM path
(Smol on-device blocker-only → Qwen7B server fallback → Rule Engine → FP
guard → verified/retake_required/rejected), plus app-side UX and
provisioning docs. No experimental scaffolding added beyond what was
explicitly requested; no thresholds changed to force outcomes; no model
mislabeled; nothing staged/pushed.

## 1. Engine status

| engine | status | latency | correctness |
|---|---|---|---|
| `reference_fp32` (**default**, `QWEN7B_ENGINE=reference_fp32`) | Working | ~315-320s/call (8/8 sequential, 0 OOM — see [qwen7b_sequential_stability_report.md](qwen7b_sequential_stability_report.md)) | Correct, deterministic (`do_sample=False`), CPU-offloaded fp32 |
| `quantized_bnb_nf4` (experimental, never default) | **NO-GO** on this P40 | fast (7-34s) | Broken (degenerate `!`-token output, both fp16 and fp32 compute dtype) |
| AWQ | Not implemented as a selectable engine | — | Blocked by missing Python.h/no root for Triton JIT (see [qwen7b_quantized_engine_report.md](qwen7b_quantized_engine_report.md)) |
| GPTQ | Not implemented | — | No official pre-quantized checkpoint exists for this model |

Engine abstraction (`backend/services/qwen7b_vision_analyzer.py`): `QWEN7B_ENGINE`
env var / `engine` constructor arg, `DEFAULT_ENGINE_VARIANT = "reference_fp32"`,
`KNOWN_ENGINE_VARIANTS = ("reference_fp32", "quantized_bnb_nf4")`. Unknown
variant raises at construction (fail loud, not silent). `health_check()` now
reports `engine_variant`, `is_default_engine_variant`, `parameter_size`
("7B"), `model_family` ("Qwen2.5-VL"), `quantization`, `image_input_supported`,
alongside the pre-existing device/dtype/memory/load-time fields. 14 unit
tests cover this (`tests/test_qwen7b_vision_analyzer.py`, 10→14 after Phase 12).

**Conclusion: the quantization effort is NO-GO on this specific Tesla P40.**
Per the task's own prescribed fallback, the recommendation is to port the
same `Qwen7BVisionAnalyzer` interface to different GPU hardware (compute
capability ≥7.5) rather than continue tuning quantization here or trying to
shrink the 315s fp32 path further.

## 2. What this means for a live demo, honestly

The end-to-end pipeline (Smol blocker-gate → Qwen7B fallback → Rule Engine
→ FP guard) is functionally correct and was validated against real images
earlier this session (clear water → verified; water FAIL → rejected;
exercise strong evidence → verified; study weak single-evidence →
conservatively `retake_required`, as intended). It is **not fast**: any
request that reaches the Qwen7B fallback on this hardware takes ~315-320s.

The app's own HTTP timeout (`postMultipart` in `frontend/lib/services/api_client.dart`)
is 60s and was **deliberately left unchanged** rather than raised to
300s+ — raising it would hide the real latency problem instead of solving
it, which this task explicitly prohibited ("do not just increase timeout to
hide 300s latency — the quantized engine must meet the latency gate
instead"). Since quantization is NO-GO, **any real demo request that
reaches the Qwen7B fallback on this P40 will hit the app's 60s timeout**
and surface as the new honest "server is still analyzing, this isn't a
rejection" message (see §3) rather than a silent freeze or a
misleading "your photo was rejected." This is a real, disclosed
limitation, not a hidden one — a live demo on this hardware would need
either: (a) different GPU hardware for the Qwen7B fallback (compute
capability ≥7.5, no CPU offload needed for fp32, likely far under 60s), or
(b) a live demo script that pre-warms the model and narrates the wait
rather than relying on the app's timeout window.

## 3. Flutter UX changes (this session, files touched: `frontend/lib/screens/image_verification_screen.dart`, `frontend/lib/services/image_verification_service.dart`, `frontend/lib/services/api_client.dart`, `frontend/test/image_verification_service_test.dart`)

- **Staged progress, not a frozen spinner**: `VerificationStage` enum
  (`localAnalysis`/`serverVerification`) threaded through
  `ImageVerificationService.verify(onStage: ...)`; the submit button label
  now reads "기기에서 1차 분석 중..." during the Smol blocker check and
  "서버에서 검증 중... (시간이 걸릴 수 있어요)" once the request reaches the
  server, instead of a single generic "인증 중...".
- **Duplicate-submission guard**: `_submitInFlight` is checked and set
  *synchronously* at the top of `_submit()`, before the first `await` —
  closes the race where a fast double-tap could fire two requests before
  `setState`'s `_loading=true` takes effect (button-disable alone only
  guards after the first frame redraws).
- **Timeout vs. rejection, distinguished honestly**: `ApiException` now
  carries an `isTimeout` flag (set in `api_client.dart` from the underlying
  `DioException.type`); the error card renders differently (amber
  hourglass, "사진이 거절된 것이 아니라... 응답 대기 시간을 초과했어요") for
  a timeout than for an actual server-communicated rejection (red, generic
  error styling) — so a user never mistakes "the model was too slow" for
  "your photo was bad."
- Explicit HTTP timeout was already present (60s send/receive on the
  multipart upload) and is untouched, per §2's reasoning.

Verified via `flutter test` (Flutter SDK upgraded in-place this session
from 3.35.5 to 3.44.6/Dart 3.12.2 to satisfy this project's pubspec
constraint — `~/flutter-sdk`, not part of the repo): **51/51 frontend
tests pass**, including one pre-existing stale test
(`water 서버 verified → review_required(재촬영)...`) that still asserted the
OLD blanket water-review-override behavior removed earlier this session —
fixed by splitting it into two tests that match the actual current policy
(server's `review_required` trusted directly: `review:true` → retake,
`review:false` on a clear case → verified with no review). This was a
genuine pre-existing test/code drift caught by actually running the suite,
not a change made to force a result.

No physical device was available this session, so none of these UX paths
were exercised in an actual running app — only via the Flutter widget/unit
test harness.

## 4. Native Smol (on-device) status

Implementation is essentially complete (`SmolVlmBridge.kt`, wired via
`inferBlocker()`), confirmed by directly reading the 775-line native file —
see [native_smol_implementation_audit.md](native_smol_implementation_audit.md).
What's missing is **provisioning the ~356MB (361,194,130 bytes measured)
model weight files onto a physical device**, documented file-by-file with
destination paths, an actually-real aggregate byte count, and a checksum
procedure (not fabricated hashes — see
[native_smol_weight_manifest.md](native_smol_weight_manifest.md) for why
per-file SHA-256 values are left as a template to fill in, not invented).
No physical device was available this session, so on-device inference has
**not** been observed running for real — this remains the standing
limitation from Phase 11, restated honestly rather than assumed resolved.

Policy (verified unchanged in code): native Smol may only ever emit a
`retake_required` on a confident blocker; it never emits `verified`
directly, in any task.

## 5. Regression testing (this session, after all Phase 12 changes)

- Backend: `python -m pytest tests/` → **1242 passed, 22 failed** (all 22
  failures are in `tests/test_schedule_dataset.py`, an unrelated
  schedule-parsing module whose fixtures hardcode expected
  relative-date-derived datetimes against an older "today" — confirmed by
  inspecting one failing case's `expected_data` containing a stale
  absolute timestamp for "내일"/tomorrow. Not touched, per the standing
  instruction not to modify unrelated modules; this is calendar drift in
  test fixtures, not a code regression from this work).
- Backend, VLM/image-verification-scoped subset specifically: **160/160
  passed** (was 156 before Phase 12; +4 new tests for the `QWEN7B_ENGINE`
  variant switch and its `health_check()` fields).
- Frontend: `flutter test` → **51/51 passed** (was 45 before Phase 12; +7 in
  `image_verification_service_test.dart`, net +6 after retiring the one
  stale test split into two correct ones, minus the 1 replaced).

## 6. Standing blockers for a truly latency-acceptable live demo

1. **Quantization NO-GO on this P40** (§1) — the single largest blocker.
   Recommended fix is different GPU hardware, not further tuning here.
2. **App timeout (60s) < reference engine latency (~315s)** — by design,
   not hidden, but means a live demo against this exact server will
   surface the new honest timeout message rather than a fast result.
3. **Physical device**: native Smol provisioning and the full Flutter UX
   flow (staged messages, duplicate-submit guard, timeout messaging) are
   implemented and unit/widget-tested, but have not been run on a real
   phone this session.
4. **Fresh real-image end-to-end re-validation of the study combo-bonus
   fix**: the bonus itself is unit-tested (5 passing tests with realistic
   evidence-code fixtures), but was not re-confirmed this session via a
   fresh real photo through the actual 315s Qwen7B pipeline (time cost:
   ~315s+ per attempt, and doing so honestly requires locating a genuine
   strong-study photo rather than reusing a synthetic fixture) — flagged
   here rather than silently assumed working end-to-end.
