# define-goal: changes for Databricks Genie

Source: https://github.com/openai/skills/tree/49f948faa9258a0c61caceaf225e179651397431/skills/.curated/define-goal
The `openai/skills` repository is marked deprecated in its README. This skill folder has its own Apache-2.0 `LICENSE.txt`.
Original files: `upstream/define-goal/`, byte-identical to the source commit.
Full diff: `genie.diff`.

| # | Change | Label | Why |
|---|---|---|---|
| 1 | Steps 5 and 6 no longer call `get_goal` and `create_goal`; the goal is written in chat under `Goal` and the user confirms it | Required | These are Codex tools. Neither Genie One nor Genie Code documents tools with these names, and in my tests Genie Code said it had no goal-tracking tool. Without them, the original tells the model to call tools that are not there. |
| 2 | Added "Never say that a goal was created, saved or tracked" | Required | Without the tool, any such claim would be false. |
| 3 | Removed "Include a token budget only when the user explicitly requested one" | Required | The token budget is a parameter of the Codex goal tool. |
| 4 | `$define-goal` became `/define-goal` (Genie One) and `@define-goal` (Genie Code); removed "asks for the goal tool" from the description and step 1 | Binding | `$` is the Codex invocation syntax. |
| 5 | Left `agents/openai.yaml` out of the Genie copy | Optional | It is Codex and ChatGPT interface metadata, and its default prompt uses `$define-goal`. It stays in `upstream/`. |
| 6 | Added a modification notice after the frontmatter | Required by the license | Apache-2.0 section 4. |

Not changed: the goal quality bar, the examples (they mention `npm` and `gh` as sample validators) and the clarifying questions.
