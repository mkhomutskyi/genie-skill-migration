# Genie skill migration

This repository moves public agent skills into Databricks Genie and adds five custom Genie skills. It goes with the article "How to move a public agent skill into Databricks Genie, and build your own".

A skill is a folder with a `SKILL.md` file. Genie One loads it when you type `/skill-name`, and Genie Code loads it when you type `@skill-name`.

## What is here

| Folder | Contents |
|--------|----------|
| `migrations/` | Five public skills. Each has the original files from a pinned commit, the Genie copy, `CHANGES.md` with the reason for every change, and `genie.diff`. |
| `skills/` | Five custom Genie skills. |
| `docs/skills/` | A guide for each custom skill: who it is for, what it needs, prompts, limits and test history. |
| `docs/install-and-verify.md` | Install, invoke, verify and troubleshoot. |
| `docs/live-results.md` | What I tested live, what failed, and what I changed. |
| `evals/held_out.json` | The test cases: a held-out case and a missing-input case for each custom skill. |
| `templates/my-skill/` | A starting point for your own Genie skill. |
| `other-runtimes/` | Cursor and Claude Code versions of the custom skills. Untested. |
| `src/`, `tests/` | A small checker (`portable-skills`) and the tests. |

## Quick start

```bash
git clone https://github.com/mkhomutskyi/genie-skill-migration.git
cd genie-skill-migration
```

Then follow [docs/install-and-verify.md](docs/install-and-verify.md) to upload one skill, start a new chat, and invoke it.

## The migrations

| Skill | Source | Main change for Genie |
|-------|--------|-----------------------|
| [write-query](migrations/write-query/CHANGES.md) | anthropics/knowledge-work-plugins | Bundle the missing SQL reference, use Unity Catalog metadata, default to Databricks SQL, ask which table when none is named |
| [define-goal](migrations/define-goal/CHANGES.md) | openai/skills | Replace Codex goal tools with a goal written in chat |
| [theme-factory](migrations/theme-factory/CHANGES.md) | anthropics/skills | Leave out the PDF, which Genie One cannot read, and show the themes from the text files |
| [security-threat-model](migrations/security-threat-model/CHANGES.md) | openai/skills | Read a workspace or Git folder, fall back to pasted code, and answer in chat instead of writing a file |
| [internal-comms](migrations/internal-comms/CHANGES.md) | anthropics/skills | None needed |

The source URLs, commits and file hashes are in [migrations/PROVENANCE.json](migrations/PROVENANCE.json).

## The custom skills

| Skill | What it does | Reads |
|-------|--------------|-------|
| [cost-investigator](docs/skills/cost-investigator.md) | Explains Databricks usage and estimated list-price cost | Billing system tables |
| [workload-radar](docs/skills/workload-radar.md) | Compares two seven-day windows of jobs, queries, warehouses and cost | Lakeflow, query, compute and billing system tables |
| [business-pulse](docs/skills/business-pulse.md) | Compares the latest business period with the one before | A table or metric view you name, or pasted rows |
| [technical-answer](docs/skills/technical-answer.md) | Answers a Databricks question from current documentation, with status labels | Public documentation |
| [solution-planner](docs/skills/solution-planner.md) | Proposes the smallest documented Databricks architecture for a need | Public documentation |

All five are read-only: they never change data, jobs, warehouses or permissions, and they ask for missing inputs instead of guessing. cost-investigator, workload-radar and business-pulse run live read-only queries when you have access and have not said "do not run SQL". Add "Do not run SQL" to a prompt for a dry run, which returns SQL marked `not executed`. Live queries need existing data access and may start an auto-stopped SQL warehouse, which incurs usage.

## Test status

On 2026-10-20 to 2026-10-22, I ran the held-out case and the missing-input case for each custom skill in Genie One and Genie Code on the final files: 20 runs in one AWS workspace with synthetic prompts. All 20 met their test checklist, but two were not error-free. Both workload-radar held-out answers, in Genie One and in Genie Code, showed the repair-like heuristic as 0, although the supplied numbers cannot measure it. The Genie Code answer also said a 30% cost rise "outpaces" a 33% rise in runs, which is false. Genie ran no SQL in those runs. After a later fix to cost-investigator and workload-radar, I reran their eight runs on the changed files: all met their checklists, and one Genie One answer had an arithmetic error. I then let Genie run the SQL for cost-investigator, workload-radar and business-pulse, read-only, on an existing warehouse: three runs in Genie One and one in Genie Code per skill. All 12 matched an answer key I computed directly, on every headline number, and every system-table query filtered to the one workspace. Four answers had one or two errors, such as a "normal noise" claim without a baseline. Those errors led to two small rule changes that were not rerun in Genie. The failures found along the way and the fixes are in [docs/live-results.md](docs/live-results.md).

Automated checks:

- CI runs on Linux and on Windows with `core.autocrlf=true`. The six Spark SQL fixture tests are skipped there, because CI does not install Apache Spark. Windows also skips one test of executable file permissions, which Windows does not have.
- Locally, with Java 21 and Apache Spark installed, all tests ran, including the six Spark tests.

Local checks:

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
uv run portable-skills scan .
```

## Limits

- One workspace, one cloud, one final run per case. Model output varies between runs.
- Genie One reads past conversations and can follow an older chat instead of the skill. Check its "Read past conversation" citations before you judge a result. See [Recall](docs/live-results.md#recall).
- Genie ran SQL in one round only, with one prompt per skill for three skills in one workspace. business-pulse ran on public sample data, not a real business table. The SQL was also checked on local Apache Spark with made-up tables. See [docs/live-results.md](docs/live-results.md#live-runs-with-sql-executed).
- The Cursor and Claude Code versions are untested.
- Product behavior and documentation change. Check the current Databricks docs before you rely on a path or limit.

## License and attribution

The migrated skills keep their original Apache-2.0 licenses, and each changed Genie copy says that it was modified. Everything else is under the [Apache-2.0 license](LICENSE). See [NOTICE](NOTICE) for attribution.

This is a personal project. It is not an official Databricks repository, and it is not supported by Databricks.
