# AI Secretary Backend — Flutter 연동 가이드

## Base URL

| 실행 환경 | Base URL |
|-----------|----------|
| Android 에뮬레이터 | `http://10.0.2.2:8000` |
| iOS 시뮬레이터 | `http://127.0.0.1:8000` |
| 실제 기기 (같은 Wi-Fi) | `http://{백엔드_PC_IP}:8000` |

> 실제 기기에서 접속하려면 백엔드를 `--host 0.0.0.0`으로 실행하고, PC와 폰이 같은 네트워크에 있어야 합니다.
> `{백엔드_PC_IP}`는 PC의 LAN IP (예: `192.168.0.12`).

API prefix는 `/api/v1`, 헬스 체크만 `/health` 입니다.

## 공통 응답 구조

모든 응답은 동일한 형태입니다.
```json
{ "success": true, "message": "...", "data": { } }
```
Flutter에서는 먼저 `success`를 확인하고, true면 `data`를 파싱, false면 `message`를 노출하세요.

```dart
final body = jsonDecode(res.body);
if (body['success'] == true) {
  final data = body['data'];
  // ... data 사용
} else {
  showError(body['message']);
}
```

## 날짜 / 시간 형식
- 날짜: 문자열 `YYYY-MM-DD` (예: `"2026-06-30"`)
- 시간: 문자열 `HH:mm` (24시간제, 예: `"14:00"`)
- 기준 시각: 일부 요청은 `current_datetime`(ISO 8601, 예: `"2026-06-29T10:00:00+09:00"`)을 보냅니다.
- 타임존: 기본 `Asia/Seoul`.

## API별 확인해야 할 핵심 필드

| API | 사용할 핵심 필드 |
|-----|------------------|
| `/health` | `data.status` |
| `/api/v1/ai/schedule/parse` | `data.schedule_draft`, `data.slots`, `data.missing_fields` |
| `/api/v1/reservations/candidates` | `data.recommended_candidates[]`, `data.rejected_slots[]` |
| `/api/v1/messages/reservation` | `data.generated_message`, `data.alternatives[]` |
| `/api/v1/alerts/departure-plan` | `data.leave_time`, `data.checklist[]`, `data.notifications[]` |
| `/api/v1/briefings/daily` | `data.summary`, `data.key_points[]`, `data.priority_order[]` |
| `/api/v1/emotion/analyze` | `data.emotion`, `data.coaching`, `data.recommended_actions[]`, `data.risk_level` |

## 주의 사항
- 일정/To-do는 앱(On-device)에 저장하고, 분석이 필요할 때 요청 본문으로 백엔드에 전달합니다.
- 분석 API는 입력이 부족해도 서버 에러 대신 `success: true` + 부족분(`missing_fields` 또는 빈 배열)으로 응답할 수 있으니, 화면에서 이 필드를 확인하세요.
- `/api/v1/emotion/analyze`는 비진단 생활 코칭이며, `risk_level == "high"`일 때 지원 안내 UI를 노출하는 것을 권장합니다.
- 응답 구조는 `mock/` 폴더의 JSON과 100% 동일합니다. 화면을 먼저 Mock으로 개발한 뒤 실제 API로 교체하면 됩니다.

## Mock 파일 매핑
```
mock/health_response.json                 -> GET  /health
mock/schedule_parse_response.json         -> POST /api/v1/ai/schedule/parse
mock/reservation_candidates_response.json -> POST /api/v1/reservations/candidates
mock/reservation_message_response.json    -> POST /api/v1/messages/reservation
mock/departure_plan_response.json         -> POST /api/v1/alerts/departure-plan
mock/daily_briefing_response.json         -> POST /api/v1/briefings/daily
mock/emotion_analyze_response.json        -> POST /api/v1/emotion/analyze
```
