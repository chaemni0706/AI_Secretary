CREATE TABLE IF NOT EXISTS model_versions (
  model_version_id UUID PRIMARY KEY,
  component VARCHAR(50) NOT NULL,
  model_name VARCHAR(100) NOT NULL,
  version VARCHAR(50) NOT NULL,
  configuration_json JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (component, model_name, version)
);

CREATE TABLE IF NOT EXISTS masked_ai_requests (
  request_id UUID PRIMARY KEY,
  device_pseudonym VARCHAR(128),
  input_mode VARCHAR(20) NOT NULL CHECK (input_mode IN ('TEXT','VOICE')),
  input_text_masked TEXT,
  intent VARCHAR(80),
  processing_route VARCHAR(20) NOT NULL CHECK (processing_route IN ('RULE','LLM','HYBRID')),
  rule_version VARCHAR(50),
  model_version_id UUID REFERENCES model_versions(model_version_id) ON DELETE SET NULL,
  status VARCHAR(30) NOT NULL,
  latency_ms INTEGER CHECK (latency_ms IS NULL OR latency_ms >= 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS masked_ai_responses (
  response_id UUID PRIMARY KEY,
  request_id UUID NOT NULL REFERENCES masked_ai_requests(request_id) ON DELETE CASCADE,
  output_json JSONB NOT NULL,
  confidence NUMERIC(5,4) CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS evaluation_results (
  evaluation_id UUID PRIMARY KEY,
  model_version_id UUID REFERENCES model_versions(model_version_id) ON DELETE SET NULL,
  dataset_name VARCHAR(200) NOT NULL,
  metric_name VARCHAR(100) NOT NULL,
  metric_value DOUBLE PRECISION NOT NULL,
  details_json JSONB,
  evaluated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS error_logs (
  error_id UUID PRIMARY KEY,
  request_id UUID REFERENCES masked_ai_requests(request_id) ON DELETE SET NULL,
  error_type VARCHAR(100) NOT NULL,
  message_masked TEXT,
  stack_hash VARCHAR(128),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
