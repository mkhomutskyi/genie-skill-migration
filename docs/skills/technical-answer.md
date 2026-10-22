# technical-answer

## Purpose and user

Answers one Databricks technical question from current official documentation. Every material claim is checked against a source, every feature gets a status label, and the skill says "Not verified from current official documentation." when it cannot back a claim.

It is for engineers, architects, and admins who need a short answer they can trust.

## Requirements

- Web search or another way to read current public documentation in the session. Without it, the skill fails closed instead of answering from memory.
- No data access is needed.

## Install and invoke

Create a folder named `technical-answer` in your personal skills folder and upload `skills/technical-answer/SKILL.md` into it. Check first that no skill with that name exists.

- Genie One documents `/Workspace/Users/{email}/.assistant/skills/`.
- Genie Code documents `/Users/{username}/.assistant/skills/`. It can also load skills from a registered folder.

In the workspace I tested, both paths pointed to the same home folder, and one upload appeared in both products.

Start a new chat, then type `/technical-answer` in Genie One or `@technical-answer` in Genie Code. See [Install, invoke and verify](../install-and-verify.md) for the commands.

## Example question

The answer is not in the skill, so it has to come from the docs.

Exact prompt:

```text
/technical-answer On AWS, how many folders deep can a Genie One skill go, how many files or folders can one skill have, and can a skill include images? Do not run SQL.
```

Expected behavior:

- Up to three folders deep and 50 files or folders per skill, text files only, so no images.
- Cites https://docs.databricks.com/aws/en/genie-one/chat.
- Uses a status label only if the docs state one; otherwise `status not verified`.
- Uses the headings Answer, Product status, Minimal example, Caveats, and Sources.

## Missing-input test

Exact prompt:

```text
/technical-answer What networking do I need to set up for private connectivity to serverless compute? Do not run SQL.
```

Expected behavior: it asks which cloud before researching, because the answer differs on AWS, Azure, and Google Cloud.

## Limitations

- It is only as current as the pages it can reach.
- Private Preview features are often undocumented, so they usually come back `status not verified`.
- It does not run code or change anything.
- Genie One reads related past conversations on its own and cites them as "Read past conversation". In one earlier test it copied a wrong sentence from a recalled test chat of the same skill. A new chat picks up skill edits, but it does not stop recall. Check the recall citations before you judge an answer. In my tests, I removed my own earlier test chats before rerunning a case. See [Live results](../live-results.md).
- Genie Code knows which cloud the current workspace runs on. Before the fix it used that cloud when the user had not named one. The skill now tells it to ask instead.

## Changes in this revision

- Added who it is for, a requirements block, and a `compatibility` field.
- It now fails closed when web search and documentation retrieval are off.
- Added the `Private Preview` and `Experimental` labels from the Databricks release types page.
- It now asks when the cloud or the product is ambiguous.
- The first check, before any search: if the answer depends on the cloud and the user did not name one, ask which cloud and stop.
- The cloud must come from the user's message, not from the workspace, the environment, or an earlier chat.

## Test history

The 2026-10-14 "10 of 10 passed" run checked that the skill loaded and kept its output format. The cases in `evals/held_out.json` add a question whose answer is not in the skill.

Final live run, 2026-10-20 to 2026-10-22, on SKILL.md hash `8367101ccb90`: the held-out and missing-input cases passed in Genie One (`/`) and Genie Code (`@`). The failures found on the way, and the fixes, are listed in [Live results](../live-results.md).

## Sources

- https://docs.databricks.com/aws/en/release-notes/release-types
- https://docs.databricks.com/aws/en/genie-one/chat
