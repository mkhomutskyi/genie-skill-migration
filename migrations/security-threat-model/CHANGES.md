# security-threat-model: changes for Databricks Genie

Source: https://github.com/openai/skills/tree/49f948faa9258a0c61caceaf225e179651397431/skills/.curated/security-threat-model
The `openai/skills` repository is marked deprecated in its README. This skill folder has its own Apache-2.0 `LICENSE.txt`.
Original files: `upstream/security-threat-model/`, byte-identical to the source commit.
Full diff: `genie.diff`.

| # | Change | Label | Why |
|---|---|---|---|
| 1 | "Repo root path" became "the workspace folder or Git folder path that holds the code" | Binding | In Genie the code lives in the workspace or a Git folder, not a local checkout. |
| 2 | Added: if the files cannot be read here, ask for a pasted summary and label the result as based on supplied content | Required | Where Genie cannot read the folder, the original would produce a "repository-grounded" model without evidence. |
| 3 | "Write the final Markdown to a file" became "Return it in chat; write a workspace file only when asked, at the path given; never overwrite" | Guardrail | Writing files is a change to the workspace. It should be the user's choice. |
| 4 | Left `agents/openai.yaml` out of the Genie copy | Optional | Codex and ChatGPT interface metadata. It stays in `upstream/`. |
| 5 | Added a modification notice after the frontmatter | Required by the license | Apache-2.0 section 4. |

Not changed: the workflow, the risk guidance and both reference files.

Observed on 2026-10-20 in one test workspace, with a made-up two-file app: Genie Code opened the workspace files itself and wrote a threat model grounded in them. Genie One said it could not open plain workspace files by path, asked for pasted code, and offered to label the result as based on supplied content, as change 2 requires. Neither product documents this either way, so treat it as an observation, not a product rule.
