# 음성 통합 라우터 실기(태블릿/폰) 검증 체크리스트

`voice_chat_screen.dart` / `ai_chat_screen.dart` → `POST /api/v1/voice/route` 로 통합된 음성
입력 기능을 실제 Android 기기에서 확인하는 절차입니다. 자동화 테스트(`tests/test_voice_intent_router.py`,
`tests/test_voice_route_api.py`)는 백엔드 로직만 검증하므로, 마이크/스피커/로컬 알림처럼 OS와
직접 맞닿는 부분은 반드시 실기에서 한 번 확인해야 합니다.

## 0. 사전 준비

| 항목 | 확인 방법 |
|---|---|
| 백엔드 실행 | `uvicorn backend.main:app --host 0.0.0.0 --port 8000` (기기와 같은 네트워크) |
| Flutter 접속 주소 | `frontend/lib/services/api_client.dart`의 `baseUrl`이 PC의 실제 IP인지 확인 |
| 마이크 권한 | 최초 실행 시 시스템 권한 팝업 허용 |
| 알림 권한(Android 13+) | 최초 실행 또는 자동 브리핑 시각 저장 시 팝업 허용 (`POST_NOTIFICATIONS`) |

---

## 1. Naver 장소 추천 — 키 미설정 시 vs 설정 시

### 1-1. 키 미설정 (기본 상태) 확인
`backend/.env`에 `NAVER_CLIENT_ID`/`NAVER_CLIENT_SECRET`이 없는 상태로 "가게 추천해줘"를 말하면:
- 백엔드 로그(터미널)에 다음이 순서대로 찍혀야 합니다.
  ```
  [VOICE INTENT] intent=reservation_recommendation matched_keywords=...
  [VOICE ROUTE] text='가게 추천해줘' intent=reservation_recommendation matched=...
  [VOICE ROUTE] reservation_recommendation start text='가게 추천해줘' naver_configured=False
  [VOICE ROUTE] reservation_recommendation degraded (naver_configured=False): 네이버 API 키가 설정되지 않았습니다...
  ```
- 앱 화면: "지금은 추천 서비스에 연결할 수 없어요..." 라는 TTS/말풍선이 뜨고, **절대 일정 등록 확인 문구("~ 일정을 추가할까요?")가 뜨면 안 됩니다.**

### 1-2. 키 설정 후 성공 경로 확인
1. `backend/.env`에 실제 발급받은 값을 채웁니다.
   ```
   NAVER_CLIENT_ID=발급받은_client_id
   NAVER_CLIENT_SECRET=발급받은_client_secret
   ```
2. 백엔드를 재시작합니다(환경변수는 프로세스 시작 시 1회 로드됨).
3. "근처 카페 추천해줘" 같은 발화로 다시 시도합니다.
4. 백엔드 로그 확인:
   ```
   [VOICE ROUTE] reservation_recommendation start text='근처 카페 추천해줘' naver_configured=True
   [VOICE ROUTE] reservation_recommendation success query='...' results=N top='...'
   ```
   - `results=0`이면 검색어/지역이 너무 좁은 것이니 다른 지역명으로 재시도.
5. 앱 화면: 자동으로 **"추천 장소" 화면(`PlaceRecommendationScreen`)으로 전환**되어야 하며(카드로만 머물러 있으면 안 됨), 목록에 이름/점수/주소/전화번호가 표시돼야 합니다.
6. 채팅 화면으로 돌아가면 방금 발화에 대한 말풍선("추천 후보를 찾아봤어요...")과 TTS 음성이 함께 남아 있어야 합니다.

> Flutter 쪽 로그는 `flutter run` 콘솔 또는 `adb logcat | grep flutter`에서 `[VoiceIntent] navigate -> PlaceRecommendationScreen (query="...", results=N)` 로 확인할 수 있습니다.

---

## 2. 텍스트 입력 vs 음성 입력 라우팅 일치 확인 (ai_chat_screen ↔ voice_chat_screen)

같은 문장을 **① 메인 화면 우측 하단 "AI" 버튼(`ai_chat_screen.dart`, 텍스트로 타이핑)**과
**② 메뉴 > AI 음성 챗봇(`voice_chat_screen.dart`, 마이크로 발화)** 양쪽에서 각각 시도해
동일한 intent/카드가 나오는지 비교합니다.

| 발화 | 기대 intent | 확인 포인트 |
|---|---|---|
| 가게 추천해줘 | reservation_recommendation | 두 화면 모두 추천 장소 화면으로 이동 |
| 오늘 진짜 피곤하다 오늘 일정 뭐야 | emotion_schedule_coaching | 두 화면 모두 공감+오늘 일정+제안이 함께 담긴 카드 |
| 내일 오후 3시에 병원 일정 추가해줘 | schedule_create | 두 화면 모두 즉시 등록 + "알림을 받을까요?" 질문 |

