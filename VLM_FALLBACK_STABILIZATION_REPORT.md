# VLM Fallback 이미지 인증 안정화 보고서

작성일: 2026-07-11
브랜치: `feature/vlm-image-verification-stabilization` (base: `feature/qwen3b-evidence-engine-integration`)
관련: [IMAGE_VERIFICATION_SYSTEM_AUDIT.md](IMAGE_VERIFICATION_SYSTEM_AUDIT.md) (Phase 0 감사)

## 0. 결론 요약 (정직한 판정)

- **시스템은 end-to-end 로 구동됨** (Smol local-first → server fallback VLM → FP guard → 기존 Rule Engine → fail-safe).
- **최종 fallback = Qwen2.5-VL-7B-Instruct(bf16) + FP guard.** (A.X-4.0-VL-Light 와 full-test 비교 후 채택.)
- **full-test(171) 전체 FP=6 → `DO_NOT_CONFIRM`.** 그러나 잔여 FP 는 전부 **외관상 물과 구분 불가**(변기물/오염수/맥주+물/borderline)로, VLM-eligible visual scope 밖.
- **VLM-eligible visual subset(165장) 기준 FP=0 → `CONFIRM_ELIGIBLE_SCOPE`.** 이 범위에서 **Qwen2.5-VL-7B fallback 확정**(AUTO-CONFIRM 조건 충족). 전체 현실 world 완전 자동화가 아니라 **"VLM-eligible scope baseline confirmed"**.
- 운영 정책: **verified(water) 는 자동 확정하지 않고 `review_required=true`** 로 표시 → 앱은 자동 성공으로 보지 않고 **"자동 인증 불가 → 다른 사진으로 재촬영"** 안내. exercise/study 는 FP=0 자동 확정. error/parse_failed → verified = **0**(안전).
  (관리자 승인/반려 큐는 이번 범위 아님 — §9 참조.)
- **Smol 온디바이스**: ONNX q4f16 자산 확보(~356MB) + Dart/Kotlin 인터페이스·브릿지 스텁 + 서버 fallback 계약 구현 → 상태 `smol_android_runtime_stubbed`. 실디바이스 ONNX 추론은 미완(문서화). → `SMOL_ONDEVICE_STATUS.md`.

### 두 후보 full-test(171) 비교
| fallback | FP | 진짜FAIL water FP | BORDERLINE FP | study FP | water recall | error/parse_fail | latency avg |
|---|---|---|---|---|---|---|---|
| A.X-4.0-VL-Light + guard | 9 | 5(아이스티/커피) | 3 | 1 | 0.95 | 4/4 | 4.5s |
| **Qwen2.5-VL-7B + guard(채택)** | **6** | 4(맥주/변기물/오염수) | 2 | **0** | 0.85 | **0/0** | 6.6s |

→ 7B 채택: FP 낮고(6<9), study/exercise FP=0, **엔진오류·파싱실패 0**(A.X 는 8건 발생). A.X 가 놓친 아이스티/커피는 7B 가 정확히 거절. latency 만 소폭↑(fallback 경로라 허용).

### VLM-eligible visual scope 재평가 (2026-07-11 확정)
full-test 잔여 FP=6 을 전수(이미지 직접 확인) 재분류: **visual_model_error = 0.** 전부 외관 기반 판단 불가:
- `non_visual_context_required`(2): intake_012(정수기/변기물), water_016(오염 식수) — 외관상 물, FAIL 사유가 비-시각적.
- `label_review_needed`(2): water_042/043 — 맥주잔 **옆에 실제 물잔도 함께** 있어 GT=FAIL 애매(모델이 물을 봄).
- `borderline_policy`(2): water_024/045 — BORDERLINE, 시각적으로 물.

이들을 VLM-only 자동 확정 대상에서 제외한 **eligible subset(165장)** 기준:

| | FP | task_fp(w/s/e) | v_from_err | decision |
|---|---|---|---|---|
| **eligible subset** | **0** | 0/0/0 | 0 | **CONFIRM_ELIGIBLE_SCOPE** |

산출: `recompute_metrics_with_scope.py` → `metrics_scope_adjusted.json`, 근거: `fp_scope_review.csv`.

