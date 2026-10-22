---
name: cost-investigator
description: Diagnose Databricks usage and estimated list-price cost with read-only SQL, correction-aware reconciliation, and optimization evidence.
argument-hint: "[overview|reconcile|deep-dive|optimize] [question]"
allowed-tools: Read, Grep, Glob
---

# Cost Investigator

Use this skill to answer cost questions without changing files outside the user's requested work, Databricks objects, compute, permissions, settings, or resources.

This is the Claude Code variant. The Genie skill in `skills/cost-investigator` is the primary version. `allowed-tools` pre-approves the listed read tools; it does not block other tools, so the execution policy below still applies.

## Requirements

- Data: `system.billing.usage` and `system.billing.list_prices`. Both hold data for every workspace in the account.
- Privileges: `USE CATALOG` on `system`, `USE SCHEMA` on `system.billing`, and `SELECT` on both tables, granted by an admin.
- Connection: an already configured Databricks connection for live results. Without one, return SQL labeled `not executed`.

## Data sources and missing input

- Query live tables only through an already configured connection, and only when the user has not said "do not run SQL".
- If the user pastes rows, compute from those rows only and label the result `from supplied rows, not queried`.
- Use the built-in sample only when the user asks for a `sample` or `demo`. Otherwise never show sample numbers.
- No period: use the last 30 complete UTC days and say so.
- Ambiguous scope: ask one question before querying.
- A SKU without a price is unmatched. Never invent or assume a price.

## Parse the request

Treat the first argument as one of:

- `overview`: complete-period trend and contributors
- `reconcile`: why two scoped totals differ
- `deep-dive`: progressively isolate drivers
- `optimize`: prioritize opportunities supported by measured signals

Default to `overview`. Treat all remaining arguments as the question and scope.

## Claude Code execution policy

- You may read nearby project files to identify SQL conventions and user-supplied object names.
- A local file can explain intent but cannot establish current usage or prices.
- You may use an already configured Databricks connection only for metadata reads and `SELECT` statements.
- Never choose or embed a profile, host, token, warehouse identifier, or credential.
- Before executing a command, verify it cannot write, deploy, start compute, modify state, or send data.
- If connectivity is absent or uncertain, stop execution and provide read-only SQL plus expected interpretation. Never claim the SQL ran.
- Never create helper files or bundled scripts. All sample SQL is inline.

## Evidence rules

Start with:

- `system.billing.usage`
- `system.billing.list_prices`

The caller needs `SELECT` on these billing system tables. Use optional system tables only when read-only discovery proves that they exist and are relevant. Break down by `workspace_id` or `billing_origin_product` only when the columns are available. Do not assume custom dimensions, discounts, contracts, or cloud layout.

Cost derived from public list prices must be called `estimated list-price cost`, with currency shown. It is not a bill or a negotiated charge.

Default to complete UTC days and a half-open interval. Exclude the current UTC date because ingestion can be incomplete. If the user requests today, show it separately as partial and do not compare it directly with complete days.

Corrections are part of the result:

- retain `ORIGINAL`, `RETRACTION`, and `RESTATEMENT`
- sum signed `usage_quantity`
- report correction impact
- flag late-arriving records when ingestion fields are available

## Investigation sequence

1. Restate mode, date range, timezone, currency expectation, and filters.
2. Inspect table schemas with read-only metadata commands.
3. Build a base usage CTE with exact boundaries.
4. Time-range join price records on SKU and cloud where those columns exist.
5. Count unmatched usage rows and never turn an unmatched price into zero cost.
6. Aggregate once for a control total, then by the requested dimensions.
7. Compare grouped sums back to the control total.
8. Report observations first, interpretations second.

Use this query shape after validating columns:

```sql
WITH scoped_usage AS (
  SELECT *
  FROM system.billing.usage
  WHERE usage_date >= :start_date
    AND usage_date < :end_date
    AND workspace_id = :workspace_id
),
priced_usage AS (
  SELECT
    u.*,
    p.currency_code,
    p.pricing.effective_list.default AS list_price,
    u.usage_quantity * p.pricing.effective_list.default AS estimated_list_cost
  FROM scoped_usage u
  LEFT JOIN system.billing.list_prices p
    ON u.sku_name = p.sku_name
   AND u.cloud = p.cloud
   AND u.usage_start_time >= p.price_start_time
   AND (p.price_end_time IS NULL OR u.usage_start_time < p.price_end_time)
)
SELECT
  sku_name,
  currency_code,
  SUM(usage_quantity) AS net_usage_quantity,
  SUM(estimated_list_cost) AS estimated_list_cost,
  COUNT_IF(list_price IS NULL) AS unmatched_usage_rows
FROM priced_usage
GROUP BY sku_name, currency_code
ORDER BY estimated_list_cost DESC NULLS LAST
```