두 화면 모두 `voice_router_api.dart` → `POST /voice/route` 를 호출하므로(개별 화면에서
`/ai/schedule/parse`를 직접 호출하지 않음), 백엔드 로그의 `[VOICE ROUTE] text=... intent=...`
줄이 어느 화면에서 보내든 동일한 규칙으로 찍히는지 확인하면 됩니다.

---

## 3. 감정 기반 일정 코칭 — 3요소 결합 확인

1. 먼저 오늘 날짜로 일정을 하나 등록합니다(예: "오늘 오후 6시에 과제 마감").
2. "오늘 진짜 피곤하다 오늘 일정 뭐야" 라고 말합니다.
3. TTS/말풍선에 아래 3가지가 **모두** 포함돼야 합니다.
   - 공감 문장 (예: "지금 많이 지치고 힘든 마음이 느껴져요.")
   - 오늘 일정 요약 (방금 등록한 일정 제목이 그대로 언급되어야 함)
   - 휴식/일정 조정 제안 (예: "~ 방법이 도움이 될 수 있어요", "그 밖에 ~도 도움이 될 수 있어요")
4. 카드에 "오늘 일정 보기 / 휴식 추가 / 일정 미루기 / 알림 설정" 액션 칩이 함께 보이는지 확인.

---

## 4. flutter_local_notifications 실기 체크리스트

### 4-1. 최초 설정
1. 마이페이지 > AI 음성 스타일 설정 화면에서 "자동 브리핑" 시각을 **지금 시각 + 2분** 정도로 설정 후 저장.
2. 저장 시 알림 권한 팝업이 뜨면 허용.
3. 앱을 백그라운드로 보내거나 화면을 끕니다.

### 4-2. 확인 항목
| 항목 | 기대 동작 |
|---|---|
| 설정 시각 도달 | 알림이 발생(진동/소리, 잠금화면에도 표시) |
| 알림 탭 | 전화 수신처럼 보이는 화면(`MockCallAlertScreen`, 어두운 그라데이션)으로 이동 |
| 화면 진입 직후 | 자동으로 TTS가 재생됨(버튼을 누르지 않아도 됨, `autoPlay: true`) |
| 화면 내용 | 오늘 브리핑 요약 문구가 표시됨(`briefingApi.getDailyBriefing()` 결과) |
| "확인했어요" | 화면이 닫히고 TTS 정지 |

### 4-3. Android 버전별 주의사항
- **Android 13+**: 알림 권한(`POST_NOTIFICATIONS`)을 거부하면 예약 자체가 조용히 스킵됩니다
  (`briefing_scheduler_service.dart`의 `ensureNotificationPermission()`). 설정 > 앱 > 알림에서
  직접 허용해도 됩니다.
- **Android 12+ 정확한 알람**: 일부 제조사(특히 삼성)는 배터리 최적화가 강해 "정확한 알람" 권한을
  별도로 요구할 수 있습니다. 알림이 정시에 오지 않으면 설정 > 앱 > 특별한 앱 접근 > 알람 및 리마인더에서
  앱을 허용 목록에 추가하세요.
- **재부팅 후**: `ScheduledNotificationBootReceiver`가 등록돼 있어 재부팅 후에도 예약이 유지돼야
  합니다(`AndroidManifest.xml` 참고). 재부팅 후 알림이 안 오면 배터리 최적화 예외 설정을 다시 확인하세요.

---

## 5. 일정 등록 → 알림 확인 2턴 흐름

1. "내일 오후 3시에 병원 일정 추가해줘" → 즉시 등록 + "이 일정 전에 알림을 받을까요?" 질문.
2. 이어서 "응 알림 받을래" → "일정 30분 전에 알려드릴게요."
3. 다시 처음부터, 이번엔 2턴째에 "1시간 전에 알려줘" → "일정 60분 전에 알려드릴게요."
4. **직전 등록 없이** 바로 "응 알림 받을래"만 말했을 때 알림 설정으로 오작동하지 않는지(엉뚱한 응답/오류 없이 자연스러운 fallback 대화로 처리되는지) 확인.

---

## 6. 마이크(STT) / 스피커(TTS) 최소 확인

- `voice_chat_screen.dart`, `ai_chat_screen.dart` 양쪽에서 마이크 버튼을 눌러 실제 목소리로
  말했을 때 인식된 텍스트가 화면/로그에 그대로 나타나는지 확인(`VoiceSttService`).
- 응답이 자동으로 스피커에서 재생되는지 확인(`VoiceTtsService`). 소리가 안 나면 기기 설정 >
  언어 및 입력 > 텍스트 음성 변환에서 한국어(ko-KR) 음성 데이터 설치 여부를 확인하세요
  (`voice_tts_service.dart`가 관련 진단 로그를 남깁니다).
