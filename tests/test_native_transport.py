"""Verify the actual fixed SSH helper, host-key checking and local forwarding."""

import contextlib
import hashlib
import io
import importlib.util
import json
import os
import shlex
import socket
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from ssh_harness import SSHHarness, free_port

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("homebrain_remote", ROOT / "native/remote.py")
REMOTE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REMOTE)


class SSHTransportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = tempfile.TemporaryDirectory(prefix="launcher-ssh-", dir=ROOT.parents[1])
        cls.root = Path(cls.work.name)
        cls.server = SSHHarness(cls.root)
        cls.reader = "python3 -c " + shlex.quote((ROOT / "native/remote.py").read_text())
        cls.folder = cls.root / "handover with spaces and 'quotes"
        cls.folder.mkdir()
        fixture = json.loads((ROOT / "fixtures/homebrain-lab.example.json").read_text())
        (cls.folder / "homebrain-lab.json").write_text(json.dumps(fixture))

    @classmethod
    def tearDownClass(cls):
        cls.server.close()
        cls.work.cleanup()

    def test_fixed_ssh_read_handles_spaces_without_shell_interpolation(self):
        body = json.dumps({"operation": "descriptor", "directory": str(self.folder)}).encode()
        result = self.server.ssh(["-T", "homebrain-test", self.reader], input=body)
        self.assertEqual(json.loads(result.stdout)["descriptor_version"], "homebrain.lab.v1")
        payload = json.dumps({"operation": "descriptor", "directory": str(self.folder) + "; touch unexpected"}).encode()
        failed = subprocess.run(["ssh", "-F", str(self.server.config), "-T", "homebrain-test", self.reader],
                                input=payload, capture_output=True)
        self.assertEqual(failed.returncode, 4)
        self.assertFalse((self.root / "unexpected").exists())

    def test_busy_port_cannot_forward_to_a_different_listener(self):
        with socket.socket() as busy:
            busy.bind(("127.0.0.1", 0))
            busy.listen()
            port = busy.getsockname()[1]
            args = ["ssh", "-F", str(self.server.config), "-o", "ExitOnForwardFailure=yes",
                    "-N", "-L", f"127.0.0.1:{port}:127.0.0.1:1", "homebrain-test"]
            failed = subprocess.run(args, capture_output=True, timeout=5)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn(b"Address already in use", failed.stderr)

    def test_changed_host_key_is_rejected(self):
        wrong = self.root / "wrong_known_hosts"
        wrong.write_text(self.server.known.read_text().replace("ssh-ed25519", "ssh-rsa"))
        result = subprocess.run(["ssh", "-F", str(self.server.config), "-o", f"UserKnownHostsFile={wrong}",
                                 "homebrain-test", "true"], capture_output=True, timeout=5)
        self.assertNotEqual(result.returncode, 0)

    def test_unknown_operation_and_unpinned_script_are_rejected(self):
        request = json.dumps({"operation": "arbitrary", "directory": str(self.folder)}).encode()
        result = subprocess.run(["ssh", "-F", str(self.server.config), "homebrain-test", self.reader],
                                input=request, capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 5)
        with self.assertRaises(ValueError):
            REMOTE.arguments({"operations": {"start": {"argv": ["/bin/sh", "start"], "sha256": "0" * 64}}}, "start")


    def test_pinned_operation_runs_in_its_own_project_directory(self):
        project = self.root / "operation project with spaces"
        scripts = project / "scripts"
        scripts.mkdir(parents=True)
        script = scripts / "homebrain-lab-launcher"
        script.write_text("""#!/bin/sh
printf '{"status":"ready"}\n'
""")
        script.chmod(0o755)
        folder = self.root / "operation-handover"
        folder.mkdir()
        value = json.loads((self.folder / "homebrain-lab.json").read_text())
        value["operations"]["status"] = {"argv": [str(script), "status"], "cwd": str(project),
                                          "sha256": hashlib.sha256(script.read_bytes()).hexdigest()}
        (folder / "homebrain-lab.json").write_text(json.dumps(value))
        body = json.dumps({"operation": "status", "directory": str(folder)}).encode()
        reply = self.server.ssh(["homebrain-test", self.reader], input=body)
        self.assertEqual(json.loads(reply.stdout), {"status": "ready"})
        script.write_text(script.read_text() + "touch unexpected\n")
        failed = subprocess.run(["ssh", "-F", str(self.server.config), "homebrain-test", self.reader],
                                input=body, capture_output=True, timeout=5)
        self.assertEqual(failed.returncode, 5)
        self.assertIn(b"script hash or executable mode does not match", failed.stderr)
        self.assertFalse((project / "unexpected").exists())


    def test_start_text_is_normalized_without_claiming_health(self):
        result = SimpleNamespace(returncode=0, stdout=b"Service start requested", stderr=b"")
        with patch.object(REMOTE, "arguments", return_value=(["known-launcher", "start"], self.root)):
            with patch.object(REMOTE.subprocess, "run", return_value=result):
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    REMOTE.operation({}, "start")
        self.assertEqual(json.loads(output.getvalue()), {"operation": "start", "accepted": True})

    def test_native_connection_replaces_a_dead_socket_and_reuses_one_real_master(self):
        with tempfile.TemporaryDirectory(prefix="hb-stale-check-") as temporary:
            control = Path(temporary) / "ssh.sock"
            stale = socket.socket(socket.AF_UNIX)
            stale.bind(str(control))
            stale.close()
            value = {"ssh_config": str(self.server.config), "socket_dir": temporary, "local_port": free_port()}
            try:
                reply = subprocess.run(["node", "tests/native_transport_runner.js"], input=json.dumps(value).encode(),
                                       cwd=ROOT, capture_output=True, timeout=25, check=True)
                self.assertEqual(json.loads(reply.stdout), {"stale_socket_recovered": True, "masters_started": 1})
            finally:
                subprocess.run(["ssh", "-F", str(self.server.config), "-S", str(control), "-O", "exit", "homebrain-test"],
                               capture_output=True, check=False)
