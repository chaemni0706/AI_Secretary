PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
  user_id TEXT PRIMARY KEY,
  display_name TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_settings (
  user_id TEXT PRIMARY KEY,
  timezone TEXT NOT NULL DEFAULT 'Asia/Seoul',
  locale TEXT NOT NULL DEFAULT 'ko-KR',
  default_reminder_minutes INTEGER CHECK (default_reminder_minutes IS NULL OR default_reminder_minutes >= 0),
  preferred_briefing_time TEXT,
  notification_persona TEXT,
  memory_enabled INTEGER NOT NULL DEFAULT 1 CHECK (memory_enabled IN (0,1)),
  emotion_coaching_enabled INTEGER NOT NULL DEFAULT 0 CHECK (emotion_coaching_enabled IN (0,1)),
  sensitive_data_consent INTEGER NOT NULL DEFAULT 0 CHECK (sensitive_data_consent IN (0,1)),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS calendars (
  calendar_id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  name TEXT NOT NULL,
  is_primary INTEGER NOT NULL DEFAULT 0 CHECK (is_primary IN (0,1)),
  is_visible INTEGER NOT NULL DEFAULT 1 CHECK (is_visible IN (0,1)),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_calendars_one_primary
ON calendars(user_id) WHERE is_primary = 1;

CREATE TABLE IF NOT EXISTS planner_items (
  item_id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  item_type TEXT NOT NULL CHECK (item_type IN ('EVENT','TODO')),
  title TEXT NOT NULL CHECK (length(trim(title)) > 0),
  description TEXT,
  category TEXT,
  status TEXT NOT NULL CHECK (status IN ('DRAFT','SCHEDULED','IN_PROGRESS','COMPLETED','CANCELLED')),
  priority TEXT NOT NULL DEFAULT 'MEDIUM' CHECK (priority IN ('HIGH','MEDIUM','LOW')),
  source_type TEXT NOT NULL DEFAULT 'MANUAL' CHECK (source_type IN ('MANUAL','AI','EXTERNAL_SYNC')),
  sort_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  deleted_at TEXT,
  FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_planner_items_dashboard
ON planner_items(user_id, deleted_at, status, sort_at);

CREATE TABLE IF NOT EXISTS event_details (
  item_id TEXT PRIMARY KEY,
  calendar_id TEXT NOT NULL,
  start_at TEXT NOT NULL,
  end_at TEXT,
  is_all_day INTEGER NOT NULL DEFAULT 0 CHECK (is_all_day IN (0,1)),
  location_text TEXT,
  travel_time_minutes INTEGER CHECK (travel_time_minutes IS NULL OR travel_time_minutes >= 0),
  external_event_id TEXT,
  CHECK (end_at IS NULL OR end_at > start_at),
  FOREIGN KEY (item_id) REFERENCES planner_items(item_id) ON DELETE CASCADE,
  FOREIGN KEY (calendar_id) REFERENCES calendars(calendar_id) ON DELETE RESTRICT
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_event_external_id
ON event_details(calendar_id, external_event_id)
WHERE external_event_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS todo_details (
  item_id TEXT PRIMARY KEY,
  due_at TEXT,
  planned_date TEXT,
  estimated_minutes INTEGER CHECK (estimated_minutes IS NULL OR estimated_minutes > 0),
  started_at TEXT,
  completed_at TEXT,
  FOREIGN KEY (item_id) REFERENCES planner_items(item_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS reminders (
  reminder_id TEXT PRIMARY KEY,
  item_id TEXT NOT NULL,
  reminder_type TEXT NOT NULL CHECK (reminder_type IN ('STANDARD','PREPARATION','DEPARTURE','WEATHER_CONTEXT')),
  trigger_at TEXT NOT NULL,
  channel TEXT NOT NULL DEFAULT 'LOCAL_NOTIFICATION',
  message_text TEXT,
  context_json TEXT,
  status TEXT NOT NULL DEFAULT 'SCHEDULED' CHECK (status IN ('SCHEDULED','SENT','CANCELLED','FAILED')),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (item_id) REFERENCES planner_items(item_id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_reminder_duplicate
ON reminders(item_id, reminder_type, trigger_at, channel);

CREATE TABLE IF NOT EXISTS user_memories (
  memory_id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  memory_type TEXT NOT NULL CHECK (memory_type IN ('PREFERENCE','PERSONA','PLACE','PREPARATION','PATTERN','FACT')),
  memory_key TEXT NOT NULL,
  memory_value_masked TEXT NOT NULL,
  tags_json TEXT,
  importance REAL CHECK (importance IS NULL OR (importance >= 0 AND importance <= 1)),
  confidence REAL CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
  is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_user_memories_lookup
ON user_memories(user_id, memory_type, is_active);

CREATE TABLE IF NOT EXISTS emotion_logs (
  emotion_log_id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  source_text_masked TEXT,
  primary_emotion TEXT,
  confidence REAL CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
  consent_snapshot INTEGER NOT NULL CHECK (consent_snapshot = 1),
  recorded_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS briefings (
  briefing_id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  briefing_type TEXT NOT NULL CHECK (briefing_type IN ('MORNING','DAILY','WEEKLY','ON_DEMAND')),
  content_text TEXT NOT NULL,
  context_snapshot_json TEXT,
  delivery_channel TEXT NOT NULL CHECK (delivery_channel IN ('IN_APP','TTS','PHONE')),
  status TEXT NOT NULL CHECK (status IN ('PENDING','READY','DELIVERED','FAILED')),
  generated_at TEXT NOT NULL,
  FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ai_local_requests (
  request_id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  input_mode TEXT NOT NULL CHECK (input_mode IN ('TEXT','VOICE')),
  input_text_masked TEXT,
  intent TEXT,
  processing_route TEXT NOT NULL CHECK (processing_route IN ('RULE','LLM','HYBRID')),
  confidence REAL CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
  result_json TEXT,
  status TEXT NOT NULL CHECK (status IN ('RECEIVED','PARSED','NEEDS_CONFIRMATION','EXECUTED','FAILED')),
  created_at TEXT NOT NULL,
  FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TRIGGER IF NOT EXISTS trg_event_item_type_insert
BEFORE INSERT ON event_details
FOR EACH ROW
WHEN (SELECT item_type FROM planner_items WHERE item_id = NEW.item_id) <> 'EVENT'
BEGIN
  SELECT RAISE(ABORT, 'event_details requires EVENT planner item');
END;

CREATE TRIGGER IF NOT EXISTS trg_todo_item_type_insert
BEFORE INSERT ON todo_details
FOR EACH ROW
WHEN (SELECT item_type FROM planner_items WHERE item_id = NEW.item_id) <> 'TODO'
BEGIN
  SELECT RAISE(ABORT, 'todo_details requires TODO planner item');
END;

-- =====================================================================
-- AI 가계부 (ledger) — 알림/영수증 기반 거래 기록.
-- planner_items 계열(일정/할일)과 완전히 독립된 신규 테이블. 기존 테이블·
-- 트리거·CHECK 는 일절 수정하지 않고 아래 정의만 추가한다(append only).
-- enum류는 기존 컨벤션대로 UPPERCASE 로 저장하고, API 응답은 소문자로 매핑한다
-- (planner_items 의 SCHEDULED↔scheduled 방식과 동일).
-- duplicated_transaction_id 는 자기참조 FK 를 걸지 않고 TEXT 로 두며, 원본
-- 참조 무결성은 LedgerService 계층에서 관리한다.
-- =====================================================================
CREATE TABLE IF NOT EXISTS ledger_transactions (
  transaction_id            TEXT PRIMARY KEY,
  user_id                   TEXT NOT NULL,

  -- 입력 출처
  source_type               TEXT NOT NULL
                              CHECK (source_type IN
                                ('NOTIFICATION','RECEIPT_SCAN','MANUAL','SEED')),
  app_name                  TEXT,          -- 알림 앱명(KB국민카드 등), 그 외 NULL
  title                     TEXT,          -- 알림 title
  raw_text                  TEXT,          -- 알림 body 또는 receipt_text 원문

  -- 거래 핵심
  merchant                  TEXT,
  normalized_merchant       TEXT,          -- dedup/카테고리용 정규화 상호명
  amount                    INTEGER NOT NULL DEFAULT 0
                              CHECK (amount >= 0),        -- KRW 정수(원)
  transaction_type          TEXT NOT NULL
                              CHECK (transaction_type IN
                                ('EXPENSE','INCOME','CANCEL','IGNORE')),

  -- 분류
  category                  TEXT,
  category_source           TEXT,          -- rule_based / mock_place_search /
                                           -- receipt_rule / notification_rule /
                                           -- category_mapping / llm / fallback /
                                           -- user_override
  confidence                REAL
                              CHECK (confidence IS NULL OR
                                     (confidence >= 0 AND confidence <= 1)),
  needs_user_confirmation   INTEGER NOT NULL DEFAULT 0
                              CHECK (needs_user_confirmation IN (0,1)),
  alternatives_json         TEXT,          -- JSON 배열 문자열, 없으면 NULL

  -- 시각 (기존 컨벤션: occurred_at=ISO datetime, date/time 분리 저장)
  occurred_at               TEXT,          -- 'YYYY-MM-DDTHH:MM:SS'
  date                      TEXT,          -- 'YYYY-MM-DD' (달력/집계 키)
  time                      TEXT,          -- 'HH:MM'

  -- 상태 / 중복
  status                    TEXT NOT NULL DEFAULT 'PENDING'
                              CHECK (status IN
                                ('PENDING','CONFIRMED','DUPLICATE',
                                 'DELETED','NEEDS_REVIEW')),
  duplicated_transaction_id TEXT,          -- 중복 시 원본 tx 참조(앱 계층 관리)
  dedup_key                 TEXT,          -- 정확 일치 지문(해시)
  source_hash               TEXT,          -- 원본 입력 해시(동일 알림 재전송 감지)

  -- 영수증 상세 / 반복결제
  items_json                TEXT,          -- JSON 배열 [{"name":..,"amount":..}]
  is_recurring              INTEGER NOT NULL DEFAULT 0
                              CHECK (is_recurring IN (0,1)),

  memo                      TEXT,          -- 사용자 자유 메모(선택)

  created_at                TEXT NOT NULL,
  updated_at                TEXT NOT NULL,

  FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- 대시보드/리포트: user + 날짜(월 범위) 조회
CREATE INDEX IF NOT EXISTS idx_ledger_tx_user_date
  ON ledger_transactions (user_id, date);

-- 정확 일치 dedup (동일 알림 재전송)
CREATE INDEX IF NOT EXISTS idx_ledger_tx_dedup
  ON ledger_transactions (user_id, dedup_key);

-- 퍼지 dedup 후보 (알림↔영수증 교차, merchant+amount 근사)
CREATE INDEX IF NOT EXISTS idx_ledger_tx_fuzzy
  ON ledger_transactions (user_id, normalized_merchant, amount);
