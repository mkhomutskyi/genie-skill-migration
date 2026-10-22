---
name: table-review
description: Review supplied table metadata and sample rows for quality risks and next checks.
disable-model-invocation: true
---

# Table Review

Review only the metadata and sample rows supplied by the user.

1. State the observed grain, columns, and time coverage.
2. Apply the [quality checklist](references/checklist.md).
3. Separate observations from hypotheses.
4. Return read-only Structured Query Language (SQL) checks for missing evidence.
5. Never claim that a query ran unless its result is present in the conversation.

Return `Scope`, `Observed risks`, `Read-only checks`, and `Limitations`.
