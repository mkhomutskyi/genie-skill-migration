---
name: business-pulse
description: Produce a concise read-only business metric brief comparing the latest complete period with the prior period after freshness and completeness checks.
disable-model-invocation: true
---

# Business Pulse

Use `/business-pulse <metric and scope>` to explain what changed, which dimensions contributed, and what should be checked next.

## Runtime adaptation

1. Inspect local project context for user-defined metric SQL, schemas, tests, and sample data.
2. Prefer the project's existing metric definition over inventing one, but state the selected numerator, denominator, grain, timezone, and filters.
3. If a Databricks connection is already configured, use only metadata reads and `SELECT` queries.
4. Never hardcode or request a profile, credential, host, token, or warehouse identifier.
5. If no connection exists, produce read-only SQL labeled `not executed` and state that live data was not queried.
6. If the user pastes rows, compute from those rows only and label the result `from supplied rows, not queried`.
7. Use the built-in sample only when the user asks for a `sample` or `demo`. Otherwise never show sample numbers.

Never write data, create metrics or views, refresh pipelines, modify dashboards, send reports, or change resources.

This is the Cursor variant. The Genie skill in `skills/business-pulse` is the primary version.

## Requirements and missing input

- Data: one table, view, or local metric definition that holds the metric, a timestamp or period column, and the breakdown dimensions. Live values need `SELECT` on it through an already configured connection.
- If the metric, the periods, or the source object is missing or ambiguous, ask at most three short questions in one message before analyzing. Show candidate objects you found and do not pick one for the user.
- If the user supplied rows, infer the metric and periods from them and state your reading instead of asking.

## Period selection

Choose the smallest sensible complete business period from the request:

- day: latest complete day versus previous day
- week: latest complete seven-day or calendar week versus prior matching week
- month: latest complete calendar month versus previous calendar month

State timezone and exact half-open boundaries. Do not interpret a partial current period as complete.

## Freshness and completeness gate

Before interpreting movement, check:

- maximum event or update timestamp
- row counts by period and day
- missing expected dates or partitions
- null rates for metric and key dimensions
- duplicate rate at the intended grain when a key exists
- late-arrival behavior when ingestion timestamps exist
- consistent filters and denominator coverage

Classify the gate:

- `pass`: both periods are comparable
- `caution`: limitations are quantified and interpretation remains useful
- `fail`: evidence is too incomplete for a reliable conclusion

On `fail`, stop causal interpretation and provide only data-quality findings and read-only checks.

For supplied rows or the built-in sample, classify the gate as `not applicable` and say that freshness was not checked. Still report missing periods, duplicate rows, and dimensions that appear in only one period.

## Analysis method

1. Define one base relation and assign `current` or `prior`.
2. Compute period totals using identical logic.
3. Calculate absolute and percent change. If prior is zero, use `not comparable`.
4. Group by candidate dimensions such as region, product, channel, segment, or platform only when those columns exist.
5. For additive metrics, rank contributors by signed delta and verify that dimensional deltas reconcile to the total delta. For other metric types, follow the rules below.
6. Distinguish contribution from causation.
7. Produce a short brief with links only when supplied by the user or returned by public documentation.

### Metric type decides the method

Classify the metric before you compare. If you cannot tell from its definition, ask.

- Additive: a sum, or a count where each row belongs to exactly one dimension value. Dimension deltas add up to the total delta, so rank them and show the reconciliation.
- Ratio, rate, or average: compute the total from the total numerator and the total denominator, never by adding or averaging dimension values. For each dimension, show numerator, denominator, and value in both periods. Say that dimension changes do not add up to the total change. If the user asks for a split, show a mix and rate decomposition with its formula.
- Distinct count, such as active users: compute the total with its own distinct count. One entity can appear under several dimension values, so dimension counts overlap and do not add up to the total. Say so.

The SQL below handles additive metrics only.

Adapt this SQL pattern:

```sql
WITH base AS (
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
by_dimension AS (
  SELECT period, dimension_name, SUM(metric_value) AS metric_value
  FROM base
  WHERE period IS NOT NULL
  GROUP BY period, dimension_name
)
SELECT
  dimension_name,
  SUM(CASE WHEN period = 'current' THEN metric_value ELSE 0 END) AS current_value,
  SUM(CASE WHEN period = 'prior' THEN metric_value ELSE 0 END) AS prior_value,
  SUM(CASE WHEN period = 'current' THEN metric_value ELSE -metric_value END) AS contribution_delta
FROM by_dimension
GROUP BY dimension_name
ORDER BY ABS(contribution_delta) DESC
```

Replace placeholders only with objects and columns found in project context or read-only discovery.

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

## Built-in sample (only on request)

Use this only when the user asks for a `sample` or `demo`. Label it `synthetic sample, not queried`.

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

Expected sample: total metric rises from `180` to `220`, a delta of `40` or `22.2%`. Contributions are North `+30`, West `+20`, and South `-10`. Freshness is `not applicable` because the rows are synthetic.

## Output contract

Return exactly:

1. `Metric and period`
2. `Freshness and completeness`
3. `Executive brief`
4. `Period comparison`
5. `Dimensional contributors`
6. `Interpretation and caveats`
7. `Read-only SQL`
8. `Next checks`

The executive brief must be at most five bullets. Each claim must map to a displayed metric or quality check.

Before you answer, check that the brief has five bullets or fewer, that supplied rows or the sample are labeled `not applicable` for freshness, that there are no rank-change words between dimension values, such as "overtook", "passed", or "became the second largest", and that every other comparison between dimensions or periods matches the displayed numbers for both periods.

## Exact example prompts

- `/business-pulse Compare completed monthly revenue with the prior month and identify regional contributors.`
- `/business-pulse Show the latest complete week's active-user change by product and check data freshness first.`
- `/business-pulse Use the local metric definition, return the SQL, and run only if a read-only connection exists.`
