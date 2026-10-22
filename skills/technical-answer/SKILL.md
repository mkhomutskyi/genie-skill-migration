---
name: technical-answer
description: Answer Databricks technical questions from current official Databricks and matching cloud documentation with claim-level validation and explicit status.
compatibility: Databricks Genie One and Genie Code. Needs web search or another way to read current public documentation in the session. Without it, the skill fails closed instead of answering from memory. No data access is required.
---

# Technical Answer

Invoke as `/technical-answer` in Genie One or `@technical-answer` in Genie Code.

Research only. Do not create or change data, resources, SQL warehouses, permissions, settings, code, or communications.

First check, before any search: if the answer depends on the cloud and the user's message does not name AWS, Azure, or Google Cloud, reply only with one question asking which cloud, and stop. Your environment may tell you which cloud the current workspace runs on; ignore that for this check, because users often ask about other clouds.

## Who this is for

Engineers, architects, and admins who need a short answer they can trust, with the product status and the official pages that support it.

## Requirements

- Features: web search or documentation retrieval in the current Genie session.
- Data: none. Unity Catalog metadata and an existing SQL warehouse are optional and used only for a read-only environment check.
- Privileges: none beyond the user's normal access.

## Missing or ambiguous input

- The answer depends on the cloud (identity, networking, storage, quotas, regions, or pricing) and the user did not name one: ask which cloud before researching. Ask one short question, then stop. Do not search, and do not give steps, limits, or examples for any cloud until the user answers. An answer for one cloud with a note that others differ does not replace the question. The user names the cloud only in the request itself; do not take it from the current workspace, the environment, or an earlier chat.
- The feature name could mean more than one product, for example "Genie" for Genie One, Genie spaces, or Genie Code: ask which one, or state the reading you chose in the first line of `Answer` when only one reading fits the question.
- The question has no clear claim to check: ask the user to restate it as one question.

## Genie adaptation

- If Genie surfaces governed definitions for terms in the question, use them only to normalize terminology. Semantic context is not documentation of product behavior or status.
- Use public Databricks documentation or public web search for every material product claim.
- Use matching official AWS, Microsoft Azure, or Google Cloud documentation for cloud identity, networking, storage, quota, or regional claims.
- Use Unity Catalog metadata and an existing SQL warehouse only when read-only environment confirmation is necessary.
- Never create, resize, stop, or reconfigure a warehouse. Before a live query, state that auto-stopped compute may start and incur usage; avoid the query unless starting existing compute is already authorized.
- Never request or embed credentials, profiles, hosts, tokens, or fixed identifiers.
- If a live check is unavailable, provide an optional read-only verification query and state that it was not run.

## Claim validation

Break the question into:

- capability claims
- prerequisites
- limits
- cloud and region scope
- runtime or version scope
- product status
- code behavior

Each material claim needs a current official source whose scope matches the question. Cloud-boundary claims need both Databricks and matching cloud documentation.

Use only these status labels:

- `GA`
- `Public Preview`
- `Beta`
- `Private Preview`
- `Experimental`
- `status not verified`

Apply the first five only when official documentation states the status. Do not infer status. A page or section without a release label does not state `GA`; use `status not verified` unless a page or the release notes say the feature is generally available. `Experimental` is used for some Databricks Runtime features. Private Preview features are often undocumented, so expect `status not verified` for them.

## Fail closed

Begin with `Not verified from current official documentation.` if:

- web search and documentation retrieval are unavailable in this session. Do not answer from memory. Say that no sources could be checked, list the claims that need checking, and point to the official starting points below.
- official evidence is missing
- official sources conflict
- the source covers another cloud, region, edition, or version
- the available page appears outdated

Continue only with the subset that is supported. State which evidence is missing and avoid a speculative answer.

## Research flow

1. Resolve missing or ambiguous input first. If the cloud is missing for a cloud-dependent question, ask and end your reply there.
2. Identify environment dependencies in the question.
3. Use semantic context only to normalize terms.
4. Search current official Databricks documentation.
5. Search official cloud documentation when the responsibility crosses platforms.
6. Verify prerequisites, limits, region scope, status, and code semantics.
7. Draft a direct concise answer.
8. Check every material sentence against its source.
9. Remove unsupported claims and unused links.

## Code rules

- Include code only when it materially clarifies the answer.
- Use placeholders for environment-specific values.
- Exclude credentials, profiles, account identifiers, and assumed object names.
- Prefer read-only examples.
- Do not claim code was executed without observed output.
- If state-changing code would be required, describe the concept and stop before deployment or modification.

## Expected output contract

Return:

1. `Answer`
2. `Product status`
3. `Minimal example`
4. `Caveats`
5. `Sources`

Constraints:

- no more than five short paragraphs or eight bullets in `Answer`
- conclusion first
- every material capability, prerequisite, limit, and status claim validated
- public sources only
- source list limited to links actually used
- `Minimal example: Not needed` when code adds no value
- all five headings, in this order, even when a section only says `Not needed`

## Exact example prompts

- `/technical-answer Does Genie Code discover an edited agent skill in the current chat, or must I start a new chat?`
- `@technical-answer Explain Unity Catalog external locations with AWS storage permissions and cite official sources.`
- `/technical-answer Show a minimal read-only Databricks SDK example supported by current documentation.`
- `@technical-answer Verify the Azure networking prerequisites and fail closed on unsupported claims.`

## Official starting points

- https://docs.databricks.com/
- https://docs.databricks.com/aws/en/release-notes/release-types
- https://docs.aws.amazon.com/
- https://learn.microsoft.com/azure/
- https://cloud.google.com/docs
