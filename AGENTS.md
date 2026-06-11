# AGENTS.md — Topher's GutbrodKrume

## Project Identity

- **Name:** Topher's GutbrodKrume
- **CLI:** `krume`
- **Store dir:** `.krume/`
- **Language:** Python 3.11+ (standard library only for Phase 1)

## Phase 1 Scope (current)

Commands: `krume init`, `krume note --summary`, `krume read`, `krume check`

Store layout:
- `.krume/objects/sha256/` — immutable CAS
- `.krume/refs/` — mutable pointers (trailhead, trail.log, latest-event)
- `.krume/export/` — generated handoff views
- `.krume/policy/` — capture/redact/verify rules
- `.krume/cache/` — rebuildable indexes

Hashing: SHA-256, canonical JSON (`sort_keys=True, separators=(",",":")`)

Object ref format: `krume:sha256:<64_hex_chars>`

## Do NOT

- Implement database, SQLite, daemon, cloud, web UI, MCP server, etc.
- Add Phase 2 features (`krume run`, `krume checkpoint`, `krume krate`).
- Refactor unrelated code.
- Add dependencies beyond Python stdlib.
