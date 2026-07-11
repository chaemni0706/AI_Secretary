# VLM Fallback Verification Pipeline (SmolVLM local-first + Qwen-3B fallback + 기존 Rule Engine)

작성 2026-07-10. branch `feature/qwen3b-evidence-engine-integration`.
목적: 카메라 이미지(water/study/exercise) 인증을 **로컬 우선 + 필요 시 fallback** 으로 처리하는 end-to-end 파이프라인.
**FP=0(오인증 최소화) 이 최우선 기준.**

> 핵심 원칙: SmolVLM/Qwen-3B 는 **evidence 추출기**일 뿐이다. `final_result` 는 **반드시 기존
> `evaluate_image_verification`(Rule Engine core, 미수정)** 또는 fail-safe(retake) 에서 나온다.
> VLM 의 raw 판단을 직접 최종 결과로 쓰지 않는다. 앱은 `final_result` 만 사용한다.

## 아키텍처

```
Camera Image + task
  ├─ 1) SmolVLM Local Evidence Engine (/data/models/SmolVLM-500M-Instruct, 로컬)
  │      → smol_evidence_adapter → 기존 Rule Engine → local_result
  │      → should_accept_local_result(local_result) 가 True 면 즉시 반환
  │
  └─ 2) (미채택 시) Qwen-3B Fallback Evidence Engine (/data/models/Qwen2.5-VL-3B-Instruct, non-AWQ bf16)
         → qwen3b_evidence_adapter → 기존 Rule Engine → final_result
         → Qwen 엔진 실패(parse_failed / rule_engine fallback) 시 fail-safe: retake_required
```

- 두 엔진(Smol, Qwen) 모두 **같은** 기존 Rule Engine 에 evidence 를 먹인다. 최종 판정 로직은 한 곳.
- Qwen fallback 런타임은 **non-AWQ Qwen2.5-VL-3B-Instruct bf16**. (AWQ 3B/7B 는 AutoAWQ 0.2.9 + torch 2.8 +
  Triton 3.4 에서 GEMM 커널 CompilationError 로 generate 실패 → 사용 안 함.)
- YOLO/OpenImages 객체탐지 경로는 **후순위 보류**(deferred).

## 파일

| 파일 | 역할 |
| --- | --- |
| `local_eval/vlm_baseline/vlm_fallback_verifier.py` | 오케스트레이터. Smol local-first → Qwen fallback → fail-safe. CLI/dry-run. |
| `local_eval/vlm_baseline/smol_evidence_engine.py` | SmolVLM-500M wrapper(기존 adapters/smolvlm_adapter 재사용). evidence dict 만 산출. |
| `local_eval/vlm_baseline/smol_evidence_adapter.py` | Smol evidence → 기존 Rule Engine 호출 → local_output(신뢰 신호). |
| `local_eval/vlm_baseline/qwen3b_evidence_engine.py` | Qwen2.5-VL-3B(non-AWQ bf16) 런타임. evidence 추출. |
| `local_eval/vlm_baseline/qwen3b_evidence_adapter.py` | Qwen evidence → 기존 Rule Engine 입력(VisionAnalysis) 매핑 + 호출. |
| `local_eval/vlm_baseline/run_vlm_fallback_full_eval.py` | full-test/probe 러너(FP, recall, latency, confirm decision). |

## Fallback trigger 정책 (Smol → Qwen)

`should_accept_local_result(local_output)` 가 **True 일 때만** Smol 결과를 로컬 채택. 그 외 전부 Qwen fallback.

**Smol `verified` 는 절대 로컬 채택하지 않는다** (SmolVLM-500M 이 FAIL 이미지에도 positive 근거를 만들어
FP=9 를 낸 이력 → verified 후보는 항상 Qwen 재확인). 로컬 채택은 아래만:

- `rejected` **AND** 명확한 blocker 존재 **AND** uncertainty=low → 로컬 채택(거절은 FP 를 못 만들어 안전).

즉 Qwen fallback 이 트리거되는 조건(= 로컬 미채택):
- engine_error / parse_failed
- rule_engine_fallback(기존 엔진 미가용)
- `final_result == verified` (항상)
- `final_result == retake_required`
- `rejected` 인데 blocker 없음 또는 uncertainty=high(불확실한 거절 → PASS 기회 부여)

Qwen fallback 자체가 실패(parse_failed / rule_engine fallback)하면 **fail-safe → retake_required**
(절대 verified 로 이어지지 않음. engine_error/parse_failed → verified 금지 불변식 유지).

## dry-run (8 케이스, 모델 없이 정책 검증)

`python local_eval/vlm_baseline/vlm_fallback_verifier.py --dry-run` → **8/8 PASS**.

