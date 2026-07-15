# real_validation_dataset_150_candidate

water / exercise / study 각 **50장, 총 150장 real-only** validation 후보셋(사용자 검수 전 candidate).

## 절대 원칙
1. **실제 사람이 촬영한 사진만.** AI/GPT/synthetic/generated/illustration/render/cartoon/icon/mockup **금지.**
2. 이미지마다 `source_url`/`source_site`/`license_or_usage_note` 정확히 기록(날조 금지).
3. 사용자 촬영본(real_zflip 등) 보존.
4. **`ground_truth` 는 UNLABELED 로 두고, 사용자가 직접 확정**(`suggested_ground_truth` 만 참고값).
5. 기존 generated/synthetic 평가결과는 이 셋의 판단에 쓰지 않음.

> ⚠️ 에이전트는 대량 이미지를 자동으로 "실제 사진 여부/내용"까지 보장할 수 없다. 그래서 인터넷 수집분은
> 모두 `needs_user_review=Y` 이며, **contact sheet + labeling page 로 사용자가 최종 검수**(사진 여부·내용·라벨·exclude)한다.

## 구조
```
real_validation_dataset_150_candidate/
  images/{water,exercise,study}/        # task 확정 후보 (파일명 water_001.jpg ...)
  images/_intake_unclassified/          # real_zflip 등 task 미상 실제 사진(사용자가 task 지정)
  excluded/                             # AI/illustration/무관 이미지 사용자가 이동(수동)
  contact_sheets/<task>_NN.png          # 시각 검수용 썸네일 격자
  labeling_page.html                    # 브라우저 검수/라벨링 도구
  manifest_unlabeled.json / .csv        # 단일 소스(아래 필드)
  collect_images.py  make_contact_sheets.py  build_labeling_page.py
```

## manifest 필드
`image_id, filepath, task, ground_truth(=UNLABELED), suggested_ground_truth, evidence_hint,
source_type(user_upload|internet_real), source_site, source_url, license_or_usage_note,
include_in_eval(=Y), notes, needs_user_review(=Y)`

## 현재 수집 현황(초기 candidate)
- user_upload 42 (water 업로드 8 + real_zflip intake 34) — **실제 촬영본**
- internet_real 38 (**Wikimedia Commons**, CC0/CC BY/PD, source_url+license 기록) — 검수 필요
- task별: water 22 / exercise 11 / study 13 / intake(UNLABELED) 34
- **부족분(→50): water +28, exercise +39, study +37 (+ intake 34 를 task 로 분류하면 충당에 기여)**

## 도구 사용법

### 1) 수집 (collect_images.py)
```bash
cd local_eval/real_validation_dataset_150_candidate
# 사용자 실촬영 편입(이미 실행됨)
python collect_images.py ingest-user
# Wikimedia Commons 후보 추가(오픈 API, 정확한 provenance) — 호출 사이 약간의 간격 권장(rate limit)
python collect_images.py from-commons --task water --query "glass of water" --count 8
python collect_images.py from-commons --task exercise --query "dumbbell" --count 8
python collect_images.py from-commons --task study --query "textbook" --count 8
# Pexels/Unsplash 등 직접 고른 사진: CSV(task,source_site,source_url,license_or_usage_note,...) 로
python collect_images.py from-csv --csv my_picks.csv
python collect_images.py report
```
> Pexels/Unsplash 는 API 키/수동 선택이 필요하므로 `from-csv` 로 사용자가 URL·라이선스를 기록해 추가한다.
> (에이전트 환경에서 키 없이 자동 수집하지 않음 — 라이선스/사진여부 보장 불가.)

### 2) 시각 검수 (contact sheet)
`contact_sheets/*.png` 를 열어 **AI/그림/렌더/무관 이미지**를 골라 `excluded/` 로 옮기고 labeling page 에서 include=N 처리.

### 3) 라벨링 (labeling_page.html)
브라우저(Chrome/Edge)로 열어 이미지별로:
- (intake) **task 지정**(water/exercise/study),
- **ground_truth 확정**(UNLABELED→PASS/FAIL/BORDERLINE),
- AI/illustration 의심 → **include=N(exclude)**, notes 기록,
- **CSV 저장**(File System Access 로 `manifest_unlabeled.csv` 덮어쓰기 또는 다운로드). localStorage 자동저장.
> 라벨링 후 `collect_images.py` 를 다시 돌리려면 json 을 갱신하거나 CSV→json 반영 절차를 따른다(현재 json 이 소스).

## 50/50/50 도달 방법(요약)
1. `_intake_unclassified` 34장을 labeling page 에서 task 분류 → 각 task 로 이동/편입.
2. `from-commons` 를 다양한 쿼리로 추가 실행(간격 두고) — 특히 exercise/study.
3. Pexels/Unsplash 에서 실제 사진을 골라 `from-csv` 로 URL·라이선스 기록해 추가.
4. contact sheet 로 사진 여부/내용 검수, 무관·AI 의심분 excluded.
5. labeling page 에서 ground_truth 확정. (기존 generated/synthetic 은 절대 편입 금지.)

## 수집 소스 메모
- **Wikimedia Commons**: 오픈 API, 파일별 descriptionurl(source_url)+라이선스 정확 기록. 단 키워드 검색이라
  무관/역사 문서/오브젝트가 섞일 수 있어 **반드시 시각 검수**.
- **Pexels/Unsplash**: 실사 품질 높으나 API 키 필요 → `from-csv` 경로 사용.
