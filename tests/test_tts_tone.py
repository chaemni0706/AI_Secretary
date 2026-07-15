"""JSON rule-based TTS tone styling (no LLM) applied to /ai/schedule/parse tts_text.

`tone` is an additive, optional request field (backend/database/schema/schedule_schema.py).
'neutral' / omitted / invalid values must reproduce the exact pre-existing tts_text
strings so tests/test_voice_schedule.py keeps passing unmodified.
"""

NOW = "2026-06-29T10:00:00+09:00"  # Monday
PARSE = "/api/v1/ai/schedule/parse"


def _parse(client, text, *, tone=None, input_type="voice"):
    body = {"input": text, "input_type": input_type, "current_datetime": NOW}
    if tone is not None:
        body["tone"] = tone
    r = client.post(PARSE, json=body)
    assert r.status_code == 200, r.text
    return r.json()["data"]


# --------------------------------------------------------------------------- #
# 1. tone 미지정/neutral -> 기존 tts_text 문자열과 완전히 동일 (회귀 방지)
# --------------------------------------------------------------------------- #
def test_no_tone_matches_legacy_tts_text(client):
    data = _parse(client, "내일 오후 2시에 병원 예약 잡아줘")
    assert data["tts_text"] == "병원 예약 일정을 2026-06-30 14:00으로 정리했어요. 등록할까요?"


def test_explicit_neutral_matches_legacy_tts_text(client):
    data = _parse(client, "병원 예약 잡아줘", tone="neutral")
    assert data["tts_text"] == "일정 정보를 일부만 이해했어요. 날짜나 시간을 다시 확인해주세요."


def test_invalid_tone_falls_back_to_neutral(client):
    data = _parse(client, "", tone="angry")
    assert data["tts_text"] == "일정 정보를 정확히 듣지 못했어요. 날짜와 시간을 포함해서 다시 말해주세요."


# --------------------------------------------------------------------------- #
# 2. gentle / warm 톤 -> 규칙 기반 문장 변형 확인
# --------------------------------------------------------------------------- #
def test_gentle_tone_styles_success_message(client):
    data = _parse(client, "내일 오후 2시에 병원 예약 잡아줘", tone="gentle")
    assert data["tts_text"] == "병원 예약 일정을 2026-06-30 14:00으로 정리해봤어요. 등록해드릴까요?"


def test_warm_tone_styles_success_message(client):
    data = _parse(client, "내일 오후 2시에 병원 예약 잡아줘", tone="warm")
    assert data["tts_text"] == "병원 예약 일정을 2026-06-30 14:00으로 정리했어요! 등록해드릴까요?"


def test_gentle_tone_styles_missing_fields_message(client):
    data = _parse(client, "병원 예약 잡아줘", tone="gentle")
    assert data["tts_text"] == "일정 정보를 일부만 이해했어요. 날짜나 시간을 다시 한 번 확인해주시겠어요?"


def test_warm_tone_styles_unrecognized_message(client):
    data = _parse(client, "", tone="warm")
    assert data["intent"] == "unknown"
    assert data["tts_text"] == "괜찮아요, 제가 잘 못 들었나 봐요. 날짜와 시간을 포함해서 다시 한 번 말해주세요."


# --------------------------------------------------------------------------- #
# 3. tone 필드는 additive optional -> 생략해도 요청 자체는 그대로 성공
# --------------------------------------------------------------------------- #
def test_tone_field_is_optional(client):
    r = client.post(
        PARSE,
        json={"input": "내일 오후 2시에 병원 예약 잡아줘", "current_datetime": NOW},
    )
    assert r.status_code == 200, r.text
    assert r.json()["success"] is True
