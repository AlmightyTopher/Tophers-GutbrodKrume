"""Tests for krume.store"""

import json
import os
import tempfile
import unittest
from pathlib import Path

from krume.store import (
    KrumStore,
    REF_PREFIX,
    _canonical_json,
    _hash_bytes,
    _ref_to_hash,
    _hash_to_ref,
    _now_iso,
    _object_storage_path,
    KRUME_DIR,
    OBJECTS_DIR,
    REFS_DIR,
)


class TestHashing(unittest.TestCase):
    def test_canonical_json_sorted_keys(self):
        a = _canonical_json({"b": 2, "a": 1})
        b = _canonical_json({"a": 1, "b": 2})
        self.assertEqual(a, b)

    def test_canonical_json_compact(self):
        raw = _canonical_json({"a": 1})
        self.assertNotIn(b" ", raw)
        self.assertEqual(raw, b'{"a":1}')

    def test_hash_consistency(self):
        data = b"hello world"
        h1 = _hash_bytes(data)
        h2 = _hash_bytes(data)
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)

    def test_ref_roundtrip(self):
        h = "a" * 64
        ref = _hash_to_ref(h)
        self.assertEqual(ref, f"{REF_PREFIX}{h}")
        self.assertEqual(_ref_to_hash(ref), h)

    def test_ref_invalid_prefix(self):
        with self.assertRaises(ValueError):
            _ref_to_hash("invalid:abc")

    def test_ref_invalid_hash(self):
        with self.assertRaises(ValueError):
            _ref_to_hash(f"{REF_PREFIX}xyz")

    def test_object_storage_path(self):
        h = "ab" + "c" * 62
        p = _object_storage_path(h)
        self.assertIn(os.sep.join(["ab", "c" * 62]), p)
        self.assertTrue(p.replace("\\", "/").endswith("ab/cccc" + "c" * 58))

    def test_now_iso_format(self):
        ts = _now_iso()
        self.assertIn("T", ts)
        self.assertTrue(ts.endswith("Z"))


class TestKrumStoreInit(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store = KrumStore(self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_init_creates_structure(self):
        self.store.init()
        self.assertTrue(os.path.exists(os.path.join(self.tmpdir, KRUME_DIR, "config.json")))
        self.assertTrue(os.path.exists(os.path.join(self.tmpdir, OBJECTS_DIR)))
        self.assertTrue(os.path.exists(os.path.join(self.tmpdir, REFS_DIR)))
        self.assertTrue(os.path.exists(os.path.join(self.tmpdir, KRUME_DIR, "export")))
        self.assertTrue(os.path.exists(os.path.join(self.tmpdir, KRUME_DIR, "policy")))
        self.assertTrue(os.path.exists(os.path.join(self.tmpdir, KRUME_DIR, "cache")))

    def test_init_creates_object_subdirs(self):
        self.store.init()
        for prefix in range(256):
            self.assertTrue(
                os.path.exists(
                    os.path.join(self.tmpdir, OBJECTS_DIR, f"{prefix:02x}")
                )
            )

    def test_init_creates_refs(self):
        self.store.init()
        self.assertEqual(self.store.read_ref("trailhead"), "UNKNOWN")
        self.assertEqual(self.store.read_ref("previous"), "UNKNOWN")
        self.assertEqual(self.store.read_ref("latest-event"), "UNKNOWN")
        trail = self.store.read_trail()
        self.assertEqual(trail, [])

    def test_init_creates_policy_files(self):
        self.store.init()
        for name in ("capture-rules.json", "redact-rules.json", "verify-rules.json"):
            self.assertTrue(
                os.path.exists(os.path.join(self.tmpdir, KRUME_DIR, "policy", name))
            )

    def test_is_initialized(self):
        self.assertFalse(self.store.is_initialized())
        self.store.init()
        self.assertTrue(self.store.is_initialized())

    def test_init_idempotent(self):
        self.store.init()
        self.store.init()
        self.assertTrue(self.store.is_initialized())


class TestKrumStoreObjects(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store = KrumStore(self.tmpdir)
        self.store.init()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_put_and_get_object(self):
        data = {"hello": "world", "n": 42}
        ref = self.store.put_object(data)
        self.assertTrue(ref.startswith(REF_PREFIX))
        retrieved = self.store.get_object(ref)
        self.assertEqual(retrieved, data)

    def test_put_object_dedup(self):
        data = {"a": 1}
        ref1 = self.store.put_object(data)
        ref2 = self.store.put_object(data)
        self.assertEqual(ref1, ref2)

    def test_get_missing_object(self):
        ref = f"{REF_PREFIX}{'a'*64}"
        with self.assertRaises(FileNotFoundError):
            self.store.get_object(ref)

    def test_verify_object(self):
        data = {"test": True}
        ref = self.store.put_object(data)
        self.assertTrue(self.store.verify_object(ref))

    def test_verify_missing(self):
        ref = f"{REF_PREFIX}{'a'*64}"
        self.assertFalse(self.store.verify_object(ref))

    def test_object_exists(self):
        ref = self.store.put_object({"x": 1})
        self.assertTrue(self.store.object_exists(ref))
        bad_ref = f"{REF_PREFIX}{'b'*64}"
        self.assertFalse(self.store.object_exists(bad_ref))

    def test_invalid_ref_raises(self):
        with self.assertRaises(ValueError):
            self.store.get_object("badref")


class TestKrumStoreTrail(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store = KrumStore(self.tmpdir)
        self.store.init()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_append_and_read_trail(self):
        ref = self.store.put_object({"seq": 1})
        self.store.append_trail(ref)
        trail = self.store.read_trail()
        self.assertEqual(trail, [ref])

    def test_write_and_read_ref(self):
        self.store.write_ref("test-ref", "hello")
        self.assertEqual(self.store.read_ref("test-ref"), "hello")

    def test_read_missing_ref(self):
        self.assertIsNone(self.store.read_ref("nonexistent"))


class TestKrumStoreCheck(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store = KrumStore(self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_check_fails_if_not_initialized(self):
        issues = self.store.check()
        self.assertTrue(any("Missing directory" in i for i in issues))

    def test_check_passes_after_init(self):
        self.store.init()
        issues = self.store.check()
        self.assertEqual(issues, [])

    def test_check_passes_with_valid_objects(self):
        self.store.init()
        ref = self.store.put_object({"kind": "note", "summary": "test"})
        self.store.append_trail(ref)
        self.store.write_ref("latest-event", ref)
        issues = self.store.check()
        self.assertEqual(issues, [])

    def test_check_fails_corrupt_object(self):
        self.store.init()
        ref = self.store.put_object({"a": 1})
        self.store.append_trail(ref)
        self.store.write_ref("latest-event", ref)

        hex_hash = _ref_to_hash(ref)
        path = os.path.join(self.tmpdir, _object_storage_path(hex_hash))
        with open(path, "wb") as f:
            f.write(b"corrupt")

        issues = self.store.check()
        self.assertTrue(any("corrupt" in i for i in issues))
