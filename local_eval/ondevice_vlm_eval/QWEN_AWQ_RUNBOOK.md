# Qwen2.5-VL-3B-AWQ 실행 런북

목적: 소형 VLM(SmolVLM-500M/MobileVLM-1.7B/SmolVLM2-2.2B)이 모두 **study recall 0.286** 에 머문
상황에서, 상위 모델 **Qwen2.5-VL-3B-AWQ** 로 study 가 개선되는지(상한/anchor) 확인.

> **Qwen-AWQ 는 온디바이스 1순위 후보가 아닙니다.** 성능 anchor / 서버 fallback / study 한계 분석용.
> 온디바이스 1순위는 SmolVLM-500M(전 타입 FP=0, ~600MB) 로 유지됩니다.

> ⚠️ **VSCode 안에서 실행하지 마세요.** 3B(AWQ) 로딩/추론은 GPU 메모리를 크게 쓰며, 과거 VSCode
> 종료 문제가 있었습니다. **아래 명령은 tmux 또는 일반 Ubuntu 터미널에서** 실행하세요.
> Claude(에이전트)는 코드/문서/경량 테스트까지만 준비했고, 대형 모델은 실행하지 않았습니다.

전제:
- 모델은 **시각 evidence 만** 추출합니다. PASS/FAIL 은 항상 **Rule Engine** 이 결정합니다.
- 프롬프트/파서는 SmolVLM 과 **동일하게 재사용**(공정 비교 — 차이는 모델에서만 발생).
- **FP=0 유지가 우선.** study recall 이 올라가도 FP 가 생기면 채택 근거가 약해집니다.

---

## 0. 세션 준비

```bash
tmux new -s qwen_awq_eval          # 재접속: tmux attach -t qwen_awq_eval
conda activate qwen-vlm
cd ~/AI_Secretary_FeatureJW_Qwen
```

의존성 확인:

```bash
python -c "import torch, transformers; print('torch', torch.__version__, 'tf', transformers.__version__, 'cuda', torch.cuda.is_available())"
python -c "import qwen_vl_utils; print('qwen_vl_utils OK')" 2>/dev/null || pip install qwen-vl-utils
python -c "import awq; print('autoawq OK')" 2>/dev/null || pip install autoawq   # AWQ 4bit 로딩에 필요
```

---

## 1. 모델 다운로드

```bash
mkdir -p /data/models/Qwen2.5-VL-3B-Instruct-AWQ

hf download Qwen/Qwen2.5-VL-3B-Instruct-AWQ \
  --local-dir /data/models/Qwen2.5-VL-3B-Instruct-AWQ

# (구버전 CLI)
# huggingface-cli download Qwen/Qwen2.5-VL-3B-Instruct-AWQ \
#   --local-dir /data/models/Qwen2.5-VL-3B-Instruct-AWQ
```

## 2. 다운로드 확인

```bash
ls -lh /data/models/Qwen2.5-VL-3B-Instruct-AWQ
du -sh /data/models/Qwen2.5-VL-3B-Instruct-AWQ
ls /data/models/Qwen2.5-VL-3B-Instruct-AWQ | grep -E "config.json|preprocessor_config.json|tokenizer|model.*safetensors|index.json"
```

> 다운로드 후 실제 크기를 `model_candidates.yaml` 의 `model_size_mb`(현재 추정 2300)에 반영하세요.

## 3. Smoke test (모델 1회 로딩 + 이미지 1장)

```bash
python local_eval/ondevice_vlm_eval/smoke_test_qwen_awq.py \
  --image local_eval/study_verification_fixture_pack/images/study_02.png \
  --verification-type study
```

기대 출력: `[deps] ... cuda_available=True`, `[load] available=True load_time_ms=...`,
`[infer] latency=...`, `[infer] raw_output='...'`, `[infer] study_visual_evidence=[...]`.

실패 시 힌트:
- `No module named 'awq'` / AWQ 로딩 실패 → `pip install autoawq`
- `No module named 'qwen_vl_utils'` → `pip install qwen-vl-utils`
- transformers 버전 낮음 → Qwen2.5-VL 지원 버전(>=4.49) 확인
- CUDA OOM → `nvidia-smi` 로 다른 프로세스 정리 후 재시도

## 4. study no-simulate 평가 (먼저 수행)

```bash
python local_eval/ondevice_vlm_eval/run_ondevice_eval.py \
  --models qwen_awq \
  --verification-types study \
  --no-simulate
```

## 5. 전체 water/exercise/study 평가

> study 결과 확인 후(개선 여부와 무관하게 anchor 목적이면 전체를 돌려도 됨) 실행.

```bash
python local_eval/ondevice_vlm_eval/run_ondevice_eval.py \
  --models qwen_awq \
  --verification-types water,exercise,study \
  --no-simulate
```

## 6. 결과 확인

```bash
RUN_DIR=$(ls -td local_eval/ondevice_vlm_eval/outputs/runs/*qwen_awq* | head -1)
echo "$RUN_DIR"
cat "$RUN_DIR/metrics_summary.csv"
cat "$RUN_DIR/error_cases.csv"      # FP/FN 케이스 확인 (FP 최우선)
```

## 7. 판정 관점 (anchor)

- **study recall > 0.286** 이면 "소형 VLM 의 한계"가 모델 용량 때문임을 시사 → study 개선 방향(상위 모델/서버 fallback/하이브리드) 근거.
- **study recall ≈ 0.286 그대로**면 문제는 모델 용량이 아니라 **파서/프롬프트/데이터/Rule Engine 임계값** 쪽 → 그 트랙으로 개선.
- **FP** 는 전 타입에서 확인. anchor 라도 FP 가 크면 서버 fallback 시에도 규칙 보정 필요.
- latency/size 는 온디바이스가 아닌 **서버 fallback** 기준으로 해석(3B AWQ 는 Z Flip3 1순위 아님).

## 8. 결과를 MODEL_SELECTION.md 에 반영

`MODEL_SELECTION.md` 의 Qwen-AWQ 행(현재 "미측정")을 metrics_summary.csv 값으로 채웁니다.

## 9. 실패 시 대응 / 다음 단계

- **로딩 실패(autoawq/qwen_vl_utils/transformers)**: 위 힌트대로 설치/버전 확인 후 재시도.
- **study 미개선(recall ≈ 0.286)**: study 개선 트랙으로 전환 —
  1. study 이미지 **OCR 텍스트 신호** 를 evidence 로 추가
  2. study 전용 프롬프트/파서 튜닝을 `infer_dump.py` + `--reparse` 로 재추론 없이 반복
  3. Rule Engine study 임계값 재검토(값 자체는 backend 소관 — 수정하지 말고 관찰/기록만)
- **study 개선됨**: water/exercise=SmolVLM-500M(온디바이스), study=Qwen(서버 fallback) **하이브리드** 설계 검토.

---

### 참고: 재추론 없이 파서만 재적용 (`--from-dump --reparse`)

1) 추론 → dump (모델 1회 로딩, GPU 사용):

```bash
python local_eval/ondevice_vlm_eval/infer_dump.py \
  --models qwen_awq --verification-types study \
  --out local_eval/ondevice_vlm_eval/outputs/dumps/qwen_awq_study.jsonl
```

2) 파서만 재적용 (재추론 없음, GPU 불필요):

```bash
python local_eval/ondevice_vlm_eval/run_ondevice_eval.py \
  --from-dump local_eval/ondevice_vlm_eval/outputs/dumps/qwen_awq_study.jsonl \
  --reparse
```
