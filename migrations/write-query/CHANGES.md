# write-query: changes for Databricks Genie

Source: https://github.com/anthropics/knowledge-work-plugins/tree/a266ab8c3c754a3ccf7a634044fc1595fc06e50e/data/skills/write-query
License: Apache-2.0 (`data/LICENSE` in the source repository, copied to `genie/write-query/LICENSE`).
Original files: `upstream/write-query/`, byte-identical to the source commit.
Full diff: `genie.diff`.

| # | Change | Label | Why |
|---|---|---|---|
| 1 | Removed the link to `../../CONNECTORS.md` | Required | The file is outside the skill folder. It is not uploaded with the skill, so the link points at nothing. |
| 2 | Pointed "see `sql-queries` skill" at a bundled `references/databricks-sql.md` | Required | `write-query` relies on a second skill that is not installed in Genie. The reference is the Databricks SQL section of that skill, copied without changes. |
| 3 | "If a data warehouse MCP server is connected" became "Use the Unity Catalog metadata available to you in Genie" | Binding | I chose Unity Catalog discovery as the binding. Genie One and Genie Code can use MCP servers, but a skill cannot assume that a particular data warehouse MCP server is connected in the user's session. Unity Catalog metadata is available in both products without extra setup and follows the user's grants. If your session does have the MCP server the original expects, you can keep that line. |
| 4 | "Ask which dialect" became "Default to Databricks SQL" | Binding | Genie runs Databricks SQL. Other dialects stay available on request. |
| 5 | "Offer to run the query" became "Run only when asked; read-only `SELECT`; may start an auto-stopped warehouse" | Guardrail | Running a query uses compute and can start a warehouse. |
| 6 | Removed `argument-hint` from the frontmatter | Optional | It is a Claude Code hint and not part of the Agent Skills specification. |
| 7 | Usage shows `/write-query` (Genie One) and `@write-query` (Genie Code); "Claude will help" became "Genie will look in Unity Catalog" | Optional | Wording only. |
| 8 | Added a modification notice after the frontmatter, and the license file | Required by the license | Apache-2.0 section 4. |
| 9 | Added: if no table is named, show the candidate tables (or say none were found) and ask which one to use; do not pick or invent a table | Guardrail | Found in live tests. Without a named table, Genie One picked an existing demo table on its own and Genie Code invented a placeholder table. |

Not changed:
- The description still mentions Snowflake, BigQuery and Postgres. It affects automatic selection only.
- The bundled reference keeps `MERGE`, `OPTIMIZE`, `ZORDER` and partitioning advice as written upstream. The skill writes `SELECT` queries unless asked. Current Databricks guidance prefers liquid clustering for new tables; that is a note for readers, not a change to the source.
