"""Topher's GutbrodKrume — content-addressable store (CAS)"""

import hashlib
import json
import os
import shutil
import datetime
from pathlib import Path


KRUME_DIR = ".krume"
OBJECTS_DIR = os.path.join(KRUME_DIR, "objects", "sha256")
REFS_DIR = os.path.join(KRUME_DIR, "refs")
EXPORT_DIR = os.path.join(KRUME_DIR, "export")
POLICY_DIR = os.path.join(KRUME_DIR, "policy")
CACHE_DIR = os.path.join(KRUME_DIR, "cache")

REF_PREFIX = "krume:sha256:"


def _canonical_json(obj):
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _hash_bytes(data):
    return hashlib.sha256(data).hexdigest()


def _object_storage_path(hex_hash):
    if len(hex_hash) != 64:
        raise ValueError(f"Invalid hash length: {len(hex_hash)}")
    return os.path.join(OBJECTS_DIR, hex_hash[:2], hex_hash[2:])


def _ref_to_hash(ref):
    if not ref.startswith(REF_PREFIX):
        raise ValueError(f"Invalid ref prefix: {ref}")
    h = ref[len(REF_PREFIX):]
    if len(h) != 64 or not all(c in "0123456789abcdef" for c in h):
        raise ValueError(f"Invalid hash in ref: {ref}")
    return h


def _hash_to_ref(hex_hash):
    return f"{REF_PREFIX}{hex_hash}"


def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def _read_file(path):
    with open(path, "rb") as f:
        return f.read()


def _write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(content)


def _write_text(path, text):
    _write_file(path, text.encode("utf-8"))


def _read_text(path):
    return _read_file(path).decode("utf-8").strip()


def _path_exists(path):
    return os.path.exists(path)


def _ensure_dir(path):
    os.makedirs(path, exist_ok=True)


