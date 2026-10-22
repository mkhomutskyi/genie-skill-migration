---
name: technical-answer
description: Research and answer a Databricks technical question using current official Databricks and relevant cloud documentation with claim-level validation.
disable-model-invocation: true
---

# Technical Answer

Use `/technical-answer <question>` for concise, evidence-backed Databricks guidance.

## Runtime adaptation

- Inspect local project files when code, configuration, runtime versions, or cloud context materially affect the answer.
- Treat local context as evidence about the project, not as current product documentation.
- Use public web or documentation search for current Databricks behavior and the matching cloud provider behavior.
- If a configured Databricks connection exists, use only read-only metadata or `SELECT` queries when the question requires runtime confirmation.
- Never hardcode or request a connection profile, credential, host, token, or warehouse identifier.
- If no connection exists, provide optional read-only verification SQL or commands and label them `not executed`.

Never deploy, create, edit, delete, restart, grant, revoke, trigger, or send anything.

This is the Cursor variant. The Genie skill in `skills/technical-answer` is the primary version.

## Requirements and missing input

- Needs web search or documentation fetch in the session. If neither is available, begin with `Not verified from current official documentation.`, do not answer from memory, list the claims that need checking, and point to the public starting points below.
- If the answer depends on the cloud and the user did not name one, ask which cloud before researching. Then stop: do not search or give steps for any cloud until the user answers. Do not take the cloud from the workspace, the environment, or an earlier chat.
- If the feature name could mean more than one product, ask which one, or state the reading you chose when only one fits.

## Evidence standard

For each material claim:

1. Find a current official Databricks source.
2. If the claim depends on cloud infrastructure, identity, storage, networking, or limits, find the corresponding official AWS, Microsoft Azure, or Google Cloud source.
3. Confirm that source scope matches the user's cloud, region, product, and runtime context.
4. Record product status exactly as `GA`, `Public Preview`, `Beta`, `Private Preview`, or `Experimental` only when an official source states it.
5. If status is not documented, write `status not verified`.
6. Prefer exact documentation over summaries, community posts, or remembered behavior.

Fail closed: if evidence is missing, stale, contradictory, or scoped to a different environment, do not make the claim. State what could not be verified and what official evidence is needed.

## Research workflow

1. Parse the question into claims, assumptions, and environment dependencies.
2. Inspect relevant local files without changing them.
3. Search official Databricks documentation.
4. Search the matching official cloud documentation when needed.
5. Cross-check terminology, support status, prerequisites, limits, and regional availability.
6. Draft the smallest correct answer.
7. Add code only when it directly helps and can be safe by default.
8. Validate every material sentence against the source set.

Use direct public URLs and cite sparingly. Two authoritative links are better than a long uncurated list.

## Code rules

- Match the user's language and project conventions when visible.
- Keep examples minimal and independently understandable.
- Use placeholders for user-specific names and identifiers.
- Do not include credentials, secrets, fixed profiles, or assumed resource identifiers.
- Prefer read-only examples.
- For code that could modify state, explain the concept without providing an execution instruction unless the user explicitly requests implementation in another task.
- Never say an example was run unless it was safely executed and its output observed.

## Status vocabulary

- `GA`: official documentation explicitly indicates general availability.
- `Public Preview`: official documentation explicitly uses that status.
- `Beta`: official documentation explicitly uses that status.
- `Private Preview`: official documentation explicitly uses that status. Such features are often undocumented.
- `Experimental`: official documentation explicitly uses that status, mostly for Databricks Runtime features.
- `status not verified`: no matching official statement was found.

Do not infer status from page age, user interface presence, naming, or third-party material. A page or section without a release label does not state `GA`; use `status not verified` unless a page or the release notes say the feature is generally available.

## Output contract

Return exactly:

1. `Answer`
2. `Status`
3. `Code` when useful, otherwise `Code: Not needed`
4. `Caveats`
5. `Sources`

Requirements:

- `Answer` is at most five short paragraphs or eight bullets.
- Put the direct answer first.
- Every material capability, prerequisite, limit, and status claim has an official source.
- `Caveats` names cloud, runtime, region, and access assumptions that matter.
- `Sources` lists only sources actually used, with title and public URL.
- When evidence is insufficient, `Answer` begins `Not verified from current official documentation.`

## Exact example prompts

- `/technical-answer Does Genie Code discover an edited agent skill in the current chat, or must I start a new chat?`
- `/technical-answer Explain how Unity Catalog external locations interact with AWS storage permissions.`
- `/technical-answer Using this project's Python version, show the smallest read-only Databricks SDK example supported by current docs.`
- `/technical-answer Compare the documented networking prerequisites for this Databricks feature on Azure.`

## Public starting points

- https://docs.databricks.com/
- https://docs.aws.amazon.com/
- https://learn.microsoft.com/azure/
- https://cloud.google.com/docs