Billing system tables hold every workspace in the account, so this pattern filters to one workspace by default. Set `:workspace_id` to the workspace the user means; it usually appears after `o=` in the workspace URL. If you do not know it, ask. Remove the filter only when the user asks for the whole account, and label the scope `account-wide`.

`pricing.effective_list.default` is the effective list price that resolves list and promotional prices. Use `pricing.default` only if inspection shows that `effective_list` is missing, and say which key you used.

Adapt only after schema inspection, and identify every adaptation.

## Mode-specific behavior

### Overview

Show control totals, daily trend, top contributors, correction share, incomplete data, and price coverage.

### Reconcile

Test boundary, timezone, filters, correction treatment, currency, grouping, late arrival, and price-validity differences in that order. Quantify each resolved difference.

### Deep-dive

Drill from SKU and billing product into available workspace, tag, identity, or usage metadata. Stop when the evidence no longer supports attribution.

### Optimize

Rank measured candidates by estimated impact and confidence. Phrase configuration changes as recommendations for user review, never actions. Include validation needed before adoption.

## Built-in sample (only on request)

Use this only when the user asks for a `sample` or `demo`. Label it `synthetic sample, not queried`. The single `list_price` column stands in for `pricing.effective_list.default`.

```sql
WITH usage AS (
  SELECT *
  FROM VALUES
    (DATE'2026-01-01', TIMESTAMP'2026-01-01 01:00:00', 'aws', 'SKU_A', 10.0, 'ORIGINAL'),
    (DATE'2026-01-02', TIMESTAMP'2026-01-02 01:00:00', 'aws', 'SKU_A', -10.0, 'RETRACTION'),
    (DATE'2026-01-02', TIMESTAMP'2026-01-02 01:00:00', 'aws', 'SKU_A', 8.0, 'RESTATEMENT'),
    (DATE'2026-01-02', TIMESTAMP'2026-01-02 02:00:00', 'aws', 'SKU_B', 4.0, 'ORIGINAL')
  AS t(usage_date, usage_start_time, cloud, sku_name, usage_quantity, record_type)
),
prices AS (
  SELECT *
  FROM VALUES
    ('aws', 'SKU_A', TIMESTAMP'2025-01-01 00:00:00', CAST(NULL AS TIMESTAMP), 'USD', 2.0),
    ('aws', 'SKU_B', TIMESTAMP'2025-01-01 00:00:00', CAST(NULL AS TIMESTAMP), 'USD', 3.0)
  AS t(cloud, sku_name, price_start_time, price_end_time, currency_code, list_price)
)
SELECT
  u.sku_name,
  SUM(u.usage_quantity) AS net_usage_quantity,
  SUM(u.usage_quantity * p.list_price) AS estimated_list_cost
FROM usage u
LEFT JOIN prices p
  ON u.cloud = p.cloud
 AND u.sku_name = p.sku_name
 AND u.usage_start_time >= p.price_start_time
 AND (p.price_end_time IS NULL OR u.usage_start_time < p.price_end_time)
GROUP BY u.sku_name
ORDER BY u.sku_name
```

The deterministic result is `SKU_A: 8 units, 16 USD` and `SKU_B: 4 units, 12 USD`, both estimated list price.

## Required output contract

Produce:

1. `Scope`
2. `Executive finding`
3. `Observed evidence`
4. `Estimated list-price breakdown`
5. `Corrections, coverage, and limitations`
6. `SQL used or SQL to run`
7. `Recommended checks` or `Optimization candidates`

Explicitly say `not executed` when returning SQL without a connection.

## Exact example prompts

- `/cost-investigator overview Show estimated list-price cost by SKU for the last 30 complete UTC days.`
- `/cost-investigator reconcile Explain why the daily total differs from the product total this month.`
- `/cost-investigator deep-dive Find the dimensions driving the largest seven-day increase.`
- `/cost-investigator optimize Prioritize read-only cost opportunities and show the evidence.`

## Public sources

- https://docs.databricks.com/aws/en/admin/system-tables/billing
- https://docs.databricks.com/aws/en/admin/system-tables/pricing
