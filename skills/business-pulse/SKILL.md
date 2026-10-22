---
name: business-pulse
description: Compare the latest complete business period with the prior period, validate data quality, and identify dimensional contributors using read-only analysis.
compatibility: Databricks Genie One and Genie Code. Live analysis needs SELECT on the table or metric view that holds the metric and an existing SQL warehouse. Without that, the skill works only on rows the user supplies.
---

# Business Pulse

Invoke as `/business-pulse` in Genie One or `@business-pulse` in Genie Code.

Produce a compact business brief without changing data, metrics, dashboards, SQL warehouses, pipelines, permissions, or resources.

## Who this is for

Analysts, business owners, and data team leads who want a short, checked explanation of what changed in one metric between two complete periods.

## Requirements

- Data: one table or metric view that holds the metric, a timestamp or period column, and the dimensions to break down by.
- Privileges: `USE CATALOG`, `USE SCHEMA`, and `SELECT` on that object.
- Compute: an existing SQL warehouse the user may use. A query can start an auto-stopped warehouse, which incurs usage.
- Features: a Unity Catalog-enabled workspace. Metric views and web search are optional.

## Data sources, in priority order

1. Live table or metric view: only when the user named it or you found exactly one clear match, the user has access, and the user has not said "do not run SQL". Before the first live query, say that an auto-stopped warehouse may start.
2. Rows the user pastes into the chat: compute from those rows only and label the result `from supplied rows, not queried`.
3. The built-in sample at the end of this file: only when the user asks for a `sample` or `demo`. Label it `synthetic sample, not queried`.

If none of these applies, do not show sample numbers. State that live data was not queried and ask for the missing input.

## Missing or ambiguous input

Ask before analyzing when any of these is missing or ambiguous. Ask at most three short questions in one message:

- the metric and how it is aggregated, such as sum of revenue or count of distinct users
- the period grain and the two periods to compare
- the table or metric view, if you found none or more than one candidate. Show the candidates you found and do not pick one for the user.

A metric name alone, such as "revenue" or "users", is not a definition. Ask what it includes and how it is aggregated, for example gross or net revenue, summed by order date. Ask this even when the candidate tables have a column with that name.

If the user supplied rows, infer the metric and periods from them and state your reading instead of asking.

## Genie runtime adaptation

1. Use Unity Catalog to discover accessible datasets, keys, timestamps, and dimensions.
2. Use an existing SQL warehouse only. Never create, resize, stop, or reconfigure one.
3. If Genie surfaces governed definitions or metric views for the metric, business calendar, or dimensions, cite them and prefer them over your own formula.
4. Confirm metric facts with read-only queries. Semantic definitions do not prove freshness or current values.
5. Use public documentation or web search, when enabled, only for current product behavior.

Never assume private data sources, account conventions, customer-specific dimensions, or unpublished definitions.

## Comparison setup

Resolve:

- metric numerator and denominator
- grain and timezone
- filters
- latest complete period
- immediately preceding comparable period
- dimensional breakdown

Use half-open boundaries. Prefer complete day, week, or month periods. Do not interpret the current partial period as complete.

## Freshness and completeness gate

For live data, check before interpreting:

- maximum event or update timestamp
- date or partition coverage
- row counts by period and subperiod
- null rates for metric and dimensions
- duplicate rate at the declared grain
- late-arrival pattern when ingestion timestamps exist
- denominator coverage for rates

Classify the result as `pass`, `caution`, or `fail`. If it fails, stop after documenting data quality and read-only validation steps.

For supplied rows or the built-in sample, classify the gate as `not applicable` and say that freshness was not checked. Still report missing periods, duplicate rows, and dimensions that appear in only one period.

## Contribution method

Apply identical formulas and filters to both periods. Compute current, prior, absolute delta, and percent delta when prior is nonzero.

Call a dimension a contributor, not a cause.

### Metric type decides the method

Classify the metric before you compare. If you cannot tell from its definition, ask.

- Additive: a sum, or a count where each row belongs to exactly one dimension value. Dimension deltas add up to the total delta, so rank them and show the reconciliation.
- Ratio, rate, or average: compute the total from the total numerator and the total denominator, never by adding or averaging dimension values. For each dimension, show numerator, denominator, and value in both periods. Say that dimension changes do not add up to the total change. If the user asks for a split, show a mix and rate decomposition with its formula.
- Distinct count, such as active users: compute the total with its own distinct count. One entity can appear under several dimension values, so dimension counts overlap and do not add up to the total. Say so.

The SQL below handles additive metrics only.

### Raw table, additive metric

After Unity Catalog discovery, adapt:

