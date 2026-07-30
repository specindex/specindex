-- Every LLM call from every call site (ingestion Flash/Sonnet, enrichment
-- passes, discovery chat, the /ask endpoints) logs one row here -- the
-- real, queryable cost-per-project metric that doesn't exist today. GCP
-- billing exports tell you total spend; this tells you spend BY PROJECT
-- and BY CALL SITE, which a budget circuit breaker and a "why did this
-- cost so much" query both need (docs/architecture-2026/01-data-platform.md).
--
-- grounding_requests_count is a Gemini-review finding, not part of the
-- original design: Vertex AI Search Grounding carries a FIXED per-search
-- fee (~$35/1,000 queries) independent of token count, which can dwarf
-- token cost by 10-50x on sparse prompts. A token-only cost model
-- silently under-calculates real spend by orders of magnitude -- this
-- column and its own price line item in the cost calculator exist
-- specifically to avoid that.
--
-- Idempotent -- safe to re-run.

BEGIN;

CREATE TABLE IF NOT EXISTS llm_call_log (
  id                       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  project_sk               BIGINT REFERENCES projects(project_sk) ON DELETE SET NULL,
  call_site                TEXT NOT NULL,
  model                    TEXT NOT NULL,
  input_tokens             INTEGER,
  output_tokens            INTEGER,
  grounding_requests_count INTEGER NOT NULL DEFAULT 0,
  estimated_cost_usd       NUMERIC(10,6),
  grounded                 BOOLEAN NOT NULL DEFAULT false,
  called_at                TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS llm_call_log_project_sk ON llm_call_log (project_sk);
CREATE INDEX IF NOT EXISTS llm_call_log_called_at ON llm_call_log (called_at);
CREATE INDEX IF NOT EXISTS llm_call_log_call_site ON llm_call_log (call_site, called_at);

COMMIT;
