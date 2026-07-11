# SECONDARY_REVIEW_FLOW

작성일: 2026-07-11
브랜치: `feature/vlm-image-verification-stabilization`
관련: `VLM_FALLBACK_STABILIZATION_REPORT.md`, `IMAGE_VERIFICATION_SYSTEM_AUDIT.md`

## 1. 왜 secondary_review 가 필요한가

VLM 기반 이미지 인증 full-test(171) 결과, water task 의 잔여 오탐(FP)은 전부 **외관만으로는 물과 구분 불가**한 케이스였다:
- `non_visual_context_required`: 오염 식수, 정수기/변기물 — 외관은 물, FAIL 사유가 수질/장소(비-시각).
- `label_review_needed`: 맥주잔 + 실제 물잔이 함께 있는 사진 — 모델이 물을 봄(라벨 애매).
- `borderline_policy`: BORDERLINE 라벨, 시각적으로 물.

즉 **VLM-only 로 water 를 자동 확정하면 안 되는 케이스가 구조적으로 존재**한다. 추론 시 이를 사전 판별할 시각 신호가 없으므로,
`verified(water)` 는 자동 최종 성공으로 처리하지 않고 **secondary_review(사람 검수/맥락 rule)** 로 보낸다.
exercise/study 는 full-test FP=0 이라 기존 자동 확정 흐름을 유지한다.

## 2. 상태 모델

`ImageVerificationData`(응답 스키마)에 추가된 필드(기본값 → 하위호환, **Rule Engine core/final_result enum 미변경**):

| 필드 | 값 | 의미 |
|---|---|---|
| `final_result`(=`result`) | verified / rejected / retake_required | 기존 룰 엔진 판정(불변) |
| `review_required` | bool | 검수 대상이었는가(현재: water verified) |
| `review_reason` | str | 예: `water_non_visual_context_risk` |
| `review_status` | none / pending / approved / rejected / needs_retake | 운영 상태(**최종 UI 판단은 이 값을 우선**) |
| `verification_id` | str? | review queue record id(등록 시 부여) |

상태 전이:
```
review_required=false → review_status="none"                (exercise/study verified, rejected, retake …)
review_required=true  → review_status="pending"             (water verified, 큐 등록)
   관리자 승인   → "approved"
   관리자 반려   → "rejected"
   재촬영 요청   → "needs_retake"
```

## 3. 저장/큐 구조 (DB 영속화 — 2026-07-11)

- 이미지 인증 결과 자체는 여전히 DB 저장이 없다(stateless). **review queue 만** 별도 테이블로 영속화한다.
- 전략 = **B안(별도 테이블)**: 기존 인증 record 테이블이 없어 확장 대상이 없고, planner/ledger 등과 완전 독립이라 가장 안전.
  ledger 도메인(별도 `*_models.py`/`*_repository.py` + `local_schema.sql` append-only)과 동일 패턴.
- 구성:
  - table: `image_verification_reviews` (`database/local_schema.sql`, `CREATE TABLE IF NOT EXISTS`, 트리거/기존 테이블 미수정).
  - model: `backend/database/image_verification_review_models.py` (`ImageVerificationReviewRow`, `models.py` 의 `Base` 공유).
  - repository: `backend/database/secondary_review_repository.py` (Session 주입 순수 CRUD).
  - service: `backend/services/secondary_review_service.py` (`register/list_pending/get/decide` — Session 주입, JSON 직렬화, `ReviewRecord` 변환).
- enum(review_status/decision)은 API/pydantic 과 동일하게 lowercase 저장 + CHECK 제약(이 도메인 신규 값 → 별도 매핑 레이어 없음).
- 시각은 ISO 문자열(created_at/reviewed_at), rule_evidence 는 JSON TEXT.
- 스키마 반영: `apply_schema_to_sqlite_file(runtime/ai_secretary_local.db)` (idempotent, IF NOT EXISTS). Alembic 없음 — SQL 파일이 단일 소스.
- 견고성: verify 라우트의 등록은 defensive(try/except+rollback) — DB 미초기화여도 인증 판정 자체는 반환(review_required 유지).