```sql
WITH scoped AS (
  SELECT
    CASE
      WHEN event_time >= :current_start AND event_time < :current_end THEN 'current'
      WHEN event_time >= :prior_start AND event_time < :prior_end THEN 'prior'
    END AS period,
    dimension_name,
    metric_value
  FROM catalog.schema.fact_table
  WHERE event_time >= :prior_start
    AND event_time < :current_end
),
aggregated AS (
  SELECT period, dimension_name, SUM(metric_value) AS metric_value
  FROM scoped
  WHERE period IS NOT NULL
  GROUP BY period, dimension_name
)
SELECT
  dimension_name,
  SUM(CASE WHEN period = 'current' THEN metric_value ELSE 0 END) AS current_value,
  SUM(CASE WHEN period = 'prior' THEN metric_value ELSE 0 END) AS prior_value,
  SUM(CASE WHEN period = 'current' THEN metric_value ELSE -metric_value END) AS contribution_delta
FROM aggregated
GROUP BY dimension_name
ORDER BY ABS(contribution_delta) DESC
```

`catalog.schema.fact_table` is a placeholder. Never present a result as live when it uses an invented object name.

### Metric views

If the metric is a measure in a metric view, evaluate it with `MEASURE()`. In Databricks Runtime 18.1 and above, `agg()` is also documented. Never wrap a measure in `SUM`, `AVG`, or `COUNT`, and never use `SELECT *`. Read the measure and field names first with `DESCRIBE TABLE EXTENDED <metric_view> AS JSON`. Query the total and the breakdown separately for each period, because a measure at the total grain is not the sum of its dimension values unless it is additive. A metric view cannot be joined directly; wrap its query in a CTE first.

```sql
SELECT MEASURE(`Metric Name`) AS current_value
FROM catalog.schema.metric_view
WHERE `Event Date` >= :current_start AND `Event Date` < :current_end;

SELECT `Dimension Name`, MEASURE(`Metric Name`) AS current_value
FROM catalog.schema.metric_view
WHERE `Event Date` >= :current_start AND `Event Date` < :current_end
GROUP BY `Dimension Name`;
```

Run the same two queries for the prior period. All names are placeholders.

## Expected output contract

Return:

1. `Metric definition and periods`, including the metric type and the data source label: live, from supplied rows, synthetic sample, or not queried
2. `Freshness and completeness`: `pass`, `caution`, `fail`, or `not applicable`. For supplied rows or the sample, the label is always `not applicable`; list completeness notes, such as a dimension that appears in one period only, under the label without changing it
3. `Executive brief`, five bullets at most
4. `Period comparison`
5. `Top dimensional contributors`
6. `Interpretation boundaries`
7. `SQL`, labeled `executed` or `not executed`
8. `Next read-only checks`

The executive brief is no more than five bullets. Put any further points in later sections. Every material claim must point to a displayed metric or quality result.

Before you answer, check:

- The executive brief has five bullets or fewer, in the chat and in any document you create.
- The gate label follows the rule above.
- No rank-change words between dimension values, such as "overtook", "passed", or "became the second largest". Report each value's delta and, if useful, its share of the total in both periods.
- Every other comparison between dimensions or periods matches the displayed numbers for both periods.
- No claim that a change is normal, typical, or noise unless you queried and displayed a baseline of more periods.
- When gains and losses nearly offset, say which side is larger and show both totals.

## Exact example prompts

- `/business-pulse Compare completed monthly revenue with the prior month and identify regional contributors.`
- `@business-pulse Check freshness, then explain the latest complete week's active-user change by product.`
- `/business-pulse Use the governed metric definition if available, show SQL, and do not modify anything.`
- `/business-pulse demo Walk through the built-in sample.`

## Built-in sample (only on request)

Use this only when the user asks for a `sample` or `demo`. Evaluate the arithmetic from the displayed values, label the SQL `not executed`, and never say that the sample query ran.

```sql
WITH sample AS (
  SELECT *
  FROM VALUES
    (DATE'2026-01-01', 'North', 100.0),
    (DATE'2026-01-01', 'South', 80.0),
    (DATE'2026-02-01', 'North', 130.0),
    (DATE'2026-02-01', 'South', 70.0),
    (DATE'2026-02-01', 'West', 20.0)
  AS t(period_start, region, metric_value)
),
periods AS (
  SELECT
    CASE
      WHEN period_start = DATE'2026-02-01' THEN 'current'
      WHEN period_start = DATE'2026-01-01' THEN 'prior'
    END AS period,
    region,
    metric_value
  FROM sample
),
by_region AS (
  SELECT period, region, SUM(metric_value) AS metric_value
  FROM periods
  GROUP BY period, region
)
SELECT
  region,
  SUM(CASE WHEN period = 'current' THEN metric_value ELSE 0 END) AS current_value,
  SUM(CASE WHEN period = 'prior' THEN metric_value ELSE 0 END) AS prior_value,
  SUM(CASE WHEN period = 'current' THEN metric_value ELSE -metric_value END) AS contribution_delta
FROM by_region
GROUP BY region
ORDER BY ABS(contribution_delta) DESC
```

Expected sample: the total rises from `180` to `220`, up `40` or `22.2%`. North contributes `+30`, West `+20`, and South `-10`. Freshness is `not applicable` because the rows are synthetic. West appears only in the current period.
