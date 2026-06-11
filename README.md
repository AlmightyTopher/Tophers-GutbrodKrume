# Topher's GutbrodKrume

Good bread. Better crumbs. Verified AI handoffs.

A local-first AI project continuity and handoff system. Records AI-assisted
project work as hash-addressed, content-verified breadcrumbs.

## CLI

```bash
krume init       # Initialize .krume store
krume note --summary "..."   # Record a breadcrumb
krume read <ref> # Read an object by hash
krume check      # Forehead Check — verify store integrity
```

## Concepts

| Term        | Meaning                                  |
|-------------|------------------------------------------|
| Krume       | A breadcrumb (hash-addressed event)      |
| Krate       | Exported handoff packet                  |
| Trail Note  | Readable handoff summary                 |
| Trailhead   | Root pointer (first event)               |
| Proof       | Evidence object                          |
| Stake       | Decision object                          |
| Snag        | Problem/blocker object                   |
| Checkpoint  | Snapshot object                          |
| Forehead Check | Verification command (`krume check`)  |

## Store

```
.krume/
  config.json
  objects/sha256/          # Immutable content-addressed storage
  refs/                    # Mutable pointers (trailhead, latest-event, trail.log)
  export/                  # Generated handoff views
  policy/                  # Capture/redact/verify rules
  cache/                   # Rebuildable indexes
```

## License

MIT
