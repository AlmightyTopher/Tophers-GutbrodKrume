"""Topher's GutbrodKrume — CLI entry point"""

import argparse
import json
import subprocess
import sys
import os
import time

import datetime

from .store import KrumStore, REF_PREFIX, KRUME_DIR, _now_iso


def build_parser():
    parser = argparse.ArgumentParser(
        prog="krume",
        description="Topher's GutbrodKrume — verified AI project breadcrumbs",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    init_p = sub.add_parser("init", help="Initialize .krume store in current directory")
    note_p = sub.add_parser("note", help="Record a krume event note")
    note_p.add_argument("--summary", required=True, help="Summary of the event")
    note_p.add_argument("--tag", action="append", default=[], help="Add a tag (repeatable)")

    read_p = sub.add_parser("read", help="Read a krume object by hash ref")
    read_p.add_argument("hash", help="krume:sha256:<hash> reference")

    run_p = sub.add_parser("run", help="Run a command and capture breadcrumbs")
    run_p.add_argument("argv", nargs=argparse.REMAINDER, help="Command to run (use -- to separate)")

    adopt_p = sub.add_parser("adopt", help="Adopt existing project into GutbrodKrume tracking")

    checkpoint_p = sub.add_parser("checkpoint", help="Create a point-in-time project state record")
    krate_p = sub.add_parser("krate", help="Create the current portable handoff packet")

    check_p = sub.add_parser("check", help="Run Forehead Check on the store")

    return parser


def cmd_init(store, args):
    if store.is_initialized():
        print("Topher's GutbrodKrume already initialized.")
        return 0
    store.init()
    trailhead = store.read_ref("trailhead")
    print("Topher's GutbrodKrume initialized.")
    print(f"Store: .krume/")
    print(f"Trailhead: {trailhead}")
    return 0


def cmd_note(store, args):
    if not store.is_initialized():
        print("ERROR: .krume/ not initialized. Run 'krume init' first.", file=sys.stderr)
        return 1

    parent_ref = store.read_ref("latest-event")
    if parent_ref == "UNKNOWN":
        parent_ref = None

    event = {
        "schema": "krume/event/v1",
        "kind": "note",
        "created_at": _now_iso(),
        "actor": {
            "type": "human",
            "name": "Topher",
            "tool": None,
        },
        "summary": args.summary,
        "refs": [],
        "parent_event_ref": parent_ref,
        "tags": args.tag if args.tag else [],
    }

    ref = store.put_object(event)
    store.append_trail(ref)
    store.write_ref("latest-event", ref)

    trailhead = store.read_ref("trailhead")
    if trailhead == "UNKNOWN" or trailhead is None:
        store.write_ref("trailhead", ref)
        store.write_ref("previous", "UNKNOWN")
    else:
        store.write_ref("previous", trailhead)

    _update_exports(store, event, ref)

    print(f"Krume written: {ref}")
    return 0


def _update_exports(store, event, ref):
    krate = {
        "schema": "krume/krate/v1",
        "latest_event": ref,
        "event_count": len(store.read_trail()),
        "summary": event.get("summary", ""),
        "created_at": event.get("created_at"),
    }
    store.write_export_krate(krate)

    trail_note = f"""# Trail Note

**Ref:** {ref}
**Kind:** {event.get('kind', 'note')}
**Created:** {event.get('created_at', 'unknown')}
**Summary:** {event.get('summary', '')}

**Tags:** {', '.join(event.get('tags', [])) or 'none'}
**Parent:** {event.get('parent_event_ref', 'none')}
"""
    store.write_export_trail_note(trail_note.strip())


def cmd_read(store, args):
    ref = args.hash
    if not ref.startswith(REF_PREFIX):
        print(f"ERROR: Invalid ref format — must start with '{REF_PREFIX}'", file=sys.stderr)
        return 1
    try:
        obj = store.get_object(ref)
    except FileNotFoundError:
        print(f"ERROR: Object not found: {ref}", file=sys.stderr)
        return 1
    except ValueError:
        print(f"ERROR: Hash mismatch (object corrupt): {ref}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    print(json.dumps(obj, indent=2, ensure_ascii=False))
    return 0


def cmd_check(store, args):
    if not store.is_initialized():
        print("Forehead Check: FAIL\n", file=sys.stderr)
        print("Store: FAIL", file=sys.stderr)
        print("ERROR: .krume/ not initialized.", file=sys.stderr)
        return 1

    issues = store.check()
    if issues:
        print("Forehead Check: FAIL\n")
        print("Store: FAIL")
        for issue in issues:
            print(issue)
        return 1

    print("Forehead Check: PASS\n")
    print("Store: PASS")
    return 0


def cmd_run(store, args):
    if not store.is_initialized():
        print("ERROR: .krume/ not initialized. Run 'krume init' first.", file=sys.stderr)
        return 1

    command = args.argv
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        print("ERROR: No command specified.", file=sys.stderr)
        return 1

    summary = " ".join(command)
    if len(summary) > 80:
        summary = summary[:77] + "..."

    cwd = os.getcwd()
    platform_info = sys.platform
    started_at = _now_iso()
    start_time = time.time()

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            cwd=cwd,
        )
    except FileNotFoundError:
        print(f"ERROR: Command not found: {command[0]}", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    end_time = time.time()
    ended_at = _now_iso()
    duration_ms = int((end_time - start_time) * 1000)
    exit_code = result.returncode

    stdout_ref = store.put_content(result.stdout)
    stderr_ref = store.put_content(result.stderr)

    output_obj = {
        "schema": "krume/output/v1",
        "stdout_ref": stdout_ref,
        "stderr_ref": stderr_ref,
        "stdout_size": len(result.stdout),
        "stderr_size": len(result.stderr),
    }
    output_ref = store.put_object(output_obj)

    cmd_obj = {
        "schema": "krume/command/v1",
        "argv": command,
        "cwd": cwd,
        "platform": platform_info,
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_ms": duration_ms,
        "exit_code": exit_code,
    }
    cmd_ref = store.put_object(cmd_obj)

    proof_obj = {
        "schema": "krume/proof/v1",
        "verified_at": _now_iso(),
        "command_ref": cmd_ref,
        "output_ref": output_ref,
        "exit_code": exit_code,
    }
    proof_ref = store.put_object(proof_obj)

    parent_ref = store.read_ref("latest-event")
    if parent_ref == "UNKNOWN":
        parent_ref = None

    event_obj = {
        "schema": "krume/event/v1",
        "kind": "run",
        "created_at": _now_iso(),
        "actor": {
            "type": "human",
            "name": "Topher",
            "tool": None,
        },
        "summary": f"Ran: {summary}",
        "refs": [cmd_ref, output_ref, proof_ref],
        "parent_event_ref": parent_ref,
        "tags": ["run"],
    }
    event_ref = store.put_object(event_obj)

    store.append_trail(event_ref)
    store.write_ref("latest-event", event_ref)

    trailhead = store.read_ref("trailhead")
    if trailhead == "UNKNOWN" or trailhead is None:
        store.write_ref("trailhead", event_ref)
        store.write_ref("previous", "UNKNOWN")
    else:
        store.write_ref("previous", trailhead)

    krate = {
        "schema": "krume/krate/v1",
        "latest_event": event_ref,
        "event_count": len(store.read_trail()),
        "summary": f"Ran: {summary}",
        "created_at": event_obj["created_at"],
        "command": cmd_ref,
        "proof": proof_ref,
    }
    store.write_export_krate(krate)

    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)

    print(f"Krume written: {event_ref}")
    print(f"  Command:  {cmd_ref}")
    print(f"  Output:   {output_ref}")
    print(f"  Proof:    {proof_ref}")

    return exit_code


# ── Phase 3 helpers ─────────────────────────────────────────────


def _git_info(store):
    info = {"available": False}
    try:
        r = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=5)
        if r.returncode != 0:
            return info
        r2 = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True, timeout=5)
        branch = r2.stdout.strip() if r2.returncode == 0 else None
        r3 = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5)
        head = r3.stdout.strip() if r3.returncode == 0 else None
        r4 = subprocess.run(["git", "status", "--short"], capture_output=True, text=True, timeout=5)
        status_text = r4.stdout
        dirty = bool(status_text.strip())
        status_ref = store.put_content(status_text) if status_text else None
        info = {
            "available": True,
            "head": head,
            "branch": branch,
            "dirty": dirty,
            "status_ref": status_ref,
        }
    except Exception:
        info = {"available": False}
    return info


