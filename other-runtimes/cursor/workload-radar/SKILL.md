---
name: workload-radar
description: Compare the latest seven complete days with the prior seven for Databricks workload frequency, duration, reliability, cost, query, and warehouse signals.
disable-model-invocation: true
---

# Workload Radar

Use `/workload-radar <scope>` to detect material workload changes without modifying data, jobs, queries, warehouses, alerts, or settings.

## Runtime adaptation

- Inspect local project context only when it helps identify user-provided job names, query conventions, or intended scope.
- Use an already configured Databricks connection only for metadata reads and `SELECT` statements.
- Never hardcode or request profiles, credentials, hosts, tokens, or warehouse identifiers.
- If no connection exists, provide read-only SQL labeled `not executed` and mark every signal `unavailable (not queried)`. List the access needed by name: `USE CATALOG` on `system`, `USE SCHEMA` on each schema, and `SELECT` on each table the SQL reads.
- If the user pastes rows or numbers, compute from those only and label the result `from supplied rows, not queried`. Mark signals they do not cover `unavailable (not supplied)`.
- Use the built-in sample only when the user asks for a `sample` or `demo`. Otherwise never show sample numbers.
- If the user names a job, workspace, or warehouse you cannot see, say so. Do not substitute another one.
- Never claim a bundled script ran.

This is the Cursor variant. The Genie skill in `skills/workload-radar` is the primary version.

## Requirements

- Data, each source optional and checked separately: `system.lakeflow` job timelines, `system.query.history`, `system.compute.warehouse_events`, and `system.billing` usage and prices.
- Privileges: `USE CATALOG` on `system`, `USE SCHEMA` on each system schema, and `SELECT` on each table, granted by an admin.
- Connection: an already configured Databricks connection for live results.

## Comparison window

Use two adjacent, complete UTC windows:

- current: `date_sub(current_date(), 7)` through but excluding `current_date()`
- prior: `date_sub(current_date(), 14)` through but excluding `date_sub(current_date(), 7)`

Do not include the current incomplete day. If the user supplies another anchor or timezone, show the exact half-open boundaries.

## Accessible evidence

Discover schemas before querying. Use only available public system tables, commonly:

- `system.lakeflow.job_run_timeline`
- `system.lakeflow.job_task_run_timeline`
- `system.query.history`
- `system.compute.warehouse_events`
- `system.billing.usage`
- `system.billing.list_prices`

Some signals may not share a stable key. Do not fabricate joins. Present job, query, warehouse, and cost evidence as separate lenses when attribution cannot be proven.

## Required signals

Compare:

1. job run frequency
2. median and high-percentile duration
3. failures and failure rate
4. retries or rerun indicators when available
5. usage and estimated list-price cost
6. query count, latency, errors, and data volume when available
7. warehouse running, starting, stopping, or saturation-related signals when available

Use rates with denominators. Show absolute change and percent change, using `not comparable` when the prior value is zero.

## Workflow

1. Resolve scope and exact windows.
2. Check table freshness and coverage for both windows.
3. Compute one normalized period label in each source.
4. Aggregate each signal independently before joining summaries.
5. Rank changes by magnitude and operational relevance.
6. Separate evidence from possible explanations.
7. Propose only read-only follow-up checks.

Use this adaptable job query shape:

```sql
WITH completed_runs AS (
  SELECT
    workspace_id,
    job_id,
    run_id,
    MAX(period_end_time) AS completed_at,
    max_by(result_state, period_end_time) AS latest_result_state
  FROM system.lakeflow.job_run_timeline
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
)
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
```

The timeline can split runs longer than one hour across rows. Assign completed runs by their final slice, sum slice durations so repair gaps are excluded, keep the last non-null state with `max_by`, and count `ONETIME_RETRY` runs and repair-like attempts separately. Confirm that the SQL session time zone is UTC before using these date boundaries.

`explicit_retry_runs` counts runs whose `trigger_type` is `ONETIME_RETRY`, which the jobs system table documents as a retry of a previous failed run. `repair_like_attempts_heuristic` counts extra non-null result states under one run identifier, the pattern the documentation's retry example uses. It usually means a repair, but it is not an official repair counter. Report the two counts separately, label the second `heuristic`, and never add them together.

Query each source separately. If one source is inaccessible, empty, or fails, mark only the signals that depend on it `unavailable` with the reason, and continue with the others.

For cost, retain correction records and join `system.billing.usage` to `system.billing.list_prices` by SKU, cloud, and price validity interval, pricing with `pricing.effective_list.default`. Label the result `estimated list-price cost`, show currency, exclude the current day, and report unmatched rows.

## Observation discipline

`Observation` must be directly supported by returned rows, such as: run count rose from 40 to 58. Observations hold values and deltas only; any "possibly", "may", "likely", "because", or "suggests" belongs in a hypothesis.

`Hypothesis` must name the evidence still needed, such as: a schedule change could explain the increase; inspect read-only job metadata or deployment history.

Never state causality from correlation alone.

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

Expected headline: current runs rise from `3` to `4`, median run duration from `100` to `195` seconds, failures remain `1`, retries rise from `0` to `1`, estimated list-price cost rises from `20` to `32 USD`, and query errors rise from `5` to `14`.

## Output contract

Return exactly:

1. `Windows and coverage`
2. `Radar summary`
3. `Job signals`
4. `Query and warehouse signals`
5. `Estimated list-price cost`
6. `Observations`
7. `Hypotheses and validation`
8. `Read-only SQL`

Use `unavailable` instead of inventing a signal.

## Exact example prompts

- `/workload-radar Compare all workloads for the latest seven complete UTC days against the prior seven.`
- `/workload-radar Focus on job frequency, duration, failures, retries, and estimated list-price cost.`
- `/workload-radar Find query and warehouse regressions, then separate observations from hypotheses.`

## Public references

- https://docs.databricks.com/aws/en/admin/system-tables/jobs
- https://docs.databricks.com/aws/en/admin/system-tables/query-history
