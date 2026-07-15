# GAP_PLAN — 부족분 타겟 수집 계획

목표: task당 50 (가이드 PASS25/FAIL20/BORDERLINE5). 실제 사진만, 수집 후 contact sheet/labeling 검수 필수.

현재 included_by_task: {'water': 57, 'exercise': 60, 'study': 54}  (excluded 66, intake 미분류 0)

## water
- 현재 include=57, 라벨 {'PASS': 20, 'FAIL': 31, 'BORDERLINE': 6}, task내 UNLABELED 0
- **부족: 총 0 (PASS 5 / FAIL 0 / BORDERLINE 0)**
- PASS 수집 쿼리(Commons) 예: `glass of water`, `pouring water into glass`, `person drinking water`, `water bottle transparent`, `pitcher of water`
- FAIL 수집 쿼리(Commons) 예: `cup of coffee`, `glass of juice`, `cola glass`, `cup of tea`, `empty glass`, `empty bottle`, `milk glass`, `smoothie glass`
- 실행: `python collect_images.py from-commons --task water --query "<위 쿼리>" --count 8` (호출 간 2초 간격) / 또는 Pexels·Unsplash 선별 후 `from-csv`.

## exercise
- 현재 include=60, 라벨 {'PASS': 32, 'FAIL': 22, 'BORDERLINE': 6}, task내 UNLABELED 0
- **부족: 총 0 (PASS 0 / FAIL 0 / BORDERLINE 0)**
- PASS 수집 쿼리(Commons) 예: `dumbbell`, `barbell`, `kettlebell`, `treadmill`, `person doing squat`, `yoga mat exercise`, `gym interior`, `weight machine`
- FAIL 수집 쿼리(Commons) 예: `office desk laptop`, `running shoes`, `empty room`, `person sitting chair`, `bedroom interior`, `water bottle only`
- 실행: `python collect_images.py from-commons --task exercise --query "<위 쿼리>" --count 8` (호출 간 2초 간격) / 또는 Pexels·Unsplash 선별 후 `from-csv`.

## study
- 현재 include=54, 라벨 {'PASS': 29, 'FAIL': 23, 'BORDERLINE': 2}, task내 UNLABELED 0
- **부족: 총 0 (PASS 0 / FAIL 0 / BORDERLINE 3)**
- PASS 수집 쿼리(Commons) 예: `open textbook`, `handwriting notebook`, `student writing`, `worksheet math`, `coding screen`, `lecture slides`, `highlighted notes`
- FAIL 수집 쿼리(Commons) 예: `video game screen`, `social media feed`, `youtube screen`, `movie screen`, `online shopping website`, `empty desk`
- 실행: `python collect_images.py from-commons --task study --query "<위 쿼리>" --count 8` (호출 간 2초 간격) / 또는 Pexels·Unsplash 선별 후 `from-csv`.

## 공통 절차
1) intake(UNLABELED) 를 labeling page 에서 task 지정(부족분 우선 충당).
2) 위 부족 유형(PASS/FAIL)만 겨냥해 수집.
3) contact sheet 재생성 → AI/illustration/무관 include=N(exclude_reason).
4) labeling page 에서 ground_truth 확정 후 이 스크립트 재실행.