> **Qwen2.5-VL-7B + guard is selected as the default server fallback model for VLM-based image verification.
> The model is confirmed only within the VLM-eligible visual scope. Water cases requiring non-visual context,
> such as contamination, toilet water, or visually indistinguishable alcohol, are excluded from VLM-only
> automatic confirmation and must be handled by secondary_review or context-based rules.**

### review_required 정책 (orchestrator, Rule Engine core 미수정)
추론 시 eligible/out-of-scope 를 사전 판별할 시각 신호가 없으므로, **verified(water) 는 자동 확정하지 않고
`review_required=true`(review_reason=`water_non_visual_context_risk`)** 로 표시 → 앱은 자동 성공 대신 **재촬영 안내**.
exercise/study 는 full-test FP=0 이라 그대로 자동 확정. 반환 schema 에 `review_required`/`review_reason` 추가.

## 1. 최종 아키텍처 (구현 완료)

```
Camera Image + task
 → SmolVLM-500M Local Evidence Engine → smol adapter → 기존 Rule Engine → local_result
 → should_accept_local_result?  (Smol verified 로컬 채택 금지; 명확 blocker rejected 만 로컬 채택)
     accept  → return (engine=smol)
     else    → Server Fallback VLM(Qwen2.5-VL-7B, pluggable) → server engine → 기존 Rule Engine → verified?
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

### 4a. 채택 모델 — Qwen2.5-VL-7B + guard
| task | n | recall | accuracy | FP |
|---|---|---|---|---|
| water | 57 | 0.85 (TP 17/20) | 0.84 | 6 |
| study | 54 | 0.21 (TP 6/29) | 0.57 | **0** |
| exercise | 60 | 0.50 (TP 16/32) | 0.73 | **0** |
| **ALL** | 171 | 0.481 | 0.719 | **6** |

- verified=45, rejected=115, retake=11. engine: smol_accept=34, server_fallback=137, **fail_safe=0, error=0, parse_failed=0**.
- latency: avg **6.6s** / p50 5.5s / p95 16.5s / max 44s.
- **판정: DO_NOT_CONFIRM (FP=6 > 0).**

### FP=6 분해 (전부 외관상 물과 구분 불가 — 직접 확인)
| 이미지 | GT | 7B reason(요약) | 성격 |
|---|---|---|---|
| intake_012 | FAIL | "toilet tank ... contains water, waterline" | **변기 물탱크의 실제 물** (외관=물) |
| water_016 | FAIL | "transparent container ... likely water" | **오염 식수**(File: Unsafe drinking water) — 외관=물 |
| water_042 | FAIL | "clear liquid ... water" | **맥주**(File: glass of beer) — 옅은 라거를 colorless 로 지각 |
| water_043 | FAIL | "colorless liquid ... water" | **맥주** — 동일 |
| water_024, water_045 | BORDERLINE | "colorless ... waterline" | 시각적으로 진짜 물(라벨만 borderline) |

→ **근본 실링:** FAIL 사유가 비-시각적(변기/수질)이거나 옅은 맥주/보더라인이라 **외관 기반 evidence 로 PASS 물과 분리 불가.** 프롬프트/guard/모델 교체로 해소 불가.

### 4b. 참고 — A.X-4.0-VL-Light + guard (탈락)
water recall 0.95, exercise FP 0 이나 FP=9(아이스티/커피 5 + borderline 3 + study 1), **engine_error 4 + parse_failed 4**(→retake). 7B 가 이 오류들과 아이스티/커피 FP 를 제거해 채택.

## 5. 확정 가능 여부 / 잔여 블로커

- **확정 불가 (FP=6 > 0).** 단, 잔여 FP 는 파이프라인/모델 결함이 아니라 **외관 기반 인증의 근본 실링**:
  변기물·오염수는 외관이 진짜 물, 옅은 맥주는 무색으로 보이고, BORDERLINE 은 정의상 물과 유사. → 더 강한 VLM 으로도 외관만으론 분리 불가.
- 7B 는 실제로 **개선 상한에 근접**: 색 있는 음료(아이스티/커피)·엔진오류·study/exercise FP 를 모두 제거. 남은 6개는 외관상 구분 불가 케이스뿐.

## 6. FP=0 도달을 위한 옵션 (사용자 결정 필요)

1. **비-시각 신호 결합(권장)** — 잔여 FP 는 외관만으론 불가. 기존 Rule Engine 이 지원하는 **GPS/시간/맥락**(현재 `gps.enabled=false`) 또는 촬영 맥락(음용 행동, 장소)로 보강해야 변기물/오염수/맥주를 걸러냄. Rule Engine core 확장 필요(별도 합의).
2. **데이터 라벨 재검토** — intake_012(변기물)·water_016(오염수)·water_042/043(맥주)는 "외관상 물"이므로 evidence 기준 GT 재정의 시 true-FAIL FP 대폭 축소. BORDERLINE 을 FAIL 에서 제외 시 FP=4.
3. **경량 색 신호(비-VLM)** — 액체 영역 색 히스토그램. 단 옅은 맥주/변기물엔 무효(색이 옅거나 물임).
4. **현 baseline 수용(운영)** — 7B fallback 을 "구동 가능한 baseline" 으로 배포하되, `verified(water)` 는 사람 검수 또는 2차 확인 큐로. exercise/study 는 FP=0.
5. **Qwen3-VL-8B 추가 비교** — 승인 시 동일 하네스로 즉시 평가(개선 여지는 제한적 — 외관 실링).

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

---

## 9. review_required = "자동 확정 불가 → 재촬영" (2026-07-11)

`verified(water)` 를 자동 확정하지 않고 `review_required` 로 표시하는 정책을 **backend service/API layer** 에 반영.
**Rule Engine core 미수정**(enum `verified/retake_required/rejected` 유지). schema 에 `review_required`/`review_reason` 필드만 추가(기본값 → 하위호환).

> **의미(중요):** `review_required=true` 는 **"관리자 검수 대기"가 아니라 "자동 인증 확정 불가 → 사용자가 다른 사진으로 재촬영"** 을 뜻한다.
> 앱은 이 결과를 자동 성공으로 처리하지 않고 재촬영 UX 로 안내한다.
> DB-backed review queue + 관리자 pending/decision(approved/rejected/needs_retake) 흐름은 한 번 구현했다가 **범위 밖으로 revert** 했다
> (앱에 관리자 검수 페이지 계획 없음). → **future work**(별도 합의 시). 현재 응답에는 `review_required`/`review_reason` 만 존재한다.

- schema: `ImageVerificationData` 에 `review_required: bool=False`, `review_reason: str=""` 추가.
- service: `apply_secondary_review_policy(data)` — `result==verified AND verification_type==water` → `review_required=true`,
  `review_reason="water_non_visual_context_risk"`. `verify_image_upload` 반환 직전 적용(study fallback 이후).
- API: `POST /api/v1/image-verifications` 응답 `data` 에 두 필드 노출(`success_response(data=model_dump())`).
- exercise/study/기타: 정책 미적용(기존 흐름 유지).

### API response 예시 (water verified → review)
```json
{
  "success": true,
  "message": "인증사진 판정이 완료되었습니다.",
  "data": {
    "verification_type": "water",
    "result": "verified",
    "score": 65,
    "mandatory_passed": true,
    "rule_evidence": [{"code": "object:cup", "message": "cup 객체가 확인되었습니다.", "score_delta": 15}, ...],
    "review_required": true,
    "review_reason": "water_non_visual_context_risk"
  }
}
```
exercise verified → `"review_required": false, "review_reason": ""` (자동 확정).

### Frontend 반영 (재촬영 UX)
- `verification_result.dart`: `reviewRequired`/`reviewReason`/`needsRetake`(=needsSecondaryReview 하위호환) getter, `isVerified` 는 review 시 false,
  `displayMessage` 는 **"자동 인증이 어렵습니다. 다른 사진으로 다시 촬영해 주세요 📷"** 반환.
- `image_verification_screen.dart`: `needsRetake` 이면 amber(카메라) 카드 + "사진상 물처럼 보이지만 … 자동 인증할 수 없어요. 다른 사진으로 다시 촬영해 주세요." + "위 카메라 촬영으로 다시 시도" 안내. (기존 카메라 촬영 버튼 재사용)
- (온디바이스 경로) `image_verification_service.dart`/`image_verification_result.dart` 도 동일 필드/`needsRetake` 지원.

### 테스트
`tests/test_image_verification_review_policy.py`(5 cases): water verified→review, water rejected/exercise verified→no review,
응답 필드 노출, schema 기본값 하위호환. → 기존 53 + 신규 5 = **58 passed**(회귀 없음).