def _scan_proof_refs(store):
    proof_refs = []
    trail = store.read_trail()
    for line in trail:
        try:
            ev = store.get_object(line)
        except Exception:
            continue
        if ev.get("kind") == "run":
            refs = ev.get("refs", [])
            for r in refs:
                try:
                    obj = store.get_object(r)
                except Exception:
                    continue
                if obj.get("schema") == "krume/proof/v1":
                    if r not in proof_refs:
                        proof_refs.append(r)
        if ev.get("kind") == "checkpoint":
            refs = ev.get("refs", [])
            for r in refs:
                try:
                    obj = store.get_object(r)
                except Exception:
                    continue
                if obj.get("schema") == "krume/checkpoint/v1":
                    cproofs = obj.get("proof_refs", [])
                    for p in cproofs:
                        if p not in proof_refs:
                            proof_refs.append(p)
    return proof_refs


def _determine_vstatus(store, proof_refs, git_info):
    if not proof_refs:
        return "UNKNOWN"
    latest_proof_ref = proof_refs[-1]
    try:
        proof = store.get_object(latest_proof_ref)
    except Exception:
        return "UNKNOWN"
    ec = proof.get("exit_code", -1)
    if ec != 0:
        return "FAIL"
    if not git_info.get("available"):
        return "UNKNOWN"
    if git_info.get("dirty"):
        return "UNKNOWN"
    return "PASS"


