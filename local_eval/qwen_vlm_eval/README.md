# Qwen VLM Study Verification Evaluation

## Purpose

GPT-4.1 mini 기반 VLM 파트를 로컬 오픈소스 VLM인 Qwen2.5-VL-3B-Instruct로 대체할 수 있는지 검증했다.

## Architecture

Image
→ Qwen VLM evidence extraction
→ VisionAnalysis-compatible normalization
→ YAML Rule Engine
→ verified / retake_required / rejected

VLM은 최종 판정을 하지 않고, 사진에서 보이는 증거만 추출한다.
최종 인증 여부는 Rule Engine이 결정한다.

## Environment

- GPU: NVIDIA RTX A5000
- Model: Qwen/Qwen2.5-VL-3B-Instruct
- Framework: PyTorch + Transformers
- Branch: Feature_JW

## Study Policy

공부 인증은 기기 존재가 아니라 학습 콘텐츠를 기준으로 판단한다.

- 노트북, 태블릿, 모니터, 휴대폰만 보이면 인증하지 않는다.
- 교재, 문제집, 필기, 강의 화면, PDF, 코드 에디터 등 학습 콘텐츠가 보여야 한다.
- 게임, SNS, 쇼핑, 오락 영상, 비학습 화면은 우선 거절한다.
- 화면이 불확실하면 재촬영 대상으로 본다.

핵심 원칙:

Devices are supporting evidence.
Study content is core evidence.
Non-study screen is priority rejection evidence.

## Final Study Fixture Result

Expected:
- study_01 ~ study_07: verified
- study_08 ~ study_10: rejected

Final result:

correct = 10 / 10
false positive = 0

## Final Report

image,expected,actual,ok,score,mandatory_passed,study_visual_evidence
study_01,verified,verified,True,70,True,"open_textbook,open_workbook,handwritten_notes"
study_02,verified,verified,True,70,True,"open_textbook,open_workbook,handwritten_notes"
study_03,verified,verified,True,90,True,"open_textbook,open_workbook,handwritten_notes,problem_solving_material"
study_04,verified,verified,True,100,True,"open_textbook,open_workbook,handwritten_notes,lecture_video,educational_document,code_editor,study_timer,study_content_on_screen"
study_05,verified,verified,True,100,True,"open_textbook,open_workbook,handwritten_notes,highlighted_text,problem_solving_material,study_content_on_screen,lecture_video,educational_document"
study_06,verified,verified,True,50,True,study_content_on_screen
study_07,verified,verified,True,85,True,"open_workbook,study_timer,lecture_video"
study_08,rejected,rejected,True,50,True,"study_content_on_screen,non_study_screen,uncertain_screen_content"
study_09,rejected,rejected,True,0,False,"gaming_content,entertainment_video,social_media,shopping_content,non_study_screen,uncertain_screen_content"
study_10,rejected,rejected,True,0,False,gaming_content

## Conclusion

Qwen2.5-VL-3B는 공부 인증 흐름에서 GPT-4.1 mini VLM 파트를 대체할 수 있는 후보로 확인됐다.

다만 최종 판정을 Qwen이 직접 하면 안 된다.
Qwen은 시각 증거만 추출하고, 최종 판정은 Rule Engine이 수행해야 한다.

다음 검증 대상:
- water verification
- exercise verification
- larger real-world photo set
- latency / VRAM measurement
- GPT-4.1 mini vs Qwen comparison
