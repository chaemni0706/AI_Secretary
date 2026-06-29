# Integration Guide — 프론트엔드(Flutter) 연동

## 1. 서버 주소 (환경별)

| 환경 | Base URL |
|------|----------|
| PC 로컬(같은 PC) | `http://127.0.0.1:8000` |
| Android Emulator | `http://10.0.2.2:8000` |
| 실제 기기(같은 Wi-Fi) | `http://{PC_IP}:8000` (예: `http://192.168.0.10:8000`) |
| Swagger 문서 | `http://127.0.0.1:8000/docs` |

- 실제 기기/에뮬레이터에서 접속하려면 서버를 `--host 0.0.0.0`으로 실행하세요.
- `{PC_IP}`는 서버 PC의 LAN IP (Windows `ipconfig`, mac/linux `ifconfig`/`ip addr`).
- CORS는 개발 기본값으로 모든 origin 허용(`CORS_ORIGINS=*`).

## 2. 공통 응답 구조

모든 응답은 동일한 envelope입니다.

```json
{ "success": true, "message": "...", "data": { } }
```

권장 처리: `success`가 true인지 먼저 확인 → `data`에서 필요한 필드 사용. `message`는 사용자 안내/토스트에 활용.
오류 시 `success=false`이고 HTTP 상태코드(404/422/500 등)로 구분됩니다.

## 3. 엔드포인트 & 프론트 핵심 필드

| 기능 | Method · Path | 프론트가 읽는 핵심 필드 |
|------|---------------|------------------------|
| 일정 생성(파싱) | POST `/api/v1/ai/schedule/parse` | `data.schedule_draft` (title/category/date/start_time/end_time/priority), `data.missing_fields` |
| 예약 후보 | POST `/api/v1/reservations/candidates` | `data.recommended_candidates[]` (candidate_id/start_time/end_time/score), `data.rejected_slots[]` |
| 예약 메시지 | POST `/api/v1/messages/reservation` | `data.generated_message`, `data.alternatives[]` |
| 준비물·출발 알림 | POST `/api/v1/alerts/departure-plan` | `data.leave_time`, `data.checklist[]`, `data.notifications[]` |
| 하루 브리핑 | POST `/api/v1/briefings/daily` | `data.summary`, `data.key_points[]`, `data.priority_order[]` |
| 감정 코칭 | POST `/api/v1/emotion/analyze` | `data.emotion`, `data.coaching`, `data.recommended_actions[]` |
| 헬스 체크 | GET `/health` | `data.status == "ok"` |

요청/응답의 상세 예시는 `docs/api_spec.md`와 `mock/*.json`을 참고하세요. (mock은 실제 응답과 동일 구조)

## 4. 날짜·시간 규약

- 날짜: `"YYYY-MM-DD"` (예: `"2026-06-30"`)
- 시간: `"HH:mm"` 24시간제 (예: `"14:00"`)
- 상대 표현 해석을 위해 일정 파싱 요청에는 `current_datetime`(ISO8601)을 함께 보내세요.

## 5. 연동 팁

- 필드는 **추가될 수는 있어도 이름은 바뀌지 않습니다**. 파싱 시 모르는 필드는 무시하도록 구현하세요.
- 빈 결과(예: 예약 후보 없음)는 오류가 아니라 `success=true` + 빈 배열입니다. message로 사용자 안내.
- 감정 코칭은 의학적 진단이 아니며, 위험 신호 시 `risk_level: "high"`와 전문가 상담 권유 메시지가 옵니다.
- 로컬 개발 시 mock JSON으로 UI를 먼저 붙이고, 동일 구조의 실제 API로 교체하면 됩니다.
