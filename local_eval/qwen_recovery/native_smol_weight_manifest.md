# Native Smol (SmolVLM-500M-Instruct, ONNX) Weight Provisioning Manifest — Phase 12, Section 6

**Honesty note up front**: none of the model weight files below exist
anywhere on this cluster server (checked: not in this repo, which
`.gitignore`s them by design, and not under any `/data/models/...` path on
this machine either — that path is documented in
[`SMOL_ONDEVICE_STATUS.md`](../../SMOL_ONDEVICE_STATUS.md) as belonging to a
prior contributor's dev machine, not this session's environment). This
manifest records the exact files, destination paths, and the ONE real
aggregate byte count that was actually measured on a physical device in a
prior session (`SMOL_ONDEVICE_STATUS.md` line 35). **Per-file SHA-256
checksums cannot be computed from this session** — computing a SHA-256
requires the actual file bytes, which aren't reachable here. Do not treat
any checksum as filled in below; the manifest instead tells you the command
to run yourself once you have the files, and where to record the result.

## Required files (6 total, per `getModelInfo()`'s own "6/6 found" check in `SmolVlmBridge.kt`)

| # | filename | destination (app `filesDir`) | expected size | role |
|---|---|---|---|---|
| 1 | `vision_encoder_q4f16.onnx` | `files/models/smolvlm/vision_encoder_q4f16.onnx` | ~57 MB | image → `image_features[1,64,960]` |
| 2 | `embed_tokens_q4f16.onnx` | `files/models/smolvlm/embed_tokens_q4f16.onnx` | ~94 MB | `input_ids[b,seq]` → `inputs_embeds[b,seq,960]` |
| 3 | `decoder_model_merged_q4f16.onnx` | `files/models/smolvlm/decoder_model_merged_q4f16.onnx` | ~205 MB | merged inputs_embeds + KV-cache → `logits[b,seq,49280]` |
| 4 | `tokenizer.json` | `files/models/smolvlm/tokenizer.json` | (not separately measured) | GPT2 byte-level BPE vocab (49152 base + 145 added tokens) for tokenize/detokenize |
| 5 | `config.json` | `files/models/smolvlm/config.json` | (not separately measured) | model config (hidden=960, vocab=49280, 32 layers, 5 KV heads, head_dim=64) |
| 6 | `preprocessor_config.json` | `files/models/smolvlm/preprocessor_config.json` | (not separately measured) | SmolVLM image processor config (512x512 single-tile, normalization params) |

**Real aggregate measurement (from a prior physical-device session, recorded
in `SMOL_ONDEVICE_STATUS.md` line 35, not fabricated here):** all 6 files
together = **361,194,130 bytes** on-device after provisioning, confirmed via
`getModelInfo()` reporting `6/6 found` at
`/data/user/0/com.example.frontend/files/models/smolvlm`.

Also referenced but NOT required for this ONNX path (a size/quantization
alternative noted in the same status doc, not used by the current
`SmolVlmBridge.kt` implementation): `SmolVLM2-2.2B-Instruct-GGUF` (Q4_K_M +
mmproj). Do not provision this instead — the Kotlin bridge is written
against the 3-ONNX-file 500M export specifically (input/output tensor names
and shapes above are for that export).

## Checksum manifest (fill in when you actually have the files)

Run this on whichever machine holds the source files (the same one referred
to as `/data/models/SmolVLM-500M-Instruct/onnx/...` in the tunnel/provisioning
doc), **before** pushing to the phone, so you have a known-good reference to
diff against after provisioning:

```bash
cd /data/models/SmolVLM-500M-Instruct
sha256sum onnx/vision_encoder_q4f16.onnx \
          onnx/embed_tokens_q4f16.onnx \
          onnx/decoder_model_merged_q4f16.onnx \
          tokenizer.json config.json preprocessor_config.json \
  | tee smolvlm_checksums.sha256
```

Record the 6 resulting hashes here (replace the placeholders) once you've
run it — this file is intentionally left as a template, not fabricated data:

```
<sha256>  vision_encoder_q4f16.onnx
<sha256>  embed_tokens_q4f16.onnx
<sha256>  decoder_model_merged_q4f16.onnx
<sha256>  tokenizer.json
<sha256>  config.json
<sha256>  preprocessor_config.json
```

## Provisioning commands (local machine, USB-attached device — same commands already in `SMOL_ONDEVICE_STATUS.md` §"모델 배치", restated here for this manifest's completeness)

```bash
PKG=com.example.frontend   # debug build; run-as requires a debuggable APK

# 1) stage files on the device's shared storage (adb push cannot write
#    directly into another app's private filesDir)
adb shell rm -rf /sdcard/Download/smolvlm_tmp
adb shell mkdir -p /sdcard/Download/smolvlm_tmp
adb push onnx/vision_encoder_q4f16.onnx        /sdcard/Download/smolvlm_tmp/
adb push onnx/embed_tokens_q4f16.onnx          /sdcard/Download/smolvlm_tmp/
adb push onnx/decoder_model_merged_q4f16.onnx  /sdcard/Download/smolvlm_tmp/
adb push tokenizer.json                        /sdcard/Download/smolvlm_tmp/
adb push config.json                           /sdcard/Download/smolvlm_tmp/
adb push preprocessor_config.json              /sdcard/Download/smolvlm_tmp/

# 2) copy from shared storage into the app's private filesDir via run-as
#    (debug APK only). IMPORTANT: use `dd`, not `sh -c 'cat > ...'` -- the
#    latter resets cwd to `/` (read-only) and fails with EROFS (documented
#    pitfall, SMOL_ONDEVICE_STATUS.md line 305).
adb shell run-as $PKG mkdir -p files/models/smolvlm
for f in vision_encoder_q4f16.onnx embed_tokens_q4f16.onnx \
         decoder_model_merged_q4f16.onnx tokenizer.json config.json \
         preprocessor_config.json; do
  adb shell run-as $PKG dd if=/sdcard/Download/smolvlm_tmp/$f \
                            of=files/models/smolvlm/$f
done

# 3) verify destination: file count, byte sizes, and total
adb shell run-as $PKG ls -l files/models/smolvlm
adb shell run-as $PKG du -sb files/models/smolvlm
# expect: 6 files listed, total close to 361,194,130 bytes

# 4) verify integrity against the checksums recorded above -- run-as can
#    pipe through sha256sum on-device directly (no need to pull files back):
for f in vision_encoder_q4f16.onnx embed_tokens_q4f16.onnx \
         decoder_model_merged_q4f16.onnx tokenizer.json config.json \
         preprocessor_config.json; do
  adb shell run-as $PKG sha256sum files/models/smolvlm/$f
done
# compare each line's hash against smolvlm_checksums.sha256 from the source
# machine -- any mismatch means a corrupted/incomplete push, re-copy that file

# 5) clean up the staged shared-storage copy (private copy in filesDir is
#    what the app actually reads)
adb shell rm -rf /sdcard/Download/smolvlm_tmp
```

## App-side confirmation (after provisioning, before trusting any inference result)

```bash
adb logcat | grep -iE "smol|onnx|ort|flutter"
```

Look for `getModelInfo()` reporting `6/6 found` and, on first real
inference attempt, `sessions_loaded=3` with no `OOM`/`FATAL`/crash lines.
Per this task's standing rule: **do not claim native on-device inference
success until this has actually been observed on a physical device** — no
physical device was available in this session, so this remains unverified
here, consistent with `native_smol_implementation_audit.md`'s conclusion
that the code is fully implemented but provisioning/execution against a
real phone has not happened yet.
