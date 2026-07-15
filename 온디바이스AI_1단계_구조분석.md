# 온디바이스 AI 접목 — 1단계: 구조 분석 & 적용 지점 정리

> 코드 수정 없음. 기존 API 계약을 유지하고, 삭제/대체가 아닌 **fallback 확장** 방향으로만 정리했습니다.
> 분석 기준일: 2026-07-06

---

## 1. 현재 구조 요약

Flutter(`frontend/lib`) ↔ FastAPI(`backend`)가 REST로 연결된 AI 일정 비서 앱입니다.

**공통 통신 규약**
- 모든 응답은 `{ success, message, data }` envelope. `api_client.dart`가 envelope를 풀어 `data`만 반환하고, `success=false`/네트워크 오류 시 `ApiException`을 던집니다.
- Base URL은 `api_client.dart` 상단 상수 하나(`http://141.223.140.84:8000`), prefix는 `/api/v1`. connect/receive 타임아웃 각 10초.

**음성 처리 현황 (중요)**
- **STT / TTS는 이미 온디바이스로 동작 중**입니다. `speech_to_text`(STT), `flutter_tts`(TTS)를 각각 `voice_stt_service.dart`, `voice_tts_service.dart`가 감싸고 있고, 서버 STT(Whisper 등)는 쓰지 않는 것이 명시적 MVP 정책입니다.
- 서버 `/voice/tts`는 **오디오를 합성하지 않고 재생할 "문장"만** 돌려주는 fallback 엔드포인트입니다. `VoiceApi.tts()`는 이미 실패 시 입력 문장을 그대로 반환하도록 구현돼 있습니다.
- 백엔드 AI 로직은 **rule-based가 기본, LLM은 선택적 상위 레이어**입니다. `llm_service.generate()`는 API 키가 없으면 `None`을 반환하고 호출부는 template로 fallback합니다. 즉 서버 자체가 이미 "LLM 실패 → 규칙 기반" 2단 구조입니다.

**`on_device/` 디렉터리 상태**
- `on_device/voice`, `memory`, `notification`, `image` 하위 dart/tflite 파일이 존재하지만 **전부 0바이트 빈 스텁**입니다. 온디바이스용 스캐폴드만 잡혀 있고 구현은 비어 있습니다. (실제 동작 중인 STT/TTS 코드는 `frontend/lib/services`에 있음)

---

## 2. 관련 파일 목록

### 2-1. 프론트엔드 — STT / TTS / 음성 버튼 / 브리핑 / 챗봇 음성입력

| 기능 | 파일 | 비고 |
|---|---|---|
| TTS (온디바이스, flutter_tts) | `frontend/lib/services/voice_tts_service.dart` | ko-KR→ko_KR→en-US 언어 fallback, 예외 방어 완비 |
| STT (온디바이스, speech_to_text) | `frontend/lib/services/voice_stt_service.dart` | 마이크 권한 처리, ko_KR 우선 |
| `/voice/tts` 클라이언트 | `frontend/lib/services/voice_api.dart` | **이미 로컬 fallback 존재** (실패 시 입력문 반환) |
| 음성 일정 화면 (STT+parse+TTS 실사용) | `frontend/lib/screens/voice_schedule_screen.dart` | 마이크→STT→`/ai/schedule/parse`→TTS |
| AI 음성 챗봇 화면 | `frontend/lib/screens/voice_chat_screen.dart` | TTS는 실제, 감정 응답은 **Mock 사용 중** |
| 챗봇/브리핑 Mock 서비스 | `frontend/lib/services/mock_voice_service.dart` | `/emotion/analyze`, `/briefings/daily`, `/voice/tts` 대응 TODO 표기 |
| 브리핑 화면 | `frontend/lib/screens/briefing_screen.dart`, `daily_briefing_screen.dart` | |
| 브리핑 API | `frontend/lib/services/briefing_api.dart` | dashboard/today → `/briefings/daily` |
| 공통 API 클라이언트 | `frontend/lib/services/api_client.dart` | envelope 처리 + 타임아웃 + 로깅 |
| 말투/응답길이/리마인드 캐시 | `frontend/lib/services/preference_store.dart` | 전역 캐시, parse 요청에 스타일 첨부 |
| 사용자 설정 API | `frontend/lib/services/user_preferences_api.dart` | `GET/PUT /user/preferences` |

### 2-2. 백엔드 — 대상 4개 엔드포인트 연결 파일

