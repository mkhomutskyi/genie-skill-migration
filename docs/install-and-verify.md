# Install, invoke and verify

These steps install one skill into your personal skills folder. They were tested with the Databricks CLI on one AWS workspace.

## Prerequisites

- A Databricks workspace where you can use Genie One, Genie Code, or both.
- The [Databricks CLI](https://docs.databricks.com/aws/en/dev-tools/cli/) with a profile for that workspace. Check it with `databricks current-user me --profile <profile>`.
- `git`, and `uv` if you want to run the checks in this repository.
- Optional, for the SQL fixture tests: Java 17 or later and a local Apache Spark.

The custom skills need no compute to install. Some of them can query system tables or business tables when you allow it; each guide in `docs/skills/` lists what it reads and the privileges it needs.

## 1. Clone

```bash
git clone https://github.com/mkhomutskyi/genie-skill-migration.git
cd genie-skill-migration
```

## 2. Pick the folder

The two products document different personal folders:

| Product | Documented personal folder | Invoke with |
|---------|----------------------------|-------------|
| Genie One | `/Workspace/Users/{email}/.assistant/skills/` | `/skill-name` |
| Genie Code | `/Users/{username}/.assistant/skills/` | `@skill-name` |

In the workspace I tested, both paths pointed to the same home folder, so one upload appeared in both products. That is an observation from one workspace, not a documented guarantee. Genie Code can also load skills from a registered folder; that path was not tested here.

Genie One limits a skill to three folders deep and 50 files or folders, and it accepts text files only, so no images or PDFs. Genie Code CLI is a separate product with its own skill setup; it is not covered here.

## 3. Check that the name is free

Set `SKILLS` to your Genie One folder, with `{email}` replaced by your workspace user name (the `userName` that `databricks current-user me --profile <profile>` prints):

```bash
SKILLS="/Workspace/Users/{email}/.assistant/skills"
databricks workspace list "$SKILLS" --profile <profile>
```

If a folder with the same name exists, stop. Export it first or choose another name. Do not overwrite a skill you did not create.

## 4. Upload

A single-file skill:

```bash
databricks workspace mkdirs "$SKILLS/workload-radar" --profile <profile>
databricks workspace import "$SKILLS/workload-radar/SKILL.md" \
  --file skills/workload-radar/SKILL.md --format AUTO --profile <profile>
```

A migrated skill with supporting files:

```bash
databricks workspace import-dir migrations/write-query/genie/write-query \
  "$SKILLS/write-query" --profile <profile>
```

The Genie One UI cannot upload files to a skill. For a personal skill, use the CLI as shown here, or the workspace file browser. The Genie One page describes Catalog Explorer uploads for published, shared skills, which this repository does not cover.

## 5. Verify the upload

Export the installed file and compare it with the repository copy:

```bash
databricks workspace export "$SKILLS/workload-radar/SKILL.md" \
  --format AUTO --file installed-SKILL.md --profile <profile>
shasum -a 256 installed-SKILL.md skills/workload-radar/SKILL.md
```

The two hashes must match. The first 12 characters of the final hashes are listed in [Live results](live-results.md).

## 6. Invoke

1. Start a new chat. An open chat may still hold the old version.
2. In Genie One, type `/workload` and choose `workload-radar` from the list. In Genie Code, type `@workload` and choose the entry that shows the skill description, not the folder with the same name.
3. Add a prompt, for example the one under "Example with supplied numbers" in `docs/skills/workload-radar.md`, or a held-out prompt from `evals/held_out.json`.

## 7. Check the answer

Compare the answer with the `must` list for that case in `evals/held_out.json`. In Genie One, open the thought process and look for "Loaded skill". If it also shows "Read past conversation", the answer may draw on an older chat. Open the cited chat and check whether it explains the answer. In my tests the cited chats were my own disposable test chats, so I removed them and reran the case.

## Troubleshooting

| Problem | What to check |
|---------|---------------|
| The skill is not in the `/` or `@` list | The folder name, that `SKILL.md` is directly inside it, and the front matter `name`. Then start a new chat. |
| The old behavior after an edit | Export and compare the hash again, then start a new chat. |
| The answer copies an earlier test | Genie One recall. Open the "Read past conversation" citation. If it is a disposable test chat of yours, you can remove it and rerun the case, as I did. |
| Genie Code answers for the workspace's cloud | The current technical-answer and solution-planner skills ask for the cloud. If you edit them, keep the rule that the cloud must come from the user's message. |
| The SQL needs access you do not have | The guide lists the privileges. The skill returns SQL marked `not executed` that you can hand to an admin. |
| You want a dry run | Add "Do not run SQL" to the prompt. Without it, cost-investigator, workload-radar and business-pulse run live read-only queries when you have access, which may start an auto-stopped SQL warehouse. |
| Genie Code saved a memory during a test | Genie Code can save memories on its own, for example the workspace and warehouse IDs, even when the prompt says not to change anything. Add "Do not save memories" to test prompts, and ask Genie Code to list and delete any memories it saved afterwards. |

## Remove

Delete only the folder you created:

```bash
databricks workspace delete "$SKILLS/workload-radar" --recursive --profile <profile>
```

## Run the repository checks

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run portable-skills scan .
```

`tests/test_sql_fixtures.py` needs Java and `pyspark` on the Python path, for example from a local Apache Spark install. Without them those tests are skipped. If Spark reports `PYTHON_VERSION_MISMATCH`, set `PYSPARK_PYTHON` to the virtual environment's Python.
