# SMOLVLM Android asset check

- model dir: `/data/models/SmolVLM-500M-Instruct`
- dir exists: True

## 파일 존재/크기

| file | exists | size(MB) |
|---|---|---|
| onnx/decoder_model_merged_q4.onnx | ✅ | 218.5 |
| onnx/vision_encoder_int8.onnx | ✅ | 94.4 |
| onnx/vision_encoder_q4.onnx | ✅ | 63.6 |
| onnx/embed_tokens_int8.onnx | ✅ | 45.1 |
| onnx/embed_tokens_q4f16.onnx | ✅ | 90.2 |
| tokenizer.json | ✅ | 3.4 |
| tokenizer_config.json | ✅ | 0.0 |
| vocab.json | ✅ | 0.8 |
| merges.txt | ✅ | 0.4 |
| config.json | ✅ | 0.0 |
| preprocessor_config.json | ✅ | 0.0 |
| processor_config.json | ✅ | 0.0 |

- tokenizer/config 합계: 4.6 MB
- ONNX Runtime Mobile(.aar, 추정): ~20.0 MB

## 조합별 합계(모델 3모듈 + tokenizer/config + 런타임)

| option | modules | model(MB) | +tok/cfg | +runtime(pkg 추정) |
|---|---|---|---|---|
| A (recommended) | decoder_q4+vision_int8+embed_int8 | 358.0 | 362.6 | **382.6** |
| B | decoder_q4+vision_q4+embed_int8 | 327.2 | 331.8 | **351.8** |
| C | decoder_q4+vision_int8+embed_q4f16 | 403.1 | 407.7 | **427.7** |

## 권장
- **A (recommended)** = decoder_q4 + vision_int8 + embed_int8 (vision int8 로 빈컵/물 시각 디테일 보존 → FP 안전). 패키지 추정 ≈ **382.6 MB**.
- 상태: ✅ 준비됨

## MISSING
- 없음(모든 후보 파일 존재)