## 4. API

| method | path | 설명 |
|---|---|---|
| POST | `/api/v1/image-verifications` | 인증 판정. `review_required` 면 pending 등록 + `verification_id` 부여(응답에 review_status 포함) |
| GET | `/api/v1/image-verifications/reviews/pending` | 검수 대기(pending) 목록 |
| GET | `/api/v1/image-verifications/reviews/{verification_id}` | 검수 항목 상세 |
| POST | `/api/v1/image-verifications/reviews/{verification_id}/decision` | 결정 처리(approved/rejected/needs_retake) |

### 예시 — water verified (자동 확정 아님)
```json
// POST /api/v1/image-verifications  (verification_type=water)
{"success": true, "data": {
  "verification_type": "water", "result": "verified", "score": 65,
  "review_required": true, "review_reason": "water_non_visual_context_risk",
  "review_status": "pending", "verification_id": "b40a6ddc…",
  "rule_evidence": [{"code": "object:cup", "message": "cup 객체가 확인되었습니다.", "score_delta": 15}, …]
}}
```
### 예시 — 결정 처리
```json
// POST /api/v1/image-verifications/reviews/{id}/decision
// body: {"decision": "approved", "note": "관리자 확인", "reviewer_id": "admin1"}
{"success": true, "data": {
  "id": "b40a6ddc…", "review_status": "approved", "review_decision": "approved",
  "review_note": "관리자 확인", "reviewer_id": "admin1", "reviewed_at": "2026-07-11T…Z"
}}
```
### exercise/study verified (기존 자동 확정 유지)
```json
{"result": "verified", "review_required": false, "review_reason": "", "review_status": "none", "verification_id": null}
```

## 5. Frontend UX

- `verification_result.dart`: `reviewStatus`/`verificationId`/`isReviewPending|Approved|Rejected|NeedsRetake`,
  `isVerified`(review 시 false), `needsSecondaryReview`(verified+pending), 상태별 `displayMessage`.
- `image_verification_screen.dart`: `needsSecondaryReview` 이면 **amber(help) 카드** + 안내
  ("물 인증은 이미지상 통과 가능성이 있지만, 물의 종류나 촬영 맥락 확인이 필요해 검수 대기 상태로 전환되었어요. 검수 완료 후 최종 인증 여부가 반영됩니다.").
- approved/rejected/needs_retake 상태 메시지도 모델에 준비(검수 화면/이력에서 사용).
- exercise/study verified 화면은 변경하지 않음.

## 6. 운영 정책

- **water review_required=true / pending 은 자동 최종 성공이 아니다.** 최종 성공 여부는 `review_status`(approved) 로 확정.
- 현재 백엔드에 이미지 인증을 소비하는 **포인트/챌린지/성공 카운트 로직은 없다**(감사 확인). 향후 그런 로직을 붙일 때는
  `review_status != "approved"` 인 water 는 성공 처리/보상에서 제외해야 한다.
- exercise/study 는 FP=0 이라 verified 를 즉시 성공 처리해도 안전.
- **전체 real-world 완전 자동화가 아니라, VLM-eligible visual scope + secondary_review policy 기반 baseline** 이다.

## 7. 남은 작업(프로덕션)

1. ✅ review queue DB 테이블 백킹 완료(`image_verification_reviews`). (인증 결과 record 전체 영속화는 필요 시 별도.)
2. 관리자 검수 화면(pending 목록/상세/결정) — 프론트/어드민.
3. GPS/시간/촬영 맥락 rule 연동 → 일부 water 자동 확정 범위 확대(Rule Engine 확장은 별도 합의).
4. 재촬영(needs_retake) 시 사용자 재제출 흐름.
5. review 항목에 user_id/이미지 참조 연결(현재 이미지 인증이 user/이미지 저장을 하지 않아 큐는 독립 테이블).
