# Qwen-3B Fallback Architecture Note

작성 2026-07-10. branch: `archive/vlm-qwen3b-unified-baseline`.

## 원래 구상
```
Camera Image → local SmolVLM(온디바이스) → (불확실 시) 서버 Qwen-3B fallback → verified/rejected/retake
```
- local 이 좁게 verified, 애매/불확실은 서버 Qwen-3B 로 fallback.

## 이번 branch 에서 정리한 구상 (임시)
```
Camera Image → Qwen-3B (local/fallback 구분 없이 전체 verification) → verified/rejected/retake
```
- **Qwen-3B 하나가 전체 verification baseline 을 수행.** SmolVLM 온디바이스 인증 탈락(FP=9)으로 local 단독 경로를 임시 제거.

## 이유
- 팀장님 **공유용으로 VLM task 를 빠르게 정리**하기 위함.
- **YOLO 기반 구조는 시간이 오래 걸릴 가능성** → 별도 phase 로 분리하고, 그 전까지 단일 Qwen-3B baseline 으로 정리.

## 한계
- **서버 의존**(온디바이스 완결성 낮음): Qwen-3B latency/VRAM 필요, 네트워크 전송 필요.
- **비용/실시간성**: 모든 인증이 서버 호출 → 비용·지연.
- **임시 baseline**: 최종 제품 구조 아님.

## 다음
- **YOLO/OpenImages 기반 구조로 전환 예정.** detector + 규칙으로 온디바이스 완결성/비용/실시간성 개선 목표. 그 시점에 Qwen-3B 는 보조/서버 확인용으로 재배치 검토.
