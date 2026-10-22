---
name: my-skill
description: One sentence that says what the skill does and when to use it. Genie shows this text in the skill list.
compatibility: Databricks Genie One and Genie Code. List the features, data and privileges the skill needs, and what it does when they are missing.
---

# My Skill

Invoke as `/my-skill` in Genie One or `@my-skill` in Genie Code.

State the boundary in one line, for example: Read-only. Do not create or change data, resources, SQL warehouses, permissions, settings, code, or communications.

First check, before any search or query: name the one input the answer cannot do without, and say to ask for it and stop when the user's message does not give it. Do not take it from the workspace, the environment, or an earlier chat.

## Who this is for

The people who use this skill and what they already have access to.

## Requirements

- Features: for example web search or documentation retrieval.
- Data: the tables or views it reads, or "none".
- Privileges: for example `USE CATALOG`, `USE SCHEMA` and `SELECT` on each table.
- Compute: an existing SQL warehouse, or "none". Never create or resize one.

## Data source

Use one of these, in this order, and say which one you used in the first line of the answer:

1. A table or metric view the user names, when the needed access is available.
2. Rows the user pastes, labeled `from supplied rows, not queried`.
3. The built-in sample, only when the user asks for `sample` or `demo`.

If none applies, do not show numbers. Say that live data was not queried and ask for the missing input.

## Missing or ambiguous input

- List each input that changes the answer, and the one short question to ask for it.
- Ask at most three questions in one message, then stop.

## Method

1. The steps the skill follows.
2. Keep observations (values and deltas) apart from explanations (hypotheses with a read-only test).

## Output

Return these sections in this order:

1. `Answer`
2. `Evidence`
3. `SQL`, labeled `executed` or `not executed`
4. `Limits`

Keep the whole answer under N words.

Before you answer, check:

- every number matches the data source you named
- every claim about product status quotes the release words from its source, or says `status not verified`
- the answer is under N words

## Exact example prompts

- `/my-skill <a prompt whose answer is not written in this file>`
- `/my-skill <a prompt with a missing input>`