def _append_event(store, event):
    ref = store.put_object(event)
    store.append_trail(ref)
    store.write_ref("latest-event", ref)
    trailhead = store.read_ref("trailhead")
    if trailhead == "UNKNOWN" or trailhead is None:
        store.write_ref("trailhead", ref)
        store.write_ref("previous", "UNKNOWN")
    else:
        store.write_ref("previous", trailhead)
    return ref


def _scan_files(store):
    entries = []
    root = os.getcwd()
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root)
        parts = rel_dir.replace("\\", "/").split("/")
        if KRUME_DIR in parts:
            continue
        for fn in filenames:
            fp = os.path.join(dirpath, fn)
            rel = os.path.relpath(fp, root).replace("\\", "/")
            try:
                st = os.stat(fp)
                entries.append({
                    "path": rel,
                    "size": st.st_size,
                    "mtime": datetime.datetime.fromtimestamp(
                        st.st_mtime, tz=datetime.timezone.utc
                    ).isoformat().replace("+00:00", "Z"),
                })
            except OSError:
                continue
    entries.sort(key=lambda e: e["path"])
    inventory = {
        "schema": "krume/inventory/v1",
        "project_root": str(root),
        "file_count": len(entries),
        "entries": entries,
        "scanned_at": _now_iso(),
    }
    return store.put_object(inventory), inventory


