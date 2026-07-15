# Native Smol Implementation Audit (Phase 11.E)

**Correction to this session's own earlier assessment**: the prior report
said native on-device inference was "not implemented." That was based on
reading only `smol_ondevice_verifier.dart`'s top-of-file doc-comment and the
older `verifyImage`/spike methods. Reading the FULL native Kotlin file
(`SmolVlmBridge.kt`, 775 lines) and the full Dart bridge shows this is
**substantially more complete** than that comment suggests.

## Category (per this task's classification)

**Category 1: model asset exists (on a prior dev machine) and only
device-specific provisioning is missing** -- NOT category 4 ("entire
implementation missing"). Specifically:

| component | status |
|---|---|
| Image preprocessing | **Implemented** (`preprocess()`: `BitmapFactory` decode → 512x512 resize → NCHW float tensor, `(x/255-0.5)/0.5` normalization) |
| Tokenizer/prompt construction | **Implemented** (hardcoded task-specific prompt token-id arrays for water/study/exercise, built from `tokenizer.json` offline via a documented tool `tools/gen_smol_prompts.py`) |
| Vision + text merged generation | **Implemented** (`imageTextGeneration()`: vision_encoder → embed_tokens → image-token-position auto-detect & merge → fixed-length padded no-cache greedy decode loop) |
| Detokenization | **Implemented** (`detokenize()`: GPT2 byte-level BPE decode from `tokenizer.json` vocab) |
| Evidence parsing | **Implemented** (`SmolEvidenceParser.kt`, Kotlin-side canonical JSON conversion, called from `imageTextGeneration()`) |
| Flutter bridge wiring | **Implemented and wired** -- `smol_ondevice_verifier.dart::inferBlocker()` DOES call the `imageTextGen` MethodChannel method (not the older no-op `verifyImage` spike) |
| Safety gate | **Implemented** -- `inferBlocker()` only returns non-null (accepting a local result) when `local_reject_candidate=true AND blockers non-empty AND parse_status in {clean,repaired}`; positive/weak/uncertain/error always return null → server fallback. This already matches "local positive는 사용 안 함, strong blocker만 local retake" exactly. |
| **Model weight files** (~356MB: `vision_encoder_q4f16.onnx`, `embed_tokens_q4f16.onnx`, `decoder_model_merged_q4f16.onnx`, `tokenizer.json`, `config.json`, `preprocessor_config.json`) | **NOT present** in this repo (`.gitignore`'d by design: `*.onnx`, `**/models/smolvlm/`) and not present in `filesDir/models/smolvlm/` on any real device from this session (no physical device attached). A documented provisioning runbook exists (`SMOL_ONDEVICE_STATUS.md` lines 90, 123-132): `adb push` from a dev machine's `/data/models/SmolVLM-500M-Instruct/onnx/...` → `/sdcard/Download/` → `run-as` copy into the app's `filesDir`. That source path (`/data/models/...`) does not exist on this cluster server (checked, absent) -- it refers to whatever machine a prior contributor used. |

## What this means for Phase 11.D (physical E2E)

Once a device is actually reachable (Part A) **and** the ~356MB model files
are pushed onto it via the documented `adb push` + `run-as` steps, the app's
existing `inferBlocker()` path will genuinely attempt real on-device
inference before ever reaching the server -- this is not scaffolding to be
built, it already exists. If the files are *not* pushed,
`isModelAvailable()` returns `false` and every call safely short-circuits to
`null` (server fallback), which is exactly what happened implicitly in this
session's curl-based tests (no on-device inference was possible without a
device, so every request went straight to the documented Smol-unavailable →
Qwen7B path).

## Known limitations of the native path itself (from the code's own comments, not new findings)

- Fixed 512x512 single-tile preprocessing, no adaptive multi-resolution
  tiling (SmolVLM's official "anyres" splitting is not implemented).
- Generation uses a **fixed-length padded, no-KV-cache** loop
  (`imageTextGeneration`), not the faster cached-KV loop -- the code's own
  comments explain the cached path hit an ONNX Runtime graph-optimization
  incompatibility (`InsertedPrecisionFreeCast` node shape mismatch) that
  the no-cache path was built specifically to work around. Slower per-call,
  but functioning.
- `maxNew` default 12 tokens (very short) -- adequate for the fixed,
  narrow blocker-detection vocabulary this path targets, not a general
  detailed-evidence generator.

## Effort estimate for a full native positive-evidence pipeline

Given the above, the remaining work is **not** "build native inference from
scratch" -- it is:
1. Provision model files onto a specific test device (operational step, no
   code).
2. If native positive-evidence (not just blocker) support is desired later,
   `inferEvidence()` in the Dart bridge currently always returns `null`
   ("미구현 → 서버 fallback" per its own comment) -- wiring it to also call
   `imageTextGen` and trust confident positive evidence would be a
   deliberate policy change (currently intentionally never accepting local
   positive, per this task's explicit prohibition on local Smol
   verified/positive), not an engineering gap.
