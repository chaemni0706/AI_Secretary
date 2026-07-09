# MiniCPM-V 2.0 (2.8B) 실행 런북

목적: SmolVLM-500M보다 높은 semantic(특히 study)을 가지면서 Z Flip3 온디바이스 가능성이 있는지 검증.
평가 기준: **FP=0 유지 + study 개선 + 온디바이스(GGUF int4) 실행성.**

> ⚠️ VSCode 금지. tmux/외부 터미널(qwen-vlm env). 에이전트는 어댑터/후보/스모크/문서/경량테스트만 준비.
> 모델은 evidence 만 추출, 최종 판정은 Rule Engine, 프롬프트/파서는 SmolVLM 과 동일 재사용.

---

## 1. 모델/양자화/크기 확인 (보고 항목 1)
```bash
tmux new -s minicpmv2 && conda activate qwen-vlm && cd ~/AI_Secretary_FeatureJW_Qwen
python - <<'PY'
from huggingface_hub import model_info
for m in ["openbmb/MiniCPM-V-2","openbmb/MiniCPM-V-2-gguf"]:
    try: print(m, "OK")
    except Exception as e: print(m, "MISSING", e)
PY
pip install -U transformers accelerate            # trust_remote_code 로딩
# int4 GGUF 사용 시 llama.cpp 별도(온디바이스 경로), transformers 평가는 fp16 원본 사용
```

## 2. 다운로드 + 실제 크기
```bash
mkdir -p /data/models/MiniCPM-V-2
hf download openbmb/MiniCPM-V-2 --local-dir /data/models/MiniCPM-V-2
du -sh /data/models/MiniCPM-V-2      # ← 실측 크기 → model_candidates.yaml model_size_mb(현재 1900 추정) 갱신
ls -lh /data/models/MiniCPM-V-2 | grep -E "safetensors|config|tokenizer"
```

## 3. Smoke test (load time / latency / raw / evidence)
```bash
python local_eval/ondevice_vlm_eval/smoke_test_minicpm_v2.py --verification-type study
```
- `.chat()` 시그니처가 2.0과 다르면 traceback 확인 후
  `adapters/minicpm_v_adapter.py` 의 `MiniCPMV2Adapter._infer` 를 실제 API 로 조정.

## 4. 평가 (study 먼저 → 성공 시 전체)
```bash
# study 먼저
python local_eval/ondevice_vlm_eval/run_ondevice_eval.py \
  --models minicpm_v2 --verification-types study --no-simulate

# study 개선(FP=0 유지 + recall↑) 확인되면 전체
python local_eval/ondevice_vlm_eval/run_ondevice_eval.py \
  --models minicpm_v2 --verification-types water,exercise,study --no-simulate
```
저장(기존 구조): `outputs/runs/<ts>_minicpm_v2_*/` → metrics_summary.csv/json, confusion_matrix.csv,
latency_summary.csv, error_cases.csv, per_image_report.csv.

## 5. 결과 확인 + memory 측정
```bash
RUN=$(ls -td local_eval/ondevice_vlm_eval/outputs/runs/*minicpm_v2* | head -1); echo "$RUN"
cat "$RUN"/metrics_summary.csv; cat "$RUN"/latency_summary.csv; cat "$RUN"/error_cases.csv

python - <<'PY'
import torch,sys; sys.path.insert(0,"local_eval/ondevice_vlm_eval")
from adapters.minicpm_v_adapter import MiniCPMV2Adapter
from pathlib import Path
a=MiniCPMV2Adapter()
a.analyze(Path("local_eval/study_verification_fixture_pack/images/study_02.png"),"study",{"verification_type":"study"})
print("peak GPU MB:", round(torch.cuda.max_memory_allocated()/1e6,1))
PY
```

## 6. 결과를 MODEL_SELECTION.md 에 반영
`MODEL_SELECTION.md` 의 MiniCPM-V-2.0 행(현재 미측정)을 채우고
SmolVLM-500M / Qwen2.5-VL-3B-AWQ 와 비교(개선점/손실/온디바이스 가능성/채택여부).

## 7. 온디바이스(Z Flip3) 관점
- **GGUF int4(`openbmb/MiniCPM-V-2-gguf`) → llama.cpp** 경로가 이 후보의 핵심 강점(Android 현실성).
  transformers 평가로 정확도/지연을 먼저 확정하고, 채택 가치가 있으면 GGUF int4를 llama.cpp(Android)로 별도 검증.
- fp16 원본은 ~5.5GB로 Z Flip3 상주 부담 → int4(~1.9GB 추정)로만 온디바이스 현실적.
- 실패 시: OOM → int4/GGUF 경로, chat API 불일치 → `_infer` 조정.