class KrumStore:
    def __init__(self, root=None):
        self.root = Path(root).resolve() if root else Path.cwd().resolve()

    def _abs(self, *parts):
        return os.path.join(str(self.root), *parts)

    # ── init ──────────────────────────────────────────────────────────

    def init(self):
        targets = [
            self._abs(OBJECTS_DIR),
            self._abs(REFS_DIR),
            self._abs(EXPORT_DIR),
            self._abs(POLICY_DIR),
            self._abs(CACHE_DIR),
        ]
        for d in targets:
            _ensure_dir(d)

        for prefix_byte in range(256):
            _ensure_dir(self._abs(OBJECTS_DIR, f"{prefix_byte:02x}"))

        refs_to_create = ["trailhead", "previous"]
        for name in refs_to_create:
            p = self._abs(REFS_DIR, name)
            if not _path_exists(p):
                _write_text(p, "UNKNOWN")

        if not _path_exists(self._abs(REFS_DIR, "trail.log")):
            _write_text(self._abs(REFS_DIR, "trail.log"), "")

        if not _path_exists(self._abs(REFS_DIR, "latest-event")):
            _write_text(self._abs(REFS_DIR, "latest-event"), "UNKNOWN")

        self._write_default_config()
        self._write_default_policy("capture-rules.json", {"capture_stdout": True, "capture_stderr": True, "capture_env": False})
        self._write_default_policy("redact-rules.json", {"patterns": []})
        self._write_default_policy("verify-rules.json", {"require_proof": True})

    def _write_default_config(self):
        cfg = {
            "schema": "krume/config/v1",
            "store_version": 1,
            "created_at": _now_iso(),
            "project": str(self.root),
        }
        self._write_json(self._abs(KRUME_DIR, "config.json"), cfg)

    def _write_default_policy(self, name, data):
        p = self._abs(POLICY_DIR, name)
        if not _path_exists(p):
            self._write_json(p, data)

    # ── object I/O ────────────────────────────────────────────────────

    def put_object(self, data):
        raw = _canonical_json(data)
        hex_hash = _hash_bytes(raw)
        path = self._abs(_object_storage_path(hex_hash))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not _path_exists(path):
            _write_file(path, raw)
        return _hash_to_ref(hex_hash)

    def get_object(self, ref):
        hex_hash = _ref_to_hash(ref)
        path = self._abs(_object_storage_path(hex_hash))
        if not _path_exists(path):
            raise FileNotFoundError(f"Object not found: {ref}")
        raw = _read_file(path)
        if _hash_bytes(raw) != hex_hash:
            raise ValueError(f"Hash mismatch for: {ref}")
        return json.loads(raw.decode("utf-8"))

    def object_exists(self, ref):
        try:
            hex_hash = _ref_to_hash(ref)
        except ValueError:
            return False
        path = self._abs(_object_storage_path(hex_hash))
        if not _path_exists(path):
            return False
        try:
            raw = _read_file(path)
            return _hash_bytes(raw) == hex_hash
        except Exception:
            return False

    def verify_object(self, ref):
        hex_hash = _ref_to_hash(ref)
        path = self._abs(_object_storage_path(hex_hash))
        if not _path_exists(path):
            return False
        raw = _read_file(path)
        return _hash_bytes(raw) == hex_hash

    # ── ref management ────────────────────────────────────────────────

    def read_ref(self, name):
        p = self._abs(REFS_DIR, name)
        if not _path_exists(p):
            return None
        return _read_text(p)

    def write_ref(self, name, value):
        _write_text(self._abs(REFS_DIR, name), value)

    def append_trail(self, ref):
        with open(self._abs(REFS_DIR, "trail.log"), "a", encoding="utf-8") as f:
            f.write(ref + "\n")

    def read_trail(self):
        p = self._abs(REFS_DIR, "trail.log")
        if not _path_exists(p):
            return []
        raw = _read_text(p)
        return [line for line in raw.split("\n") if line.strip()]

    def write_export_krate(self, data):
        self._write_json(self._abs(EXPORT_DIR, "current-krate.json"), data)

    def write_export_trail_note(self, text):
        _write_text(self._abs(EXPORT_DIR, "current-trail-note.md"), text)

    # ── forehead check ───────────────────────────────────────────────

    def check(self):
        issues = []

        required_dirs = [
            self._abs(OBJECTS_DIR),
            self._abs(REFS_DIR),
            self._abs(EXPORT_DIR),
            self._abs(POLICY_DIR),
            self._abs(CACHE_DIR),
        ]
        for d in required_dirs:
            if not _path_exists(d):
                issues.append(f"Missing directory: {d}")

        required_refs = ["trailhead", "previous", "trail.log", "latest-event"]
        for name in required_refs:
            p = self._abs(REFS_DIR, name)
            if not _path_exists(p):
                issues.append(f"Missing ref: {name}")

        trail = self.read_trail()
        for i, line in enumerate(trail):
            line = line.strip()
            if not line:
                continue
            if not line.startswith(REF_PREFIX):
                issues.append(f"trail.log line {i+1}: invalid ref format: {line}")
                continue
            if not self.object_exists(line):
                issues.append(f"trail.log line {i+1}: object missing or corrupt: {line}")

        latest = self.read_ref("latest-event")
        if latest and latest != "UNKNOWN":
            if not self.object_exists(latest):
                issues.append(f"latest-event ref missing or corrupt: {latest}")

        trailhead = self.read_ref("trailhead")
        if trailhead and trailhead != "UNKNOWN":
            if not self.object_exists(trailhead):
                issues.append(f"trailhead ref missing or corrupt: {trailhead}")

        previous = self.read_ref("previous")
        if previous and previous != "UNKNOWN":
            if not self.object_exists(previous):
                issues.append(f"previous ref missing or corrupt: {previous}")

        krate = None
        try:
            krate = self.read_export_krate()
        except (json.JSONDecodeError, ValueError, OSError) as e:
            issues.append(f"Krate JSON malformed: {e}")

        if krate is not None:
            krate_th = krate.get("trailhead_ref")
            if krate_th:
                if not krate_th.startswith(REF_PREFIX):
                    issues.append(f"Krate trailhead_ref invalid format: {krate_th}")
                elif not self.object_exists(krate_th):
                    issues.append(f"Krate trailhead_ref missing or corrupt: {krate_th}")

            krate_cp = krate.get("checkpoint_ref")
            if krate_cp and krate_cp.startswith(REF_PREFIX):
                if not self.object_exists(krate_cp):
                    issues.append(f"Krate checkpoint_ref missing or corrupt: {krate_cp}")

            if not self.export_trail_note_exists():
                issues.append("Krate exists but Trail Note is missing")

        return issues

    # ── Phase 3 helpers ──────────────────────────────────────────────

    def resolve_if_ref(self, value):
        if value and value != "UNKNOWN" and value.startswith(REF_PREFIX):
            return value
        return None

    # ── content blobs (raw text) ──────────────────────────────────────

    def put_content(self, text):
        data = {
            "schema": "krume/content/v1",
            "data": text,
        }
        return self.put_object(data)

    def get_content(self, ref):
        obj = self.get_object(ref)
        if obj.get("schema") != "krume/content/v1":
            raise ValueError(f"Not a content object: {ref}")
        return obj["data"]

    # ── helpers ───────────────────────────────────────────────────────

    def _write_json(self, path, data):
        raw = _canonical_json(data)
        _write_file(path, raw)

    def is_initialized(self):
        return _path_exists(self._abs(KRUME_DIR, "config.json"))

    # ── export helpers (Phase 3) ─────────────────────────────────────

    def read_export_krate(self):
        p = self._abs(EXPORT_DIR, "current-krate.json")
        if not _path_exists(p):
            return None
        raw = _read_file(p)
        return json.loads(raw.decode("utf-8"))

    def export_krate_exists(self):
        return _path_exists(self._abs(EXPORT_DIR, "current-krate.json"))

    def export_trail_note_exists(self):
        return _path_exists(self._abs(EXPORT_DIR, "current-trail-note.md"))

    def read_export_trail_note_raw(self):
        p = self._abs(EXPORT_DIR, "current-trail-note.md")
        if not _path_exists(p):
            return None
        return _read_file(p).decode("utf-8")
