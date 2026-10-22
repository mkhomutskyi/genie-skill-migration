---
name: write-query
description: Write optimized SQL for your dialect with best practices. Use when translating a natural-language data need into SQL, building a multi-CTE query with joins and aggregations, optimizing a query against a large partitioned table, or getting dialect-specific syntax for Snowflake, BigQuery, Postgres, etc.
---

<!-- Modified for Databricks Genie by Maks Khomutskyi on 2026-10-20 from anthropics/knowledge-work-plugins data/skills/write-query at commit a266ab8. The changes are listed in the repository file migrations/write-query/CHANGES.md. -->

# /write-query - Write Optimized SQL

Write a SQL query from a natural language description, optimized for your specific SQL dialect and following best practices.

## Usage

```
/write-query <description of what data you need>     (Genie One)
@write-query <description of what data you need>     (Genie Code)
```

## Workflow

### 1. Understand the Request

Parse the user's description to identify:

- **Output columns**: What fields should the result include?
- **Filters**: What conditions limit the data (time ranges, segments, statuses)?
- **Aggregations**: Are there GROUP BY operations, counts, sums, averages?
- **Joins**: Does this require combining multiple tables?
- **Ordering**: How should results be sorted?
- **Limits**: Is there a top-N or sample requirement?

### 2. Determine SQL Dialect

Default to **Databricks SQL**. Use another dialect only when the user asks for one, for example to translate a query for another system.

### 3. Discover Schema (Unity Catalog)

Use the Unity Catalog metadata available to you in Genie, and only tables the user can access:

1. Search for relevant tables based on the user's description
2. Inspect column names, types, and relationships
3. Check for partitioning or clustering keys that affect performance
4. Look for pre-built views or materialized views that might simplify the query

If the user did not name a table, show the candidate tables you found, or say that you found none, and ask which one to use before writing the query. Do not pick a table for the user and do not invent table names.

### 4. Write the Query

Follow these best practices:

**Structure:**
- Use CTEs (WITH clauses) for readability when queries have multiple logical steps
- One CTE per logical transformation or data source
- Name CTEs descriptively (e.g., `daily_signups`, `active_users`, `revenue_by_product`)

**Performance:**
- Never use `SELECT *` in production queries -- specify only needed columns
- Filter early (push WHERE clauses as close to the base tables as possible)
- Use partition filters when available (especially date partitions)
- Prefer `EXISTS` over `IN` for subqueries with large result sets
- Use appropriate JOIN types (don't use LEFT JOIN when INNER JOIN is correct)
- Avoid correlated subqueries when a JOIN or window function works
- Be mindful of exploding joins (many-to-many)

**Readability:**
- Add comments explaining the "why" for non-obvious logic
- Use consistent indentation and formatting
- Alias tables with meaningful short names (not just `a`, `b`, `c`)
- Put each major clause on its own line

**Dialect-specific optimizations:**
- Apply dialect-specific syntax and functions (see `references/databricks-sql.md`)
- Use dialect-appropriate date functions, string functions, and window syntax
- Note any dialect-specific performance features (e.g., Snowflake clustering, BigQuery partitioning)

### 5. Present the Query

Provide:

1. **The complete query** in a SQL code block with syntax highlighting
2. **Brief explanation** of what each CTE or section does
3. **Performance notes** if relevant (expected cost, partition usage, potential bottlenecks)
4. **Modification suggestions** -- how to adjust for common variations (different time range, different granularity, additional filters)

### 6. Offer to Execute

Do not run the query unless the user asks. Before running it, say that it uses a SQL warehouse the user can already use and that it may start an auto-stopped warehouse. Run only read-only `SELECT` queries. If the user wants to run it themselves, the query is ready to copy-paste.

## Examples

**Simple aggregation:**
```
/write-query Count of orders by status for the last 30 days
```

**Complex analysis:**
```
/write-query Cohort retention analysis -- group users by their signup month, then show what percentage are still active (had at least one event) at 1, 3, 6, and 12 months after signup
```

**Performance-critical:**
```
/write-query We have a 500M row events table partitioned by date. Find the top 100 users by event count in the last 7 days with their most recent event type.
```

## Tips

- Mention another SQL dialect upfront if you need one; the default is Databricks SQL
- If you know the table names, include them -- otherwise Genie will look for them in Unity Catalog
- Specify if you need the query to be idempotent (safe to re-run) or one-time
- For recurring queries, mention if it should be parameterized for date ranges
