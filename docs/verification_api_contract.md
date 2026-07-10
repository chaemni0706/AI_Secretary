# 통합 인증(Verification) API 계약서

프론트엔드 연동 및 Swagger 시연용 request/response 계약. 모든 응답은 공통 envelope을 따른다:

```json
{ "success": true, "message": "...", "data": { } }
```

인증 타입은 두 범주로 나뉜다 (판정 책임 분리):

- **VLM 기반 시각 인증**: `water` / `exercise` / `study` → 이미지 → VisionAnalyzer → Rule Engine
- **세션/시간 기반 인증**: `wakeup` → 서버 수신 시각 · 세션 · 이미지 SHA256 중복 · 재촬영 횟수 (VLM/Rule Engine 미사용)

Base URL: `/api/v1`. 판정값 `result`: `verified` | `rejected` | `retake_required`.

---

## 1. 기존 endpoint와 새 endpoint의 관계

| 구분 | 기존(유지) | 새 통합 경로 | 관계 |
|------|-----------|-------------|------|
| 이미지 인증 | `POST /api/v1/image-verifications` (form `verification_type`) | `POST /api/v1/verification/image/{verification_type}` | 동일 pipeline(`verify_image_upload`). 새 경로는 타입을 URL path로 받음 |
| wakeup 세션 발급 | `POST /api/v1/image-verifications/wakeup/sessions` | `POST /api/v1/verification/wakeup/session` | 동일 `wakeup_session_store.create_session` |
| wakeup 제출 | `POST /api/v1/image-verifications/wakeup/sessions/{id}/verify` | `POST /api/v1/verification/wakeup/submit` (form `session_id`) | 동일 판정. 새 경로는 응답을 `{verification_type, result, wakeup_data}`로 래핑 |

> 기존 endpoint는 삭제되지 않았다(하위호환). 신규 프론트는 `/verification/*` 통합 경로를 사용하면 된다.

---

## 2. VLM 이미지 인증

### 2-1. water — `POST /api/v1/verification/image/water`

- Content-Type: `multipart/form-data`
- required: `file` (image/jpeg|png|webp, ≤10MB)
- optional: `latitude`, `longitude`, `target_latitude`, `target_longitude`, `captured_at`, `scheduled_at`
- 판정 기준(MVP): 물이 명확히 보이면 `verified`. 빈 컵/색 음료/근거 부족은 `rejected`(false positive 우선 차단).

```bash
curl -X POST http://localhost:8000/api/v1/verification/image/water \
  -F "file=@water.jpg;type=image/jpeg"
```

verified 응답:

```json
{
  "success": true,
  "message": "인증사진 판정이 완료되었습니다.",
  "data": {
    "verification_type": "water",
    "result": "verified",
    "score": 65,
    "mandatory_passed": true,
    "score_breakdown": { "base_score": 0, "object_score": 65, "text_score": 0, "scene_score": 0, "gps_score": 0, "total_score": 65 },
    "vlm_analysis": { "quality": {"usable": true}, "objects": [{"label": "glass", "confidence": 0.9}], "water_visual_evidence": ["visible_water", "filled_container"] },
    "rule_evidence": [
      { "code": "object:glass", "message": "glass 객체가 확인되었습니다.", "score_delta": 15 },
      { "code": "water_evidence:visible_liquid", "message": "물 또는 투명 액체가 확인되었습니다.", "score_delta": 30 }
    ]
  }
}
```

rejected 응답 (빈 컵):

```json
{
  "success": true,
  "message": "인증사진 판정이 완료되었습니다.",
  "data": {
    "verification_type": "water",
    "result": "rejected",
    "score": 15,
    "mandatory_passed": false,
    "rule_evidence": [
      { "code": "water_priority:empty_container", "message": "빈 용기가 확인되어 물 인증을 거절합니다.", "score_delta": 0 },
      { "code": "water_pattern_missing", "message": "물 인증에 필요한 물/용기 근거가 부족합니다.", "score_delta": 0 }
    ]
  }
}
```

retake_required 응답 (닫힌/불투명 용기 등 재촬영 필요): 구조는 동일, `"result": "retake_required"`.

### 2-2. exercise — `POST /api/v1/verification/image/exercise`

- required: `file`, **`activity_type`** (Form) — MVP: `gym` | `home_workout` (그 외 `running`/`swimming`/`yoga`/`pilates`도 enum상 허용)
- `activity_type` 누락 → **422**
- 판정 기준: 운동기구 또는 운동 자세가 명확해야 `verified`. 운동화만/물병만/사무실/침실/음식은 `rejected`.

```bash
curl -X POST http://localhost:8000/api/v1/verification/image/exercise \
  -F "file=@gym.jpg;type=image/jpeg" -F "activity_type=gym"
```

verified 응답:

```json
{
  "success": true,
  "message": "인증사진 판정이 완료되었습니다.",
  "data": {
    "verification_type": "exercise",
    "result": "verified",
    "score": 50,
    "mandatory_passed": true,
    "vlm_analysis": { "objects": [{"label": "weight_machine", "confidence": 0.9}], "exercise_visual_evidence": ["gym_environment", "weight_machine_present"] },
    "rule_evidence": [ { "code": "exercise_environment:gym", "message": "선택한 운동과 관련된 환경이 확인되었습니다.", "score_delta": 30 } ]
  }
}
```

activity_type 누락 시 (422):

```json
{ "success": false, "message": "exercise 인증에는 activity_type이 필요합니다.", "data": null }
```

### 2-3. study — `POST /api/v1/verification/image/study`

- required: `file`
- 판정 기준: 책/문제집/필기/학습 화면/강의/PDF/코드에디터 등 **학습 콘텐츠**가 보이면 `verified`. 노트북/모니터 등 **기기만** 있으면 verified 아님. 게임/SNS/쇼핑/오락 화면은 `rejected`.

```bash
curl -X POST http://localhost:8000/api/v1/verification/image/study \
  -F "file=@study.jpg;type=image/jpeg"
```

verified 응답:

```json
{
  "success": true,
  "message": "인증사진 판정이 완료되었습니다.",
  "data": {
    "verification_type": "study",
    "result": "verified",
    "score": 70,
    "mandatory_passed": true,
    "vlm_analysis": { "objects": [{"label": "book", "confidence": 0.9}], "study_visual_evidence": ["open_textbook", "open_workbook", "handwritten_notes"] }
  }
}
```

rejected 응답 (게임 화면): 구조 동일, `"result": "rejected"`, `rule_evidence`에 `study_priority:gaming_content`.

### 2-4. 잘못된 타입 — `POST /api/v1/verification/image/{unknown}`

`water/exercise/study`가 아니면 (예: `dancing`, `wakeup`) **400**:

```json
{ "success": false, "message": "지원하지 않는 이미지 인증 타입입니다: dancing (water/exercise/study)", "data": null }
```

---

## 3. 기상(wakeup) 인증

VLM을 사용하지 않는다. **서버 수신 시각** 기준으로 `scheduled_at`과 비교하며, 휴대전화 시간·EXIF·사진 속 시각은 신뢰하지 않는다. 이미지는 품질/중복(SHA256) 검사에만 사용한다.

### 3-1. 세션 발급 — `POST /api/v1/verification/wakeup/session`

- Content-Type: `application/json`
- required: `scheduled_at` (ISO8601, **timezone 필수**)
- optional: `allowed_early_minutes`(기본 5), `allowed_late_minutes`(기본 10), `session_ttl_seconds`(기본 120), `max_retries`(기본 2)

```bash
curl -X POST http://localhost:8000/api/v1/verification/wakeup/session \
  -H "Content-Type: application/json" \
  -d '{"scheduled_at":"2026-07-02T07:00:00+09:00","session_ttl_seconds":600}'
```

응답:

```json
{
  "success": true,
  "message": "기상 인증 세션이 발급되었습니다.",
  "data": {
    "session_id": "8faba27b27c64961864c606306ae9b14",
    "scheduled_at": "2026-07-02T07:00:00+09:00",
    "server_issued_at": "2026-07-05T11:35:08.040647+00:00",
    "expires_at": "2026-07-05T11:45:08.040647+00:00",
    "display_time": "2026-07-05T11:35:08.040647+00:00",
    "max_retries": 2
  }
}
```

`scheduled_at`에 timezone이 없으면 **422** (`scheduled_at에는 timezone 정보가 필요합니다.`).

### 3-2. 인증 제출 — `POST /api/v1/verification/wakeup/submit`

- Content-Type: `multipart/form-data`
- required: `session_id` (Form), `file` (image)

```bash
curl -X POST http://localhost:8000/api/v1/verification/wakeup/submit \
  -F "session_id=8faba27b27c64961864c606306ae9b14" \
  -F "file=@wake.jpg;type=image/jpeg"
```

응답 (공통 래퍼 + `wakeup_data`):

```json
{
  "success": true,
  "message": "기상 인증 판정이 완료되었습니다.",
  "data": {
    "verification_type": "wakeup",
    "result": "verified",
    "wakeup_data": {
      "decision": "verified",
      "scheduled_at": "2026-07-02T07:00:00+09:00",
      "server_issued_at": "2026-07-05T11:35:08+00:00",
      "received_at": "2026-07-05T11:38:08+00:00",
      "difference_minutes": 3.0,
      "session_expired": false,
      "duplicate_image": false,
      "image_quality_usable": true,
      "reasons": ["server_received_at_within_allowed_window"],
      "image_sha256": "e4b3...9a6f",
      "retry_count": 0,
      "max_retries": 2
    }
  }
}
```

주요 실패 케이스 (`result`/`wakeup_data.reasons`):

