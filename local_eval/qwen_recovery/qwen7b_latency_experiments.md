# Qwen7B Latency Stabilization — Real Measurements (Phase 11.B)

All rows below are real `Qwen7BVisionAnalyzer.analyze_with_context()` calls
against the same real image (`water_001.png`, 252x252px, from
`local_eval/real_validation_dataset_150_candidate/images/water/`), on this
server's Tesla P40. No mock predictions, no estimated latency -- every
number here came from an actual `torch.cuda`/`transformers.generate()` call,
logged via `health_check()` + wall-clock timing in
`~/model_cache/qwen7b_latency_experiment.py`.

## Candidates measured

| candidate | dtype | device_map | cpu_offload | max_new_tokens | load_s | gen_s | parse | result |
|---|---|---|---|---|---|---|---|---|
| baseline (Phase 10) | float32 | auto | yes | 512 | ~25 | 200-345 | clean | verified |
| max_new_tokens=128 | float32 | auto | yes | 128 | 25.3 | **316.5** | clean | verified |
| no_cpu_offload requested | float32 | auto (forced back to offload) | yes (unavoidable) | 128 | 25.1 | 318.0 | clean | verified |
| max_pixels capped (100k) | float32 | auto | yes | 128 | 25.2 | 316.6 | clean | verified (no effect -- image already 252x252, below any cap) |
| **float16** | float16 | auto | **no** | 64 | 21.5 | **12.6** | **failed** (no_json_object_found, even after 1 repair attempt) | unusable |

## Findings (not assumed -- measured)

1. **max_new_tokens has almost no effect** (316-318s regardless of 512 vs
   128). This means the dominant cost is NOT the autoregressive generation
   loop -- it is the one-time **prefill** pass (processing the ~465-token
   image+text context through the model once), which happens before any
   token is generated.
2. **CPU offload is not avoidable in float32 on this GPU.** Requesting
   `no_cpu_offload` (omitting the `max_memory` hint entirely) did not change
   `device_map`'s decision -- `accelerate`'s `device_map="auto"` still
   offloaded some layers to CPU, because a float32 7B model (~28GB) simply
   does not fit in this P40's 24GB regardless of what hint is given. This is
   a hard capacity constraint, not a configuration bug.
3. **Image resolution capping showed no effect on this dataset's images**
   (already small, 252x252px, below the 100k-pixel cap tested) -- this does
   NOT mean resolution capping is useless in production: real phone camera
   photos (typically 3000x4000+) would produce far more vision tokens and a
   correspondingly larger prefill, so capping is still a reasonable
   production safeguard, just not demonstrated as a win on this specific
   test asset. Flagged as untested-at-real-scale, not proven ineffective.
4. **float16 is ~25x faster (12.6s vs ~317s) and fits fully on GPU with zero
   CPU offload** -- but reconfirms (with the CURRENT full pipeline, including
   the objects-in-prompt fix from Phase 11 and the one-shot repair attempt)
   the same degenerate-output failure found in the prior session: the raw
   text produced no parseable JSON, even after a repair prompt. **This is
   not a workable path on this GPU without further investigation (e.g.
   isolating which specific layer's fp16 computation is unstable) that was
   not undertaken this session.**
5. **do_sample=False and torch.inference_mode()** were already in place
   before this phase (verified by reading the code, not re-tested as new
   candidates).
6. **Request concurrency semaphore=1** implemented (`threading.Semaphore(1)`
   around the `generate()` call) -- serializes concurrent requests rather
   than letting them race for the same ~20GB budget and both OOM.
7. **Startup warm-up** implemented (`Qwen7BVisionAnalyzer.warmup()`, a tiny
   real generation on a synthetic 64x64 image) -- moves the ~20-25s cold
   weight-load cost to server startup instead of the first user request. Not
   wired into `backend/main.py`'s startup event this session (would need an
   explicit opt-in env flag and is a small addition, deferred to keep this
   phase's diff focused on the analyzer itself).

## Conclusion: no viable latency win found this session

**The ~300s/call reality from Phase 10 stands.** Every tested candidate that
preserves correct output (float32 + CPU offload) landed in the same 300-320s
range regardless of max_new_tokens or resolution-cap tuning; the one
candidate that was dramatically faster (float16) is not usable due to a
real, reproducible output-quality failure on this specific GPU. This is
reported honestly rather than picking whichever number looks best.

**`max_new_tokens=128`** was still adopted as the new default (down from
512): it does not measurably help latency on this hardware, but it is
strictly safe (real evidence JSON responses are short) and slightly reduces
worst-case token generation for verbose model outputs, with no observed
downside across all tests run.

## torch.cuda.empty_cache() status (per this task's instruction)

Kept as an explicit, **labeled-temporary** mitigation in
`_generate_raw`'s `finally` block (see code comment), now paired with
`gc.collect()`. Not bisected against removal within this session's time
budget; instead validated as a whole via the 8-consecutive-real-call
stability test (see `qwen7b_sequential_stability_results.md`) -- if OOM had
recurred with this mitigation in place, that would have been reported
here, but it did not (see that file for the actual outcome).
