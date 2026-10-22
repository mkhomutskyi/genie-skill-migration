# Live results

This page summarizes the live tests of the five custom skills. The raw outputs stay private because they show a real workspace. Everything below uses synthetic inputs, and no SQL ran in the workspace.

## Setup

- One Databricks workspace on AWS, tested 2026-10-20 to 2026-10-22.
- Each skill was uploaded as a single `SKILL.md` to the personal skills folder. After each upload I exported the installed file and compared its SHA-256 with the file in this repository. Every final upload matched.
- Genie One: a new chat, the skill chosen with `/`, then the exact prompt from `evals/held_out.json`.
- Genie Code: a new chat in an empty test notebook, the skill chosen with `@`, then the same prompt without the leading `/skill-name`, followed by: "Do not run any code or SQL, do not edit the notebook and do not start compute. Answer in chat only."
- Each case was graded against its `must` list, expected values and `must_not_contain` list in `evals/held_out.json`. A failure was fixed in the skill, never by changing the case.
- Word counts include tokens that contain a letter or a digit and exclude the diagram.

## Final results

Each skill was tested at the hash shown, which is the first 12 characters of the SHA-256 of `skills/<name>/SKILL.md` in this repository.

| Skill | Hash | Case | Genie One | Genie Code |
|-------|------|------|-----------|------------|
| cost-investigator | `480b1570ff47` | held-out | pass | pass |
| cost-investigator | `480b1570ff47` | missing-input | pass, recall shown | pass |
| workload-radar | `00ab1759915b` | held-out | met checklist, one error | met checklist, two errors |
| workload-radar | `00ab1759915b` | missing-input | pass, recall shown | pass |
| business-pulse | `305cb5999b9f` | held-out | pass, recall shown | pass |
| business-pulse | `305cb5999b9f` | missing-input | pass, recall shown | pass |
| technical-answer | `8367101ccb90` | held-out | pass | pass |
| technical-answer | `8367101ccb90` | missing-input | pass | pass |
| solution-planner | `84816acfd0d8` | held-out | pass, 792 words | pass, 855 words |
| solution-planner | `84816acfd0d8` | missing-input | pass | pass |

"Recall shown" means Genie One displayed a "Read past conversation" step. In all four final cases it read an older chat that held no answer to the prompt, and the result met the grading.

The workload-radar held-out answers are not error-free, and the errors fall outside the `must` list:

- Both products showed the repair-like heuristic as 0 to 0. The prompt gives no run identifiers or attempts, so the heuristic cannot be measured and should be `unavailable (not supplied)`. I first noted this only for Genie Code; on review, the Genie One answer has the same error.
- In Genie Code, one hypothesis says a 30% cost rise "outpaces" a 33% rise in runs, which is false.

The other 18 final runs had no errors that I found.

## Evidence categories

| Category | What was shown |
|----------|----------------|
| Static | `tests/test_held_out.py` checks the cases and the skill rules; `tests/test_tooling.py` checks the tooling. |
| SQL logic | `tests/test_sql_fixtures.py` runs the workload, cost and business queries on local Apache Spark against small made-up tables. These six tests ran locally with Java 21 and Apache Spark. CI skips them, because it does not install Spark. |
| Upload and discovery | Each final file matched its hash after upload, and each skill appeared in the `/` and `@` pickers. |
| Invocation | Every run showed the skill being loaded: "Loaded skill" in Genie One, "Read ... skill" or the skill chip in Genie Code. |
| Correct response | All 20 final runs met their `must` items. Two workload-radar answers also contained errors outside that list, described above. |
| SQL generated, not executed | Cost, workload and business answers included SQL marked `not executed`. |
| SQL executed in the workspace | None. Every prompt said not to run SQL. |

## Failures found and fixed

Each fix was followed by a re-upload and a rerun of both cases for that skill.

