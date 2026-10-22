---
name: cost-investigator
description: Investigate Databricks usage and estimated list-price cost in overview, reconcile, deep-dive, or optimize mode using read-only evidence.
disable-model-invocation: true
---

# Cost Investigator

Investigate Databricks cost without changing data, compute, settings, budgets, or resources.

This is the Cursor variant. The Genie skill in `skills/cost-investigator` is the primary version.

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

## Invocation

Use `/cost-investigator <mode> <question>`.

Modes:

- `overview`: summarize complete-period usage and estimated cost.
- `reconcile`: explain differences between two totals, scopes, or time windows.
- `deep-dive`: isolate contributors by SKU, product, workspace, tags, or available usage metadata.
- `optimize`: rank evidence-backed opportunities without applying changes.

If no mode is given, use `overview`.

## Runtime adaptation

1. Inspect relevant local project context when it can clarify table names, SQL dialect, or the user's requested scope. Treat local files as context, not proof of live state.
2. If a Databricks connection is already configured, discover available columns and run only read-only metadata queries and `SELECT` statements.
3. Never hardcode or request a connection profile, token, host, warehouse identifier, or credential.
4. If no connection is available, return read-only SQL for the user to run. Do not imply that it ran.
5. Use only objects the user can access. The caller needs `SELECT` on the billing system tables. Start with `system.billing.usage` and `system.billing.list_prices`; add optional system tables only after confirming availability.

## Guardrails

- Never create, alter, optimize, repair, refresh, delete, insert, update, merge, grant, revoke, start, stop, or resize anything.
- Never send or post results.
- Never assume account-specific schemas, tags, discounts, contracts, currencies, or cloud configuration.
- Label list-price calculations as estimates. Do not call them invoices or negotiated charges.
- Default to complete UTC days. Exclude `current_date()` unless the user explicitly asks for partial-day data, and label that period incomplete.
- Preserve correction semantics. Include `ORIGINAL`, `RETRACTION`, and `RESTATEMENT` records and sum signed `usage_quantity`; do not silently discard correction rows.
- State scope, timezone, currency, filters, unavailable dimensions, and any unmatched price rows.

## Core method

### 1. Establish scope

Confirm or infer:

- mode
- UTC date range
- complete periods versus partial current day
- requested dimensions, including `workspace_id` or `billing_origin_product` when available
- whether the user wants usage units, estimated list price, or both

Use half-open time boundaries. For example, seven complete days means `usage_date >= date_sub(current_date(), 7)` and `usage_date < current_date()`.

### 2. Inspect before querying

Use read-only discovery such as `DESCRIBE TABLE` or information schema queries. Confirm:

- correction and quantity fields in `system.billing.usage`
- price validity fields and nested pricing fields in `system.billing.list_prices`
- which optional dimensions exist

Do not invent missing columns. Offer an adjusted query when a desired dimension is unavailable.

### 3. Estimate list-price cost

Join usage to prices on SKU, cloud when available, and the price validity interval:

```sql
WITH scoped_usage AS (
  SELECT *
  FROM system.billing.usage
  WHERE usage_date >= :start_date
    AND usage_date < :end_date
),
priced AS (
  SELECT
    u.usage_date,
    u.sku_name,
    u.usage_quantity,
    u.record_type,
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
FROM priced
GROUP BY sku_name, currency_code
ORDER BY estimated_list_cost DESC NULLS LAST
```

`pricing.effective_list.default` is the effective list price that resolves list and promotional prices. Use `pricing.default` only if inspection shows that `effective_list` is missing, and say which key you used.

If the inspected schema differs, adapt the query and disclose the change. Do not coalesce unmatched prices to zero.

### 4. Analyze by mode

- `overview`: totals, trend, top contributors, correction impact, coverage gaps.
- `reconcile`: normalize date boundaries, timezone, filters, currency, corrections, late-arriving records, price validity, and grouping before comparing.
- `deep-dive`: move from total to the smallest available explanatory dimensions; show contribution and change, not only rank.
- `optimize`: distinguish measured waste signals from ideas needing validation. Estimate opportunity ranges only when assumptions are explicit.

### 5. Built-in sample (only on request)

Use this only when the user asks for a `sample` or `demo`. Label it `synthetic sample, not queried`. Keep values unchanged so expected results are reproducible. The single `list_price` column stands in for `pricing.effective_list.default`.

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

Expected sample result: `SKU_A` has net usage `8` and estimated list cost `16 USD`; `SKU_B` has net usage `4` and estimated list cost `12 USD`.

## Output contract

Return exactly these sections:

1. `Scope and confidence`
2. `Findings`
3. `Cost table`
4. `Corrections and data quality`
5. `Read-only SQL`
6. `Optimization opportunities` for `optimize`, otherwise `Next checks`

Every monetary value must include currency and the label `estimated list price`. Separate observed facts from assumptions.

## Exact example prompts

- `/cost-investigator overview Show estimated list-price cost by SKU for the last 30 complete UTC days.`
- `/cost-investigator reconcile Reconcile this month's daily total with the sum by product.`
- `/cost-investigator deep-dive Explain the largest week-over-week cost contributors using available tags.`
- `/cost-investigator optimize Rank cost opportunities for the last 28 complete days without making changes.`

## Public references

- https://docs.databricks.com/aws/en/admin/system-tables/billing
- https://docs.databricks.com/aws/en/admin/system-tables/pricing
