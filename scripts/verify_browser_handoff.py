"""Exercise the actual file-form session handoff in installed Linux Chromium."""

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path

from verify_live_launcher import ROOT, SSHHarness, free_port, open_tunnel, read_remote, validate_descriptor
import shlex


def form(path: Path, deployment: dict, local: str, ticket: dict) -> None:
    script = "const c=require('./native/core.js'); const v=JSON.parse(require('fs').readFileSync(0)); process.stdout.write(c.form(v.local,v.deployment,v.ticket));"
    payload = json.dumps({"local": local, "deployment": deployment, "ticket": ticket}).encode()
    completed = subprocess.run(["node", "-e", script], input=payload, capture_output=True, cwd=ROOT, check=True)
    fd = os.open(path, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(completed.stdout)


def browser_check(page, context, server, reader: str, directory: Path, deployment: dict, local: str, private: Path) -> dict:
    expected = local + deployment["service"]["workspace_path"]
    failures = []
    page.on("response", lambda reply: failures.append(reply.status) if
            reply.url.startswith(local + "/api/") and reply.status in (401, 403) else None)
    for _ in range(2):
        ticket = read_remote(server, reader, directory, "handoff")
        file = private / "open-workspace.html"
        form(file, deployment, local, ticket)
        page.goto(file.as_uri())
        page.wait_for_url(expected, timeout=15000)
        page.wait_for_timeout(1200)
        file.unlink()
        if not context.cookies(local):
            raise ValueError("The real browser did not accept the handoff session cookie.")
    if failures:
        raise ValueError("The authenticated workspace returned unauthorized API responses after the handoff.")
    return {"platform": "Linux", "browser_engine": "Chromium", "file_origin_form_post": "passed",
            "workspace_loaded_twice": True, "session_cookie": "present", "unauthorized_workspace_responses": failures,
            "tokens_in_url": False, "viewer_gamepad_audio": "pending_attended_mac", "physical_actions": 0}


def run(directory: Path, private: Path, control: str) -> dict:
    from playwright.sync_api import sync_playwright

    server = SSHHarness(private)
    reader = "python3 -c " + shlex.quote((ROOT / "native/remote.py").read_text())
    try:
        deployment = read_remote(server, reader, directory, "descriptor")
        validate_descriptor(deployment)
        local = open_tunnel(server, control, free_port(), deployment)
        with sync_playwright() as engine:
            browser = engine.chromium.launch(headless=True, args=["--disable-gpu"])
            try:
                context = browser.new_context()
                page = context.new_page()
                report = browser_check(page, context, server, reader, directory, deployment, local, private)
                report["browser_version"] = browser.version
                return report
            finally:
                browser.close()
    finally:
        subprocess.run(["ssh", "-F", str(server.config), "-S", control, "-O", "exit", "homebrain-test"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        server.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--handover", type=Path, default=Path.home() / ".local/share/homebrain-lab/handover")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="launcher-browser-", dir=ROOT.parents[1]) as private:
        with tempfile.TemporaryDirectory(prefix="hb-browser-socket-") as sockets:
            result = run(args.handover, Path(private), str(Path(sockets) / "ssh"))
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
