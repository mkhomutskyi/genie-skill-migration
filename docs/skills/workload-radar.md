# workload-radar

## Purpose and user

Compares the last seven complete UTC days with the seven before them: job runs, duration, failures, retries, estimated list-price cost, queries, and SQL warehouse events. It separates what the data shows from guesses about why. It is read-only.

It is for workspace admins, platform owners, and on-call data engineers who can already read system tables. Other users get SQL to hand to an admin.

## Requirements

Each source is optional and checked on its own. A missing source makes only its signals `unavailable`.

- Jobs: `system.lakeflow.job_run_timeline` and `system.lakeflow.job_task_run_timeline`
- Queries: `system.query.history`
- SQL warehouses: `system.compute.warehouse_events`
- Cost: `system.billing.usage` and `system.billing.list_prices`
- `USE CATALOG` on `system`, `USE SCHEMA` on each schema, and `SELECT` on each table. Account admins who are also metastore admins have this by default.
- An existing SQL warehouse. A query can start an auto-stopped warehouse.

## Install and invoke

Create a folder named `workload-radar` in your personal skills folder and upload `skills/workload-radar/SKILL.md` into it. Check first that no skill with that name exists.

- Genie One documents `/Workspace/Users/{email}/.assistant/skills/`.
- Genie Code documents `/Users/{username}/.assistant/skills/`. It can also load skills from a registered folder.

In the workspace I tested, both paths pointed to the same home folder, and one upload appeared in both products.

Start a new chat, then type `/workload-radar` in Genie One or `@workload-radar` in Genie Code. See [Install, invoke and verify](../install-and-verify.md) for the commands.

## Example with supplied numbers

Exact prompt:

```text
/workload-radar Do not run SQL. Use only these numbers. Prior window: job_x ran 3 times, taking 300, 420 and 360 seconds; the 420-second run FAILED. Current window: job_x ran 4 times, taking 540, 600, 480 and 510 seconds; the 480-second run TIMED_OUT and the 510-second run was a ONETIME_RETRY. Estimated list-price cost: prior 50 USD, current 65 USD. I have no query or SQL warehouse data.
```

Expected behavior:

- Runs go from 3 to 4. Median duration goes from 360 to 525 seconds.
- Non-success runs stay at 1 (FAILED, then TIMED_OUT). Retries go from 0 to 1.
- Estimated list-price cost goes from 50 to 65 USD, up 30%.
- Query and SQL warehouse signals are `unavailable (not supplied)`. The other signals are still reported.
- The result is labeled `from supplied rows, not queried`.

A common wrong answer: 532.5 seconds is the mean, not the median.

## Missing-input test

Exact prompt:

```text
/workload-radar Compare my workloads this week against last week. Do not run SQL.
```

Expected behavior: both windows with exact boundaries, read-only SQL labeled `not executed`, every signal `unavailable (not queried)`, and the access needed. No numbers from the built-in sample.

## Limitations

- Retries come in two separate counts. `explicit_retry_runs` counts runs with `trigger_type = 'ONETIME_RETRY'`. `repair_like_attempts_heuristic` counts extra non-null result states under one run identifier, the pattern the jobs documentation uses in its retry example. It usually means a repair, but it is not an official counter, so it is labeled `heuristic` and never added to the explicit count.
- Job, query, warehouse, and cost signals are not joined unless a reliable key exists, so it does not attribute cost to a job.
- System tables update during the day, so the current day is excluded.
- Genie One reads related past conversations on its own and cites them as "Read past conversation". In one earlier test it copied a wrong sentence from a recalled test chat of the same skill. A new chat picks up skill edits, but it does not stop recall. Check the recall citations before you judge an answer. In my tests, I removed my own earlier test chats before rerunning a case. See [Live results](../live-results.md).

## SQL checks

The job query in `skills/workload-radar/SKILL.md` runs in `tests/test_sql_fixtures.py` on local Apache Spark against a small made-up timeline: a run split into hourly slices, a run repaired after a failure, a `ONETIME_RETRY` run, a run that crosses the window boundary, a run that never started, and runs outside both windows. This checks the query logic only. It was not run on Databricks system tables.

## Changes in this revision

- Added who it is for, a requirements block, and a `compatibility` field.
- Each source now degrades on its own to `unavailable` with a reason.
- Explicit retries and the repair-like heuristic are separate columns. An earlier version added them into one `retry_count`.
- Cost uses `pricing.effective_list.default`.
- The built-in sample now runs only on request (`sample` or `demo`).
- `Observed changes` holds values and deltas only. Words such as "possibly", "likely" or "because" belong under hypotheses.
- When SQL is not executed, the access needed is listed by name: `USE CATALOG`, `USE SCHEMA`, and `SELECT` on each table.

## Test history

The 2026-10-14 "10 of 10 passed" run used prompts that asked for the sample whose answer is written in the skill. It shows the skill loaded and followed its sample, not that it computes correctly. The cases in `evals/held_out.json` replace it.

Final live run, 2026-10-20 to 2026-10-22, on SKILL.md hash `00ab1759915b`: the held-out and missing-input cases met their checklists in Genie One (`/`) and Genie Code (`@`). Both held-out answers showed the repair-like heuristic as 0, although the supplied numbers cannot measure it, and the Genie Code answer said a 30% cost rise "outpaces" a 33% rise in runs. Neither error is on the checklist. The failures found on the way, and the fixes, are listed in [Live results](../live-results.md).

## Sources

- https://docs.databricks.com/aws/en/admin/system-tables/jobs
- https://docs.databricks.com/aws/en/admin/system-tables/query-history
- https://docs.databricks.com/aws/en/admin/system-tables/warehouse-events
- https://docs.databricks.com/aws/en/admin/system-tables/
