"""Tests for krume.cli"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from krume.cli import main, build_parser


class TestCLIInit(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_cwd = os.getcwd()
        os.chdir(self.tmpdir)

    def tearDown(self):
        os.chdir(self.orig_cwd)
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_init_creates_store(self):
        exit_code = main(["init"])
        self.assertEqual(exit_code, 0)
        self.assertTrue(os.path.exists(".krume/config.json"))
        self.assertTrue(os.path.exists(".krume/objects/sha256"))
        self.assertTrue(os.path.exists(".krume/refs/trailhead"))
        self.assertTrue(os.path.exists(".krume/refs/latest-event"))
        self.assertTrue(os.path.exists(".krume/refs/trail.log"))

    def test_init_output(self):
        with patch("sys.stdout") as mock_stdout:
            exit_code = main(["init"])
            self.assertEqual(exit_code, 0)

    def test_init_idempotent(self):
        main(["init"])
        exit_code = main(["init"])
        self.assertEqual(exit_code, 0)

    def test_parser_basic(self):
        parser = build_parser()
        args = parser.parse_args(["init"])
        self.assertEqual(args.command, "init")

    def test_parser_note(self):
        parser = build_parser()
        args = parser.parse_args(["note", "--summary", "hello"])
        self.assertEqual(args.command, "note")
        self.assertEqual(args.summary, "hello")

    def test_parser_read(self):
        parser = build_parser()
        args = parser.parse_args(["read", "krume:sha256:" + "a" * 64])
        self.assertEqual(args.command, "read")
        self.assertEqual(args.hash, "krume:sha256:" + "a" * 64)

    def test_parser_check(self):
        parser = build_parser()
        args = parser.parse_args(["check"])
        self.assertEqual(args.command, "check")


class TestCLINote(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_cwd = os.getcwd()
        os.chdir(self.tmpdir)
        main(["init"])

    def tearDown(self):
        os.chdir(self.orig_cwd)
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_note_creates_event(self):
        exit_code = main(["note", "--summary", "Test note"])
        self.assertEqual(exit_code, 0)

    def test_note_appends_trail(self):
        main(["note", "--summary", "First"])
        main(["note", "--summary", "Second"])
        with open(".krume/refs/trail.log") as f:
            lines = [l.strip() for l in f if l.strip()]
        self.assertEqual(len(lines), 2)

    def test_note_updates_latest_event(self):
        main(["note", "--summary", "Something"])
        with open(".krume/refs/latest-event") as f:
            ref = f.read().strip()
        self.assertTrue(ref.startswith("krume:sha256:"))

    def test_note_with_tag(self):
        exit_code = main(["note", "--summary", "Tagged", "--tag", "test"])
        self.assertEqual(exit_code, 0)

    def test_note_without_init_fails(self):
        other = tempfile.mkdtemp()
        orig = os.getcwd()
        os.chdir(other)
        exit_code = main(["note", "--summary", "Should fail"])
        os.chdir(orig)
        import shutil
        shutil.rmtree(other, ignore_errors=True)
        self.assertEqual(exit_code, 1)


class TestCLIRead(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_cwd = os.getcwd()
        os.chdir(self.tmpdir)
        main(["init"])
        main(["note", "--summary", "Read test"])
        with open(".krume/refs/latest-event") as f:
            self.ref = f.read().strip()

    def tearDown(self):
        os.chdir(self.orig_cwd)
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_read_valid_ref(self):
        exit_code = main(["read", self.ref])
        self.assertEqual(exit_code, 0)

    def test_read_invalid_ref_format(self):
        exit_code = main(["read", "invalid"])
        self.assertEqual(exit_code, 1)

    def test_read_missing_hash(self):
        ref = "krume:sha256:" + "f" * 64
        exit_code = main(["read", ref])
        self.assertEqual(exit_code, 1)


class TestCLICheck(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_cwd = os.getcwd()
        os.chdir(self.tmpdir)

    def tearDown(self):
        os.chdir(self.orig_cwd)
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_check_fails_before_init(self):
        exit_code = main(["check"])
        self.assertEqual(exit_code, 1)

    def test_check_passes_after_init(self):
        main(["init"])
        exit_code = main(["check"])
        self.assertEqual(exit_code, 0)

    def test_check_passes_with_note(self):
        main(["init"])
        main(["note", "--summary", "Check test"])
        exit_code = main(["check"])
        self.assertEqual(exit_code, 0)

    def test_check_fails_with_corrupt_object(self):
        main(["init"])
        main(["note", "--summary", "Corrupt me"])
        with open(".krume/refs/trail.log") as f:
            lines = [l.strip() for l in f if l.strip()]
        ref = lines[0]
        hex_hash = ref[len("krume:sha256:"):]
        obj_dir = os.path.join(".krume/objects/sha256", hex_hash[:2])
        obj_path = os.path.join(obj_dir, hex_hash[2:])
        with open(obj_path, "wb") as f:
            f.write(b"garbage")
        exit_code = main(["check"])
        self.assertEqual(exit_code, 1)


class TestCLIErrorHandling(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_cwd = os.getcwd()
        os.chdir(self.tmpdir)

    def tearDown(self):
        os.chdir(self.orig_cwd)
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_unknown_command(self):
        with self.assertRaises(SystemExit) as cm:
            main(["unknown"])
        self.assertEqual(cm.exception.code, 2)

    def test_note_missing_summary(self):
        with self.assertRaises(SystemExit):
            main(["note"])
