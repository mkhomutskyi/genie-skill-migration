# business-pulse

## Purpose and user

Compares one metric between the latest complete period and the one before it, checks data freshness first, and ranks which dimensions moved the total. The brief is five bullets or fewer. It is read-only.

It is for analysts, business owners, and data team leads.

## Requirements

- One table or metric view with the metric, a timestamp or period column, and the dimensions to break down by.
- `USE CATALOG`, `USE SCHEMA`, and `SELECT` on that object.
- An existing SQL warehouse. A query can start an auto-stopped warehouse.
- Without any of this, the skill still works on rows you paste into the chat.

## Install and invoke

Create a folder named `business-pulse` in your personal skills folder and upload `skills/business-pulse/SKILL.md` into it. Check first that no skill with that name exists.

- Genie One documents `/Workspace/Users/{email}/.assistant/skills/`.
- Genie Code documents `/Users/{username}/.assistant/skills/`. It can also load skills from a registered folder.

In the workspace I tested, both paths pointed to the same home folder, and one upload appeared in both products.

Start a new chat, then type `/business-pulse` in Genie One or `@business-pulse` in Genie Code. See [Install, invoke and verify](../install-and-verify.md) for the commands.

## Example with supplied rows

Exact prompt:

```text
/business-pulse Do not run SQL. Use only these rows. Metric: weekly orders, summed. Week of 2026-09-28: Lisbon 410, Porto 260, Faro 130. Week of 2026-10-05: Lisbon 380, Porto 300, Faro 175, Braga 35. Compare the two weeks and rank city contributors.
```

Expected behavior:

- The total goes from 800 to 890, up 90 or 11.25%.
- Contributors, ranked by size: Faro +45, Porto +40, Braga +35, Lisbon -30. They add up to +90.
- Braga appears only in the current week.
- Freshness is `not applicable` because the rows were supplied, not queried.
- Cities are called contributors, not causes.

## Missing-input test

Exact prompt:

```text
/business-pulse What changed in revenue? Do not run SQL.
```

Expected behavior: at most three short questions about the metric definition, the periods, and the table or metric view. No numbers and no table picked for the user.

## Limitations

- One metric per run.
- Contributions add up to the total only for additive metrics, such as a sum or a count where each row belongs to one dimension value. For a rate or an average, the skill shows numerator, denominator, and value per dimension and says the parts do not add up. For a distinct count, it says the dimension counts overlap. These two paths are written into the skill but were not tested live.
- For a metric view, the skill evaluates measures with `MEASURE()` and queries the total and the breakdown separately. This path was not executed or tested live.
- Contribution is arithmetic. It does not prove why a number moved.
- Freshness can only be checked on live data.
- Genie One reads related past conversations on its own and cites them as "Read past conversation". In one earlier test it copied a wrong sentence from a recalled test chat of the same skill. A new chat picks up skill edits, but it does not stop recall. Check the recall citations before you judge an answer. In my tests, I removed my own earlier test chats before rerunning a case. See [Live results](../live-results.md).

## SQL checks

The raw-table query and the built-in sample in `skills/business-pulse/SKILL.md` run in `tests/test_sql_fixtures.py` on local Apache Spark against made-up rows, including rows outside both periods. The test checks that the dimension deltas add up to the total change for an additive metric. The metric-view queries were not executed.

## Changes in this revision

- Added who it is for, a requirements block, and a `compatibility` field.
- The skill now classifies the metric first. Reconciliation is limited to additive metrics, with separate rules for rates, averages, and distinct counts.
- Metric-view measures use `MEASURE()`. An earlier version had only a raw-table `SUM` query.
- The skill now asks for the metric, periods, and table when they are missing, instead of guessing.
- The freshness gate reports `not applicable` for supplied rows and the sample.
- The built-in sample now runs only on request (`sample` or `demo`).
- A short check before answering: at most five bullets in the brief, the freshness label, and every comparison checked against both periods.
- A metric name alone, such as "revenue", is not a definition. The skill asks what it includes and how it is aggregated.
- No rank-change words such as "overtook" or "became the second largest". Each value gets its own delta and, if useful, its share of the total.

## Test history

The 2026-10-14 "10 of 10 passed" run used prompts that asked for the sample whose answer is written in the skill. It shows the skill loaded and followed its sample, not that it computes correctly. The cases in `evals/held_out.json` replace it.

Final live run, 2026-10-20 to 2026-10-22, on SKILL.md hash `305cb5999b9f`: the held-out and missing-input cases passed in Genie One (`/`) and Genie Code (`@`). The failures found on the way, and the fixes, are listed in [Live results](../live-results.md).

## Sources

- https://docs.databricks.com/aws/en/uc-semantics/metric-views/query
- https://docs.databricks.com/aws/en/sql/language-manual/functions/measure