| 엔드포인트 | 라우터 | 핵심 서비스 |
|---|---|---|
| `POST /api/v1/voice/tts` | `backend/api/voice.py` | (서비스 없음 — 문장 그대로 반환) `tts_response_builder.py`는 parse 응답용 |
| `POST /api/v1/ai/schedule/parse` | `backend/api/schedule.py` | `schedule_parser.py` (rule), + enhanced: `schedule_parse_service.py`, `schedule_llm_parser.py`, `llm_service.py`, `tts_response_builder.py` |
| `POST /api/v1/emotion/analyze` | `backend/api/emotion.py` | `emotion_analyzer.py` (rule + 선택적 LLM 코칭) |
| `POST /api/v1/briefings/daily` | `backend/api/briefing.py` | `briefing_generator.py` (rule) |
| (관련) 스타일 반영 | — | `assistant_style_service.py`, `user_preference_service.py` |

---

## 3. 온디바이스 적용 가능 기능 (우선 대상)

이미 온디바이스이거나, 규칙 로직이 단순해 Dart로 이식 가능한 것들입니다.

1. **Flutter TTS fallback** — ✅ 이미 온디바이스(flutter_tts). 남은 일은 "서버 `/voice/tts` 호출 실패 → 로컬 TTS로 그대로 읽기" 경로를 화면에서 일관되게 타도록 정리하는 정도. `voice_api.dart`가 이미 문장 fallback을 하므로 리스크 낮음.
2. **Flutter STT** — ✅ 이미 온디바이스(speech_to_text). 서버 STT 미사용이 정책이라 추가 이식 불필요. 안정화(권한/로케일 fallback)만 점검.
3. **간단한 일정 키워드 추출** — 오프라인 시 `/ai/schedule/parse`를 대체할 **경량 로컬 파서**. "내일/오늘/모레 + 시각(N시) + 제목 명사" 정도만 추출해 draft를 구성. 서버 규칙 파서(`schedule_parser.py`)의 축소판을 Dart로.
4. **간단한 감정/부담도 키워드 분류** — `emotion_rules.json` 수준의 키워드 매칭(피로/불안/슬픔/분노/스트레스/긍정)을 Dart로 이식해, 오프라인에서 감정 라벨 + 안전한 정형 문구만 표시. **위기 신호는 반드시 고정 안전문구**(진단성 표현 금지)로.
5. **로컬 사용자 말투 설정 반영** — `preference_store.dart`가 이미 tone/length/nudge를 로컬 캐시. 오프라인일 때 이 값으로 **간단한 문장 후처리**(존댓말/짧게-길게)를 Dart에서 적용.

---

## 4. 서버 유지 기능 (온디바이스로 옮기지 않음)

정확도·안전성·외부 API 의존이 큰 기능은 서버에 남깁니다.

1. **복잡한 자연어 일정 분석** — `parse/enhanced`의 LLM-first + hybrid merge(날짜/시간은 룰, 제목/분류는 LLM). 상대 날짜·중의성 해소는 서버 유지.
2. **감정 기반 생활 코칭 문장 생성** — LLM/템플릿 코칭 문장. 금지어 필터 등 안전 로직 포함이므로 서버 유지.
3. **하루 브리핑 생성** — `briefing_generator.py`. 일정/할일 요약·우선순위 문장화.
4. **예약 후보 추천** — `reservation_candidate_service.py`, `reservation_recommender.py` 등.
5. **예약 메시지 생성** — `reservation_message_service.py`, `message_generator.py`.
6. **지도/거리/이동 시간 계산** — `naver_maps_client.py`, `travel_time_service.py`, `place_recommendation_service.py` (외부 API 키 필요).

---

## 5. 수정 우선순위

| 순위 | 항목 | 이유 | 난이도/리스크 |
|---|---|---|---|
| **P0** | TTS 재생 경로 fallback 일관화 | 이미 온디바이스라 즉시 안정성↑, 계약 영향 0 | 낮음 |
| **P0** | `api_client` 오프라인/타임아웃 감지 공통화 | 모든 fallback의 전제 조건 | 낮음 |
| **P1** | 음성 챗봇 화면 Mock → 실 API + 로컬 fallback | 현재 `voice_chat_screen`이 Mock 고정 | 중간 |
| **P1** | 경량 로컬 일정 키워드 파서(오프라인 draft) | 네트워크 실패 시에도 일정 초안 제공 | 중간 |
| **P2** | 로컬 감정/부담도 키워드 분류 | 안전문구 정책 준수 필요 | 중간(안전 주의) |
| **P2** | 로컬 말투 후처리 | UX 향상, 실패해도 원문 표시 | 낮음 |
| **P3** | 브리핑 오프라인 요약(로컬 템플릿) | 서버 문장 품질과 차이 큼 → 후순위 | 중간 |

