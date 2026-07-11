# VLM Fallback 이미지 인증 안정화 보고서

작성일: 2026-07-11
브랜치: `feature/vlm-image-verification-stabilization` (base: `feature/qwen3b-evidence-engine-integration`)
관련: [IMAGE_VERIFICATION_SYSTEM_AUDIT.md](IMAGE_VERIFICATION_SYSTEM_AUDIT.md) (Phase 0 감사)

## 0. 결론 요약 (정직한 판정)

- **시스템은 end-to-end 로 구동됨** (Smol local-first → A.X server fallback → FP guard → 기존 Rule Engine → fail-safe). error/parse_failed → verified = **0** (안전).
- **full-test(171) FP=9 → `DO_NOT_CONFIRM`.** 인증 시스템으로 **확정 불가**. 현 상태는 **"구동 가능한 baseline"**.
- 단, incumbent 대비 대폭 개선: fallback FP(mini_probe) **15→3**, **water recall 0.95 유지**, **latency 2.3배↓**, exercise FP=0.
- **잔여 FP 근본원인(확정): A.X-4.0-VL-Light 의 색 판별 한계** — 아이스티/커피를 "colorless/clear water" 로 진짜 오인. reason 에 색 신호가 없어 guard 로 분리 불가. → **더 강한 VLM(다운로드) 또는 비-VLM 색 신호** 필요.

## 1. 최종 아키텍처 (구현 완료)

```
Camera Image + task
 → SmolVLM-500M Local Evidence Engine → smol adapter → 기존 Rule Engine → local_result
 → should_accept_local_result?  (Smol verified 로컬 채택 금지; 명확 blocker rejected 만 로컬 채택)
     accept  → return (engine=smol)
     else    → A.X-4.0-VL-Light Server Fallback → server engine → 기존 Rule Engine → verified?
                 → vlm_fp_guard: reason 스캔(빈잔/색깔/불투명/불확실) → 위험시 retake 로 강등
               fallback 엔진 오류(parse_failed/rule_fallback/engine_error) → fail_safe retake_required
```
- **final_result 는 항상 기존 `evaluate_image_verification`(Rule Engine core 미수정) 또는 fail-safe/guard** 에서 나옴.
- Smol/A.X 는 evidence extractor. 앱은 `final_result` 만 사용.

## 2. Fallback VLM 선정 (Gate B, mini_probe48)

| 후보 | FP | task_fp(w/s/e) | recall | parse_fail | v_from_err | latency avg |
|---|---|---|---|---|---|---|
| Qwen2.5-VL-3B (bf16, incumbent) | 15 | 12/1/2 | 0.53 | 0 | 0 | 11.4s |
| **A.X-4.0-VL-Light** | 9 | 7/0/2 | 0.60 | 1 | 0 | **4.9s** |
| **A.X + FP guard (선택)** | **3** | 3/0/0 | 0.60 | 1 | 0 | 5.0s |

- **선택: A.X-4.0-VL-Light + FP guard.** 이유: 전 지표(FP·recall·latency)에서 Qwen2.5-VL-3B 우위.
  guard 적용 후 mini_probe water recall **1.0**(PASS 5/5 verified), 진짜 FAIL(빈잔/녹차) 포착.
- 미평가(미다운로드): Qwen2.5-VL-7B(bf16), Qwen3-VL-8B — 사용자 승인 시 동일 하네스로 비교 예정.
- AWQ(3B/7B)는 Triton generate 실패 이력으로 제외.

### A.X 런타임 이슈 해결
1. 커스텀 프로세서 `processing_ax4vl.py` 가 transformers>=4.55 에서 제거된 `_validate_images_text_input_order` import → **no-op shim** 패치(모델 소스+HF 캐시).
2. `generation_config.use_cache=false` → 디코드마다 KV 재계산(O(n²))으로 이미지당 수 분 → **generate(use_cache=True) 강제**로 ~5s/이미지 정상화.

## 3. FP=0 hard guard (`vlm_fp_guard.py`)

- Rule Engine core 미수정. Rule Engine 이 `verified` 를 내도 **A.X 의 `reason` 자유텍스트**를 스캔해
  빈 잔/색깔 음료/불투명/불확실이면 `retake_required` 로 강등.
- **핵심 교훈:** A.X 의 `positive_evidence`/`negative_evidence` 필드는 **vocabulary-dump 로 신뢰 불가**
  (PASS 물에도 `negative_evidence:["colored_beverage"]` 남발 → 초기 guard 가 이를 스캔해 PASS recall 을 0.13 으로 붕괴).
  → guard 는 **reason 중심 스캔, negative_evidence 제외**로 수정 → recall 0.60 회복 + 진짜 FAIL 포착.
- water/exercise 에만 적용(study 는 FP 낮음). study 는 guard 대신 recall 개선 과제.

## 4. Full-test 결과 (Gate C, 171 images, `--borderline-as-fail`)

