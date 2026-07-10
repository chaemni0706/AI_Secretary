# advanced eval — smolvlm500_final

- evaluated rows: 171 / manifest 171
- borderline(primary): as_fail
- **contamination(synthetic/generated): 0**
- missing prediction: 0, duplicate: 0

## task-level (primary borderline mode)
| scope | n | FP | FN | acc | prec | rec | f1 | FPR |
|---|---|---|---|---|---|---|---|---|
| ALL | 171 | 9 | 61 | 0.5906 | 0.6897 | 0.2469 | 0.3636 | 0.1 |
| water | 57 | 6 | 15 | 0.6316 | 0.4545 | 0.25 | 0.3226 | 0.1622 |
| exercise | 60 | 0 | 29 | 0.5167 | 1.0 | 0.0938 | 0.1714 | 0.0 |
| study | 54 | 3 | 17 | 0.6296 | 0.8 | 0.4138 | 0.5455 | 0.12 |

## safety-first
- **FP_count: 9** (verified_on_fail: 8)
- fail_open_rate: 0.1
- FP_by_task: {'water': 6, 'study': 3}
- FP_by_rule_evidence: {'object:glass': 6, 'water_evidence:visible_liquid': 6, 'water_evidence:filled_container': 6, 'object:pen': 3, 'object:desk': 3, 'similar_group_cap': 3, 'study_evidence:handwritten_notes': 1, 'study_evidence:open_textbook': 3, 'object:monitor': 1, 'object:laptop': 1, 'study_evidence:code_editor': 1, 'study_evidence:highlighted_text': 1}
- borderline_as_fail FP=9 / borderline_excluded FP=8

## rule diagnostics
- result: {'rejected': 122, 'verified': 29, 'retake_required': 20}
- mandatory_passed_rate: 0.2573
- score_distribution: {'0-9': 127, '30-39': 15, '50-59': 17, '60-69': 11, '70-79': 1}

## evidence metrics
- {'available': False, 'note': 'manifest 에 expected_evidence 컬럼이 없어 evidence 정밀도/재현율 미산출'}

## latency
- {'model_load_time': {'avg': 6276.9, 'p50': 6276.9, 'p90': 6276.9, 'p95': 6276.9, 'max': 6276.9, 'n': 171}, 'inference_time': {'avg': 716.85, 'p50': 622.6, 'p90': 1016.1, 'p95': 1074.4, 'max': 1600.6, 'n': 171}, 'parse_time': {'avg': 0.0, 'p50': 0.0, 'p90': 0.0, 'p95': 0.0, 'max': 0.0, 'n': 171}, 'rule_engine_time': {'avg': 0.16, 'p50': 0.09, 'p90': 0.1, 'p95': 0.11, 'max': 4.7, 'n': 171}, 'total_time': {'avg': 717.02, 'p50': 622.7, 'p90': 1016.2, 'p95': 1074.5, 'max': 1600.7, 'n': 171}, 'latency_ms': {'avg': 717.02, 'p50': 622.7, 'p90': 1016.2, 'p95': 1074.5, 'max': 1600.7, 'n': 171}}

## 판정 관점
- FP=0 최우선. FP>0 이면 라벨오류/parser/prompt/rule threshold/모델 hallucination 순으로 분석.
- study FN 과다 → Qwen2.5-VL-3B-AWQ fallback 유지. VLM은 evidence만, 판정은 Rule Engine.