| 상황 | result | reasons 예 |
|------|--------|-----------|
| 세션 만료 (수신 > expires_at) | `rejected` | `session_expired` |
| 허용 창 이탈 (너무 이르거나 늦음) | `rejected` | `too_early` / `too_late` |
| 동일 이미지 재사용 (SHA256 중복) | `rejected` | `duplicate_image` |
| 이미지 품질 불가 (재촬영 여유 있음) | `retake_required` | `image_unusable` |
| 재촬영 횟수 초과 | `rejected` | `max_retries_exceeded` |
| 없는 세션 | `rejected` | `session_not_found:{id}` |

HTTP는 항상 200이며 판정은 `data.result`로 전달된다(정상 판정 흐름). 입력 오류(세션 생성 시 tz 누락 등)만 422.

---

## 4. 프론트엔드 연동 계약표

| 기능 | endpoint | method | content-type | required | optional | success(data) | failure | 프론트 표시 메시지 |
|------|----------|--------|--------------|----------|----------|---------------|---------|-------------------|
| 물 인증 | `/api/v1/verification/image/water` | POST | multipart/form-data | `file` | lat/lng, target_lat/lng, captured_at, scheduled_at | `result=verified/rejected/retake_required`, `score`, `rule_evidence`, `vlm_analysis` | 400(잘못된 타입), 422(이미지 오류) | verified: "물 인증 완료" / rejected: "물이 확인되지 않았어요" / retake: "다시 촬영해 주세요" |
| 운동 인증 | `/api/v1/verification/image/exercise` | POST | multipart/form-data | `file`, `activity_type`(gym\|home_workout) | 위와 동일 | 동일 | 422(activity_type 누락/이상, 이미지 오류) | verified: "운동 인증 완료" / rejected: "운동 근거가 부족해요" / 422: "운동 종류를 선택해 주세요" |
| 공부 인증 | `/api/v1/verification/image/study` | POST | multipart/form-data | `file` | 위와 동일 | 동일 | 422(이미지 오류) | verified: "공부 인증 완료" / rejected: "학습 내용이 확인되지 않았어요" |
| 기상 세션 발급 | `/api/v1/verification/wakeup/session` | POST | application/json | `scheduled_at`(tz 포함) | allowed_early/late_minutes, session_ttl_seconds, max_retries | `session_id`, `expires_at`, `scheduled_at`, `max_retries` | 422(tz 누락/형식 오류) | "기상 인증을 시작합니다" |
| 기상 제출 | `/api/v1/verification/wakeup/submit` | POST | multipart/form-data | `session_id`, `file` | — | `result`, `wakeup_data`(decision/reasons/retry_count/…) | (판정은 200 내 result) | verified: "기상 인증 완료" / retake_required: "사진을 다시 찍어 주세요" / rejected: reasons별 안내 |

프론트가 반드시 읽어야 할 필드: **`success`**, **`data.result`**(이미지) 또는 **`data.wakeup_data.decision`**(기상, `data.result`와 동일). 부가 표시용: `data.score`, `data.rule_evidence[].message`, `data.wakeup_data.reasons`, `retry_count`/`max_retries`.

---

## 5. 데모 시연 순서 (Swagger `/docs`)

1. **wakeup 세션 생성** — `POST /verification/wakeup/session` (`scheduled_at`을 현재 시각 근처 tz 포함으로) → `session_id` 확보
2. **wakeup 제출 성공/실패** — `POST /verification/wakeup/submit`
   - 성공: 방금 세션 + 이미지 → `verified`(허용 창 내)
   - 실패: 같은 이미지 재제출 → `rejected`(`duplicate_image`) / 만료 세션 → `rejected`(`session_expired`)
3. **water 이미지 인증** — `POST /verification/image/water` (물컵 사진 → `verified`, 빈 컵 → `rejected`)
4. **exercise 이미지 인증** — `POST /verification/image/exercise` + `activity_type=gym` (헬스장 사진 → `verified`)
5. **study 이미지 인증** — `POST /verification/image/study` (교재/필기 → `verified`, 게임 화면 → `rejected`)
6. **잘못된 verification_type** — `POST /verification/image/dancing` → **400**
7. **exercise activity_type 누락** — `POST /verification/image/exercise` (activity_type 없이) → **422**

> 실제 Qwen VLM 없이 시연하려면 backend가 `MockVisionAnalyzer`를 쓰도록 설정하거나(테스트 참고),
> Qwen 서버가 연결된 환경에서 실제 사진을 업로드하면 된다. wakeup은 VLM과 무관하게 항상 동작한다.

---

## 6. 관련 코드/테스트

- 라우팅: `backend/services/verification_orchestrator.py`
- 엔드포인트: `backend/api/verification.py` (기존 `backend/api/image_verification.py` 유지)
- 계약 smoke 테스트: `tests/test_verification_api_contract.py`
- 라우팅/책임 분리 테스트: `tests/test_verification_orchestrator.py`
