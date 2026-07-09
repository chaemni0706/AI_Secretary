# SmolVLM On-Device Eval — Final Decision

작성 2026-07-10. branch: `archive/vlm-qwen3b-unified-baseline`.

## 결론 (요약)
- **SmolVLM-500M 온디바이스 단독 인증 후보 = 탈락(NO-GO).** real-only 171장 최종 평가 **FP=9**. FP=0 기준 미달.
- 대체: **Qwen-3B unified verification baseline** 으로 정리(임시, YOLO 전환 전).

## 상세
1. **온디바이스 후보 검토 완료**: SmolVLM-500M 을 온디바이스 단독 VLM 인증 후보로 검토. Android packaging/runtime(ONNX/llama.cpp) 가능성 확인(크기 대역 OK).
2. **final real-only 171 평가**: 동일 Rule Engine/파서로 평가 → **FP=9**(water 6 / study 3 / exercise 0).
3. **원인**: 빈컵 vs 물, 색음료 vs 물, 게임화면 vs 공부화면, 닫힌책 vs 열린책 등 **세밀 시각 분별력 부족**. 파서/프롬프트 보정으로 해결 불가(모델 자체 한계).
4. **판정**: **FP=0 기준 미달 → 단독 온디바이스 인증 모델 탈락.** (아카이브: `local_eval/ondevice_vlm_eval/SMOLVLM_FINAL_NO_GO.md`, `SMOLVLM_FP_FAILURE_TAXONOMY.csv`.)
5. **대체 정리**: Qwen-3B(Qwen2.5-VL-3B[-AWQ], 별도 실측 전 task FP=0/study 1.000)를 **unified verification baseline** 으로 임시 채택(`QWEN3B_UNIFIED_VERIFICATION_BASELINE.md`).

## 위치/한계
- SmolVLM 은 폐기하지 않고 **local router/verifier 구성요소(FP 방어)로만 재활용 가능성**은 남김(이 branch 범위 밖).
- 이 결정은 **VLM baseline 정리용**이며 최종 제품 구조 아님. **YOLO/OpenImages 전환 예정.**