---

## 6. 다음 단계(2단계)에서 수정할 파일 목록

기존 파일은 **삭제 없이 fallback 분기만 추가**, 신규는 온디바이스 로직 전용으로 생성.

**수정(기존, 계약 유지)**
- `frontend/lib/services/api_client.dart` — 오프라인/타임아웃을 구분하는 헬퍼(`isNetworkError`) 노출. 기존 예외 흐름은 유지.
- `frontend/lib/services/schedule_api.dart` — `parse()` 실패 시 로컬 파서 결과를 반환하는 fallback 분기 추가(성공 경로 불변).
- `frontend/lib/services/briefing_api.dart` — 실패 시 로컬 요약 fallback 분기 추가.
- `frontend/lib/screens/voice_chat_screen.dart` — Mock → 실제 `/emotion/analyze` 호출 + 실패 시 로컬 감정 분류 fallback.
- `frontend/lib/services/mock_voice_service.dart` — 실 API 연결 시 참조용으로 유지(즉시 삭제 금지).
- `frontend/lib/screens/voice_schedule_screen.dart` — parse 실패 시 로컬 draft 표시 분기.

**신규(온디바이스 전용, 빈 스텁 채우기 우선 활용)**
- `frontend/lib/services/local_schedule_parser.dart` (신규) 또는 `on_device/voice/*` 스텁 활용 — 경량 키워드 일정 추출.
- `frontend/lib/services/local_emotion_classifier.dart` (신규) — 키워드 감정/부담도 분류 + 안전문구.
- `frontend/lib/services/local_tts_style.dart` (신규, 선택) — 말투/길이 후처리.
- (참고 데이터) 서버 `backend/rules/emotion_rules.json`, `backend/rules/*`의 키워드 일부를 앱 asset으로 복제해 로컬 규칙 소스로 사용.

> `on_device/` 하위 0바이트 스텁(`stt_service.dart`, `preference_manager.dart` 등)은 실제로 쓰이는 코드가 아니므로, 신규 로컬 로직을 `frontend/lib/services`에 두고 `on_device/`는 정리 대상으로만 표시하는 것을 권장합니다.

---

## 7. 리스크 및 주의사항

1. **API 계약 불변** — 서버 응답 스키마(`intent`, `schedule_draft`, `missing_fields`, `tts_text` / 감정 `coaching_reply`, `tts_text` / envelope)를 로컬 fallback도 **동일 형태로 생성**해야 화면 코드가 안 깨집니다.
2. **감정 분류 안전성** — 로컬 분류는 라벨·정형 문구까지만. 진단성 표현(우울증/장애/처방 등) 금지어 정책을 Dart에도 이식하고, 위기 신호는 고정 안전 메시지로 처리. 코칭 "문장 생성"은 서버 전용 유지.
3. **정확도 저하 고지** — 로컬 파서/분류는 서버 대비 정확도가 낮으므로, fallback 결과에는 "오프라인 임시 분석" 같은 상태 표시를 두어 사용자가 신뢰 수준을 알 수 있게 합니다.
4. **온·오프라인 결과 불일치** — 재접속 시 서버 결과로 갱신(re-parse) 경로를 두어 로컬 draft가 최종본으로 오인되지 않도록.
5. **기존 fallback 중복 주의** — `voice_api.dart`는 이미 문장 fallback 보유. 새 분기를 얹을 때 이중 fallback로 인한 혼선 없도록 단일 진입점 정리.
6. **`on_device/` 빈 스텁** — 참조 코드가 아니므로 여기에 구현하려면 pubspec/빌드 경로 편입 여부부터 확인 필요. 안전하게는 `frontend/lib` 내부에 구현.
7. **타임아웃 UX** — 현재 10초 타임아웃. 오프라인 fallback을 붙이면 사용자가 10초를 기다리지 않도록, 네트워크 불가가 명확할 때 즉시 로컬 경로로 전환하는 로직 고려.
