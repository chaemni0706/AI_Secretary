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

## 3. 저장/큐 구조 (구현 현황)

- 이미지 인증은 현재 **DB 저장이 없다(stateless)**. `ImageVerificationData` 는 API 응답 스키마이며 DB 모델이 아니다.
- 따라서 review queue 는 기존 선례(`wakeup_session_store`)와 동일하게 **in-memory 스토어**로 구현했다:
  `backend/services/secondary_review_service.py` → `SecondaryReviewStore` + 싱글턴 `secondary_review_store`.
- **PoC 한계:** 서버 재시작 시 큐가 사라진다. 프로덕션은 DB 테이블(`image_verification_reviews`)로 백킹해야 한다(아래 4항).

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

1. review queue DB 테이블 백킹(현재 in-memory PoC) + 인증 결과 영속화.
2. 관리자 검수 화면(pending 목록/상세/결정) — 프론트/어드민.
3. GPS/시간/촬영 맥락 rule 연동 → 일부 water 자동 확정 범위 확대(Rule Engine 확장은 별도 합의).
4. 재촬영(needs_retake) 시 사용자 재제출 흐름.
