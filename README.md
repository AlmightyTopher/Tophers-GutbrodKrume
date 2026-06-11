# Topher's GutbrodKrume

Good bread. Better crumbs. Verified AI handoffs.

## What it is

Topher's GutbrodKrume is a local-first AI project continuity and handoff system.
It records AI-assisted project work as hash-addressed, content-verified breadcrumbs
that any AI tool can read and continue from.

- **Gutbrod** = good bread
- **Krume** = crumb
- **Brotkrume** = bread crumb

## Why it exists

AI tools forget context between sessions. GutbrodKrume preserves a tamper-evident
trail of commands run, decisions made, blockers found, and handoff packets — so
the next session picks up exactly where the last one stopped.

Existing files are baseline reality, not Proof.
No task is complete without verified output, Proof, Checkpoint, and updated Krate.

## Install for local development

```bash
git clone <repo-url>
cd Tophers-GutbrodKrume
python -m krume version
```

Requires Python 3.11+ and no dependencies beyond the standard library.

## Quick start: new project

```bash
krume init
krume run -- python --version
krume checkpoint
krume krate
krume check
```

## Quick start: existing project

```bash
krume adopt
krume check
```

## Core commands

| Command            | Purpose                                        |
|--------------------|-------------------------------------------------|
| `krume init`       | Initialize a new Krume store                   |
| `krume adopt`      | Adopt an existing project into Krume tracking  |
| `krume note`       | Record a breadcrumb event note                 |
| `krume run`        | Run a command and capture Proof                |
| `krume checkpoint` | Create a Checkpoint snapshot of project state  |
| `krume krate`      | Create the current portable Krate handoff      |
| `krume stake`      | Record a decision Stake                        |
| `krume snag`       | Record a Snag (blocker or problem)             |
| `krume read`       | Read a Krume object by hash ref                |
| `krume check`      | Run the Forehead Check on store integrity      |
| `krume version`    | Show the Krume version                         |

## Normal workflow

1. `krume init` or `krume adopt` to start.
2. `krume run -- <command>` when verification matters.
3. `krume stake` to record decisions.
4. `krume snag` to record blockers.
5. `krume checkpoint` to snapshot state.
6. `krume krate` to build the handoff packet.
7. `krume check` to verify integrity.
8. Read `current-krate.json` and `krume read <trailhead>` to continue.

Decision/blocker workflow:

```bash
krume stake --title "Use local CAS" --body "Keep project state repo-local and content-addressed."
krume snag --title "External API unavailable" --body "Live verification blocked until service returns." --status blocked
krume krate
```

Read current handoff:

```bash
krume read "$(cat .krume/refs/trailhead)"
```

Windows PowerShell equivalent:

```powershell
krume read (Get-Content .krume\refs\trailhead)
```

## Verification rule

Two rules govern all Krume work:

- **Existing files are baseline reality, not Proof.** Pre-existing file content is
  inventoried but has no Proof trail. Only `krume run` creates verifiable Proof.
- **No task is complete without verified output, Proof, Checkpoint, and updated Krate.**
  Every task must produce a `krume run` (verified output), a `krume checkpoint`
  (state snapshot), a `krume krate` (handoff packet), and a passing `krume check`
  before the session ends.

## Object store layout

```
.krume/
  config.json
  objects/sha256/          # Immutable content-addressed storage
  refs/                    # Mutable pointers (trailhead, latest-event, trail.log)
  export/                  # Generated handoff views (current-krate.json, current-trail-note.md)
  policy/                  # Capture/redact/verify rules
  cache/                   # Rebuildable indexes
```

## AI handoff protocol

When an AI tool reads this project, it should:

1. Read `.krume/export/current-krate.json` if it exists.
2. Resolve `trailhead_ref` with `krume read <hash>`.
3. Inspect Proof objects before trusting summaries.
4. Continue from `priority_queue`.
5. Use `krume stake` for decisions, `krume snag` for blockers.
6. Run commands through `krume run -- <command>` when verification matters.
7. Run `krume checkpoint`, `krume krate`, then `krume check` before stopping.

No task is complete without verified output, Proof, Checkpoint, and updated Krate.

## Development and tests

Run tests with Python's built-in unittest:

```bash
python -m unittest discover -s tests -v
```

## Current phase status

| Phase | Tag               | What it does                            |
|-------|-------------------|-----------------------------------------|
| 1     | `v0.1.0-phase1`   | Core CAS + init/note/read/check         |
| 2     | `v0.2.0-phase2`   | Command Proof capture                   |
| 3     | `v0.3.0-phase3`   | Checkpoint + Krate handoff              |
| 4     | `v0.4.0-phase4`   | Adopt existing projects safely          |
| 5     | `v0.5.0-phase5`   | Stake + Snag records                    |
| 6     | `v0.6.0-phase6`   | Stake/Snag Krate integration + CRLF fix |
| 7     | `v0.7.0-phase7`   | Release hardening (version, docs, help) |

## License

MIT
