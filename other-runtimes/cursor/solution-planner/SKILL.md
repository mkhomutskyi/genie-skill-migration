---
name: solution-planner
description: Design the smallest public-documentation-backed Databricks solution from integration, latency, scale, governance, reliability, recovery, observability, and cost requirements.
disable-model-invocation: true
---

# Solution Planner

Use `/solution-planner <requirements>` to produce a read-only architecture recommendation and phased implementation plan. Do not deploy or modify anything.

## Required inputs

Capture:

- source
- destination
- latency target
- scale and growth
- change pattern: append, update, delete, snapshot, CDC, or mixed
- cloud
- governance requirements
- reliability target
- recovery objectives
- observability requirements
- cost constraints

The core inputs are source, destination, latency target, and cloud. If two or more core inputs are missing, ask at most three short questions in one message and stop before drafting a plan. The cloud counts as given only when the user names it; when it is missing, one question must ask for it.

If one core input or any other input is missing, mark it `unknown`, make the smallest conservative assumption needed to continue, and show how the choice changes if the assumption is wrong.

This is the Cursor variant. The Genie skill in `skills/solution-planner` is the primary version. It needs web search or documentation fetch to cite product choices; without it, label every status `status not verified`.

## Runtime adaptation

- Inspect local project files for existing formats, dependencies, infrastructure constraints, and naming conventions.
- Use local context to avoid duplicate components, but validate product capabilities through current public documentation.
- A configured Databricks connection may be used only for read-only metadata or `SELECT` discovery.
- Never hardcode or request a profile, credential, host, token, workspace identifier, or warehouse identifier.
- Without a connection, provide optional read-only discovery SQL and label it `not executed`.

Never create catalogs, schemas, tables, pipelines, jobs, endpoints, warehouses, policies, permissions, storage, networks, or cloud resources. Never send the plan.

## Selection principles

1. Start with the fewest managed components that meet stated requirements.
2. Prefer Unity Catalog for governed data and access boundaries.
3. Choose ingestion by source and change semantics, considering Lakeflow Connect only when its current public connector support matches.
4. Choose Lakeflow pipelines when managed batch or streaming transformations materially satisfy reliability and observability needs.
5. Use Lakeflow Jobs only when orchestration beyond a pipeline is required.
6. Use Databricks SQL and an existing SQL warehouse for SQL serving when it meets latency and concurrency needs.
7. Add Delta Sharing only for an explicit cross-boundary sharing requirement.
8. Add serving or application components only when the destination requires them.
9. Do not add a component merely because it is available.

Validate each selected capability, prerequisite, limitation, and status with current public Databricks documentation and matching AWS, Microsoft Azure, or Google Cloud documentation where cloud behavior matters.

Label product status as `GA`, `Public Preview`, `Beta`, `Private Preview`, `Experimental`, or `status not verified`, and cite the page you used next to each product choice. A page or section without a release label does not state `GA`; use `status not verified` unless a page or the release notes say the feature is generally available. Quote the release words from the cited page next to each status. List any component that is not `GA` under risks. Fail closed on unsupported claims.

## Planning workflow

### 1. Normalize requirements

Turn prose into measurable values and distinguish requirements from preferences.

### 2. Build a decision table

For every proposed component state:

- requirement satisfied
- why the component is necessary
- documented prerequisite
- product status
- cost driver
- simpler rejected option

### 3. Recommend the minimum stack

Choose one primary architecture. Include exactly one alternative and explain the tradeoff that would justify it.

### 4. Draw the architecture

Use ASCII only:

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

Replace generic labels with selected public products and data boundaries. Do not imply deployment.

### 5. Describe data flow

Number each transition. Include protocol or format, checkpoint or state behavior, schema handling, update/delete handling, and destination contract.

### 6. Address operations

Cover:

- availability and retry behavior
- idempotency and replay
- recovery point and recovery time
- data quality
- lineage and access
- metrics, logs, and alert inputs
- capacity and major cost drivers

### 7. Create a phased plan

Use:

- Phase 0: validate assumptions with read-only checks
- Phase 1: smallest end-to-end slice
- Phase 2: reliability and governance
- Phase 3: scale, performance, and cost validation

Each phase has entry criteria, deliverables, validation, and rollback concept. Stop before execution.

## Output contract

Return exactly:

1. `Requirements and assumptions`
2. `Recommended smallest stack`
3. `Status and evidence`
4. `ASCII architecture`
5. `Data flow`
6. `Reliability, recovery, governance, and observability`
7. `Cost drivers`
8. `One alternative and tradeoff`
9. `Risks and open decisions`
10. `Phased plan`
11. `Sources`

Use no more than six public sources and cite only material claims. Keep the whole answer under 900 words, not counting the diagram, with one sentence per operational item and one line per phase field. Cite sources only in the status table and the source list. Before you answer, check that every status has quoted release words or is `status not verified`, that every product in the stack table has a status row with its own source link (find a page or drop the product), that there are at most six distinct sources, that the answer is under 900 words, and that the diagram has no Unicode arrows such as "→".

## Exact example prompts

- `/solution-planner Source: PostgreSQL. Destination: governed Delta tables and SQL analytics. Latency: 15 minutes. Scale: 500 GB growing 5 GB/day. Changes: inserts, updates, deletes. Cloud: AWS. Governance: row-level access and lineage. Reliability: 99.9%. Recovery: RPO 15 minutes, RTO 2 hours. Observability: freshness and failure metrics. Cost: minimize idle compute.`
- `/solution-planner Plan a GCS-to-Delta append pipeline with hourly latency, 20 TB scale, Unity Catalog governance, daily recovery point, monitored freshness, and a strict cost ceiling.`
- `/solution-planner Use this repository's existing components, recommend the smallest supported stack, include one alternative, and do not deploy.`

## Public starting points

- https://docs.databricks.com/
- https://docs.databricks.com/aws/en/data-governance/unity-catalog/
- https://docs.databricks.com/aws/en/ldp/
