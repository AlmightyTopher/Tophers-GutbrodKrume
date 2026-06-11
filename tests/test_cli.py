"""Tests for krume.cli"""

import json
import os
import subprocess
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


class TestCLIRun(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_cwd = os.getcwd()
        os.chdir(self.tmpdir)
        main(["init"])

    def tearDown(self):
        os.chdir(self.orig_cwd)
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_run_python(self):
        exit_code = main(["run", sys.executable, "-c", "print('hello')"])
        self.assertEqual(exit_code, 0)

    def test_run_writes_objects(self):
        main(["run", sys.executable, "-c", "print('test')"])
        self.assertTrue(os.path.exists(".krume/refs/latest-event"))
        with open(".krume/refs/latest-event") as f:
            ref = f.read().strip()
        self.assertTrue(ref.startswith("krume:sha256:"))

    def test_run_appends_trail(self):
        main(["run", sys.executable, "-c", "print('one')"])
        main(["run", sys.executable, "-c", "print('two')"])
        with open(".krume/refs/trail.log") as f:
            lines = [l.strip() for l in f if l.strip()]
        self.assertEqual(len(lines), 2)

    def test_run_with_dash_dash(self):
        exit_code = main(["run", "--", sys.executable, "-c", "print('dash')"])
        self.assertEqual(exit_code, 0)

    def test_run_without_init_fails(self):
        other = tempfile.mkdtemp()
        orig = os.getcwd()
        os.chdir(other)
        exit_code = main(["run", sys.executable, "-c", "print('fail')"])
        os.chdir(orig)
        import shutil
        shutil.rmtree(other, ignore_errors=True)
        self.assertEqual(exit_code, 1)

    def test_run_command_not_found(self):
        exit_code = main(["run", "nonexistent_cmd_xyz123"])
        self.assertNotEqual(exit_code, 0)

    def test_run_no_command(self):
        exit_code = main(["run"])
        self.assertEqual(exit_code, 1)

    def test_run_proof_exists(self):
        main(["run", sys.executable, "-c", "print('proof-test')"])
        trail = []
        with open(".krume/refs/trail.log") as f:
            trail = [l.strip() for l in f if l.strip()]
        self.assertTrue(len(trail) >= 1)

    def test_parser_run(self):
        parser = build_parser()
        args = parser.parse_args(["run", "echo", "hi"])
        self.assertEqual(args.command, "run")
        self.assertEqual(args.argv, ["echo", "hi"])


class TestCLICheckpoint(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_cwd = os.getcwd()
        os.chdir(self.tmpdir)
        main(["init"])

    def tearDown(self):
        os.chdir(self.orig_cwd)
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_checkpoint_creates_object(self):
        exit_code = main(["checkpoint"])
        self.assertEqual(exit_code, 0)
        with open(".krume/refs/latest-event") as f:
            ref = f.read().strip()
        self.assertTrue(ref.startswith("krume:sha256:"))

    def test_checkpoint_appends_trail(self):
        main(["checkpoint"])
        trail = []
        with open(".krume/refs/trail.log") as f:
            trail = [l.strip() for l in f if l.strip()]
        self.assertEqual(len(trail), 1)

    def test_checkpoint_updates_latest_event(self):
        main(["checkpoint"])
        with open(".krume/refs/latest-event") as f:
            ref = f.read().strip()
        self.assertTrue(ref.startswith("krume:sha256:"))

    def test_checkpoint_status_unknown_no_proof(self):
        exit_code = main(["checkpoint"])
        self.assertEqual(exit_code, 0)

    def test_checkpoint_without_init_fails(self):
        other = tempfile.mkdtemp()
        orig = os.getcwd()
        os.chdir(other)
        exit_code = main(["checkpoint"])
        os.chdir(orig)
        import shutil
        shutil.rmtree(other, ignore_errors=True)
        self.assertEqual(exit_code, 1)

    def test_checkpoint_after_run_has_proof(self):
        main(["run", sys.executable, "-c", "print('ok')"])
        exit_code = main(["checkpoint"])
        self.assertEqual(exit_code, 0)


class TestCLIKrate(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_cwd = os.getcwd()
        os.chdir(self.tmpdir)
        main(["init"])

    def tearDown(self):
        os.chdir(self.orig_cwd)
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_krate_creates_manifest(self):
        exit_code = main(["krate"])
        self.assertEqual(exit_code, 0)

    def test_krate_export_exists(self):
        main(["krate"])
        self.assertTrue(os.path.exists(".krume/export/current-krate.json"))

    def test_krate_trail_note_exists(self):
        main(["krate"])
        self.assertTrue(os.path.exists(".krume/export/current-trail-note.md"))

    def test_krate_trailhead_resolves(self):
        main(["krate"])
        with open(".krume/refs/trailhead") as f:
            ref = f.read().strip()
        self.assertTrue(ref.startswith("krume:sha256:"))

    def test_krate_previous_updates(self):
        main(["krate"])
        with open(".krume/refs/previous") as f:
            prev = f.read().strip()
        self.assertEqual(prev, "UNKNOWN")
        main(["krate"])
        with open(".krume/refs/previous") as f:
            prev = f.read().strip()
        self.assertTrue(prev.startswith("krume:sha256:"))

    def test_krate_reader_protocol(self):
        main(["krate"])
        with open(".krume/export/current-krate.json") as f:
            krate = json.load(f)
        self.assertIn("reader_protocol", krate)
        self.assertTrue(len(krate["reader_protocol"]) > 0)

    def test_krate_priority_queue(self):
        main(["krate"])
        with open(".krume/export/current-krate.json") as f:
            krate = json.load(f)
        self.assertIn("priority_queue", krate)
        self.assertTrue(len(krate["priority_queue"]) > 0)

    def test_krate_status_unknown_no_proof(self):
        main(["krate"])
        with open(".krume/export/current-krate.json") as f:
            krate = json.load(f)
        self.assertEqual(krate["verification_status"], "UNKNOWN")

    def test_krate_without_init_fails(self):
        other = tempfile.mkdtemp()
        orig = os.getcwd()
        os.chdir(other)
        exit_code = main(["krate"])
        os.chdir(orig)
        import shutil
        shutil.rmtree(other, ignore_errors=True)
        self.assertEqual(exit_code, 1)

    def test_krate_after_run_reflects_proof(self):
        main(["run", sys.executable, "-c", "print('ok')"])
        exit_code = main(["krate"])
        self.assertEqual(exit_code, 0)


class TestCLIAdopt(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_cwd = os.getcwd()
        os.chdir(self.tmpdir)

    def tearDown(self):
        os.chdir(self.orig_cwd)
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_adopt_initializes_store(self):
        exit_code = main(["adopt"])
        self.assertEqual(exit_code, 0)
        self.assertTrue(os.path.exists(".krume/config.json"))

    def test_adopt_fails_if_already_initialized(self):
        main(["init"])
        exit_code = main(["adopt"])
        self.assertEqual(exit_code, 1)

    def test_adopt_status_unknown(self):
        main(["adopt"])
        with open(".krume/export/current-krate.json") as f:
            krate = json.load(f)
        self.assertEqual(krate["verification_status"], "UNKNOWN")

    def test_adopt_creates_krate_export(self):
        main(["adopt"])
        self.assertTrue(os.path.exists(".krume/export/current-krate.json"))

    def test_adopt_creates_trail_note(self):
        main(["adopt"])
        self.assertTrue(os.path.exists(".krume/export/current-trail-note.md"))

    def test_adopt_trailhead_resolves(self):
        main(["adopt"])
        with open(".krume/refs/trailhead") as f:
            ref = f.read().strip()
        self.assertTrue(ref.startswith("krume:sha256:"))

    def test_adopt_previous_is_unknown(self):
        main(["adopt"])
        with open(".krume/refs/previous") as f:
            prev = f.read().strip()
        self.assertEqual(prev, "UNKNOWN")

    def test_adopt_records_files(self):
        with open("main.py", "w") as f:
            f.write("# hello\n")
        with open("README.md", "w") as f:
            f.write("# Project\n")
        main(["adopt"])
        with open(".krume/export/current-krate.json") as f:
            krate = json.load(f)
        self.assertEqual(krate["verification_status"], "UNKNOWN")
        self.assertIn("inventory_ref", krate)

    def test_adopt_checkpoint_kind(self):
        main(["adopt"])
        with open(".krume/refs/trail.log") as f:
            ref = f.read().strip().split("\n")[0]
        ev = json.loads(subprocess.check_output([sys.executable, "-m", "krume", "read", ref], text=True, cwd=self.tmpdir))
        self.assertEqual(ev.get("kind"), "adoption")

    def test_adopt_with_check(self):
        main(["adopt"])
        exit_code = main(["check"])
        self.assertEqual(exit_code, 0)

    def test_adopt_parser(self):
        parser = build_parser()
        args = parser.parse_args(["adopt"])
        self.assertEqual(args.command, "adopt")


class TestCLIPhase3Integration(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_cwd = os.getcwd()
        os.chdir(self.tmpdir)
        main(["init"])

    def tearDown(self):
        os.chdir(self.orig_cwd)
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_checkpoint_then_krate_then_check(self):
        exit_code = main(["checkpoint"])
        self.assertEqual(exit_code, 0)
        exit_code = main(["krate"])
        self.assertEqual(exit_code, 0)
        exit_code = main(["check"])
        self.assertEqual(exit_code, 0)

    def test_run_checkpoint_krate_check(self):
        main(["run", sys.executable, "--version"])
        main(["checkpoint"])
        main(["krate"])
        exit_code = main(["check"])
        self.assertEqual(exit_code, 0)

    def test_failed_run_checkpoint_krate_check(self):
        main(["run", sys.executable, "-c", "import sys; sys.exit(7)"])
        main(["checkpoint"])
        exit_code = main(["krate"])
        self.assertEqual(exit_code, 0)
        with open(".krume/export/current-krate.json") as f:
            krate = json.load(f)
        self.assertEqual(krate["verification_status"], "FAIL")
        exit_code = main(["check"])
        self.assertEqual(exit_code, 0)

    def test_check_detects_bad_trailhead(self):
        main(["krate"])
        with open(".krume/refs/trailhead", "w") as f:
            f.write("krume:sha256:" + "f" * 64 + "\n")
        exit_code = main(["check"])
        self.assertEqual(exit_code, 1)

    def test_check_detects_malformed_krate(self):
        main(["krate"])
        with open(".krume/export/current-krate.json", "w") as f:
            f.write("not json\n")
        exit_code = main(["check"])
        self.assertEqual(exit_code, 1)

    def test_check_detects_missing_trail_note(self):
        main(["krate"])
        os.remove(".krume/export/current-trail-note.md")
        exit_code = main(["check"])
        self.assertEqual(exit_code, 1)

    def test_parser_checkpoint(self):
        parser = build_parser()
        args = parser.parse_args(["checkpoint"])
        self.assertEqual(args.command, "checkpoint")

    def test_parser_krate(self):
        parser = build_parser()
        args = parser.parse_args(["krate"])
        self.assertEqual(args.command, "krate")


class TestCLIStake(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_cwd = os.getcwd()
        os.chdir(self.tmpdir)
        main(["init"])

    def tearDown(self):
        os.chdir(self.orig_cwd)
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_stake_creates_object(self):
        exit_code = main(["stake", "--title", "Use stdlib", "--body", "No external deps"])
        self.assertEqual(exit_code, 0)

    def test_stake_appends_trail(self):
        main(["stake", "--title", "Decision One", "--body", "Body one"])
        main(["stake", "--title", "Decision Two", "--body", "Body two"])
        with open(".krume/refs/trail.log") as f:
            lines = [l.strip() for l in f if l.strip()]
        self.assertEqual(len(lines), 2)

    def test_stake_updates_latest_event(self):
        main(["stake", "--title", "T", "--body", "B"])
        with open(".krume/refs/latest-event") as f:
            ref = f.read().strip()
        self.assertTrue(ref.startswith("krume:sha256:"))

    def test_stake_with_tag(self):
        exit_code = main(["stake", "--title", "T", "--body", "B", "--tag", "arch"])
        self.assertEqual(exit_code, 0)

    def test_stake_without_init_fails(self):
        other = tempfile.mkdtemp()
        orig = os.getcwd()
        os.chdir(other)
        exit_code = main(["stake", "--title", "T", "--body", "B"])
        os.chdir(orig)
        import shutil
        shutil.rmtree(other, ignore_errors=True)
        self.assertEqual(exit_code, 1)

    def test_parser_stake(self):
        parser = build_parser()
        args = parser.parse_args(["stake", "--title", "T", "--body", "B"])
        self.assertEqual(args.command, "stake")


class TestCLISnag(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_cwd = os.getcwd()
        os.chdir(self.tmpdir)
        main(["init"])

    def tearDown(self):
        os.chdir(self.orig_cwd)
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_snag_creates_object(self):
        exit_code = main(["snag", "--title", "Bug", "--body", "It crashes"])
        self.assertEqual(exit_code, 0)

    def test_snag_appends_trail(self):
        main(["snag", "--title", "S1", "--body", "B1"])
        main(["snag", "--title", "S2", "--body", "B2"])
        with open(".krume/refs/trail.log") as f:
            lines = [l.strip() for l in f if l.strip()]
        self.assertEqual(len(lines), 2)

    def test_snag_updates_latest_event(self):
        main(["snag", "--title", "T", "--body", "B"])
        with open(".krume/refs/latest-event") as f:
            ref = f.read().strip()
        self.assertTrue(ref.startswith("krume:sha256:"))

    def test_snag_with_status(self):
        exit_code = main(["snag", "--title", "T", "--body", "B", "--status", "blocked"])
        self.assertEqual(exit_code, 0)

    def test_snag_with_tag(self):
        exit_code = main(["snag", "--title", "T", "--body", "B", "--tag", "urgent"])
        self.assertEqual(exit_code, 0)

    def test_snag_without_init_fails(self):
        other = tempfile.mkdtemp()
        orig = os.getcwd()
        os.chdir(other)
        exit_code = main(["snag", "--title", "T", "--body", "B"])
        os.chdir(orig)
        import shutil
        shutil.rmtree(other, ignore_errors=True)
        self.assertEqual(exit_code, 1)

    def test_parser_snag(self):
        parser = build_parser()
        args = parser.parse_args(["snag", "--title", "T", "--body", "B"])
        self.assertEqual(args.command, "snag")
