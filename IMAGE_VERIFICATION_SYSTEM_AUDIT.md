# IMAGE_VERIFICATION_SYSTEM_AUDIT

작성일: 2026-07-11
작성자: Claude Code (Phase 0 상태 감사)
대상: VLM 기반 이미지 인증 시스템 (SmolVLM local-first + Server fallback VLM + Rule Engine)

> **후속 진행(2026-07-11):** Phase 0 감사 이후 end-to-end 파이프라인 안정화 + fallback 모델 확정 완료.
> - fallback 후보 비교(A.X vs Qwen2.5-VL-7B) → **Qwen2.5-VL-7B + guard 채택**.
> - full-test 잔여 FP=6 전수 재분류 → **VLM-eligible visual scope 기준 FP=0 → CONFIRM_ELIGIBLE_SCOPE**.
> - `verified(water)` → 자동 확정 차단(`review_required=true` → 앱 재촬영 안내). 관리자 검수 큐는 범위 밖(future work). Smol 온디바이스 = onnxruntime-android 통합 + **Flip3 실기기 이미지→텍스트 생성 성공**(vision→embed→image merge→패딩 no-cache→detokenize; "A glass of yellow liquid" 정확 생성)(`smol_android_image_text_generation_spike_verified`, evidence/Rule Engine 미연결→서버 fallback 유지).
> - 상세: **`VLM_FALLBACK_STABILIZATION_REPORT.md`**, **`SMOL_ONDEVICE_STATUS.md`**.

---

## 0. 요약 (TL;DR)

- **Feature_CM 에 image_verification Rule Engine 이 이미 병합됨** (rule_engine / service / API / rules yaml / schema / tests / Flutter screen 전부 존재).
- **VLM evidence engine(qwen3b / smol / fallback verifier) 은 Feature_CM 에 아직 없음.** 해당 작업은 전부 `feature/qwen3b-evidence-engine-integration`(로컬 `AI_Secretary_FeatureJW_Qwen`) 브랜치에만 존재.
- **end-to-end 파이프라인(`vlm_fallback_verifier.py`)은 이미 구현되어 있고 실제 구동됨** (mini_probe48: error=0, parse_failed=0, fail_safe=0).
- **가장 큰 블로커: FP.** mini_probe48 에서 **FP=14 (water=12, study=1, exercise=1)** → 현재 시스템은 "구동 가능한 baseline" 이며, **인증 시스템으로 확정 불가 (FP>0)**.
- Rule Engine 은 CM 과 JW 가 **완전 동일**(diff clean) → JW 에서 작업 후 CM 통합해도 rule 충돌 없음.
- 원격 fetch/pull **불가**(GitHub credential/`gh` 없음) → 아래 상태는 **로컬 기준**, remote stale 가능성 있음.

---

## 1. Git / 브랜치 상태

| 항목 | 값 |
|---|---|
| 공통 remote | `https://github.com/chaemni0706/AI_Secretary.git` |
| Feature_CM 작업본 | `/home/piai/AI_Secretary_CM_MERGE` (branch `Feature_CM`) |
| VLM 작업본 (권장 base) | `/home/piai/AI_Secretary_FeatureJW_Qwen` (branch `feature/qwen3b-evidence-engine-integration`) |
| Feature_CM local vs origin | HEAD == origin/Feature_CM (0/0 ahead-behind), **단 fetch 실패로 stale 가능** |
| 원격에 내 브랜치 존재? | ✅ `origin/feature/qwen3b-evidence-engine-integration` remote-tracking 존재 (어제 push 성공) |

### 원격 최신화 실패 원인 (기록)
```
git fetch origin
→ fatal: could not read Username for 'https://github.com': No such device or address
```
- `gh` CLI 미설치, git credential.helper 미설정 → **비대화형 환경에서 원격 pull 불가**.
- 대응: 로컬 Feature_CM 기준으로 감사. **remote stale 가능성 notes 에 명시.** 사용자가 대화형 세션에서 `git pull origin Feature_CM` 재확인 권장.

### 관련 원격 브랜치 (fetch된 ref 기준)
`Feature_CM`, `Feature_JW`, `feature/image-verification`, `feature/qwen3b-evidence-engine-integration`, `archive/vlm-qwen3b-unified-baseline`, `backup/Feature_JW-before-image-20260704-154710` 등.

---

## 2. image_verification Rule Engine 존재 여부

**Feature_CM: ✅ 존재 (병합 완료)** — Qwen/Smol VLM 부분만 미포함.

| 파일 | Feature_CM | JW_Qwen | CM==JW? |
|---|:---:|:---:|:---:|
| `backend/services/image_verification_rule_engine.py` | ✅ | ✅ | **동일** |
| `backend/services/image_verification_rules_loader.py` | ✅ | ✅ | **동일** |
| `backend/services/image_verification_service.py` | ✅ | ✅ | — |
| `backend/api/image_verification.py` (API route) | ✅ | ✅ | — |
| `backend/rules/image_verification/*.yaml` (water/study/exercise/gym/medicine/wakeup) | ✅ | ✅ | — |
| `backend/database/schema/image_verification_schema.py` | ✅ | ✅ | — |
| `tests/test_image_verification_rule_engine.py`, `..._api.py` | ✅ | ✅ | — |
| `frontend/lib/screens/image_verification_screen.dart` | ✅ | ✅ | — |

