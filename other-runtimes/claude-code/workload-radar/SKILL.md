---
name: workload-radar
description: Detect seven-day Databricks workload changes across jobs, reliability, cost, queries, and SQL warehouses using read-only evidence.
argument-hint: "[scope or question]"
allowed-tools: Read, Grep, Glob
---

# Workload Radar

Compare the latest seven complete days with the preceding seven complete days. Diagnose, but do not alter, workload behavior.

## Claude Code operating rules

1. Read local project files only to understand user-provided workload names, SQL style, or intended filters.
2. Treat repository configuration as context, never as proof of current operations.
3. Use a configured Databricks connection only if one is already available, and only for read-only metadata and `SELECT` queries.
4. Do not select, embed, or request a profile, host, token, credential, or warehouse identifier.
5. Inspect every command before execution. Reject any command that could write, deploy, trigger a run, change a schedule, or manage compute.
6. When no safe connection exists, produce SQL marked `not executed` and mark every signal `unavailable (not queried)`. List the access needed by name: `USE CATALOG` on `system`, `USE SCHEMA` on each schema, and `SELECT` on each table the SQL reads.
7. If the user pastes rows or numbers, compute from those only and label the result `from supplied rows, not queried`. Mark signals they do not cover `unavailable (not supplied)`.
8. Use the built-in sample only when the user asks for a `sample` or `demo`. Otherwise never show sample numbers.
9. If the user names a job, workspace, or warehouse you cannot see, say so. Do not substitute another one.

This is the Claude Code variant. The Genie skill in `skills/workload-radar` is the primary version. `allowed-tools` pre-approves the listed read tools; it does not block other tools, so the rules above still apply.

## Requirements

- Data, each source optional and checked separately: `system.lakeflow` job timelines, `system.query.history`, `system.compute.warehouse_events`, and `system.billing` usage and prices.
- Privileges: `USE CATALOG` on `system`, `USE SCHEMA` on each system schema, and `SELECT` on each table, granted by an admin.
- Connection: an already configured Databricks connection for live results.

## Fixed default windows

In UTC:

- `current_7d`: `date_sub(current_date(), 7)` inclusive to `current_date()` exclusive
- `prior_7d`: `date_sub(current_date(), 14)` inclusive to `date_sub(current_date(), 7)` exclusive

Never mix the incomplete current day into the default comparison. If the request uses a different timezone, anchor both windows consistently and print their boundaries.

## Source discovery

Discover accessible tables and columns first. Candidate public system tables include:

- `system.lakeflow.job_run_timeline`
- `system.lakeflow.job_task_run_timeline`
- `system.query.history`
- `system.compute.warehouse_events`
- `system.billing.usage`
- `system.billing.list_prices`

Use only confirmed columns. Do not force joins between sources lacking a validated common key. Separate lenses are preferable to false attribution.

## Measurement plan

For each period calculate, where visible:

- distinct job runs and runs per day
- median and p95 run duration
- failed, timed out, and canceled outcomes with rates
- explicit retry count or retry rate
- net usage and estimated list-price cost by currency
- query count, median and p95 duration, error rate, and scanned or returned volume
- SQL warehouse event counts, running intervals, and capacity signals

Report numerator and denominator for every rate. For change percentages, use `not comparable` when the prior denominator is zero.

## Query construction

After validating fields, adapt:

```sql
WITH completed_runs AS (
  SELECT
    workspace_id,
    job_id,
    run_id,
    MAX(period_end_time) AS completed_at,
    max_by(result_state, period_end_time) AS latest_result_state
  FROM system.lakeflow.job_run_timeline
  WHERE workspace_id = :workspace_id
  GROUP BY workspace_id, job_id, run_id
  HAVING completed_at >= date_sub(current_date(), 14)
     AND completed_at < current_date()
     AND latest_result_state IS NOT NULL
),
run_slices AS (
  SELECT
    t.workspace_id,
    t.job_id,
    t.run_id,
    c.completed_at,
    t.trigger_type,
    t.result_state,
    t.period_start_time,
    t.period_end_time
  FROM system.lakeflow.job_run_timeline t
  INNER JOIN completed_runs c
    USING (workspace_id, job_id, run_id)
),
runs AS (
  SELECT
    CASE
      WHEN completed_at >= date_sub(current_date(), 7) THEN 'current_7d'
      ELSE 'prior_7d'
    END AS period,
    workspace_id,
    job_id,
    run_id,
    max_by(trigger_type, period_end_time) AS trigger_type,
    max_by(result_state, period_end_time)
      FILTER (WHERE result_state IS NOT NULL) AS result_state,
    SUM(timestampdiff(SECOND, period_start_time, period_end_time)) AS duration_seconds,
    GREATEST(COUNT_IF(result_state IS NOT NULL) - 1, 0) AS repair_like_attempts
  FROM run_slices
  GROUP BY completed_at, workspace_id, job_id, run_id
),
job_summary AS (
  SELECT
    period,
    workspace_id,
    job_id,
    COUNT(*) AS run_count,
    median(duration_seconds) AS median_duration_seconds,
    percentile_approx(duration_seconds, 0.95) AS p95_duration_seconds,
    COUNT_IF(
      result_state IN ('FAILED', 'TIMED_OUT', 'CANCELLED', 'ERROR')
    ) AS non_success_count,
    COUNT_IF(trigger_type = 'ONETIME_RETRY') AS explicit_retry_runs,
    SUM(repair_like_attempts) AS repair_like_attempts_heuristic
  FROM runs
  GROUP BY period, workspace_id, job_id
)
SELECT *
FROM (
  SELECT
    *,
    row_number() OVER (
      PARTITION BY period
      ORDER BY non_success_count DESC, run_count DESC, job_id
    ) AS job_rank
  FROM job_summary
)
WHERE job_rank <= 20
ORDER BY period, job_rank
```

