# SmolVLM2-2.2B-Instruct 실행 런북

목적: SmolVLM-500M 에서 부족했던 **study recall** 이 SmolVLM2-2.2B 에서 개선되는지 평가.

> ⚠️ **VSCode 안에서 실행하지 마세요.** 대형 모델(2.2B) 로딩/추론은 GPU 메모리를 크게 쓰며,
> 과거 VSCode 종료 문제가 있었습니다. **아래 명령은 tmux 또는 일반 Ubuntu 터미널에서** 실행하세요.
> Claude(에이전트)는 이 런북에서 코드/문서/경량 테스트까지만 준비했고, 대형 모델은 실행하지 않았습니다.

전제:
- 모델은 **시각 evidence 만** 추출합니다. PASS/FAIL 은 항상 **Rule Engine** 이 결정합니다.
- 채택 전제는 **FP=0 유지**. study recall 이 올라가도 FP 가 생기면 채택 근거가 약해집니다.
- 어댑터/프롬프트/파서는 SmolVLM-500M 과 동일하게 재사용하며, 로딩 경로/dtype 만 분리했습니다.

---

## 0. 세션 준비

```bash
tmux new -s smolvlm2_eval          # 세션 생성 (재접속: tmux attach -t smolvlm2_eval)
conda activate qwen-vlm
cd ~/AI_Secretary_FeatureJW_Qwen
```

환경 확인:

```bash
python -c "import torch, transformers; print('torch', torch.__version__, 'tf', transformers.__version__, 'cuda', torch.cuda.is_available())"
# SmolVLM processor 는 num2words 가 필요합니다. 없으면 설치:
python -c "import num2words" 2>/dev/null && echo "num2words OK" || pip install num2words
```

---

## 1. 모델 다운로드

```bash
mkdir -p /data/models/SmolVLM2-2.2B-Instruct

# huggingface_hub 최신 CLI (권장)
hf download HuggingFaceTB/SmolVLM2-2.2B-Instruct \
  --local-dir /data/models/SmolVLM2-2.2B-Instruct

# (구버전 CLI 라면)
# huggingface-cli download HuggingFaceTB/SmolVLM2-2.2B-Instruct \
#   --local-dir /data/models/SmolVLM2-2.2B-Instruct
```

## 2. 다운로드 확인

```bash
ls -lh /data/models/SmolVLM2-2.2B-Instruct
du -sh /data/models/SmolVLM2-2.2B-Instruct

# 필수 파일 확인 (config / processor / 가중치 shard)
ls /data/models/SmolVLM2-2.2B-Instruct | grep -E "config.json|processor_config.json|tokenizer|model.*safetensors|model.safetensors.index.json"
```

> 다운로드 후 실제 크기를 `model_candidates.yaml` 의 `model_size_mb` 에 반영하세요(현재 추정 4400).

## 3. Smoke test (모델 1회 로딩 + 이미지 1장)

```bash
python local_eval/ondevice_vlm_eval/smoke_test_smolvlm2.py \
  --image local_eval/study_verification_fixture_pack/images/study_02.png \
  --verification-type study
```

기대 출력:
- `[deps] torch=... transformers=... cuda_available=True`
- `[load] ... available=True load_time_ms=...`
- `[infer] latency = ... ms`
- `[infer] raw_output = '...'`
- `[infer] study_visual_evidence = [...]`

실패 시:
- `num2words is required` → `pip install num2words`
- `Input type ... FloatTensor ... weight ... BFloat16` → 어댑터 `_move_inputs` dtype 캐스팅 확인(이미 반영됨)
- CUDA OOM → 다른 GPU 프로세스 종료 후 재시도(`nvidia-smi`)

## 4. study no-simulate 평가 (실제 추론)

```bash
python local_eval/ondevice_vlm_eval/run_ondevice_eval.py \
  --models smolvlm2_2b \
  --verification-types study \
  --no-simulate
```