| # | 시나리오 | 기대 |
| --- | --- | --- |
| 1 | Smol verified → 로컬 채택 금지, Qwen 재확인 → 기존 엔진 verified | fallback, qwen3b, verified |
| 2 | Smol 명확 blocker 거절 | 로컬 채택, smol, rejected |
| 3 | Smol 근거 텅 빔 → Qwen verify | fallback, qwen3b |
| 4 | Smol engine_error → Qwen verify | fallback |
| 5 | Smol verified 이나 uncertainty high → Qwen | fallback |
| 6 | Qwen fallback 성공(verify) | fallback, qwen3b, verified |
| 7 | Qwen engine_error → fail-safe | fallback, fail_safe, retake_required |
| 8 | force_fallback | fallback, qwen3b |

## CLI

```bash
# 단건
python local_eval/vlm_baseline/vlm_fallback_verifier.py --image <path> --task water|study|exercise [--force-fallback] [--no-qwen] [--json]
# probe(48) / full(171)
python local_eval/vlm_baseline/run_vlm_fallback_full_eval.py --probe  --output-dir <dir>
python local_eval/vlm_baseline/run_vlm_fallback_full_eval.py         --output-dir <dir>   # 전체 manifest
```
런타임 env: `QWEN3B_MODEL_PATH=/data/models/Qwen2.5-VL-3B-Instruct QWEN3B_DTYPE=bf16 QWEN3B_DEVICE=cuda`.

## 평가 결과 & 확정 결정 (FP=0 기준)

데이터셋: `local_eval/real_validation_dataset_150_candidate/final_manifest.csv` (171장; probe 48장).
`--borderline-as-fail`(기본) → BORDERLINE 은 non-PASS 로 취급(엄격).

### mini probe(48) — 정책 강화 전/후
| | FP total | water FP | study FP | exercise FP | recall(ALL) |
| --- | --- | --- | --- | --- | --- |
| 강화 전 | 20 | 13 | 6 | 1 | 0.60 |
| 강화 후(vocab-dump 캡 + water 보수) | **14** | 12 | 1 | 1 | 0.40 |

**probe 확정 결정: DO_NOT_CONFIRM (FP=14 > 0).**

### full-test(171) — (아래 표는 실행 완료 시 report.md/metrics.json 에서 채움)
> 산출물: `local_eval/vlm_baseline/outputs/vlm_fallback_full171/{report.md,metrics.json,fp_review.csv,...}` (git 미포함).

## 근본 원인 분석 (fp_review 기반)

1. **water — 빈/투명 용기의 '물' 환각 (지배적 FP, adapter 로 교정 불가).**
   Qwen-3B 가 **빈 유리잔(water_009), 빈 물병(water_035, intake_009 빈 유리 카라페)** 에 대해
   `visible_water` + `clear_liquid_visible` + `transparent_container` 를 **uncertainty=low, blocker 없음**으로
   출력. 이는 **실제로 물이 담긴 용기와 토큰이 완전히 동일** → keyword/adapter 수준에서 분리 불가능.
   기존 Rule Engine 의 water 게이트(용기 객체 + visible_water/clear_liquid)를 그대로 통과 → verified(FP).
   `empty_container` 신호는 Qwen 이 내주지 않아 blocker 로 잡히지 않음.

2. **study — vocabulary dump ↔ recall 상충.**
   Qwen 이 한 장에 lecture_video+code_editor+open_textbook+handwritten_notes 등 **허용 토큰을 무더기 나열**.
   dump 캡(≥4 positive 코드 폐기)으로 study FP 는 6→1 로 줄였으나, 같은 dump 가 **PASS 이미지에도 발생** →
   캡이 함께 폐기 → `study_pattern_missing` → PASS 도 rejected(**study recall 0**). 캡을 완화하면 dump FP 재발.
   Qwen study evidence 가 양방향으로 신뢰 불가.

3. **exercise — recall 낮음(0.2).** 장비/배경만으로는 미verify(FP=0 정책상 보수적으로 맞음), 동작 근거를 잘 못 냄.

## 결론 / 권고

- **현재 구성(SmolVLM-500M + Qwen-3B + 기존 Rule Engine)은 FP=0 을 만족하지 못한다 → 이미지 인증 시스템으로 확정 불가.**
- 지배적 FP(빈/투명 용기 물 환각)는 **adapter/프롬프트 튜닝으로 제거 불가**(evidence 가 진짜 물과 동일). 필요:
  1. **더 강한 VLM** (빈 vs 채워진 투명 용기 구분 가능한 모델), 또는
  2. **보류했던 YOLO/액체-수위(liquid-level) 신호** 도입(용기 안 실제 액체 표면 검출), 또는
  3. water 인증 정책 재정의(예: '마시는 동작' 요구 등) — 단 이는 기존 Rule Engine core 수정이 필요.
- 안전장치는 정상 동작: engine_error/parse_failed → **fail-safe retake**, verified 로 새지 않음. Smol verified 로컬 채택 금지.

## 제약 준수
- 기존 Rule Engine core(`backend/services/image_verification_rule_engine.py`) **미수정**. backend/Flutter 미수정.
- 모델 weight/`outputs/`/이미지/`/data/models` **git 미포함**. full-test 산출물은 report.md/metrics.json 등 요약만 로컬 보관.
