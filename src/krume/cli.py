"""Topher's GutbrodKrume — CLI entry point"""

import argparse
import json
import sys
import os

from .store import KrumStore, REF_PREFIX, _now_iso


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
        "check": cmd_check,
    }

    fn = dispatch.get(args.command)
    if fn is None:
        parser.print_help()
        return 2

    return fn(store, args)


if __name__ == "__main__":
    sys.exit(main())
