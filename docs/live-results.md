# Live results

This page summarizes the live tests of the five custom skills. The raw outputs stay private because they show a real workspace. Most Genie tests below use synthetic inputs, and no SQL ran during them. A separate read-only run of two skills' SQL against live system tables is described in [Live system tables](#live-system-tables), and Genie runs that executed the SQL themselves are in [Live runs with SQL executed](#live-runs-with-sql-executed).

## Setup

- One Databricks workspace on AWS, tested 2026-10-20 to 2026-10-22.
- Each skill was uploaded as a single `SKILL.md` to the personal skills folder. After each upload I exported the installed file and compared its SHA-256 with the file in this repository. Every final upload matched.
- Genie One: a new chat, the skill chosen with `/`, then the exact prompt from `evals/held_out.json`.
- Genie Code: a new chat in an empty test notebook, the skill chosen with `@`, then the same prompt without the leading `/skill-name`, followed by: "Do not run any code or SQL, do not edit the notebook and do not start compute. Answer in chat only."
- Each case was graded against its `must` list, expected values and `must_not_contain` list in `evals/held_out.json`. A failure was fixed in the skill, never by changing the case.
- Word counts include tokens that contain a letter or a digit and exclude the diagram.

## Initial synthetic-input results

Each skill was tested at the hash shown, which is the first 12 characters of the SHA-256 of `skills/<name>/SKILL.md` at the time of the run. cost-investigator and workload-radar changed after these runs (see [Live system tables](#live-system-tables)), and their four cases were rerun on the changed files (see [Rerun after the scope fix](#rerun-after-the-scope-fix)). workload-radar and business-pulse changed again after the live runs with SQL (see [Live runs with SQL executed](#live-runs-with-sql-executed)), and their live prompts were rerun on the changed files (see [Rerun with the live-run rules](#rerun-with-the-live-run-rules)).

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
| SQL logic | `tests/test_sql_fixtures.py` runs the workload, cost and business queries on local Apache Spark against small made-up tables. These seven tests ran locally with Java 21 and Apache Spark. CI skips them, because it does not install Spark. |
| Upload and discovery | Each final file matched its hash after upload, and each skill appeared in the `/` and `@` pickers. |
| Invocation | Every run showed the skill being loaded: "Loaded skill" in Genie One, "Read ... skill" or the skill chip in Genie Code. |
| Correct response | All 20 final runs met their `must` items. Two workload-radar answers also contained errors outside that list, described above. |
| SQL generated, not executed | Cost, workload and business answers included SQL marked `not executed`. |
| SQL executed by Genie | None in the synthetic-input tests, where every prompt said not to run SQL. In the live runs, Genie ran read-only SQL on an existing warehouse. See [Live runs with SQL executed](#live-runs-with-sql-executed). |
| SQL executed directly | The cost-investigator and workload-radar queries, read-only, against live system tables. See [Live system tables](#live-system-tables). |

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

## Live system tables

On 2026-10-22 I ran the cost-investigator and workload-radar queries directly against live system tables in the same workspace, outside Genie, with read-only `SELECT` and `DESCRIBE` statements. The columns matched, the session time zone was UTC, and each grouped result added back up exactly to an independent control total.

The run also showed three gaps, now fixed in all three variants of both skills:

| Gap | Fix |
|-----|-----|
| The billing and jobs tables included other workspaces. Billing usage is global across the account; jobs data covers account workspaces in the same cloud region. | Both queries filter to one workspace by default. Request broader scope explicitly and check whether each source is regional or global. |
| workload-radar returned one row per job per window, too many to summarize in chat. | It returns at most 20 jobs per window. Window totals come from the unranked runs. |
| No retry-triggered runs occurred in the window, so the retry count was 0. | A zero count is reported as "no explicit retries observed", not as healthy retries. |

I then ran the fixed queries the same way. The single-workspace cost total matched its control total exactly, and workload-radar returned one ranked list per window for that workspace. The raw results stay private because they show account data.

The fix changed these files after the first Genie runs:

| Skill | Hash in the first runs | Hash after this revision |
|-------|------------------------|--------------|
| cost-investigator | `480b1570ff47` | `8524543d4ce3` |
| workload-radar | `00ab1759915b` | `4377275cd433` |

## Rerun after the scope fix

On 2026-10-22 I uploaded the changed files, checked that each installed copy matched its current hash, and reran both cases for each skill in both products with the same prompts and grading. Each Genie One test chat was removed before the next run of the same skill.

| Skill | Case | Genie One | Genie Code |
|-------|------|-----------|------------|
| cost-investigator | held-out | pass | pass |
| cost-investigator | missing-input | pass | pass |
| workload-radar | held-out | met checklist, one error | pass |
| workload-radar | missing-input | pass | pass |

- Every run showed the skill being loaded. Genie One showed no past-conversation step in any of these runs.
- The new rules appeared as written. All four missing-input answers kept the `:workspace_id` filter and said where to find the ID, and both workload answers kept the top-20 rank in their SQL. None of the held-out answers asked for a workspace when the rows were supplied.
- The repair-like heuristic was `unavailable (not supplied)` in both workload held-out answers, which fixes the error in the first runs. The Genie Code "outpaces" error did not recur.
- The Genie One workload held-out answer said cost per second of runtime "roughly halved". It fell by about a third, from 0.046 to 0.031 USD per second.
- Minor wording, not graded: the Genie Code cost held-out answer says SKU_O "has no cost" in one line while its table marks it `not priced`, and the Genie Code workload missing-input answer refers to "the other four" queries when there are three.
- No SQL ran: the workspace query history shows no statements from my user during the runs, and the warehouse stayed stopped.

## Live runs with SQL executed

On 2026-10-22 I let Genie run the SQL itself. I uploaded cost-investigator (`8524543d4ce3`), workload-radar (`4377275cd433`) and business-pulse (`305cb5999b9f`), checked each installed copy against its hash, and wrote one prompt per skill that asked for live, read-only queries on the workspace's existing Serverless Starter Warehouse:

- cost-investigator: estimated list-price cost by SKU for one workspace over the last 30 complete UTC days.
- workload-radar: jobs, queries, SQL warehouses and cost for one workspace, the latest seven complete UTC days against the prior seven.
- business-pulse: revenue, defined as the sum of `totalPrice`, in the public sample table `samples.bakehouse.sales_transactions`, one week in May 2024 against the week before, by product.

Genie One ran each prompt three times, and I removed the test chat between runs. Genie Code ran each prompt once, in a test notebook attached to the same warehouse, with this added: "Do not start or create any other compute and do not change anything else." Before the runs I built an answer key by running the skills' SQL and independent control totals directly on the same warehouse.

| Skill | Genie One, 3 runs | Genie Code, 1 run |
|-------|-------------------|-------------------|
| cost-investigator | all numbers match, no errors | all numbers match, no errors |
| workload-radar | all numbers match; one run with one unsupported claim | headline numbers match; two errors |
| business-pulse | all numbers match; one run with one unsupported claim | all numbers match; one false comparison and one missing heading |

- Every run matched the answer key on its headline numbers: the cost total and each SKU; job runs, non-successful runs, retries, queries, warehouse starts and cost in both windows; and total revenue and each product's change. The three Genie One runs of each skill agreed on every number.
- Genie One, workload-radar: one run said unpriced usage leaves cost "understated by an unknown amount", which the data does not show.
- Genie One, business-pulse: one run called a 0.6% drop "within normal week-to-week noise" without checking a baseline.
- Genie Code, workload-radar: one daily query count was 3 higher than the control. It also said as fact that the current week's job data was incomplete. The jobs table was current, and the workspace had simply run no jobs after the first day of the window.
- Genie Code, business-pulse: it said the declines "almost entirely cancelled out" the gains, but the declines (1,695) were larger than the gains (1,524). It also left out the `Top dimensional contributors` heading.
- Genie Code saved a memory holding the workspace and warehouse IDs during the workload run, although the prompt said not to change anything. I asked it to delete the memory, and it then listed the memory folder as empty. The next prompt added "do not save memories", and no memory was saved.
- I checked the other facts the answers cited, such as a daily cost spike, the first day with usage, cost by product, failure codes and the price check on every bakehouse row, against direct queries. All of them matched.

Query history for my user during the runs shows what Genie ran. Every statement was a `SELECT` or `DESCRIBE`, every one finished, and all of them ran on the existing warehouse. Every statement that read the billing, jobs, query history or warehouse events tables filtered on the workspace ID. Genie One used the skill's top-20 job query in all three workload runs.

The raw outputs and the system-table figures stay private because they show account data. The bakehouse figures come from public sample data: revenue fell from 28,434 to 28,263 (-171, -0.6%), Pearly Pies rose by 1,116 and Orchard Oasis fell by 732. After the runs I removed the uploaded skills, the test chats, the Genie Code conversations and the test notebook, and the warehouse auto-stopped.

These runs led to two rule changes, made after the runs and tested in [Rerun with the live-run rules](#rerun-with-the-live-run-rules):

| Skill | Hash in the live runs | Hash after this revision |
|-------|-----------------------|--------------|
| workload-radar | `4377275cd433` | `12c8464cf906` |
| business-pulse | `305cb5999b9f` | `8ccc336eb2c7` |

- workload-radar: before it calls job data late or incomplete, it compares the workspace's newest job record with the newest record in the whole table. If the table is current, it writes `no completed runs after <timestamp>`.
- business-pulse: no "normal", "typical" or "noise" claim without a displayed baseline. When gains and losses nearly offset, it says which side is larger and shows both totals.

## Rerun with the live-run rules

Later on 2026-10-22 I uploaded the current workload-radar (`12c8464cf906`) and business-pulse (`8ccc336eb2c7`), checked each installed copy against its hash, and reran the same live prompts: three runs in Genie One and one in Genie Code per skill. Both Genie Code prompts also said "do not save memories". I rebuilt the answer key before the runs, and it matched the first one exactly.

| Skill | Genie One, 3 runs | Genie Code, 1 run |
|-------|-------------------|-------------------|
| workload-radar | all headline numbers match | all headline numbers match |
| business-pulse | all headline numbers match | all headline numbers match |

- This table reports headline-number agreement, not an error-free grade. The errors and scope statements below remain part of the results.
- The two new rules held in all eight runs. Every workload answer compared the workspace's newest job record with the whole table and reported no completed runs after a timestamp, instead of calling the data late. Every business-pulse answer said the losses were larger, showed both totals, and declined to call the change normal without a longer baseline.
- Genie One, workload-radar: one run said most prior-week job runs belonged to one series of evaluation jobs, but less than a third did.
- Genie One, workload-radar: one run called the current week's only job "unnamed". The job has a name, in a table that run did not query.
- Genie Code, business-pulse: it renamed the required headings and again left out `Top dimensional contributors`. It listed the contributors under its summary.
- One more Genie One workload run stalled after its queries finished. It showed no answer after ten minutes, also after a page reload, so I cancelled it, removed the chat and started again. It is not graded.
- Genie One used the skill's top-20 job query in two of the three workload runs. The third wrote its own per-job query, filtered to the workspace and capped at 40 rows.
- Query history again shows only finished `SELECT` statements on the existing warehouse. The only system-table reads without a workspace filter were the new freshness checks, and each returned only the newest timestamp in the whole table. Two answers still said that every query was filtered to the workspace. Those statements were incorrect. I have not established their overlap with the three answers listed above, so I do not use a single error-free-answer count for this round.
- Genie Code saved no memory this time, and its memory folder was empty afterwards.
- I checked the other facts the answers cited, such as data read, cache hits, warehouse events by type, costs on idle days and failing jobs, against direct queries. Apart from the errors above, they matched.

Afterwards I removed the uploaded skills, the test chats, the Genie Code conversations and the test notebook.

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

- The jobs tables cover workspaces in the same cloud region. Billing usage is global across the account. A table-wide latest timestamp is a freshness signal, not proof that a particular workspace has complete records.
- The workload query template ranks at most 20 jobs per window. Genie can generate different SQL: one rerun used its own query capped at 40 rows, which does not establish a 20-per-window cap.

- One AWS workspace. Each synthetic case ran once per product at each tested revision; each live prompt ran three times in Genie One and once in Genie Code per skill per round. Model output varies between runs, so a pass here does not guarantee every future answer passes. The solution-planner held-out cases came in under the 900-word limit by 45 to 108 words.
- I graded the runs myself against the written `must` lists. There was no second grader.
- Genie ran SQL in two rounds, with one prompt per skill: three skills, then the two that changed, each with three runs in Genie One and one in Genie Code. business-pulse ran on public sample data, not on a real business table. technical-answer and solution-planner run no SQL.
- The Cursor and Claude Code versions in `other-runtimes/` were not tested.