| Skill | What failed | Fix in the skill |
|-------|-------------|------------------|
| business-pulse | A six-bullet brief and a "caution" freshness label on supplied rows | The rules moved into the output list, plus a check before answering |
| business-pulse | "Porto overtook Faro", which is false: Porto was larger in both weeks | Rank-change words are banned; each value gets a delta and a share |
| business-pulse | "Revenue" was treated as defined because a table had that column | A metric name alone is not a definition |
| technical-answer | A status was given as GA because the page had no preview label | No release label means `status not verified` |
| technical-answer | It answered for one cloud instead of asking which cloud | A hard stop: ask one question first |
| technical-answer | Genie Code used the workspace's cloud | The cloud must come from the user's message |
| workload-radar | "Possibly" and "may" inside `Observed changes` | Observations hold values and deltas only |
| workload-radar | Access listed as tables, not privileges | Name `USE CATALOG`, `USE SCHEMA` and `SELECT` |
| solution-planner | GA inferred, 1,400+ words, 11 sources | Quote release words; a word budget; at most six sources; plan in chat |
| solution-planner | Genie Code did not ask for the cloud | The cloud counts only when the user names it |
| solution-planner | No source for two of the chosen products | One status row and link per product |
| solution-planner | 973 words and 10 sources in Genie One | Cite only in the status table; at most five searches |
| solution-planner | A Unicode arrow (U+2192) inside the ASCII diagram | The check before answering rejects Unicode arrows |

## Migrated public skills

The migrations were tested on 2026-10-20, first with the unchanged upstream files and then with the Genie copies. Two Genie One cases were rerun on 2026-10-22 after I removed my earlier test chats. The hashes are the first 12 characters of the SHA-256 of the Genie copy's `SKILL.md`, as pinned in `migrations/PROVENANCE.json`.

| Skill | Hash | Unchanged upstream | Genie copy |
|-------|------|--------------------|------------|
| write-query | `dcc71b7913db` | Both products tried to open a file outside the skill folder and failed. | Loaded its bundled reference in both products. With no table named, Genie Code asked which table. Genie One first copied a recalled test chat and picked a table on its own; after I removed my earlier test chats, it asked. |
| define-goal | `2cebba177447` | Genie One saved a memory and said "Goal Created". Genie Code said it had no goal tool. | Genie Code wrote the goal in chat. Genie One first repeated the recalled baseline chat; after I removed my earlier test chats, it wrote the goal in chat and said it was stored only there. |
| theme-factory | `f77357bbc536` | Genie One could not read the bundled PDF. | Both products opened all 11 text files, with no loader error. |
| security-threat-model | `3c04efc458f0` | Not run. | Genie Code read the workspace files. Genie One said it could not open them and asked for pasted code, as the adapted skill says. |
| internal-comms | `067b7587a344` | No change needed. | Tested in both products in an earlier round on 2026-10-19 and not retested for this page. |

## Recall

Genie One reads related past conversations on its own and cites each one as "Read past conversation" in its steps. In two runs it followed an earlier test chat instead of a skill rule, and in a third it copied a false sentence from one. A new chat picks up a re-uploaded skill at once, but it does not stop recall.

This was my test procedure, not a general recommendation: the earlier chats were my own disposable test chats, so I removed them before rerunning a case. After that, the write-query and define-goal cases passed with the same files and prompts. During the final runs, I removed each test chat before the next run of the same skill. Genie Code showed no past-conversation step in any run.

When you test a skill, read the recall citations before you judge the answer. A cited chat can explain an answer that does not follow the skill.

## Limits of this evidence

- One workspace, one cloud and one run per final case. Model output varies between runs, so a pass here does not guarantee every future answer passes. The solution-planner held-out cases came in under the 900-word limit by 45 to 108 words.
- I graded the runs myself against the written `must` lists. There was no second grader.
- No SQL ran against real system tables or business tables. The queries were checked only on local Spark fixtures.
- The Cursor and Claude Code versions in `other-runtimes/` were not tested.
