/// 음성/브리핑/알림 관련 Mock 데이터 모음.
///
/// 여기 담긴 Map 들은 모두 백엔드 공통 응답 형식
/// `{ "success": bool, "message": string, "data": {...} }` 을 그대로 흉내낸다.
/// 추후 실제 API 연결 시 이 파일 대신 HTTP 응답이 들어오면 되고,
/// 화면/서비스 코드는 `response['data']` 만 파싱하므로 변경이 최소화된다.
library;

import '../theme/app_constants.dart';

/// 하루 브리핑 Mock (`POST /api/v1/briefings/daily`).
final Map<String, dynamic> mockDailyBriefing = {
  "success": true,
  "message": "하루 브리핑을 생성했습니다.",
  "data": {
    "briefing_id": "brief_20260702_user1",
    "date": "2026-07-02",
    "summary": {
      "schedule_count": 2,
      "todo_count": 1,
      "high_priority_count": 2,
    },
    "briefing_text":
        "좋은 아침이에요. 오늘은 오전 10시에 팀 회의가 있고, 오후 3시에 병원 예약이 있어요. 오늘 안에 과제 제출도 필요하니 회의가 끝난 뒤 미리 정리해두면 좋아요.",
    "sections": [
      {
        "type": "today_schedule",
        "title": "오늘 일정",
        "content": "오늘은 팀 회의와 병원 예약이 있습니다.",
      },
      {
        "type": "important_todo",
        "title": "중요한 할 일",
        "content": "오늘 안에 과제 제출이 필요합니다.",
      },
      {
        "type": "recommendation",
        "title": "추천 행동",
        "content": "팀 회의 후 과제 제출 준비 시간을 확보하는 것을 추천합니다.",
      },
    ],
    "next_event": {
      "id": "sch_001",
      "title": "팀 회의",
      "start_time": "10:00",
      "minutes_until_start": 120,
    },
    "tts_text":
        "좋은 아침이에요. 오늘은 오전 10시에 팀 회의가 있고, 오후 3시에 병원 예약이 있어요. 과제 제출도 오늘까지라서 회의가 끝난 뒤 미리 정리해두면 좋아요.",
    "recommended_actions": [
      "팀 회의 30분 전 알림 설정",
      "과제 제출 마감 알림 설정",
    ],
  },
};

/// 음성 챗봇이 흉내낼 사용자의 고정 발화(마이크 버튼용).
const String mockUserSpeechText = "오늘 너무 힘들어. 과제 시간을 좀 미룰 수 있을까?";

/// 감정 기반 코칭 Mock (`POST /api/v1/emotion/analyze`).
final Map<String, dynamic> mockEmotionAnalyze = {
  "success": true,
  "message": "감정 기반 생활 코칭 응답을 생성했습니다.",
  "data": {
    "emotion": {
      "label": "tired",
      "intensity": "high",
      "confidence": 0.88,
    },
    "burden": {
      "level": "high",
      "reason": "사용자가 피로감을 표현했고, 오늘 마감인 높은 우선순위 할 일이 있습니다.",
    },
    "empathy_strategy": {
      "type": "emotional_support",
      "description": "먼저 감정을 인정하고, 이후 실행 가능한 일정 조정을 제안합니다.",
    },
    "coaching_reply":
        "많이 지친 상태인 것 같아요. 오늘 과제 제출이 중요하긴 하지만, 바로 시작하기보다 30분 정도 쉬고 나서 핵심 부분부터 정리하는 걸 추천해요. 지금 일정 기준으로는 저녁 8시부터 10시 사이를 과제 집중 시간으로 잡을 수 있어요.",
    "schedule_suggestions": [
      {
        "type": "reschedule_todo",
        "target_id": "todo_001",
        "suggested_start_time": "2026-07-02T20:00:00+09:00",
        "suggested_end_time": "2026-07-02T22:00:00+09:00",
        "reason": "회의 이후 회복 시간을 확보한 뒤 과제 시간을 배치했습니다.",
      },
      {
        "type": "rest",
        "suggested_start_time": "2026-07-02T15:30:00+09:00",
        "suggested_end_time": "2026-07-02T16:00:00+09:00",
        "reason": "피로도가 높아 짧은 휴식 시간을 먼저 추천합니다.",
      },
    ],
    "tts_text":
        "많이 지친 상태인 것 같아요. 바로 과제를 시작하기보다 30분 정도 쉬고, 저녁 8시부터 핵심 부분을 정리해보는 걸 추천해요.",
    "safety_note": "이 응답은 생활 코칭 목적이며, 의학적 진단이나 치료 조언이 아닙니다.",
  },
};

/// 가짜 전화 알림 Mock (`POST /api/v1/alerts/departure-plan`).
final Map<String, dynamic> mockCallAlert = {
  "success": true,
  "message": "알림 계획을 생성했습니다.",
  "data": {
    "schedule_id": "sch_001",
    "alert_plan": {
      "reminders": [
        {
          "reminder_id": "rem_003",
          "type": "mock_call",
          "trigger_datetime": "2026-07-02T09:30:00+09:00",
          "title": AppStrings.callAlertTitle(),
          "message": "팀 회의가 곧 시작돼요.",
          "screen": "voice_alert_screen",
          "notification_channel": "mock_call",
        },
      ],
      "checklist": [
        "노트북",
        "회의 자료",
        "필기구",
      ],
      "voice_alert_text": "${AppStrings.assistantNotifiesPrefix()} 팀 회의가 30분 후 시작돼요. 노트북과 회의 자료를 챙겨주세요.",
      "save_required_on_frontend": true,
    },
  },
};

/// TTS Mock 응답 생성기 (`POST /api/v1/voice/tts`).
/// 실제 음성 파일을 만들지 않고 재생할 문장만 반환한다.
Map<String, dynamic> mockTtsResponse(String text) {
  return {
    "success": true,
    "message": "Flutter TTS로 재생할 문장을 반환했습니다.",
    "data": {
      "mode": "flutter_tts",
      "text": text,
      "audio_url": null,
      "mime_type": null,
      "duration_seconds": null,
      "voice_id": "device_default",
      "cached": false,
    },
  };
}
