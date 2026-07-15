"""Reservation inquiry message generation tests.

POST /api/v1/messages/reservation

Without an OPENAI_API_KEY the service must produce a natural template message
(LLM is an optional enhancement). Response field names are part of the
frontend contract: data.generated_message / data.alternatives / data.style.
"""

PATH = "/api/v1/messages/reservation"


def _post(client, *, category="etc", purpose=None, target_date="2026-06-30",
          preferred_time="10:00", tone="polite", length="short", channel="sms",
          user_input=None):
    payload = {
        "input": user_input,
        "reservation_info": {
            "category": category,
            "target_date": target_date,
            "preferred_time": preferred_time,
            "purpose": purpose,
        },
        "style": {"tone": tone, "length": length, "channel": channel},
    }
    r = client.post(PATH, json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    return body["data"]


# --------------------------------------------------------------------------- #
# Response contract
# --------------------------------------------------------------------------- #
def test_response_structure_is_stable(client):
    data = _post(client, category="hospital", purpose="진료 예약")
    assert set(data.keys()) == {"generated_message", "alternatives", "style"}
    assert isinstance(data["generated_message"], str) and data["generated_message"]
    assert len(data["alternatives"]) >= 2
    assert data["style"]["tone"] == "polite"


def test_date_and_time_are_human_readable(client):
    data = _post(client, category="hospital", purpose="진료 예약",
                 target_date="2026-06-30", preferred_time="14:00")
    assert "6월 30일" in data["generated_message"]
    assert "오후 2시" in data["generated_message"]


# --------------------------------------------------------------------------- #
# 1. hospital + 진료 예약
# --------------------------------------------------------------------------- #
def test_case1_hospital(client):
    data = _post(client, category="hospital", purpose="진료 예약")
    msg = data["generated_message"]
    assert msg.startswith("안녕하세요.")
    assert "진료 예약" in msg            # purpose, no '예약 예약' doubling
    assert "예약 예약" not in msg
    assert len(data["alternatives"]) == 2


# --------------------------------------------------------------------------- #
# 2. beauty + 커트 예약
# --------------------------------------------------------------------------- #
def test_case2_beauty(client):
    msg = _post(client, category="beauty", purpose="커트 예약")["generated_message"]
    assert "커트 또는 시술" in msg


# --------------------------------------------------------------------------- #
# 3. restaurant + 2명 예약
# --------------------------------------------------------------------------- #
def test_case3_restaurant(client):
    msg = _post(client, category="restaurant", purpose="2명 예약")["generated_message"]
    assert msg.startswith("안녕하세요.")
    assert "예약이 가능한지" in msg
    assert "6월 30일" in msg


# --------------------------------------------------------------------------- #
# 4. meeting + 회의 일정 조율
# --------------------------------------------------------------------------- #
def test_case4_meeting(client):
    msg = _post(client, category="meeting")["generated_message"]
    assert "회의 일정 조율" in msg


# --------------------------------------------------------------------------- #
# 5. category 없음/etc
# --------------------------------------------------------------------------- #
def test_case5_etc_and_unknown(client):
    assert "예약 가능 여부" in _post(client, category="etc")["generated_message"]
    # an unknown category falls back to the etc template
    assert "예약 가능 여부" in _post(client, category="banking")["generated_message"]


# --------------------------------------------------------------------------- #
# Style: tone / length / sms length cap
# --------------------------------------------------------------------------- #
def test_casual_tone_changes_endings(client):
    msg = _post(client, category="etc", tone="casual")["generated_message"]
    assert "문의해요" in msg
    assert "문의드립니다" not in msg


def test_sms_does_not_use_long_form(client):
    sms = _post(client, category="etc", length="long", channel="sms")["generated_message"]
    kakao = _post(client, category="etc", length="long", channel="kakao")["generated_message"]
    # the verbose long-only opener is only used for non-SMS channels
    assert not sms.startswith("바쁘신 와중에")
    assert kakao.startswith("바쁘신 와중에")
    assert len(sms) < len(kakao)


# --------------------------------------------------------------------------- #
# Template fallback when no LLM key is configured (default test env)
# --------------------------------------------------------------------------- #
def test_template_fallback_without_key(client):
    # No OPENAI_API_KEY in tests -> llm_service.generate returns None -> template.
    data = _post(client, category="hospital", purpose="진료 예약")
    assert data["generated_message"].startswith("안녕하세요.")
    assert "진료 예약" in data["generated_message"]


# --------------------------------------------------------------------------- #
# purpose == "예약" edge: must not produce "예약 예약"
# --------------------------------------------------------------------------- #
def test_purpose_exactly_reservation_word_no_duplication(client):
    msg = _post(client, category="hospital", purpose="예약")["generated_message"]
    assert "예약 예약" not in msg
    assert "진료 예약" in msg            # falls back to hospital default '진료'


def test_purpose_padded_reservation_word_no_duplication(client):
    msg = _post(client, category="hospital", purpose=" 예약 ")["generated_message"]
    assert "예약 예약" not in msg
    assert "진료 예약" in msg


def test_purpose_keeps_real_subject(client):
    msg = _post(client, category="hospital", purpose="진료 예약")["generated_message"]
    assert "진료 예약" in msg
    assert "예약 예약" not in msg


def test_purpose_reservation_word_restaurant_and_etc(client):
    rest = _post(client, category="restaurant", purpose="예약")["generated_message"]
    assert "예약 예약" not in rest and rest.startswith("안녕하세요.")
    etc = _post(client, category="etc", purpose="예약")["generated_message"]
    assert "예약 예약" not in etc and "예약 가능 여부" in etc


# --------------------------------------------------------------------------- #
# Repeated trailing "예약" must all be stripped (purpose="예약 예약")
# --------------------------------------------------------------------------- #
def test_repeated_reservation_word_no_duplication(client):
    msg = _post(client, category="hospital", purpose="예약 예약")["generated_message"]
    assert "예약 예약" not in msg
    assert "진료 예약" in msg            # default '진료'


def test_real_subject_with_repeated_reservation(client):
    msg = _post(client, category="hospital", purpose="진료 예약 예약")["generated_message"]
    assert "예약 예약" not in msg
    assert "진료 예약" in msg            # cleaned to '진료'


def test_repeated_reservation_word_beauty_and_etc(client):
    beauty = _post(client, category="beauty", purpose="예약 예약")["generated_message"]
    assert "예약 예약" not in beauty
    assert "커트 또는 시술" in beauty     # default '커트'
    etc = _post(client, category="etc", purpose="예약 예약")["generated_message"]
    assert "예약 예약" not in etc
    assert "예약 가능 여부" in etc


def test_reservation_word_not_at_end_is_preserved(client):
    # "예약 상담" — 예약 is not the trailing token, so it must not be stripped.
    msg = _post(client, category="hospital", purpose="예약 상담")["generated_message"]
    assert "예약 상담" in msg
    assert "예약 예약" not in msg
