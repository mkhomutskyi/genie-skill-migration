---
name: solution-planner
description: Plan a minimal Databricks architecture from source, destination, latency, scale, change, cloud, governance, reliability, recovery, observability, and cost requirements.
argument-hint: "[architecture requirements]"
allowed-tools: Read, Grep, Glob, WebFetch, WebSearch
---

# Solution Planner

Design and document. Never deploy, provision, configure, modify, or send.

## Input contract

Extract these fields from the request:

1. source
2. destination
3. latency
4. current scale and growth
5. append, update, delete, snapshot, CDC, or mixed change pattern
6. cloud
7. governance
8. reliability
9. recovery point and recovery time
10. observability
11. cost constraints

The core fields are source, destination, latency, and cloud. If two or more core fields are missing, ask at most three short questions in one message and stop before drafting a plan. The cloud counts as given only when the user names it; when it is missing, one question must ask for it.

Otherwise record missing values as `unknown`. Use explicit conservative assumptions only when they preserve a smaller design and do not hide material risk. Explain the decision that depends on each assumption.

This is the Claude Code variant. The Genie skill in `skills/solution-planner` is the primary version. `allowed-tools` pre-approves the listed read and web tools; it does not block other tools, so the rules here still apply. Without working web tools, label every status `status not verified`.

## Claude Code adaptation

- Search the local project for existing libraries, data formats, orchestration, infrastructure definitions, and conventions.
- Reuse existing components conceptually when they satisfy the requirements.
- Validate all product capabilities against current official public documentation.
- For cloud-dependent storage, networking, identity, reliability, or quotas, also validate against official AWS, Microsoft Azure, or Google Cloud documentation.
- Use a preconfigured Databricks connection only for read-only metadata and `SELECT` discovery.
- Never choose or embed a profile, host, credential, token, workspace identifier, or warehouse identifier.
- If no connection exists, provide optional discovery SQL marked `not executed`.
- Never run a bundled script or claim that one ran.

## Minimality test

For every component, answer:

- Which stated requirement needs it?
- Can an existing platform capability satisfy that requirement?
- What public prerequisite or limitation applies?
- What operational and cost burden does it add?
- What breaks if it is removed?

Remove components without a concrete answer.

Consider public products only when justified, including:

- Unity Catalog for governance
- Lakeflow Connect for a documented supported ingestion path
- Lakeflow pipelines for managed batch or streaming transformations
- Lakeflow Jobs for orchestration not covered by a pipeline
- Databricks SQL with an existing SQL warehouse for SQL serving
- Delta Sharing for explicit cross-boundary sharing

Do not assume connector availability, regional support, or product status. Label each selected capability `GA`, `Public Preview`, `Beta`, `Private Preview`, `Experimental`, or `status not verified` from official sources, and cite the page you used next to each product choice. A page or section without a release label does not state `GA`; use `status not verified` unless a page or the release notes say the feature is generally available. Quote the release words from the cited page next to each status. List any component that is not `GA` under risks. Fail closed when a material claim cannot be supported.

## Architecture procedure

1. Normalize the inputs into measurable acceptance criteria.
2. Identify data boundaries, trust boundaries, and the system of record.
3. Select the smallest primary stack.
4. Validate source semantics, schema evolution, state, replay, and update/delete handling.
5. Map governance, reliability, recovery, observability, and cost requirements.
6. Create one alternative that changes a meaningful tradeoff.
7. Draw an ASCII architecture.
8. Describe numbered data flow.
9. Record risks and unresolved decisions.
10. Create a phased implementation plan that stops before deployment.

Use ASCII characters only:

```text
+------------+     +-------------------+     +----------------+
| Source     | --> | Ingest/Transform  | --> | Destination    |
+------------+     +-------------------+     +----------------+
                           |
                           v
                    +--------------+
                    | Governance   |
                    +--------------+
```

Replace labels with actual selected products and boundaries.

## Operational coverage

Address:

- delivery semantics and idempotency
- checkpointing, replay, and backfill
- schema evolution and data quality
- retries and failure isolation
- recovery point and recovery time
- Unity Catalog ownership, lineage, and access boundaries
- freshness, throughput, lag, errors, and cost signals
- capacity assumptions and major cost drivers

Never invent a service objective that the user did not provide.

## Phased plan

- `Phase 0 - Evidence`: read-only discovery and requirement validation.
- `Phase 1 - Thin slice`: smallest source-to-destination path.
- `Phase 2 - Controls`: governance, quality, reliability, and recovery.
- `Phase 3 - Validation`: scale, performance, observability, and cost tests.

For each phase provide entry criteria, deliverables, validation evidence, and rollback concept. Do not execute any phase.

## Required output contract

1. `Normalized requirements`
2. `Assumptions`
3. `Smallest recommended stack`
4. `Capability status and evidence`
5. `ASCII architecture`
6. `Numbered data flow`
7. `Operational design`
8. `Cost model and drivers`
9. `One alternative and tradeoff`
10. `Risks and open decisions`
11. `Phased plan`
12. `Sources`

Use no more than six public sources. Keep the whole answer under 900 words, not counting the diagram, with one sentence per operational item and one line per phase field. Cite sources only in the status table and the source list. Before you answer, check that every status has quoted release words or is `status not verified`, that every product in the stack table has a status row with its own source link (find a page or drop the product), that there are at most six distinct sources, that the answer is under 900 words, and that the diagram has no Unicode arrows such as "→".

## Exact example prompts

- `/solution-planner Source: PostgreSQL. Destination: governed Delta tables and SQL analytics. Latency: 15 minutes. Scale: 500 GB growing 5 GB/day. Changes: inserts, updates, deletes. Cloud: AWS. Governance: row-level access and lineage. Reliability: 99.9%. Recovery: RPO 15 minutes, RTO 2 hours. Observability: freshness and failures. Cost: minimize idle compute.`
- `/solution-planner Plan a GCS-to-Delta append flow with hourly latency, 20 TB scale, Unity Catalog governance, daily recovery point, monitored freshness, and strict cost limits.`
- `/solution-planner Inspect existing project choices, recommend one minimal architecture and one alternative, then stop before deployment.`

## Public starting points

- https://docs.databricks.com/
- https://docs.databricks.com/aws/en/data-governance/unity-catalog/
- https://docs.databricks.com/aws/en/ldp/