def cmd_adopt(store, args):
    if store.is_initialized():
        print("ERROR: .krume/ already exists. Use 'krume checkpoint' and 'krume krate' instead.", file=sys.stderr)
        return 1

    store.init()
    print("Topher's GutbrodKrume initialized.")
    print("Store: .krume/")

    inventory_ref, inventory = _scan_files(store)
    file_count = inventory["file_count"]

    gi = _git_info(store)

    checkpoint = {
        "schema": "krume/checkpoint/v1",
        "created_at": _now_iso(),
        "checkpoint_kind": "adoption",
        "git": gi,
        "inventory_ref": inventory_ref,
        "file_count": file_count,
        "latest_event_ref": None,
        "proof_refs": [],
        "verification_status": "UNKNOWN",
    }
    cp_ref = store.put_object(checkpoint)

    event = {
        "schema": "krume/event/v1",
        "kind": "adoption",
        "created_at": _now_iso(),
        "actor": {"type": "system", "name": "krume", "tool": None},
        "summary": f"Adopted project with {file_count} files",
        "refs": [cp_ref, inventory_ref],
        "parent_event_ref": None,
        "tags": ["adoption"],
    }
    old_trailhead = store.read_ref("trailhead")
    event_ref = _append_event(store, event)

    print(f"Adoption Checkpoint written: {cp_ref}")
    print(f"  Files recorded: {file_count}")
    print(f"  Status: UNKNOWN")

    manifest = {
        "schema": "krume/manifest/v1",
        "created_at": _now_iso(),
        "project": "Topher's GutbrodKrume",
        "objective": "Adopted existing project. Establish baseline from current state.",
        "checkpoint_ref": cp_ref,
        "latest_event_ref": event_ref,
        "proof_refs": [],
        "inventory_ref": inventory_ref,
        "priority_queue": [
            {"priority": 1, "title": "Inspect baseline and continue project work", "status": "open", "ref": None}
        ],
        "verification_status": "UNKNOWN",
    }
    manifest_ref = store.put_object(manifest)

    krate = {
        "schema": "krume/krate/v1",
        "created_at": _now_iso(),
        "project": "Topher's GutbrodKrume",
        "from_actor": "krume",
        "to_actor": "any",
        "trailhead_ref": manifest_ref,
        "checkpoint_ref": cp_ref,
        "instructions": {
            "canonical": "Adoption baseline. No Proof exists for pre-existing files. Run krume run to create verified Proof. Run krume check before claiming completion, then write Checkpoint and Krate.",
            "compressed": "Adoption baseline. No Proof for existing files. Create Proof with krume run.",
        },
        "priority_queue": [
            {"priority": 1, "title": "Inspect baseline and continue project work", "status": "open", "ref": None}
        ],
        "proof_refs": [],
        "verification_status": "UNKNOWN",
        "inventory_ref": inventory_ref,
        "reader_protocol": [
            "This is an ADOPTION krate — existing files have NO Proof.",
            "Read the Krate.",
            "Resolve trailhead_ref with krume read.",
            "Run krume run to create verified Proof for any changes.",
            "Run krume check before claiming completion.",
            "Write new Checkpoint and Krate before stopping.",
        ],
    }
    krate_ref = store.put_object(krate)

    store.write_export_krate(krate)

    proof_lines = "No Proof refs captured yet (adoption baseline)."
    trail_note = f"""# Topher's GutbrodKrume Trail Note

## Status Snapshot

- Verification Status: UNKNOWN
- Trailhead: {manifest_ref}
- Checkpoint: {cp_ref}
- Inventory: {inventory_ref}
- Files Recorded: {file_count}
- Latest Event: {event_ref or 'None'}

## Reader Protocol

1. This is an ADOPTION krate — existing files have NO Proof.
2. Read `current-krate.json`.
3. Resolve `trailhead_ref` with `krume read`.
4. Run `krume run` to create verified Proof for changes.
5. Run `krume check`.
6. Write new Checkpoint and Krate before stopping.

## Proof Refs

{proof_lines}

## File Inventory

This krate records {file_count} files at adoption time.
Use `krume read {inventory_ref}` to list all files.
"""
    store.write_export_trail_note(trail_note.strip())

    store.write_ref("previous", old_trailhead if old_trailhead and old_trailhead != "UNKNOWN" else "UNKNOWN")
    store.write_ref("trailhead", manifest_ref)

    print(f"Krate written: .krume/export/current-krate.json")
    print(f"Trail Note written: .krume/export/current-trail-note.md")
    print(f"Trailhead: {manifest_ref}")
    return 0


# ── Phase 3 commands ────────────────────────────────────────────


def cmd_checkpoint(store, args):
    if not store.is_initialized():
        print("ERROR: .krume/ not initialized. Run 'krume init' first.", file=sys.stderr)
        return 1

    latest_event_ref = store.read_ref("latest-event")
    if latest_event_ref == "UNKNOWN":
        latest_event_ref = None

    proof_refs = _scan_proof_refs(store)
    gi = _git_info(store)
    vstatus = _determine_vstatus(store, proof_refs, gi)

    checkpoint = {
        "schema": "krume/checkpoint/v1",
        "created_at": _now_iso(),
        "checkpoint_kind": "standard",
        "git": gi,
        "latest_event_ref": latest_event_ref,
        "proof_refs": proof_refs,
        "verification_status": vstatus,
    }
    cp_ref = store.put_object(checkpoint)

    event = {
        "schema": "krume/event/v1",
        "kind": "checkpoint",
        "created_at": _now_iso(),
        "actor": {"type": "system", "name": "krume", "tool": None},
        "summary": f"Checkpoint: {vstatus}",
        "refs": [cp_ref],
        "parent_event_ref": latest_event_ref,
        "tags": ["checkpoint"],
    }
    _append_event(store, event)

    print(f"Checkpoint written: {cp_ref}")
    print(f"Status: {vstatus}")
    return 0