## 5. 전체 water/exercise/study 평가

> study 가 개선(FP=0 유지 + recall>0.286)일 때만 전체를 돌리는 것을 권장.

```bash
python local_eval/ondevice_vlm_eval/run_ondevice_eval.py \
  --models smolvlm2_2b \
  --verification-types water,exercise,study \
  --no-simulate
```

## 6. 결과 확인

```bash
RUN_DIR=$(ls -td local_eval/ondevice_vlm_eval/outputs/runs/*smolvlm2* | head -1)
echo "$RUN_DIR"
cat "$RUN_DIR/metrics_summary.csv"
cat "$RUN_DIR/error_cases.csv"      # 오분류 케이스 (FP/FN 확인)
cat "$RUN_DIR/run_meta.json" 2>/dev/null | head -40
```

FP 확인 (가장 중요):

```bash
# metrics_summary.csv 에서 fp 컬럼이 0 인지 확인. 0 이 아니면 채택 근거 약화.
```

## 7. 판정 기준 (study)

| 결과 | 조건 |
| --- | --- |
| ✅ 개선(우수) | FP=0 유지 AND recall ≥ 0.6 AND accuracy ≥ 0.7 |
| 🟡 개선(부분) | FP=0 유지 AND recall > 0.286 AND accuracy > 0.5 |
| ❌ 미개선 | FP>0, 또는 recall ≤ 0.286 |

- study 가 🟡 이상이면 5번(전체 평가) 진행 → `MODEL_SELECTION.md` 표 갱신.
- study 가 ❌ 이면 전체 평가 없이 미채택 기록 후 다음 대안 검토.

## 8. 결과를 MODEL_SELECTION.md 에 반영

`local_eval/ondevice_vlm_eval/MODEL_SELECTION.md` 의 SmolVLM2-2.2B 행(현재 "미측정")을
metrics_summary.csv 값으로 채웁니다.

## 9. 실패 시 대응 / 다음 대안

- **로딩 실패(num2words/transformers 버전)**: 위 hint 대로 처리. 그래도 안되면 transformers 버전 기록 후 보류.
- **study 미개선(recall ≤ 0.286)**: study 는 소형 VLM 공통 난제. 대안 순서:
  1. study 프롬프트 튜닝 + `--reparse`(재추론 없이 파서만 재적용)
  2. Qwen2.5-VL-3B-AWQ(anchor)로 study 상한 확인
  3. study 만 상위 모델/규칙 보강, water/exercise 는 SmolVLM-500M 유지(하이브리드)
- **FP 발생**: 어떤 이미지에서 FP 인지 error_cases.csv 로 확인 → study 파서의 과확장 문구 축소.

---

### 참고: 재추론 없이 파서만 재적용 (`--from-dump --reparse`)

study 파서를 튜닝할 때 모델을 매번 다시 돌리지 않으려면, 먼저 추론 결과를 **dump(JSONL)** 로
한 번만 뽑아두고(`infer_dump.py`), 이후에는 파서만 재적용(`--reparse`)합니다.
`--from-dump` 은 `raw_text`/`verification_type` 필드를 가진 dump JSONL 을 입력으로 받습니다.

1) 추론 → dump (모델 1회 로딩, GPU 사용):

```bash
python local_eval/ondevice_vlm_eval/infer_dump.py \
  --models smolvlm2_2b --verification-types study \
  --out local_eval/ondevice_vlm_eval/outputs/dumps/smolvlm2_study.jsonl
```

2) 파서만 재적용 (재추론 없음, GPU 불필요):

```bash
python local_eval/ondevice_vlm_eval/run_ondevice_eval.py \
  --from-dump local_eval/ondevice_vlm_eval/outputs/dumps/smolvlm2_study.jsonl \
  --reparse
```

3) 결과 확인은 위 6번과 동일(생성된 run 폴더의 metrics_summary.csv / error_cases.csv).
