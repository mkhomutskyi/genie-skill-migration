# cost-investigator

## Purpose and user

Explains Databricks usage and estimated list-price cost: totals and trends, why two totals differ, what drives an increase, and which savings ideas the data supports. It is read-only.

It is for account admins, workspace admins, FinOps analysts, and platform owners who can already read billing system tables. Other users get SQL to hand to an admin.

## Requirements

- `USE CATALOG` on `system`, `USE SCHEMA` on `system.billing`, and `SELECT` on `system.billing.usage` and `system.billing.list_prices`. Account admins who are also metastore admins have this by default.
- An existing SQL warehouse. A query can start an auto-stopped warehouse.
- The data covers every workspace in the account, so share results with care.

## Install and invoke

Create a folder named `cost-investigator` in your personal skills folder and upload `skills/cost-investigator/SKILL.md` into it. Check first that no skill with that name exists.

- Genie One documents `/Workspace/Users/{email}/.assistant/skills/`.
- Genie Code documents `/Users/{username}/.assistant/skills/`. It can also load skills from a registered folder.

In the workspace I tested, both paths pointed to the same home folder, and one upload appeared in both products.

Start a new chat, then type `/cost-investigator` in Genie One or `@cost-investigator` in Genie Code. See [Install, invoke and verify](../install-and-verify.md) for the commands.

## Example with supplied rows

The numbers live in the prompt, not in the skill, so the answer has to be computed.

Exact prompt:

```text
/cost-investigator overview Do not run SQL. Use only these rows. Usage on Azure in August 2026: SKU_M ORIGINAL 40 units, SKU_M RETRACTION -40 units, SKU_M RESTATEMENT 32 units, SKU_N ORIGINAL 6 units, SKU_N ORIGINAL 4 units, SKU_O ORIGINAL 5 units. Prices in USD per unit: SKU_M default 0.90 and effective_list 0.75, SKU_N default 2.20 and effective_list 2.20, SKU_O has no price row. Show estimated list-price cost by SKU and the total.
```

Expected behavior:

- SKU_M nets to 32 units and 24.00 USD, priced with `effective_list`.
- SKU_N is 10 units and 22.00 USD.
- SKU_O is 5 units and unmatched. It gets no price and no zero cost.
- The priced total is 46.00 USD, with one unmatched SKU.
- The result is labeled `from supplied rows, not queried` and called estimated list-price cost.

Common wrong answers: 50.80 USD means the `default` price key was used. 76.00 USD means the retraction was dropped.

## Missing-input test

Exact prompt:

```text
/cost-investigator Which SKUs cost the most last quarter? Do not run SQL.
```

Expected behavior: read-only SQL labeled `not executed`, a clear "live data was not queried", the access needed, and the boundaries of the last complete calendar quarter. No numbers from the built-in sample.

## Limitations

- Estimated list price is not a bill. It ignores discounts and contracts.
- Billing data arrives during the day, so the current day is excluded by default.
- Breakdowns by workspace, product, or tags depend on which columns exist.
- Genie One reads related past conversations on its own and cites them as "Read past conversation". In one earlier test it copied a wrong sentence from a recalled test chat of the same skill. A new chat picks up skill edits, but it does not stop recall. Check the recall citations before you judge an answer. In my tests, I removed my own earlier test chats before rerunning a case. See [Live results](../live-results.md).

## Changes in this revision

- Added who it is for, a requirements block, and a `compatibility` field.
- Prices now use `pricing.effective_list.default`, which the pricing docs describe as the effective list price used for calculating cost. The earlier `pricing.default` is meant for simple long-term estimates.
- The built-in sample now runs only on request (`sample` or `demo`). Without access the skill returns SQL marked `not executed` and no sample numbers.
- Added rules for missing period, mode, scope, and prices.

## Test history

The 2026-10-14 "10 of 10 passed" run used prompts that asked for the sample whose answer is written in the skill. It shows the skill loaded and followed its sample, not that it computes correctly. The cases in `evals/held_out.json` replace it.

Final live run, 2026-10-20 to 2026-10-22, on SKILL.md hash `480b1570ff47`: the held-out and missing-input cases passed in Genie One (`/`) and Genie Code (`@`). The failures found on the way, and the fixes, are listed in [Live results](../live-results.md).

## Sources

- https://docs.databricks.com/aws/en/admin/system-tables/billing
- https://docs.databricks.com/aws/en/admin/system-tables/pricing
- https://docs.databricks.com/aws/en/admin/system-tables/