def cmd_krate(store, args):
    if not store.is_initialized():
        print("ERROR: .krume/ not initialized. Run 'krume init' first.", file=sys.stderr)
        return 1

    latest_event_ref = store.read_ref("latest-event")
    if latest_event_ref == "UNKNOWN":
        latest_event_ref = None

    trail = store.read_trail()

    checkpoint_ref = None
    for line in reversed(trail):
        try:
            ev = store.get_object(line)
        except Exception:
            continue
        if ev.get("kind") == "checkpoint":
            refs = ev.get("refs", [])
            for r in refs:
                try:
                    obj = store.get_object(r)
                except Exception:
                    continue
                if obj.get("schema") == "krume/checkpoint/v1":
                    checkpoint_ref = r
                    break
            if checkpoint_ref:
                break

    proof_refs = _scan_proof_refs(store)
    gi = _git_info(store)
    vstatus = _determine_vstatus(store, proof_refs, gi)

    manifest = {
        "schema": "krume/manifest/v1",
        "created_at": _now_iso(),
        "project": "Topher's GutbrodKrume",
        "objective": "Continue project from verified GutbrodKrume trail.",
        "checkpoint_ref": checkpoint_ref,
        "latest_event_ref": latest_event_ref,
        "proof_refs": proof_refs,
        "priority_queue": [
            {"priority": 1, "title": "Continue from current GutbrodKrume state", "status": "open", "ref": None}
        ],
        "verification_status": vstatus,
    }
    manifest_ref = store.put_object(manifest)

    old_trailhead = store.read_ref("trailhead")
    if old_trailhead == "UNKNOWN":
        old_trailhead = None

    krate = {
        "schema": "krume/krate/v1",
        "created_at": _now_iso(),
        "project": "Topher's GutbrodKrume",
        "from_actor": "krume",
        "to_actor": "any",
        "trailhead_ref": manifest_ref,
        "checkpoint_ref": checkpoint_ref,
        "instructions": {
            "canonical": "Read this Krate, resolve trailhead_ref with krume read, inspect Proof before trusting summaries, continue from priority_queue, run krume check before claiming completion, and write a new Checkpoint and Krate before stopping.",
            "compressed": "Read Krate -> resolve trailhead -> inspect Proof -> follow queue -> check -> checkpoint+krate before stop.",
        },
        "priority_queue": [
            {"priority": 1, "title": "Continue from current GutbrodKrume state", "status": "open", "ref": None}
        ],
        "proof_refs": proof_refs,
        "verification_status": vstatus,
        "reader_protocol": [
            "Read this Krate.",
            "Resolve trailhead_ref with krume read.",
            "Inspect Proof before trusting summaries.",
            "Continue from priority_queue only.",
            "Run krume check before claiming completion.",
            "Write new Checkpoint and Krate before stopping.",
        ],
    }
    krate_ref = store.put_object(krate)

    store.write_export_krate(krate)

    old_trailhead_original = old_trailhead

    proof_lines = "\n".join(f"- {r}" for r in proof_refs) if proof_refs else "No Proof refs captured yet."
    trail_note = f"""# Topher's GutbrodKrume Trail Note

## Status Snapshot

- Verification Status: {vstatus}
- Trailhead: {manifest_ref}
- Checkpoint: {checkpoint_ref or 'None'}
- Latest Event: {latest_event_ref or 'None'}

## Reader Protocol

1. Read `.krume/export/current-krate.json`.
2. Resolve `trailhead_ref` with `krume read <hash>`.
3. Inspect Proof before trusting summaries.
4. Continue from `priority_queue`.
5. Run `krume check`.
6. Write new Checkpoint and Krate before stopping.

## Priority Queue

1. Continue from current GutbrodKrume state.

## Proof Refs

{proof_lines}
"""
    store.write_export_trail_note(trail_note.strip())

    event = {
        "schema": "krume/event/v1",
        "kind": "krate",
        "created_at": _now_iso(),
        "actor": {"type": "system", "name": "krume", "tool": None},
        "summary": f"Krate: {vstatus}",
        "refs": [manifest_ref, krate_ref],
        "parent_event_ref": latest_event_ref,
        "tags": ["krate"],
    }
    event_ref = store.put_object(event)
    store.append_trail(event_ref)
    store.write_ref("latest-event", event_ref)
    store.write_ref("previous", old_trailhead_original if old_trailhead_original else "UNKNOWN")
    store.write_ref("trailhead", manifest_ref)

    print(f"Krate written: .krume/export/current-krate.json")
    print(f"Trail Note written: .krume/export/current-trail-note.md")
    print(f"Trailhead: {manifest_ref}")
    print(f"Status: {vstatus}")
    return 0


# ── Minimal Phase 2 change: add proof_ref to event refs ─────────

def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    parser = build_parser()
    args = parser.parse_args(argv)

    store = KrumStore()

    dispatch = {
        "init": cmd_init,
        "note": cmd_note,
        "read": cmd_read,
        "run": cmd_run,
        "adopt": cmd_adopt,
        "checkpoint": cmd_checkpoint,
        "krate": cmd_krate,
        "check": cmd_check,
    }

    fn = dispatch.get(args.command)
    if fn is None:
        parser.print_help()
        return 2

    return fn(store, args)


if __name__ == "__main__":
    sys.exit(main())
