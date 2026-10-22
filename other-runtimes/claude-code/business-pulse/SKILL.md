---
name: business-pulse
description: Build a concise period-over-period business brief from read-only metrics after validating freshness, completeness, and dimensional contribution.
argument-hint: "[metric] [daily|weekly|monthly] [dimensions]"
allowed-tools: Read, Grep, Glob
---

# Business Pulse

Create an evidence-backed business update for the latest complete period versus the immediately preceding comparable period.

## Claude Code adaptation

- Search the local project for metric definitions, semantic configuration, tests, fixtures, and SQL before proposing a formula.
- Use repository content to resolve user intent, not to assert live values.
- Use an already configured Databricks connection only for schema discovery and `SELECT` statements.
- Never choose, embed, or request a profile, host, token, credential, or warehouse identifier.
- Review each command before execution and reject anything that could write data, refresh a pipeline, change a dashboard, start compute, or send a result.
- Without safe connectivity, return SQL marked `not executed` and state that live data was not queried.
- If the user pastes rows, compute from those rows only and label the result `from supplied rows, not queried`.
- Use the built-in sample only when the user asks for a `sample` or `demo`. Otherwise never show sample numbers.

This is the Claude Code variant. The Genie skill in `skills/business-pulse` is the primary version. `allowed-tools` pre-approves the listed read tools; it does not block other tools, so the rules above still apply.

## Requirements and missing input

- Data: one table, view, or local metric definition that holds the metric, a timestamp or period column, and the breakdown dimensions. Live values need `SELECT` on it through an already configured connection.
- If the metric, the periods, or the source object is missing or ambiguous, ask at most three short questions in one message before analyzing. Show candidate objects you found and do not pick one for the user.
- If the user supplied rows, infer the metric and periods from them and state your reading instead of asking.

## Define the comparison

Select and print:

- metric formula
- grain
- timezone
- filters
- current complete period `[start, end)`
- prior matching period `[start, end)`
- requested breakdown dimensions

Daily compares the latest complete day, weekly compares matching complete weeks or explicit seven-day windows, and monthly compares complete calendar months. Never silently compare a partial period to a complete one.

## Quality gate before interpretation

Run read-only checks for:

1. latest source timestamp
2. expected date or partition coverage
3. rows by period and subperiod
4. metric nulls
5. dimension nulls
6. duplicate keys at the declared grain
7. late arrivals when an ingestion timestamp exists
8. denominator stability for rates

Return `pass`, `caution`, or `fail`.

For supplied rows or the built-in sample, return `not applicable` and say that freshness was not checked. Still report missing periods, duplicate rows, and dimensions that appear in only one period.

If `fail`, do not produce a business explanation. Report the quality issue, its measured impact, and queries needed to validate recovery.

## Contribution analysis

Use identical filters and formulas in both periods. Compute:

- current value
- prior value
- absolute delta
- percent delta when prior is nonzero
- dimension-level signed deltas
- share of total delta where mathematically meaningful
- reconciliation gap between dimension deltas and total delta, for additive metrics only

Use dimensions found in project context or schema discovery. Never invent a region, segment, product, or channel hierarchy. A contributor explains arithmetic movement, not cause.

### Metric type decides the method

Classify the metric before you compare. If you cannot tell from its definition, ask.

- Additive: a sum, or a count where each row belongs to exactly one dimension value. Dimension deltas add up to the total delta, so rank them and show the reconciliation.
- Ratio, rate, or average: compute the total from the total numerator and the total denominator, never by adding or averaging dimension values. For each dimension, show numerator, denominator, and value in both periods. Say that dimension changes do not add up to the total change. If the user asks for a split, show a mix and rate decomposition with its formula.
- Distinct count, such as active users: compute the total with its own distinct count. One entity can appear under several dimension values, so dimension counts overlap and do not add up to the total. Say so.

The SQL below handles additive metrics only.

Reference pattern:

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

Adapt object and column names only from discovered evidence.

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

The expected total moves from `180` to `220`, up `40` or `22.2%`. North contributes `+30`, West `+20`, and South `-10`. Freshness is `not applicable` because the rows are synthetic.

## Brief-writing rules

- Lead with direction, magnitude, and quality status.
- Limit the executive brief to five bullets, and count them before answering.
- For supplied rows or the sample, label freshness `not applicable` even when a dimension appears in one period only.
- Use no rank-change words between dimension values, such as "overtook", "passed", or "became the second largest"; report deltas and shares instead.
- Check every other comparison between dimensions or periods against the displayed numbers for both periods.
- Make no claim that a change is normal, typical, or noise unless you queried and displayed a baseline of more periods.
- When gains and losses nearly offset, say which side is larger and show both totals.
- Name the top positive and negative dimensional contributors.
- Mark explanations as hypotheses unless directly evidenced.
- Include SQL actually used, or SQL to run with `not executed`.
- Do not recommend operational changes until the quality gate passes.

## Required output contract

1. `Definition and scope`
2. `Freshness and completeness gate`
3. `Executive brief`
4. `Current versus prior`
5. `Contribution analysis`
6. `Evidence limits`
7. `SQL used or SQL to run`
8. `Read-only follow-ups`

## Exact example prompts

- `/business-pulse Compare completed monthly revenue with the previous month and rank regional contributors.`
- `/business-pulse Analyze the latest complete week of active users by product after checking freshness and completeness.`
- `/business-pulse Find the metric definition in this project and provide SQL if no read-only connection is configured.`
