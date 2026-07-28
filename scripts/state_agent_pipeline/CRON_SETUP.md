# NJ DCA daily cron setup

Incremental Socrata job for `data.nj.gov` dataset `w9se-dmra`.

## What it does

1. Reads `data/pipeline/nj-dca/state.json` (`last_processed_id`, `last_run_timestamp`)
2. Fetches only new commercial rows (`recordid > last_processed_id`), or last 30 days on first run
3. Model A: Gemini Flash extract
4. Model B: Claude Sonnet golden-record dedupe
5. Advances watermark only after a successful run
6. Emails **asif@specindex.ai** when the job finishes (success or failure)

## One-time setup

1. Ensure `.env` has SMTP creds (same as the API contact form):

```bash
EMAIL_SMTP_USERNAME=your-gmail@gmail.com
EMAIL_SMTP_PASSWORD=your-app-password
NJ_DCA_NOTIFY_TO=asif@specindex.ai
```

2. Make the wrapper executable:

```bash
chmod +x scripts/state_agent_pipeline/run_job.sh
```

3. Manual smoke test:

```bash
./scripts/state_agent_pipeline/run_job.sh
# or:
NJ_DCA_SKIP_LLM=1 NJ_DCA_LIMIT=25 ./scripts/state_agent_pipeline/run_job.sh
tail -n 50 data/pipeline/nj-dca/pipeline.log
```

## Install cron (daily 2:00 AM local time)

```bash
crontab -e
```

Add (replace `/path/to/specindex` with the real absolute path):

```cron
0 2 * * * /bin/bash /path/to/specindex/scripts/state_agent_pipeline/run_job.sh
```

`run_job.sh` already appends stdout/stderr to:

` /path/to/specindex/data/pipeline/nj-dca/pipeline.log `

If you also want a second copy in the crontab line:

```cron
0 2 * * * /bin/bash /Users/ahussain2373/Projects/specindex/scripts/state_agent_pipeline/run_job.sh >> /Users/ahussain2373/Projects/specindex/data/pipeline/nj-dca/cron.out 2>&1
```

## State file shape

`data/pipeline/nj-dca/state.json`:

```json
{
  "last_processed_id": "60025214",
  "last_run_timestamp": "2026-07-27T06:00:00",
  "last_composite_key": "2012:60025214",
  "last_fetched_count": 120,
  "last_extracted_count": 120,
  "last_golden_count": 95
}
```

On first run (`last_processed_id` missing or `"0"`), the job uses `--lookback-days 30` so it never full-pulls the multi-million-row dataset.

## Optional env knobs

| Variable | Effect |
|----------|--------|
| `NJ_DCA_LOOKBACK_DAYS` | First-run window (default 30) |
| `NJ_DCA_LIMIT` | Cap rows (testing) |
| `NJ_DCA_SKIP_LLM` | Set to `1` for deterministic passthrough |
| `NJ_DCA_MERGE_STATE` | Set to `1` to merge golden rows into `data/states/nj.json` |
| `NJ_DCA_NOTIFY_TO` | Override email recipient |
