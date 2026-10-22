# solution-planner

## Purpose and user

Turns a short list of requirements into the smallest Databricks architecture that meets them, with one alternative, an ASCII diagram, risks, and a phased plan that stops before anything is built. Every product choice comes with a status label and a source.

It is for data engineers, architects, and technical leads who want a first design to review with their team.

## Requirements

- Web search or another way to read current public documentation. Without it, every status is `status not verified`.
- No data access is needed. Unity Catalog metadata is optional.

## Install and invoke

Create a folder named `solution-planner` in your personal skills folder and upload `skills/solution-planner/SKILL.md` into it. Check first that no skill with that name exists.

- Genie One documents `/Workspace/Users/{email}/.assistant/skills/`.
- Genie Code documents `/Users/{username}/.assistant/skills/`. It can also load skills from a registered folder.

In the workspace I tested, both paths pointed to the same home folder, and one upload appeared in both products.

Start a new chat, then type `/solution-planner` in Genie One or `@solution-planner` in Genie Code. See [Install, invoke and verify](../install-and-verify.md) for the commands.

## Example requirements

Exact prompt:

```text
/solution-planner Source: CSV files that land once a day in a Unity Catalog volume. Destination: governed Delta tables for SQL dashboards. Latency: data ready by 06:00 UTC daily. Scale: 2 GB per day. Changes: append only. Cloud: AWS. Governance: Unity Catalog access control and lineage. Reliability: a failed day can be rerun. Recovery: RPO 24 hours, RTO 4 hours. Observability: alert on a failed or late load. Cost: no always-on compute. Do not run SQL.
```

Expected behavior:

- A small stack: Unity Catalog, incremental file ingestion from the volume (for example Auto Loader in a triggered pipeline or a scheduled job), and an existing SQL warehouse.
- No Lakeflow Connect, no Delta Sharing, and no always-on streaming compute, because nothing in the requirements needs them.
- Exactly one alternative with a tradeoff.
- A status label and a source link for each selected product.
- An ASCII-only diagram, a phased plan that stops before implementation, and under 900 words without the diagram.

## Missing-input test

Exact prompt:

```text
/solution-planner Plan a pipeline for our sales data. Do not run SQL.
```

Expected behavior: at most three short questions about the source, the destination or latency, and the cloud. No stack, diagram, or plan yet.

## Limitations

- It plans; it never deploys or checks that a design works in your workspace.
- Connector and regional support change. Re-check the cited pages before you build.
- Genie One reads related past conversations on its own and cites them as "Read past conversation". In one earlier test it copied a wrong sentence from a recalled test chat of the same skill. A new chat picks up skill edits, but it does not stop recall. Check the recall citations before you judge an answer. In my tests, I removed my own earlier test chats before rerunning a case. See [Live results](../live-results.md).
- Genie Code knows which cloud the current workspace runs on. Before the fix it used that cloud when the user had not named one. The skill now tells it to ask instead.

## Changes in this revision

- Added who it is for, a requirements block, and a `compatibility` field.
- It now asks up to three questions when two or more core requirements are missing.
- Each product choice needs a status label and a source. Components that are not GA are listed as risks.
- The answer is capped at 900 words, not counting the diagram.
- Added the `Private Preview` and `Experimental` labels.
- The evidence column must quote release words from the cited page. Without them the status is `status not verified`.
- The plan goes in the chat reply, with a word budget and a check before answering: at most six sources and under 900 words.
- The cloud counts as given only when the user names it.
- Each product in the stack gets its own status row and source link. The stack table has no links, and there are no citations outside the status table and the source list.
- At most five documentation searches.
- The diagram check now rejects Unicode arrows such as U+2192 (rightwards arrow).

## Test history

The 2026-10-14 "10 of 10 passed" run checked that the skill loaded and kept its output format. The cases in `evals/held_out.json` add requirements that are not in the skill and a missing-input case.

Final live run, 2026-10-20 to 2026-10-22, on SKILL.md hash `84816acfd0d8`: the held-out and missing-input cases passed in Genie One (`/`) and Genie Code (`@`). The failures found on the way, and the fixes, are listed in [Live results](../live-results.md).

## Sources

- https://docs.databricks.com/aws/en/release-notes/release-types
- https://docs.databricks.com/aws/en/ldp/
- https://docs.databricks.com/aws/en/data-governance/unity-catalog/
