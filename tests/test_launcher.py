import contextlib
import io
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from robot_platform.cli import choose, main
from robot_platform.config import Config, Target, http_url
from robot_platform.experiment import experiment, launch
from robot_platform.status import Result, snapshots


class StatusHandler(BaseHTTPRequestHandler):
    replies = {
        "/api/status": {"resources": {"device_inventory": {"wrist": {"present": False}}},
                        "policy_ready": False, "jobs": []},
        "/api/health": {"armed": False},
        "/api/rosmaster/observation": None,
        "/api/fleet/live": {"robots": {"tank": {"error": "Clock samples expired", "published_streams": []}}},
        "/api/state": {},
        "/": {},
    }

    def do_GET(self):
        self.server.requests.append((self.command, self.path))
        data = self.replies.get(self.path)
        self.send_response(503 if data is None else 200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, fmt, *args):
        pass


class LauncherTest(unittest.TestCase):
    def test_passive_checks_when_hardware_is_absent(self):
        with ThreadingHTTPServer(("127.0.0.1", 0), StatusHandler) as server:
            server.requests = []
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            config = Config({key: Target(base, key) for key in
                             ("wrist", "explorer", "mlflow", "legacy_cube")}, Path("."), "test")
            try:
                status = snapshots(config)
            finally:
                server.shutdown()
                thread.join()
        self.assertEqual(status["wrist"].state, "hardware_missing")
        self.assertIn("model unavailable", status["wrist"].detail)
        self.assertEqual(status["cube"].state, "hardware_unavailable")
        self.assertEqual(status["tank"].state, "sensors_unavailable")
        self.assertEqual(status["explorer"].state, "available")
        self.assertCountEqual(server.requests, [("GET", path) for path in StatusHandler.replies])

    def test_start_then_quit_uses_no_network_or_browser(self):
        with patch("robot_platform.cli.get") as probes, patch("webbrowser.open") as browser, patch("robot_platform.cli.launch") as swarm:
            with patch("builtins.input", return_value="q"), contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main([]), 0)
        probes.assert_not_called()
        browser.assert_not_called()
        swarm.assert_not_called()
        for label in ("Wrist / SO101 LeRobot", "Cube / ROSMASTER", "Tank", "Smart Swarm", "Explorer"):
            self.assertIn(label, output.getvalue())

    def test_swarm_descriptor_uses_its_own_status_file(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            self.assertEqual(experiment(folder)[0].state, "unavailable")
            (folder / "experiment.json").write_text(json.dumps({
                "protocol_version": "robot-platform/1.0.0", "experiment_id": "smart-swarm",
                "display_name": "Smart Swarm", "project_path": ".", "data_root": "example-data",
                "entrypoint": ["smart-swarm", "status"], "supported_run_modes": ["mujoco"],
                "status_location": "status.json",
            }))
            (folder / "status.json").write_text('{"state":"ready_to_record"}')
            self.assertEqual(experiment(folder)[0].state, "ready_to_record")

    def test_origin_rejects_embedded_credentials_and_paths(self):
        for url in ("http://user:password@example.org", "http://localhost/control", "file:///tmp/status"):
            with self.assertRaises(ValueError):
                http_url(url, origin_only=True)

    def test_menu_opens_the_existing_browser_routes(self):
        targets = {key: Target(base, key) for key, base in
                   (("wrist", "http://wrist:8020"), ("explorer", "http://explorer:8030"),
                    ("mlflow", "http://wrist:5020"), ("legacy_cube", "http://cube:8090"))}
        config = Config(targets, Path("."), "test")
        cases = [
            ("1", "", "http://wrist:8020/"),
            ("2", "1", "http://explorer:8030/rosmaster/control"),
            ("2", "3", "http://cube:8090/"),
            ("3", "1", "http://explorer:8030/fleet/live"),
            ("3", "2", "http://explorer:8030/"),
            ("5", "", "http://explorer:8030/"),
        ]
        for option, suboption, expected in cases:
            with self.subTest(option=option, suboption=suboption):
                with patch("robot_platform.cli.get", return_value=Result("available", "HTTP 200")):
                    with patch("builtins.input", side_effect=[suboption, "open"]), patch("webbrowser.open") as browser:
                        with contextlib.redirect_stdout(io.StringIO()):
                            choose(config, option, False)
                browser.assert_called_once_with(expected, new=2)

    def test_unreachable_route_displays_error(self):
        targets = {key: Target("http://unreachable", key) for key in ("wrist", "explorer", "legacy_cube")}
        config = Config(targets, Path("."), "test")
        with patch("robot_platform.cli.get", return_value=Result("service_unreachable", "Connection timed out.")):
            with patch("webbrowser.open") as browser, contextlib.redirect_stdout(io.StringIO()) as output:
                choose(config, "1", False)
        browser.assert_not_called()
        self.assertIn("Connection timed out.", output.getvalue())

    def test_swarm_launches_declared_program_and_arguments(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            program = project / "smart-swarm"
            program.write_text("#!/bin/sh\n", encoding="utf-8")
            program.chmod(0o700)
            arguments = ["collect", "--plan", "so101-pilot", "--plan-only"]
            (project / "experiment.json").write_text(json.dumps({
                "protocol_version": "robot-platform/1.0.0", "experiment_id": "smart-swarm",
                "display_name": "Smart Swarm", "project_path": str(project),
                "entrypoint": [str(program), *arguments], "supported_run_modes": ["mujoco"],
                "status_location": "status.json", "data_root": "example-data",
            }), encoding="utf-8")
            with patch("robot_platform.experiment.subprocess.run") as run:
                run.return_value.returncode = 0
                self.assertEqual(launch(Config({}, project, "test")), 0)
            run.assert_called_once_with([str(program), *arguments], cwd=project, check=False)

    def test_mac_uses_existing_homebrain_command_without_local_project(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Config({}, Path(directory), "test", "operator@homebrain", "/home/operator/Robot Lab.command")
            with patch("robot_platform.experiment.subprocess.run") as run:
                run.return_value.returncode = 0
                self.assertEqual(launch(config), 0)
            args = run.call_args.args[0]
            self.assertEqual(args[0], "ssh")
            self.assertIn("StrictHostKeyChecking=yes", args)
            self.assertEqual(args[-2:], ["operator@homebrain", "'/home/operator/Robot Lab.command' --launch-smart-swarm"])
