---
name: adit
description: ADIT — manage cloud project linking and development intents
---

**Requested action:** `$ARGUMENTS`

## Routing

Parse the requested action above and follow the **first matching rule**:

1. Action is `link` (with optional flags) → run `npx adit cloud link` with the appropriate flags mapped from the arguments: `--force`, `--skip-docs`, `--skip-commits`, `--dry-run`.
2. Action is `intent` (with optional flags) → run `npx adit cloud intent` with the appropriate flags mapped from the arguments: `--id <value>`, `--state <value>`. Add `--json` for structured output.
3. No action, empty arguments, or unrecognized action → display the **Help** section below as your response. Do not run any commands.

---

## Help

Display the following when no valid action is provided:

### ADIT Cloud

ADIT tracks your AI-assisted development sessions, links project context to the cloud, and helps you manage development intents (plans).

**Usage:** `/adit <action> [options]`

#### `link` — Sync project to adit-cloud

Uploads git metadata (branches, commits) and project documents for intent planning.

| Option | Description |
|---|---|
| `--force` | Clear cache and re-link from scratch |
| `--skip-docs` | Only upload git metadata, skip documents |
| `--skip-commits` | Skip commit history upload |
| `--dry-run` | Preview what would be uploaded |

#### `intent` — View development intents

Shows intents (development plans) and tasks from the connected adit-cloud project.

| Option | Description |
|---|---|
| `--id <id>` | Show a specific intent by ID |
| `--state <state>` | Filter by state (e.g. `capture`, `execution`, `shipped`) |

#### Examples

- `/adit link` — link the project with defaults
- `/adit link --force --skip-docs` — re-link, git metadata only
- `/adit intent` — list all intents
- `/adit intent --state execution` — show active intents

> **Tip:** Not logged in? Run `npx adit cloud login` in your terminal first.
