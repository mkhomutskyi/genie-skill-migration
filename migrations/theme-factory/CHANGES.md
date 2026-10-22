# theme-factory: changes for Databricks Genie

Source: https://github.com/anthropics/skills/tree/dbd4588f9e1033efb41dad4bef2f7947c8993d44/skills/theme-factory
License: Apache-2.0 (`LICENSE.txt` in the skill folder).
Original files: `upstream/theme-factory/`, byte-identical to the source commit.
Full diff: `genie.diff`.

| # | Change | Label | Why |
|---|---|---|---|
| 1 | Removed `theme-showcase.pdf` | Required for Genie One | The Genie One documentation says skills support text files only; PDFs are not supported. Genie Code documents no file-type limit, so the same copy is used for both. |
| 2 | Step 1 "Display the PDF" became "Read `themes/` and show a table of name, mood, hex colors and fonts" | Required | The step pointed at the removed file. The theme files already hold the same information as text. |
| 3 | "Each showcased in `theme-showcase.pdf`" became "each defined in `themes/`" | Required | Same reason. |
| 4 | Step 4 "apply to the deck" now names artifacts Genie can produce, and says to return the theme values when it cannot edit the artifact | Binding | What Genie can create or edit depends on the product and the session: connectors, documents, and Genie One code execution (Public Preview) differ. The step names what to produce and falls back to theme values when the deck cannot be edited in the session. |
| 5 | Added a modification notice after the frontmatter | Required by the license | Apache-2.0 section 4. |

Not changed: the 10 theme files, the description and the "Create your Own Theme" section.
