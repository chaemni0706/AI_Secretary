# Study Verification Fixture Pack

## 구성
- `images/study_01.png` ~ `study_10.png`
- `fixtures/study_01.json` ~ `study_10.json`
- `study_ground_truth.jsonl`
- `CODEX_STUDY_RULE_PROMPT.txt`

## 기준
- study_01 ~ study_07: verified
- study_08 ~ study_10: rejected

## 주의
이 JSON은 GPT-4.1 mini의 실제 출력이 아니라 사람이 검수해 만든 VisionAnalysis 대체 Fixture입니다. Rule Engine, Schema, API 흐름을 비용 없이 검증하는 데 사용합니다.
