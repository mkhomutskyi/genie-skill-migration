---
name: technical-answer
description: Produce a concise Databricks technical answer after validating material claims against current official Databricks and cloud documentation.
argument-hint: "[technical question]"
allowed-tools: Read, Grep, Glob, WebFetch, WebSearch
---

# Technical Answer

Answer the user's Databricks question with claim-level evidence. Do not fill gaps with plausible product behavior.

## Claude Code context handling

1. Search relevant local files for versions, imports, infrastructure choices, SQL, and configuration names.
2. Do not expose sensitive local values. Summarize only context needed for the answer.
3. Use official public documentation to establish current product behavior.
4. When a claim depends on cloud identity, storage, networking, quotas, or regional support, use the matching official AWS, Microsoft Azure, or Google Cloud documentation.
5. A preconfigured Databricks connection may be used only for read-only metadata and `SELECT` verification.
6. Never select or encode a profile, host, token, credential, or warehouse identifier.
7. If connectivity is absent, provide optional read-only verification steps marked `not executed`.

No workflow step may create or change resources, files, permissions, compute, jobs, data, or outbound communications.

This is the Claude Code variant. The Genie skill in `skills/technical-answer` is the primary version. `allowed-tools` pre-approves the listed read and web tools; it does not block other tools, so the rules here still apply.

## Requirements and missing input

- Needs `WebSearch` or `WebFetch` to reach official documentation. If neither works, begin with `Not verified from current official documentation.`, do not answer from memory, list the claims that need checking, and point to the official starting points.
- If the answer depends on the cloud and the user did not name one, ask which cloud before researching. Then stop: do not search or give steps for any cloud until the user answers. Do not take the cloud from the workspace, the environment, or an earlier chat.
- If the feature name could mean more than one product, ask which one, or state the reading you chose when only one fits.

## Build a claim ledger

Before writing, identify each material claim:

- capability
- prerequisite
- limitation
- supported cloud or region
- runtime or version requirement
- product status
- behavior shown by code

For each claim, retain one current official source and verify that its scope matches the question. Use a second official source for cross-product or cloud-boundary claims.

Allowed status labels:

- `GA`
- `Public Preview`
- `Beta`
- `Private Preview`
- `Experimental`
- `status not verified`

Use the first five only when the official source uses that status. `Experimental` is used for some Databricks Runtime features. Never infer status from a page title, release date, interface, or memory. A page or section without a release label does not state `GA`; use `status not verified` unless a page or the release notes say the feature is generally available.

## Fail-closed rules

Start with `Not verified from current official documentation.` when:

- no official source supports a material claim
- available sources conflict
- only a different cloud or product edition is documented
- a source appears obsolete and no current replacement is found
- local implementation and official prerequisites cannot be reconciled

Then state the smallest answer that remains supported and list the missing evidence. Do not soften uncertainty into a recommendation.

## Research sequence

1. Parse the question and identify cloud, product, runtime, region, and access dependencies.
2. Read only the local files needed to establish project context.
3. Search official Databricks documentation with current product terminology.
4. Search official cloud documentation for shared-responsibility details.
5. Check prerequisites, limits, status, and examples.
6. Draft the direct answer.
7. Validate each material sentence against the claim ledger.
8. Remove unsupported detail and redundant sources.

## Code quality

- Match local language and dependency versions when discovered.
- Keep code minimal and use placeholders for environment-specific values.
- Exclude credentials, account identifiers, fixed connection profiles, and assumed object names.
- Prefer read-only metadata or query examples.
- Clearly separate documented code from project-specific adaptation.
- Never claim execution unless the observed result is available.

## Required output contract

Use:

1. `Answer`
2. `Product status`
3. `Minimal example`
4. `Caveats`
5. `Sources`

If no code helps, write `Minimal example: Not needed`.

The answer must:

- lead with the conclusion
- stay within five short paragraphs or eight bullets
- label each discussed feature `GA`, `Public Preview`, `Beta`, `Private Preview`, `Experimental`, or `status not verified`
- cite every material prerequisite, limit, capability, and status
- include only sources actually used
- use public URLs

## Exact example prompts

- `/technical-answer Does Genie Code discover an edited agent skill in the current chat, or must I start a new chat?`
- `/technical-answer Explain Unity Catalog external locations with AWS storage permissions and cite both sides.`
- `/technical-answer Check this repository's Python constraints and show the smallest supported read-only SDK example.`
- `/technical-answer What Azure networking prerequisites apply, and which claims cannot be verified?`

## Official starting points

- https://docs.databricks.com/
- https://docs.aws.amazon.com/
- https://learn.microsoft.com/azure/
- https://cloud.google.com/docs
