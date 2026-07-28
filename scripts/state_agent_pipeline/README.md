# NJ DCA incremental pipeline (scripts/state_agent_pipeline/)
#
# Architecture:
#   Socrata w9se-dmra (recordid watermark in state.json)
#     -> Model A Gemini Flash (high recall extract)
#     -> Model B Claude Sonnet (golden-record dedupe)
#     -> email asif@specindex.ai
#
# Daily cron: see CRON_SETUP.md / run_job.sh
#
# Manual:
#   python3 scripts/state_agent_pipeline/main.py --lookback-days 30 --limit 50 --notify
#   python3 scripts/state_agent_pipeline/main.py --dry-run
#   NJ_DCA_SKIP_LLM=1 NJ_DCA_LIMIT=25 ./scripts/state_agent_pipeline/run_job.sh
