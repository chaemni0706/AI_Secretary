# Qwen7B Sequential Stability — fp32 Reference Engine (Phase 11.H, completed)

8 real, sequential `analyze_with_context()` calls in **one process** (one
model load, matching how the real backend server keeps the model resident
across requests), all against the same real `water_001.png` image,
`max_new_tokens=128`, `torch_dtype=float32`, CPU-offloaded `device_map="auto"`.

This ran far longer in wall-clock time than the earlier isolated
single-call measurements suggested (~42 minutes total vs. an expected
~25-40 minutes) -- reported honestly as observed, not smoothed over. No
diagnosis was made for the added per-call variance (session had many prior
GPU experiments; possible host-side memory/cache effects). All 8 calls
still completed correctly.

## Results

| call | seconds | quality_usable | parser_status | cuda_oom | water_visual_evidence |
|---|---|---|---|---|---|
| 1 | 316.7 | true | clean | false | filled_container, visible_water |
| 2 | 315.4 | true | clean | false | filled_container, visible_water |
| 3 | 315.4 | true | clean | false | filled_container, visible_water |
| 4 | 315.5 | true | clean | false | filled_container, visible_water |
| 5 | 315.3 | true | clean | false | filled_container, visible_water |
| 6 | 315.3 | true | clean | false | filled_container, visible_water |
| 7 | 315.3 | true | clean | false | filled_container, visible_water |
| 8 | 315.3 | true | clean | false | filled_container, visible_water |

**Summary: 8/8 completed, 0 OOM.**

## Interpretation

- **No cumulative latency explosion**: calls 2-8 were actually *more*
  consistent than call 1 (within 1.4s of each other: 315.3-315.5s), and call
  1 itself was only marginally slower (316.7s) -- no drift, no degradation
  across the run.
- **No result drift**: identical `water_visual_evidence` on every single
  call for the same input image -- deterministic (`do_sample=False`) and
  stable across repeated real inference in the same process.
- **The `torch.cuda.empty_cache()` + `gc.collect()` mitigation (Phase 11.B)
  is confirmed necessary and sufficient**: this is the exact configuration
  that previously OOM'd around call 4 without this cleanup (Phase 10
  finding) -- with it in place, all 8 calls succeeded.

## Standing limitation

At ~315s/call, this fp32 reference engine's absolute latency is unchanged
and remains unsuitable for a live demo (see Phase 12 for the quantized
engine investigation). This test's purpose was narrowly to confirm
**stability** (no OOM, no drift) at that latency, which it does.