→ 최종 판정 함수 `backend.services.image_verification_rule_engine.evaluate_image_verification` 사용 가능, **수정 불필요** (계획대로 그대로 사용).

---

## 3. VLM Evidence Engine / Fallback Pipeline 상태

**Feature_CM: ❌ 없음** (vlm_baseline 에 README/prompts/qwen3b_unified_verifier/sample_schema 뿐).
**JW_Qwen: ✅ 구현 존재** (아래 전부 `local_eval/vlm_baseline/`).

| 파일 | 상태 | 라인 | git |
|---|---|---:|---|
| `vlm_fallback_verifier.py` | ✅ end-to-end 오케스트레이터 (Phase1 아키텍처/Phase2 정책 반영) | 218 | untracked |
| `smol_evidence_engine.py` | ✅ SmolVLM-500M lazy singleton wrapper | 62 | untracked |
| `smol_evidence_adapter.py` | ✅ evidence→VisionAnalysis→Rule Engine | 90 | untracked |
| `qwen3b_evidence_engine.py` | ✅ Qwen2.5-VL-3B evidence engine | 230 | committed |
| `qwen3b_evidence_adapter.py` | ✅ | 235 | modified |
| `qwen3b_runtime_config.py` | ✅ (default path = AWQ, bf16 override 사용) | 38 | committed |
| `run_vlm_fallback_full_eval.py` | ✅ full-test runner | 174 | untracked |
| `outputs/vlm_fallback_mini_probe48/` | ✅ 이전 mini probe 결과 | — | untracked (git 미포함 유지) |

### 파이프라인 아키텍처 (구현 확인됨)
```
image + task
 → SmolVLM local evidence → smol_adapter → Rule Engine → local_result
 → should_accept_local_result?  (Smol verified 로컬 채택 절대 금지, 명확 blocker rejected 만 채택)
     accept → return (engine=smol)
     else   → Qwen3B fallback evidence → qwen_adapter → Rule Engine → final_result (engine=qwen3b_fallback)
              qwen 실패(parse_failed/rule_fallback) → fail_safe retake_required
```
- 반환 schema 는 Phase 1 스펙과 거의 일치 (task/final_result/engine_used/fallback_used/local_result/fallback_result/rule_reason/rule_trace/evidence/debug).
- `--dry-run` 8 케이스 mock 테스트 내장. `--no-qwen` local-only smoke 모드 존재.
- **정책 핵심(FP 대비):** Smol 의 `verified` 는 로컬에서 절대 채택 안 함 → 항상 fallback 재확인. Smol 은 명확한 blocker `rejected(uncertainty=low)` 만 로컬 채택.

---

## 4. Smol 엔진 현재 상태

**상태 분류: `smol_local_python`** (서버/워크스테이션 Python transformers 로만 구동).

| 항목 | 값 |
|---|---|
| 모델 경로 | `/data/models/SmolVLM-500M-Instruct` (weight git 미포함) |
| 모델 크기 | 6.5G (safetensors) |
| 실행 방식 | Python transformers, `build_adapter("smolvlm")` 재사용, lazy singleton |
| 온디바이스(Android) | ❌ 미변환 (GGUF/ONNX/TFLite 없음, Flutter/Android 런타임 호출 없음) |
| GGUF 대안 | `/data/models/SmolVLM2-2.2B-Instruct-GGUF` 존재 (500M 용은 아님) |
| 역사적 리스크 | final171 에서 **FP=9** → 단독 최종 인증 금지, 1차 evidence engine 으로만 사용 |

### 온디바이스화 가능성 (예비 평가 — 미착수)
- SmolVLM-500M 은 소형이라 이론상 온디바이스 후보이나, 500M safetensors 6.5G(bf16) → 양자화(GGUF Q4/Q8) 필요, llama.cpp mmproj 변환 필요.
- Galaxy Z Flip3 실디바이스 smoke 는 **별도 변환+패키징 작업** 필요, 현재 미착수. 우선순위 후순위 권장(먼저 서버 파이프라인 FP=0 확정).

---

## 5. Fallback 서버 VLM 후보 상태 (Phase 3 대상)

디스크 실측(`/data/models`) 기준. GPU: **RTX A5000 24GB** (현재 ~1.4GB 사용, ~23GB 여유).