The jobs system tables can include other workspaces in the account, so the query filters to one workspace by default. Set `:workspace_id` to the workspace the user means; it usually appears after `o=` in the workspace URL. If you do not know it, ask. Remove the filter only when the user asks for the whole account. The query returns at most 20 jobs per window, ranked by non-successful runs and then run count. Compute window totals from `runs` without the rank filter and reconcile them before you summarize. If `explicit_retry_runs` is 0 in both windows, write `no explicit retries observed`; do not describe retries as healthy. If the workspace's newest job record is older than the window end, compare it with the newest record in the whole table before you call the job data late or incomplete. When the table is current, write `no completed runs after <timestamp>`.

The timeline can split runs longer than one hour across rows. Assign completed runs by their final slice, sum slice durations so repair gaps are excluded, keep the last non-null state with `max_by`, and count `ONETIME_RETRY` runs and repair-like attempts separately. Confirm that the SQL session time zone is UTC before using these date boundaries.

`explicit_retry_runs` counts runs whose `trigger_type` is `ONETIME_RETRY`, which the jobs system table documents as a retry of a previous failed run. `repair_like_attempts_heuristic` counts extra non-null result states under one run identifier, the pattern the documentation's retry example uses. It usually means a repair, but it is not an official repair counter. Report the two counts separately, label the second `heuristic`, and never add them together.

Query each source separately. If one source is inaccessible, empty, or fails, mark only the signals that depend on it `unavailable` with the reason, and continue with the others.

Estimate cost separately with `system.billing.usage` and `system.billing.list_prices`, pricing with `pricing.effective_list.default`. Preserve correction rows, sum signed quantities, use price validity intervals, show currency, and count unmatched prices. Always label the metric `estimated list-price cost`.

## Interpretation protocol

Write all direct evidence under `Observations`. Include exact period values and deltas. Observations hold values and deltas only; any "possibly", "may", "likely", "because", or "suggests" belongs under `Hypotheses`.

Write all possible explanations under `Hypotheses`. For each hypothesis specify:

- supporting observation
- contradicting or missing evidence
- next read-only query that could test it

Do not present schedule change, code change, data growth, contention, or warehouse sizing as causal without evidence.

## Built-in sample (only on request)

Use this only when the user asks for a `sample` or `demo`. Label it `synthetic sample, not queried`.

```sql
WITH runs AS (
  SELECT *
  FROM VALUES
    ('prior_7d', 'job_a', 'p1', 100, 'SUCCEEDED', false),
    ('prior_7d', 'job_a', 'p2', 120, 'FAILED', false),
    ('prior_7d', 'job_b', 'p3', 60, 'SUCCEEDED', false),
    ('current_7d', 'job_a', 'c1', 180, 'SUCCEEDED', false),
    ('current_7d', 'job_a', 'c2', 240, 'FAILED', false),
    ('current_7d', 'job_a', 'c3', 210, 'SUCCEEDED', true),
    ('current_7d', 'job_b', 'c4', 60, 'SUCCEEDED', false)
  AS t(period, job_id, run_id, duration_seconds, result_state, is_retry)
),
cost AS (
  SELECT *
  FROM VALUES
    ('prior_7d', 'USD', 20.0),
    ('current_7d', 'USD', 32.0)
  AS t(period, currency_code, estimated_list_cost)
),
queries AS (
  SELECT *
  FROM VALUES
    ('prior_7d', 100, 5, 4.0),
    ('current_7d', 140, 14, 6.0)
  AS t(period, query_count, error_count, median_duration_seconds)
)
SELECT
  r.period,
  COUNT(*) AS runs,
  median(r.duration_seconds) AS median_run_seconds,
  COUNT_IF(r.result_state = 'FAILED') AS failures,
  COUNT_IF(r.is_retry) AS retries,
  MAX(c.estimated_list_cost) AS estimated_list_cost_usd,
  MAX(q.query_count) AS queries,
  MAX(q.error_count) AS query_errors,
  MAX(q.median_duration_seconds) AS median_query_seconds
FROM runs r
JOIN cost c ON r.period = c.period
JOIN queries q ON r.period = q.period
GROUP BY r.period
ORDER BY r.period
```

Expected result: runs `3 to 4`; median run duration `100 to 195` seconds; failures `1 to 1`; retries `0 to 1`; estimated list-price cost `20 to 32 USD`; query errors `5 to 14`.

## Required response

Use these sections:

1. `Coverage and freshness`
2. `Seven-day comparison`
3. `Job frequency and duration`
4. `Failure and retry signals`
5. `Query and warehouse signals`
6. `Estimated list-price cost`
7. `Observations`
8. `Hypotheses`
9. `SQL used or SQL to run`

Mark unsupported metrics `unavailable`.

## Exact example prompts

- `/workload-radar Compare the latest seven complete UTC days to the prior seven across all visible workloads.`
- `/workload-radar Identify job reliability regressions and include denominators.`
- `/workload-radar Compare query latency, errors, warehouse signals, and estimated list-price cost.`

## Public sources

- https://docs.databricks.com/aws/en/admin/system-tables/jobs
- https://docs.databricks.com/aws/en/admin/system-tables/query-history
