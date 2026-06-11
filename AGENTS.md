# AGENTS.md — Topher's GutbrodKrume

## Project Identity

- **Name:** Topher's GutbrodKrume
- **CLI:** `krume`
- **Store dir:** `.krume/`
- **Language:** Python 3.11+ (standard library only for Phase 1)

## Phase 2 Scope (current)

Commands: `krume init`, `krume note --summary`, `krume read`, `krume run -- <command>`, `krume check`

Store layout:
- `.krume/objects/sha256/` — immutable CAS
- `.krume/refs/` — mutable pointers (trailhead, trail.log, latest-event)
- `.krume/export/` — generated handoff views
- `.krume/policy/` — capture/redact/verify rules
- `.krume/cache/` — rebuildable indexes

### Object schemas (Phase 2)
- `krume/content/v1` — raw text blobs (stdout, stderr)
- `krume/output/v1` — references stdout/stderr content blobs
- `krume/command/v1` — captured command metadata (argv, cwd, platform, times, exit code)
- `krume/proof/v1` — verification evidence linking command → output → event

Hashing: SHA-256, canonical JSON (`sort_keys=True, separators=(",",":")`)

Object ref format: `krume:sha256:<64_hex_chars>`

## Do NOT

- Implement database, SQLite, daemon, cloud, web UI, MCP server, etc.
- Add Phase 3+ features (`krume checkpoint`, `krume krate`, `krume adopt`, `krume stake`, `krume snag`).
- Refactor unrelated code.
- Add dependencies beyond Python stdlib.
