# Qwen2-VL-2B-AWQ 실행 런북

목적: SmolVLM-500M(600MB, study 약함)과 Qwen2.5-VL-3B-AWQ(2.3GB, study 최고) 사이의 **2B 절충 후보**를
동일 벤치마크로 평가하고, **"정확도 대비 온디바이스 가능성"** 기준으로 SmolVLM 대체 가능성을 판단.

> ⚠️ **VSCode 안에서 실행 금지.** 2B(AWQ) 로딩/추론은 GPU 메모리를 크게 쓴다. tmux/일반 터미널에서 실행.
> 에이전트는 어댑터/후보/스모크/문서/경량테스트까지만 준비했고, 대형 모델은 실행하지 않았다.

전제: 모델은 시각 evidence 만 추출. 최종 판정은 Rule Engine. 프롬프트/파서는 SmolVLM 과 동일 재사용.

---

## 0. 세션 준비
```bash
tmux new -s qwen2vl_2b && conda activate qwen-vlm && cd ~/AI_Secretary_FeatureJW_Qwen
python -c "import torch,transformers;print('torch',torch.__version__,'tf',transformers.__version__,'cuda',torch.cuda.is_available())"
python -c "from transformers import Qwen2VLForConditionalGeneration;print('Qwen2VL OK')"   # 없으면 transformers>=4.45 업그레이드
python -c "import qwen_vl_utils" 2>/dev/null || pip install qwen-vl-utils
python -c "import awq" 2>/dev/null || pip install autoawq
```

## 1. 후보 존재/양자화 확인 + 다운로드
```bash
# 존재 확인(메타만): 200 이면 존재
python - <<'PY'
from huggingface_hub import model_info
for m in ["Qwen/Qwen2-VL-2B-Instruct","Qwen/Qwen2-VL-2B-Instruct-AWQ"]:
    try: print(m, "OK", model_info(m).siblings[0].rfilename)
    except Exception as e: print(m, "MISSING", e)
PY

mkdir -p /data/models/Qwen2-VL-2B-Instruct-AWQ
hf download Qwen/Qwen2-VL-2B-Instruct-AWQ --local-dir /data/models/Qwen2-VL-2B-Instruct-AWQ
```

## 2. 다운로드 크기 확인 (보고 항목 2)
```bash
du -sh /data/models/Qwen2-VL-2B-Instruct-AWQ
ls -lh /data/models/Qwen2-VL-2B-Instruct-AWQ | grep -E "safetensors|config|preprocessor|index"
# 실제 크기를 model_candidates.yaml 의 model_size_mb(추정 1800)에 반영
```

## 3. Smoke test (로딩 + 1장 추론, latency)
```bash
python local_eval/ondevice_vlm_eval/smoke_test_qwen2vl_2b.py \
  --image local_eval/study_verification_fixture_pack/images/study_02.png --verification-type study
```

## 4. 동일 벤치마크 (water/exercise/study)
```bash
python local_eval/ondevice_vlm_eval/run_ondevice_eval.py \
  --models qwen2vl_2b --verification-types water,exercise,study --no-simulate
```
산출물(기존 metrics 구조 유지): `outputs/runs/<ts>_qwen2vl_2b_*/`
- metrics_summary.csv/json, latency_summary.csv, confusion_matrix.csv, error_cases.csv, per_image_report.csv

## 5. 결과 확인 + 3-모델 비교
```bash
RUN=$(ls -td local_eval/ondevice_vlm_eval/outputs/runs/*qwen2vl_2b* | head -1); echo "$RUN"
cat "$RUN/metrics_summary.csv"; cat "$RUN/latency_summary.csv"; cat "$RUN/error_cases.csv"
```
SmolVLM-500M / Qwen2.5-VL-3B-AWQ / Qwen2-VL-2B 를 accuracy/precision/recall/F1/FP/FN/latency/size 로 비교해
`MODEL_SELECTION.md` 의 Qwen2-VL-2B 행을 채운다.

## 6. 온디바이스 가능성 측정 (보고 항목 9)
```bash
# inference memory (peak): 추론 직후
python - <<'PY'
import torch,sys; sys.path.insert(0,"local_eval/ondevice_vlm_eval")
from adapters.qwen_awq_adapter import Qwen2VL2BAdapter
a=Qwen2VL2BAdapter(); 
from pathlib import Path
a.analyze(Path("local_eval/study_verification_fixture_pack/images/study_02.png"),"study",{"verification_type":"study"})
print("peak GPU MB:", round(torch.cuda.max_memory_allocated()/1e6,1))
PY
nvidia-smi --query-gpu=memory.used --format=csv
```

## 7. 실패 시 대응
- `Qwen2VLForConditionalGeneration` 없음 → `pip install -U transformers` (>=4.45)
- AWQ 로딩 실패 → `pip install autoawq`, dtype 은 어댑터가 fp16 고정
- OOM → 다른 GPU 프로세스 정리(`nvidia-smi`)
- AWQ 체크포인트가 HF 에 없으면 → 비양자화 `Qwen/Qwen2-VL-2B-Instruct`(fp16 ~4.4GB) 로 정확도 상한만 먼저 확인 후 양자화(MLC/llama.cpp int4) 별도 검토

## 온디바이스(Z Flip3) 관점 메모
- 2B AWQ(int4) 디스크 ~1.8GB < 3B AWQ 2.3GB → 메모리/전송 유리, 그러나 SmolVLM 600MB 보다는 큼.
- ONNX: Qwen2-VL 은 동적 비전 토큰/rotary 로 ONNX export 난이도 높음(부분 지원).
- MLC-LLM / llama.cpp: Qwen2-VL 계열 int4 변환 커뮤니티 지원 있음(비전 타워 포함 여부/속도는 실측 필요).
- 판단 기준: **정확도(특히 study recall, FP=0) 대비 온디바이스 실행성**. 2B 가 study 를 충분히 올리고
  Z Flip3 에서 실행 가능(int4)하면 채택 후보, 아니면 SmolVLM 유지 + 3B 서버 fallback.
