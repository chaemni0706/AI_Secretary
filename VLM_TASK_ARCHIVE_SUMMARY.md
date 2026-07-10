# VLM Task Archive Summary (Qwen-3B Unified Baseline)

작성 2026-07-10. branch: `archive/vlm-qwen3b-unified-baseline`.
> ⚠️ **이 branch 는 최종 제품 구조가 아니라, YOLO 전환 이전의 VLM 기반 task 정리본(팀 공유용 baseline)이다.** 이후 **YOLO/OpenImages 기반 구조로 다시 전환 예정**.

## 1. 프로젝트 목적
갤럭시(모바일) 이미지 인증: **water / study / exercise** 사진이 실제 활동을 담고 있는지 판정(verified/rejected/retake_required). **FP=0(오탐 최소화)** 이 최우선.

## 2. 기존 SmolVLM 온디바이스 후보 검토
- 온디바이스 단독 VLM 인증을 목표로 **SmolVLM-500M** 을 우선 후보로 검토.
- Android packaging/runtime(ONNX/llama.cpp) 가능성은 확인됨(크기 OK 대역).

## 3. SmolVLM-500M final 171 결과 → 탈락
- **real-only 171장 최종 평가에서 FP=9**(water 6 / study 3 / exercise 0).
- 원인: 빈컵/물, 색음료/물, 게임/공부화면, 닫힌/열린책 등 **세밀 시각 분별력 부족**(파서/프롬프트로 교정 불가).
- **FP=0 기준 미달 → 단독 온디바이스 인증 모델 탈락.** (상세: `SMOLVLM_ONDEVICE_EVAL_FINAL_DECISION.md`, `local_eval/ondevice_vlm_eval/SMOLVLM_FINAL_NO_GO.md`, `SMOLVLM_FP_FAILURE_TAXONOMY.csv`.)

## 4. Qwen-3B fallback 구조
- 원래 구상: **local SmolVLM(온디바이스) → 불확실 시 서버 Qwen-3B fallback**.
- Qwen2.5-VL-3B(-AWQ)는 별도 실측에서 **전 task FP=0, study accuracy/recall 1.000**(성능 anchor/서버 fallback)로 확인됨(`MODEL_SELECTION.md`).

## 5. 이번 branch 에서 Qwen-3B 를 unified verification baseline 으로 정리한 이유
- 팀장님 공유용으로 **VLM task 를 빠르게 정리**해야 함.
- SmolVLM 단독 온디바이스 인증은 탈락 → 임시로 **Qwen-3B 하나가 local/fallback 구분 없이 전체 verification 을 수행**하는 단일 baseline 으로 정리(구현 스켈레톤 + 문서).
- 즉 이 baseline 은 "온디바이스 완결"이 아니라 **서버 Qwen-3B 가 water/study/exercise 를 직접 verified/rejected/retake_required 판정**하는 임시 통합본.

## 6. YOLO 전환 예정 (명시)
- 다음 단계는 **YOLO/OpenImages 기반 구조**로 전환 예정(별도 phase). 이번 branch 에는 **YOLO 구현 미포함**.
- 온디바이스 완결성/서버 비용/실시간성을 YOLO 기반 detector + 규칙으로 개선하는 것이 후속 목표.

## 7. 범위(이번 branch 에 포함/제외)
- **포함**: SmolVLM 온디바이스 검토 결론, Qwen-3B unified verification baseline(문서+스켈레톤), task prompt, fallback 구조 노트, pipeline audit/cleanup.
- **제외(섞지 않음)**: YOLO 설계, A.X-4.0-VL-Light / Qwen2.5-VL-7B / Qwen3-VL / InternVL / FastVLM / Moondream 등 **추가 서버/온디바이스 후보 탐색**, 대형 모델 weight, 대용량 raw outputs, dataset 이미지 원본.

## 8. 결론
- 이 branch = **VLM 기반 task 정리본**. 실제 실행은 서버 Qwen-3B 의존. FP=0 우선 정책(애매→retake, 부정근거→rejected).
- **최종 제품 구조 아님. YOLO 전환 전 임시 baseline.**
