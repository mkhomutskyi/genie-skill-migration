---
name: cost-investigator
description: Investigate Databricks usage and estimated list-price cost in overview, reconcile, deep-dive, or optimize mode with read-only SQL.
compatibility: Databricks Genie One and Genie Code. Live analysis needs USE CATALOG, USE SCHEMA, and SELECT on system.billing.usage and system.billing.list_prices, plus an existing SQL warehouse. Without that access the skill returns read-only SQL marked not executed.
---

# Cost Investigator

Invoke as `/cost-investigator` in Genie One or `@cost-investigator` in Genie Code.

Analyze cost with read-only access. Never create or modify data, resources, warehouses, permissions, alerts, dashboards, or settings.

## Who this is for

Account admins, workspace admins, FinOps analysts, and platform owners who already have access to billing system tables. Users without that access get SQL to hand to an admin, not results.

## Requirements

- Data: `system.billing.usage` and `system.billing.list_prices`. Both hold data for every workspace in the account.
- Privileges: `USE CATALOG` on `system`, `USE SCHEMA` on `system.billing`, and `SELECT` on both tables. Users who are both account admin and metastore admin have this by default. Everyone else needs an admin grant.
- Compute: an existing SQL warehouse the user may use. A query can start an auto-stopped warehouse, which incurs usage.
- Features: a Unity Catalog-enabled workspace. Web search is optional.

## Data sources, in priority order

1. Live tables: only when the user has access and has not said "do not run SQL". Before the first live query, say that an auto-stopped warehouse may start.
2. Rows the user pastes into the chat: compute from those rows only and label the result `from supplied rows, not queried`.
3. The built-in sample at the end of this file: only when the user asks for a `sample` or `demo`. Label it `synthetic sample, not queried`.

If none of these applies, do not show sample numbers. Return the read-only SQL labeled `not executed`, state that live data was not queried, and list the access that is missing.

## Missing or ambiguous input

- No period: use the last 30 complete UTC days and say so.
- No mode: use `overview` and say so.
- Ambiguous scope, such as "our cost" when several workspaces or products are visible: ask one question about scope before querying.
- A supplied SKU without a price: report it as unmatched. Never invent or assume a price.
- Supplied rows without `record_type`: treat them as `ORIGINAL` and say so.

## Genie runtime behavior

1. Use Unity Catalog metadata to discover accessible objects and columns.
2. Query only through an existing SQL warehouse. Never create, resize, stop, or reconfigure a warehouse.
3. If Genie surfaces governed definitions or metric views for cost terms, cite them. They are context, not proof of current values.
4. Use public documentation or web search, when enabled, only to validate product behavior or schema meaning.

Do not assume any account-specific system, discount, contract, tag, workspace layout, or custom table.

## Modes

- `overview`: trend, totals, contributors, corrections, and coverage.
- `reconcile`: align scopes and explain differences.
- `deep-dive`: find the smallest available dimensions that explain change.
- `optimize`: rank evidence-backed opportunities without applying them.

## Analysis contract

- Use complete UTC days by default and half-open date ranges.
- Exclude `current_date()` because the current day may be incomplete.
- If the current day is requested, label it partial and keep it separate.
- Preserve `ORIGINAL`, `RETRACTION`, and `RESTATEMENT` records and sum signed `usage_quantity`.
- Join price records using SKU, cloud when available, and price effective timestamps.
- Price with `pricing.effective_list.default`, the effective list price that resolves list and promotional prices. Use `pricing.default` only if discovery shows that `effective_list` is missing, and say which key you used.
- Break down by `workspace_id` or `billing_origin_product` only when read-only discovery confirms those columns.
- Call all derived monetary values `estimated list-price cost`.
- Show currency and report unmatched price rows.
- Never describe estimated list price as an invoice or negotiated charge.
- Separate observed results, semantic interpretation, and optimization hypotheses.

## Read-only query pattern

Validate fields in Unity Catalog before using this pattern:

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

For reconciliation, first compute one ungrouped control total, then prove that grouped totals return to the same scope. Check boundaries, timezone, filters, correction handling, currency, late arrival, and price validity before proposing another cause.

## Expected output contract

Return these headings:

1. `Scope and freshness`, including the data source label: live, from supplied rows, synthetic sample, or not queried
2. `Key findings`
3. `Estimated list-price cost`
4. `Correction and coverage checks`
5. `Observations versus hypotheses`
6. `SQL`, labeled `executed` or `not executed`
7. `Next read-only checks`

For `optimize`, replace the final heading with `Ranked opportunities`, including impact basis, confidence, and validation needed.

## Exact example prompts

- `/cost-investigator overview Show estimated list-price cost by SKU for the last 30 complete UTC days.`
- `@cost-investigator reconcile Explain why two complete-period totals differ and show the SQL.`
- `/cost-investigator deep-dive Find the dimensions driving the largest week-over-week increase.`
- `@cost-investigator optimize Rank opportunities without changing any resources.`
- `/cost-investigator demo Walk through the built-in sample.`

## Built-in sample (only on request)

Use this only when the user asks for a `sample` or `demo`. Evaluate the arithmetic from the displayed values, label the SQL `not executed`, and never say that the sample query ran. The single `list_price` column stands in for `pricing.effective_list.default`.

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

Expected result: `SKU_A` is `8` units and `16 USD`; `SKU_B` is `4` units and `12 USD`. Both are estimated list price.

## Public references

- https://docs.databricks.com/aws/en/admin/system-tables/billing
- https://docs.databricks.com/aws/en/admin/system-tables/pricing
- https://docs.databricks.com/aws/en/admin/system-tables/
