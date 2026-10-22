---
name: workload-radar
description: Compare two complete seven-day Databricks workload windows for job, reliability, cost, query, and SQL warehouse changes.
compatibility: Databricks Genie One and Genie Code. Live analysis needs USE CATALOG, USE SCHEMA, and SELECT on the system.lakeflow, system.query, system.compute, and system.billing tables it reads, plus an existing SQL warehouse. Each missing source is reported as unavailable.
---

# Workload Radar

Invoke as `/workload-radar` in Genie One or `@workload-radar` in Genie Code.

This is a read-only diagnostic workflow. Never change jobs, schedules, queries, SQL warehouses, data, permissions, alerts, or resources.

## Who this is for

Workspace admins, platform owners, and on-call data engineers who already have access to system tables. Users without that access get SQL to hand to an admin, not results.

## Requirements

- Data, each one optional and checked separately:
  - jobs: `system.lakeflow.job_run_timeline` and `system.lakeflow.job_task_run_timeline`
  - queries: `system.query.history`
  - SQL warehouses: `system.compute.warehouse_events`
  - cost: `system.billing.usage` and `system.billing.list_prices`
- Privileges: `USE CATALOG` on `system`, `USE SCHEMA` on each system schema, and `SELECT` on each table. Users who are both account admin and metastore admin have this by default. Everyone else needs an admin grant.
- Compute: an existing SQL warehouse the user may use. A query can start an auto-stopped warehouse, which incurs usage.
- Features: a Unity Catalog-enabled workspace. Web search is optional.

## Data sources, in priority order

1. Live tables: only when the user has access and has not said "do not run SQL". Before the first live query, say that an auto-stopped warehouse may start.
2. Rows or numbers the user pastes into the chat: compute from those only and label the result `from supplied rows, not queried`.
3. The built-in sample at the end of this file: only when the user asks for a `sample` or `demo`. Label it `synthetic sample, not queried`.

If none of these applies, do not show sample numbers. Print the windows, return the read-only SQL labeled `not executed`, and mark every signal `unavailable (not queried)`.

## Missing or ambiguous input

- No window: use the default windows below and print the boundaries.
- A different window: use it, keep both windows the same length, and print the boundaries.
- A job, workspace, or warehouse the user names but you cannot see: say so. Do not substitute another one.
- Supplied data that covers only some signals: compute those and mark the rest `unavailable (not supplied)`.

## Genie adaptation

- Resolve accessible data through Unity Catalog.
- Use an existing SQL warehouse only. Never create, resize, stop, or reconfigure one.
- If Genie surfaces governed definitions or metric views for workload names or metrics, cite them. Validate operational facts against query results, not semantic definitions.
- Use public documentation or web search, when enabled, to verify current schema and product behavior.

Never assume a custom table, common identifier, private integration, or account-specific convention.

## Window definition

Compare complete UTC periods:

- current seven days: `date_sub(current_date(), 7)` inclusive to `current_date()` exclusive
- prior seven days: `date_sub(current_date(), 14)` inclusive to `date_sub(current_date(), 7)` exclusive

Print boundaries. Keep the incomplete current date out of both windows.

## Signal contract

Compare, when accessible:

1. run frequency
2. median and p95 duration
3. failures, timeouts, cancellations, and rates
4. explicit retries (`ONETIME_RETRY`) and retry rate, with repair-like attempts reported separately as a heuristic
5. net usage and estimated list-price cost
6. query count, latency, errors, and volume
7. SQL warehouse lifecycle and capacity-related events

Query each source separately. If one source is inaccessible, empty, or fails, mark only the signals that depend on it `unavailable` with the reason, and continue with the others. Do not derive retry count from naming patterns. Do not join sources unless Unity Catalog discovery confirms a reliable key.

For cost, retain correction records, sum signed usage, time-range join list prices with `pricing.effective_list.default`, show currency, and count unmatched usage. Call the result `estimated list-price cost`.

## Read-only query shape

Adapt only after checking column names:

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

`completed_at` assigns a completed run to one window. Summed slice durations exclude gaps between repaired attempts, and `max_by` preserves the last non-null result state. Confirm that the SQL session time zone is UTC before using these date boundaries.

`explicit_retry_runs` counts runs whose `trigger_type` is `ONETIME_RETRY`, which the jobs system table documents as a retry of a previous failed run. `repair_like_attempts_heuristic` counts extra non-null result states under one run identifier, the pattern the documentation's retry example uses. It usually means a repair, but it is not an official repair counter. Report the two counts separately, label the second `heuristic`, and never add them together.

Compute each source at its natural grain first. Reconcile control totals before combining summaries.

## Observations and hypotheses

An observation must quote a returned value and period delta. Keep `Observed changes` to values and deltas only; any "possibly", "may", "likely", "because", or "suggests" belongs under `Hypotheses and read-only tests`.

A hypothesis must include the missing evidence and a read-only validation query. Never claim that code changes, schedules, data growth, contention, or warehouse sizing caused an observed change unless the evidence proves it.

## Expected output contract

Return:

1. `Windows, freshness, and coverage`, including the data source label and which signals are unavailable and why
2. `Radar summary`
3. `Jobs`
4. `Reliability and retries`, with explicit retries and the repair-like heuristic reported separately
5. `Queries and SQL warehouses`
6. `Estimated list-price cost`
7. `Observed changes`
8. `Hypotheses and read-only tests`
9. `SQL`, labeled `executed` or `not executed`. When it is not executed, also list the access needed by name: `USE CATALOG` on `system`, `USE SCHEMA` on each schema, and `SELECT` on each table the SQL reads, such as `system.lakeflow.job_run_timeline` and `system.billing.usage`.

## Exact example prompts

- `/workload-radar Compare all visible workloads for the latest seven complete UTC days against the prior seven.`
- `@workload-radar Show job frequency, duration, failure, retry, and cost changes.`
- `/workload-radar Separate query and SQL warehouse observations from hypotheses.`
- `/workload-radar demo Walk through the built-in sample.`

## Built-in sample (only on request)

Use this only when the user asks for a `sample` or `demo`. Evaluate the arithmetic from the displayed values, label the SQL `not executed`, and never say that the sample query ran.

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

Expected result: runs rise `3 to 4`, median run duration `100 to 195` seconds, failures remain `1`, retries rise `0 to 1`, estimated list-price cost rises `20 to 32 USD`, and query errors rise `5 to 14`. The sample has no SQL warehouse events, so that signal is `unavailable`.

## Public references

- https://docs.databricks.com/aws/en/admin/system-tables/jobs
- https://docs.databricks.com/aws/en/admin/system-tables/query-history
- https://docs.databricks.com/aws/en/admin/system-tables/warehouse-events
- https://docs.databricks.com/aws/en/admin/system-tables/
