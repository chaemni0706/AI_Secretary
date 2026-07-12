# Qwen3B Runtime Smoke Report (non-AWQ bf16)

작성 2026-07-10. branch `feature/qwen3b-evidence-engine-integration`.
> Qwen-3B = evidence extractor. **final_result 는 기존 Rule Engine(evaluate_image_verification)** 산출(Qwen 아님). Rule Engine core 미수정. full 48/171 미실행(단일 이미지 smoke만).

## 환경 / 모델
- model: **`/data/models/Qwen2.5-VL-3B-Instruct`** (non-AWQ, **quant=None, bf16**, arch Qwen2_5_VLForConditionalGeneration). 다운로드 7.1GB. **weight 는 git 미포함.**
- runtime: transformers 4.55.1 + Qwen2_5_VLForConditionalGeneration + AutoProcessor + qwen_vl_utils, **lazy singleton**. RTX A5000, torch 2.8/cu128.
- config(env): QWEN3B_MODEL_PATH, DEVICE=cuda, DTYPE=bf16, MAX_NEW_TOKENS=512, TEMPERATURE=0.0, DO_SAMPLE=false.
- **AWQ 회피 성공**: non-AWQ bf16 라 이전 AWQ Triton 커널 오류 없음. generate 정상.

## dry-run
- `--dry-run` → **7/7 통과**, `rule_engine_fallback=false`(실제 Rule Engine).

## 단일 이미지 smoke (task별 real PASS 1장, 이미지 원본 미수정/미이동)
| task | image | qwen generate | parse | final_result (Rule Engine) | fallback |
| --- | --- | --- | --- | --- | --- |
| water | water_001.png | 성공 | clean | **verified** | false |
| study | intake_023.jpg | 성공 | clean | **rejected** | false |
| exercise | intake_016.jpg | 성공 | clean | **rejected** | false |

- **water_001(PASS) → verified**: Qwen positive=clear_liquid_visible/waterline/transparent_container(+cup) → adapter→visible_water+filled_container → Rule Engine verified. rule_reason "cup 객체 확인".
- **study_023(PASS) → rejected**: Qwen 이 화면의 코드/문서 대신 **일반 책상 객체**(keyboard/laptop/notebook/cup/pen)만 서술 → study positive 코드 미매핑 → Rule Engine "학습 근거 부족". **recall 한계(prompt/mapper), 런타임 오류 아님.**
- **exercise_016(PASS) → rejected**: 덤벨만 보이고 동작 근거 없음 → exercise positive 미형성 → "운동 무관 환경". (equipment-only → 미verify: FP=0 정책상 보수적으로 맞음.)

## 성공 기준 대조
- model load ✓ / generate ✓(3/3) / JSON parse clean ✓(3/3) / adapter 통과 ✓ / Rule Engine 호출 ✓ / **final_result 는 Rule Engine 산출** ✓ / **rule_engine_fallback=false** ✓.
- → **런타임 smoke 성공**(실 generation 완료). 개별 verdict 는 evidence 매핑/recall 사안.

## 이번 수정(코드)
- `prompts.py`: 허용 토큰 목록 **나열(vocabulary dump) 금지**, 실제 present 만 보고, disqualifier 는 **blockers 에만** 넣도록 강화.
- `qwen3b_evidence_adapter.py`: (a) 하드 disqualifier 는 **blockers 필드만** 사용(negative_evidence 는 dump 위험으로 reject 근거 제외), (b) positive/blocker 매핑을 **한/영 keyword substring** 방식으로 변경(Qwen 자유서술 + dry-run 정확 토큰 모두 매핑).

## 한계 / 다음 (out of scope this turn)
- **study/exercise recall 낮음**: Qwen 이 화면 학습콘텐츠/운동 동작을 evidence 토큰으로 잘 안 냄(일반 객체 나열). prompt 강화 + mapper 보강 필요(별도 단계). water 는 verified 확인.
- **negative_evidence vocabulary dump**: Qwen 이 여전히 허용 토큰을 negative_evidence 에 나열(무시하도록 처리). prompt 추가 튜닝 여지.
- full 48/171 평가/Gate3 는 미실행. vLLM/AWQ 미사용.
