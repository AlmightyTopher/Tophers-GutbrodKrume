# Topher's GutbrodKrume Protocol

Authoritative project state lives in `.krume/export/current-krate.json`.

Before doing work:

1. Read `.krume/export/current-krate.json` if it exists.
2. Resolve `trailhead_ref` with `krume read <hash>`.
3. Inspect Proof objects before trusting summaries.
4. Continue from `priority_queue`.
5. Use `krume stake` for decisions.
6. Use `krume snag` for blockers.
7. Run commands through `krume run -- <command>` when verification matters.
8. Run `krume checkpoint`.
9. Run `krume krate`.
10. Run `krume check`.

No task is complete without verified output, Proof, Checkpoint, and updated Krate.

## Project Identity

- **Name:** Topher's GutbrodKrume
- **CLI:** `krume`
- **Store dir:** `.krume/`
- **Language:** Python 3.11+ (standard library only)

## Store layout

```
.krume/
  objects/sha256/          # Immutable CAS
  refs/                    # Mutable pointers (trailhead, trail.log, latest-event)
  export/                  # Generated handoff views
  policy/                  # Capture/redact/verify rules
  cache/                   # Rebuildable indexes
```

Hashing: SHA-256, canonical JSON (`sort_keys=True, separators=(",",":")`)

Object ref format: `krume:sha256:<64_hex_chars>`

## Do NOT

- Implement database, SQLite, daemon, cloud, web UI, MCP server, etc.
- Add dependencies beyond Python stdlib.
- Commit `.krume/` unless explicitly instructed.
