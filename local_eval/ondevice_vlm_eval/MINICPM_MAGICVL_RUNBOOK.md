# MiniCPM-V 2.6 / MagicVL-2B 실행 런북

목적: SmolVLM-500M 한계 개선 + Z Flip3 온디바이스 가능성 관점에서 두 후보를 동일 벤치마크로 평가.
평가 기준: **정확도(특히 FP=0 유지, study recall) 대비 온디바이스 가능성.**

> ⚠️ VSCode 금지. tmux/외부 터미널(qwen-vlm env)에서 실행. 에이전트는 어댑터/후보/스모크/문서/경량테스트만 준비.
> 모델은 시각 evidence 만 추출, 최종 판정은 Rule Engine, 프롬프트/파서는 SmolVLM 과 동일 재사용.

---

## 0. 모델 정보 조사 (보고 항목 1)

| 항목 | MiniCPM-V 2.6 | MagicVL-2B |
| --- | --- | --- |
| 공식 model id | `openbmb/MiniCPM-V-2_6` (int4: `-int4`, gguf: `-gguf`) | **UNVERIFIED** — 확인 필요 |
| parameter | ~8B (Qwen2-7B + SigLIP) | 2B (표기 기준) |
| license | MiniCPM Model License(연구 자유/상업 등록) — 다운로드 시 재확인 | **UNVERIFIED** |
| quantized ckpt | int4(bnb), GGUF int4 공식 존재 | **UNVERIFIED** |
| 추론 API | `model.chat(image=None, msgs=[...], tokenizer=...)` (trust_remote_code) | 가정: .chat() 류 — **검증 필요** |
| Android/MLC/ONNX | llama.cpp GGUF 공식 → int4 온디바이스 경로 있음(8B라 무거움). ONNX 난이도 높음 | **UNVERIFIED** |

### 존재/정확 id 확인
```bash
python - <<'PY'
from huggingface_hub import model_info, list_models
for m in ["openbmb/MiniCPM-V-2_6","openbmb/MiniCPM-V-2_6-int4","openbmb/MiniCPM-V-2_6-gguf"]:
    try: print(m,"OK")
    except Exception as e: print(m,"MISSING",e)
print("MagicVL search:", [x.id for x in list_models(search="MagicVL", limit=20)])
PY
```
→ MagicVL 정확 id 확정 후 `model_candidates.yaml`(magicvl_2b.model_id)와 `magicvl_adapter.py` 를 갱신.

---

## 1. 의존성
```bash
tmux new -s minicpm && conda activate qwen-vlm && cd ~/AI_Secretary_FeatureJW_Qwen
python -c "import torch,transformers;print(torch.__version__,transformers.__version__,torch.cuda.is_available())"
pip install -U transformers accelerate   # trust_remote_code 로딩
# int4 사용 시: pip install bitsandbytes
```

## 2. 다운로드
```bash
# MiniCPM-V 2.6 (bf16 ~16GB) 또는 int4(~6GB) 택1
mkdir -p /data/models/MiniCPM-V-2_6
hf download openbmb/MiniCPM-V-2_6 --local-dir /data/models/MiniCPM-V-2_6
# int4 대안:
# hf download openbmb/MiniCPM-V-2_6-int4 --local-dir /data/models/MiniCPM-V-2_6-int4
du -sh /data/models/MiniCPM-V-2_6   # 실측 크기 → yaml model_size_mb 갱신

# MagicVL: 정확 id 확정 후
# hf download <org>/MagicVL-2B --local-dir /data/models/MagicVL-2B
```

## 3. Smoke test
```bash
python local_eval/ondevice_vlm_eval/smoke_test_minicpm_v.py --verification-type study
# MagicVL (검증된 id 지정):
python local_eval/ondevice_vlm_eval/smoke_test_magicvl.py --model-id <org>/MagicVL-2B --verification-type study
```

## 4. 동일 벤치마크 (water/exercise/study)
```bash
python local_eval/ondevice_vlm_eval/run_ondevice_eval.py --models minicpm_v \
  --verification-types water,exercise,study --no-simulate
# MagicVL: 어댑터 검증/조정 후
python local_eval/ondevice_vlm_eval/run_ondevice_eval.py --models magicvl_2b \
  --verification-types water,exercise,study --no-simulate
```
저장(기존 구조): `outputs/runs/<ts>_<adapter>_*/` → metrics_summary.csv/json, confusion_matrix.csv,
latency_summary.csv, error_cases.csv, per_image_report.csv.

## 5. 결과 확인 + 비교
```bash
RUN=$(ls -td local_eval/ondevice_vlm_eval/outputs/runs/*minicpm_v* | head -1); echo "$RUN"
cat "$RUN"/metrics_summary.csv; cat "$RUN"/latency_summary.csv; cat "$RUN"/error_cases.csv
```
`MODEL_SELECTION.md` 의 해당 행을 채우고 SmolVLM-500M / Qwen2.5-VL-3B-AWQ / Qwen2-VL-2B-AWQ 와 비교.

특히 확인(보고 항목 3):
- **FP=0 유지 여부** (전 타입)
- water: 투명 병(transparent bottle) 인식 — 빈 병은 FAIL 유지
- study: open textbook / handwritten notes / screen learning 추출
- exercise: equipment/environment 근거

## 6. 온디바이스 가능성 측정 (보고 항목 4)
```bash
python - <<'PY'
import torch,sys; sys.path.insert(0,"local_eval/ondevice_vlm_eval")
from adapters.minicpm_v_adapter import MiniCPMVAdapter
from pathlib import Path
a=MiniCPMVAdapter()
a.analyze(Path("local_eval/study_verification_fixture_pack/images/study_02.png"),"study",{"verification_type":"study"})
print("peak GPU MB:", round(torch.cuda.max_memory_allocated()/1e6,1))
PY
nvidia-smi --query-gpu=memory.used --format=csv
```
확인: 모델 파일 크기 / inference peak memory / latency / Android runtime(llama.cpp GGUF·MLC) / ONNX 가능 여부.

## 7. 실패 시 대응
- MiniCPM `.chat()` API 오류 → 설치된 transformers/remote code 버전 확인, `sampling=False`/`max_new_tokens` 인자 호환 확인(버전별 상이).
- OOM(8B) → int4 체크포인트(`openbmb/MiniCPM-V-2_6-int4`)로 model_id 지정.
- MagicVL: 존재/ API 미확정이면 벤치마크 보류하고 §0 존재확인부터. .chat() 없으면 `magicvl_adapter._infer` 를 실제 API 로 수정.
