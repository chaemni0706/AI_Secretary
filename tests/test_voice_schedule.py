"""Voice-based schedule parsing + TTS fallback tests.

Covers the MVP "voice → parse → (draft) → tts" backend contract:

  POST /api/v1/ai/schedule/parse   with input_type="voice"
  POST /api/v1/voice/tts           (flutter_tts fallback envelope)

current_datetime is fixed to a Monday (2026-06-29) so relative dates resolve
deterministically. No LLM / no external calls.
"""

NOW = "2026-06-29T10:00:00+09:00"  # Monday
PARSE = "/api/v1/ai/schedule/parse"
TTS = "/api/v1/voice/tts"


def _parse(client, text, *, input_type="voice"):
    r = client.post(
        PARSE,
        json={"input": text, "input_type": input_type, "current_datetime": NOW},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True
    return body["data"]


# --------------------------------------------------------------------------- #
# 1. voice 입력으로 파싱 성공
# --------------------------------------------------------------------------- #
def test_voice_parse_success(client):
    data = _parse(client, "내일 오후 2시에 병원 예약 잡아줘")
    assert data["intent"] == "create_schedule"
    assert data["slots"]["date"] == "2026-06-30"
    assert data["slots"]["start_time"] == "14:00"
    assert data["slots"]["category"] == "hospital"
    assert data["missing_fields"] == []


# --------------------------------------------------------------------------- #
# 2. text 입력 기존 동작 유지 (source=ai)
# --------------------------------------------------------------------------- #
def test_text_input_keeps_source_ai(client):
    data = _parse(client, "내일 오후 2시에 병원 예약 잡아줘", input_type="text")
    assert data["schedule_draft"]["source"] == "ai"


# --------------------------------------------------------------------------- #
# 3. voice 입력 시 schedule_draft.source == "voice"
# --------------------------------------------------------------------------- #
def test_voice_input_sets_source_voice(client):
    data = _parse(client, "내일 오후 2시에 병원 예약 잡아줘")
    assert data["schedule_draft"]["source"] == "voice"


# --------------------------------------------------------------------------- #
# 4. 성공 응답에 tts_text 포함 (등록 확인 유도)
# --------------------------------------------------------------------------- #
def test_success_includes_tts_text(client):
    data = _parse(client, "내일 오후 2시에 병원 예약 잡아줘")
    assert data["tts_text"]
    assert "등록할까요" in data["tts_text"]
    # 요약에 날짜/시간이 반영되는지 가볍게 확인
    assert "2026-06-30" in data["tts_text"]
    assert "14:00" in data["tts_text"]


# --------------------------------------------------------------------------- #
# 5. 날짜/시간 누락 시 부분 인식 tts_text
# --------------------------------------------------------------------------- #
def test_missing_fields_partial_tts_text(client):
    # "병원 예약 잡아줘" -> title+category 있음(intent=create_schedule) 이지만 날짜/시간 없음
    data = _parse(client, "병원 예약 잡아줘")
    assert "date" in data["missing_fields"]
    assert "time" in data["missing_fields"]
    assert data["tts_text"] == "일정 정보를 일부만 이해했어요. 날짜나 시간을 다시 확인해주세요."


def test_unrecognized_input_failure_tts_text(client):
    # 의미 없는 입력 -> intent unknown -> 실패 안내
    data = _parse(client, "")
    assert data["intent"] == "unknown"
    assert data["tts_text"] == "일정 정보를 정확히 듣지 못했어요. 날짜와 시간을 포함해서 다시 말해주세요."


# --------------------------------------------------------------------------- #
# 6. 잘못된 input_type -> 422 + 공통 error envelope
# --------------------------------------------------------------------------- #
def test_invalid_input_type_returns_422(client):
    r = client.post(
        PARSE,
        json={"input": "내일 회의", "input_type": "video", "current_datetime": NOW},
    )
    assert r.status_code == 422, r.text
    body = r.json()
    assert body["success"] is False
    assert "message" in body


def test_missing_input_returns_422(client):
    r = client.post(PARSE, json={"input_type": "voice"})
    assert r.status_code == 422, r.text
    assert r.json()["success"] is False


# --------------------------------------------------------------------------- #
# 7. /voice/tts fallback 엔드포인트
# --------------------------------------------------------------------------- #
def test_voice_tts_fallback(client):
    r = client.post(TTS, json={"text": "일정이 등록됐어요.", "source": "voice_schedule"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True
    data = body["data"]
    assert data["mode"] == "flutter_tts"
    assert data["text"] == "일정이 등록됐어요."
    assert data["audio_url"] is None
    assert data["voice_id"] == "device_default"
    assert data["cached"] is False


def test_voice_tts_empty_text_422(client):
    r = client.post(TTS, json={"text": ""})
    assert r.status_code == 422, r.text
    assert r.json()["success"] is False