| task | n | recall | accuracy | FP |
|---|---|---|---|---|
| water | 57 | **0.95** (TP 19/20) | 0.84 | 8 |
| study | 54 | 0.31 (TP 9/29) | 0.61 | 1 |
| exercise | 60 | 0.56 (TP 18/32) | 0.77 | **0** |
| **ALL** | 171 | 0.568 | 0.743 | **9** |

- verified=55, rejected=93, retake=23.
- engine: smol_accept=34, server_fallback=133, fail_safe=4, **error=4, parse_failed=4** (모두 fail_safe→retake, verified 로 이어지지 않음).
- latency: avg **4.5s** / p50 4.5s / p95 8.3s / max 14.8s.
- **판정: DO_NOT_CONFIRM (FP=9 > 0).**

### FP=9 분해
| 유형 | 이미지 | 원인 |
|---|---|---|
| BORDERLINE water (3) | water_014, 024, 045 | 시각적으로 물과 동일(라벨만 borderline). PASS 물과 evidence 분리 불가 |
| 진짜 FAIL water (5) | water_004(애매), **041(커피), 047·049·052(아이스티)** | **A.X 가 아이스티/커피를 "colorless/clear water"로 오인** — reason 에 색 신호 없음 → guard 불가 |
| 진짜 FAIL study (1) | study_034 (모바일 게임) | study evidence 오탐 |

**근거(직접 확인):** water_041 reason="clear liquid... colorless appearance"(실제 커피), water_047/049/052="clear/colorless liquid... water"(실제 아이스티). → A.X 모델의 색 판별 한계로 확정.

## 5. 확정 가능 여부 / 잔여 블로커

- **확정 불가 (FP>0).** FP=0 은 A.X 단독으로는 도달 불가 — 색깔 음료(아이스티/커피) 오인은 프롬프트/guard 로 해소 안 되는 **모델 판별 한계**.
- BORDERLINE 3장은 semantically 물과 동일 → strict borderline-as-fail 에서만 FP.

## 6. FP=0 도달을 위한 옵션 (사용자 결정 필요)

1. **더 강한 fallback VLM 다운로드** — Qwen2.5-VL-7B(bf16, ~16G) / Qwen3-VL-8B(~18G). 동일 하네스(registry/guard)로 즉시 비교 가능. 색 판별이 나아지면 진짜 FAIL FP 감소 기대. (승인 필요)
2. **경량 색 신호 추가(비-VLM)** — 액체 영역 색 히스토그램으로 "무색 아님" 판정 → colored beverage 차단. YOLO 없이 가능하나 액체 영역 검출이 별도 과제.
3. **BORDERLINE 재정의** — borderline 을 FAIL 이 아닌 별도 클래스로 취급 시 true-FAIL FP=6 로 축소(여전히 >0).
4. **현 baseline 수용** — FP>0 명시하고 "구동 가능한 baseline" 으로 사용, borderline/colored 는 사람 검수.

## 7. 산출물 / 파일

신규(코드):
- `local_eval/vlm_baseline/server_vlm_evidence_engine.py` — pluggable server VLM(A.X/Qwen) evidence engine (+guard 적용, use_cache 강제).
- `local_eval/vlm_baseline/server_vlm_model_registry.py` — 후보 registry(ax_4_0_vl_light/qwen25_3b/qwen25_7b/qwen3_8b).
- `local_eval/vlm_baseline/vlm_fp_guard.py` — reason 기반 보수적 FP guard.
- `local_eval/vlm_baseline/run_server_vlm_candidate_eval.py` — 후보 공정비교 runner(Gate B).
- `local_eval/vlm_baseline/vlm_fallback_verifier.py`, `smol_evidence_engine.py`, `smol_evidence_adapter.py`, `run_vlm_fallback_full_eval.py` — end-to-end 파이프라인/러너.

수정:
- `prompts.py`(water 프롬프트 색/빈잔 강화), `qwen3b_evidence_adapter.py`, `README.md`, `.gitignore`(outputs 제외).

외부(git 미포함): A.X `processing_ax4vl.py` shim 패치(/data/models, HF 캐시). weight 는 repo 미포함.

## 8. 앱/backend 호출 진입점

```python
from local_eval.vlm_baseline.vlm_fallback_verifier import verify_image_with_vlm_fallback
out = verify_image_with_vlm_fallback(image_path, task)   # task ∈ {water, study, exercise}
# out["final_result"] ∈ {verified, rejected, retake_required}  ← 앱은 이 값만 사용
# env VLM_FALLBACK_MODEL 로 fallback 모델 교체(registry key)
```
반환 schema: task/final_result/engine_used(smol|server_fallback|fail_safe)/fallback_used/local_result/
fallback_result/rule_reason/rule_trace/evidence/debug(guard_reason 포함). 기존 backend Rule Engine 과 동일 판정 함수 사용.