| 후보 | 디스크 | 크기 | AWQ 이슈 | 즉시 구동 |
|---|---|---:|---|:---:|
| **Qwen2.5-VL-3B-Instruct** (bf16, 현 fallback) | ✅ 있음 | 7.1G | 없음(bf16) | ✅ |
| **A.X-4.0-VL-Light** (SKT) | ✅ 있음 | 15G | — | ✅(로드 검증 필요) |
| **Qwen2.5-VL-7B-Instruct** (bf16) | ❌ 없음 | ~16G dl | — (7B-AWQ만 이슈) | ⚠️ 다운로드 필요 |
| **Qwen3-VL-8B-Instruct** | ❌ 없음 | ~18G dl | — | ⚠️ 다운로드 필요 |
| Qwen2.5-VL-3B-AWQ / 7B-AWQ | ✅ 있음 | — | **Triton GEMM CompilationError 이력** | ❌ 재시도 금지 |

- Phase 3 가 지정한 3후보 중 **A.X-4.0-VL-Light 만 디스크 존재**, 나머지 2개(7B bf16, Qwen3-VL-8B)는 **대용량 다운로드 필요 → 사용자 승인 필수**.
- 24GB VRAM 에 7B/8B bf16 모두 적재 가능(여유 있음).

---

## 6. 이전 평가 결과 (mini_probe48, 이미 실행됨)

| 지표 | 값 |
|---|---|
| n | 48 (water 20 / study 13 / exercise 15) |
| **FP total** | **14** ❌ |
| task FP | water=**12**, study=1, exercise=1 |
| verified_on_negative | 14 |
| recall (ALL) | 0.40 (water 1.0 / study 0.0 / exercise 0.2) |
| verified / rejected / retake | 20 / 27 / 1 |
| fallback_used | 37 (smol_accept=11) |
| qwen_fallback_success | 37/37 |
| error / parse_failed / fail_safe | **0 / 0 / 0** ✅ |
| latency avg / p50 / p95 | 9581 / 8245 / 18196 ms |
| **판정** | **DO_NOT_CONFIRM (FP>0)** |

### FP 근본 원인 (분석 완료)
- water 룰(`water.yaml`): verified 임계값 **60점**. 점수: `water_bottle/cup=15`, `visible_water/clear_liquid=30`, `filled_container=20`, `sealed_water_bottle=60(즉시 verified)`.
- FAIL water 이미지에서 **Qwen3B evidence engine 이 positive water 근거(visible_water+filled_container 등)를 과대보고** → 65점 이상 → verified.
- 즉 **FP 는 파이프라인 배선 문제가 아니라 fallback VLM 의 evidence 품질(과대보고) 문제** → Phase 3(더 나은 fallback VLM 선택) 또는 프롬프트/근거 채택 정책 강화가 레버.
- Rule Engine 은 수정 대상 아님(계획 고정).

---

## 7. 시스템 구동 가능 여부 / 블로커 / 다음 우선순위

**구동 가능? → ✅ Yes (baseline 으로 구동됨).** **확정 가능? → ❌ No (FP=14).**

### 가장 큰 블로커
1. **water FP=12** — fallback VLM 이 FAIL 이미지에 water 근거 과대보고. (최우선)
2. study recall=0.0 — study 근거 인식 약함(FN 5). FP 해결 후 다룰 2순위.
3. 원격 pull 불가 → CM 최신 상태 확인 못함(로컬 기준). 대화형 세션 재확인 필요.
4. Smol 온디바이스화 미착수(후순위).

### 다음 작업 우선순위 (권장)
1. **Phase 3-4: fallback VLM 후보 비교** — A.X-4.0-VL-Light(디스크) vs Qwen2.5-VL-7B/Qwen3-VL-8B(다운로드 승인 시) vs 현 Qwen3B. Gate A(smoke)→Gate B(mini probe48 FP)→최선 1개 선택.
2. **water FP=0 달성** 을 1차 성공 기준으로.
3. Gate C full-test (final_manifest.csv, 176 img) 는 mini probe FP=0 통과 모델만 1회 실행.
4. FP=0 확정 후 Smol 온디바이스화 검토.

---

## 8. full-test runner / manifest

- runner: `local_eval/vlm_baseline/run_vlm_fallback_full_eval.py` ✅ (predictions.jsonl / per_image.csv / metrics.json / metrics_by_task.csv / fp_review.csv / fn_review.csv / error_review.csv / report.md 산출).
- full manifest: `local_eval/real_validation_dataset_150_candidate/final_manifest.csv` ✅ (176 이미지 + header).
- mini probe manifest: outputs 로 보아 48-case probe 이미 사용 이력.

---

## 9. 결론 / 확정 기준

- 현재 시스템은 **"구동 가능한 VLM fallback baseline"**. 파이프라인·Rule Engine·runner·평가 하네스 모두 존재하고 동작함.
- **인증 시스템으로 "완결/확정" 불가** — full-test 는 물론 mini probe 에서도 **FP>0**.
- 확정 조건: full-test 에서 **FP total=0 AND task FP=0 AND (parse_failed→verified)=0 AND (engine_error→verified)=0**.
- 다음 단계는 구현 배선이 아니라 **fallback VLM 품질로 FP 를 0 으로 낮추는 것** — Phase 3-4 우선.

> 주의: 이 감사 이후 구현은 사용자 스코프 승인 후 진행. 특히 (1) fallback 후보 다운로드 승인, (2) 작업 base 브랜치 확정이 선행되어야 함.
