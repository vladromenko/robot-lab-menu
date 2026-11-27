"""Verify the launcher against the actual published Homebrain Lab deployment."""

import argparse
import http.cookiejar
import json
import shlex
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from ssh_harness import SSHHarness, free_port


def read_remote(server: SSHHarness, reader: str, folder: Path, operation: str) -> dict:
    request = json.dumps({"operation": operation, "directory": str(folder)}).encode()
    reply = server.ssh(["-T", "homebrain-test", reader], input=request, timeout=55)
    return json.loads(reply.stdout)


def browser() -> tuple:
    cookies = http.cookiejar.CookieJar()
    return cookies, urllib.request.build_opener(
        urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(cookies))


def health(opener, local: str, deployment: dict) -> None:
    with opener.open(local + deployment["service"]["health_path"], timeout=4) as response:
        actual = json.load(response)
    expected = deployment["service"]["health_expected"]
    if any(actual.get(key) != value for key, value in expected.items()):
        raise ValueError("The tunneled port does not identify the declared Homebrain Lab service.")


def sign_in(opener, local: str, deployment: dict, ticket: dict) -> str:
    payload = urllib.parse.urlencode({"ticket": ticket["ticket"]}).encode()
    target = local + deployment["authentication"]["post_path"]
    request = urllib.request.Request(target, data=payload, headers={"Origin": "null"})
    with opener.open(request, timeout=5) as response:
        result = response.geturl()
        response.read(1024)
    expected = local + deployment["service"]["workspace_path"]
    if result != expected or ticket["ticket"] in result:
        raise ValueError("The browser handoff did not reach the declared workspace cleanly.")
    return result


def rejected(opener, local: str, deployment: dict, ticket: dict) -> bool:
    try:
        sign_in(opener, local, deployment, ticket)
    except urllib.error.HTTPError as error:
        with error:
            return error.code in (400, 401, 403, 409, 410)
    return False


def open_tunnel(server: SSHHarness, control: str, port: int, deployment: dict) -> str:
    remote = urllib.parse.urlsplit(deployment["service"]["origin"])
    forward = f"127.0.0.1:{port}:{remote.hostname}:{remote.port}"
    server.ssh(["-M", "-S", control, "-o", "ExitOnForwardFailure=yes", "-f", "-N", "-L", forward, "homebrain-test"])
    return f"http://127.0.0.1:{port}"


def validate_descriptor(value: dict) -> None:
    script = "require('./native/core.js').descriptor(JSON.parse(require('fs').readFileSync(0, 'utf8')))"
    subprocess.run(["node", "-e", script], input=json.dumps(value).encode(), cwd=ROOT, check=True)
    if value.get("deployed") is not True or value.get("fixture"):
        raise ValueError("The final launcher check requires the actual deployed descriptor.")


def validate(server: SSHHarness, directory: Path, control: str, check_expiry: bool) -> dict:
    reader = "python3 -c " + shlex.quote((ROOT / "native/remote.py").read_text())
    deployment = read_remote(server, reader, directory, "descriptor")
    validate_descriptor(deployment)
    local = open_tunnel(server, control, free_port(), deployment)
    cookies, opener = browser()
    health(opener, local, deployment)
    read_remote(server, reader, directory, "status")
    ticket = read_remote(server, reader, directory, "handoff")
    sign_in(opener, local, deployment, ticket)
    if not list(cookies) or not rejected(opener, local, deployment, ticket):
        raise ValueError("The live browser cookie or single-use ticket contract failed.")
    old_cookie = [cookie.value for cookie in cookies]
    cookies.clear()
    renewed = read_remote(server, reader, directory, "handoff")
    sign_in(opener, local, deployment, renewed)
    if not list(cookies) or [cookie.value for cookie in cookies] == old_cookie:
        raise ValueError("A fresh one-click handoff did not renew the browser session.")
    server.ssh(["-S", control, "-O", "check", "homebrain-test"])
    restore_transport(server, control, local, deployment, opener)
    expired = None
    if check_expiry:
        candidate = read_remote(server, reader, directory, "handoff")
        time.sleep(min(candidate["expires_in_s"] + 1, 121))
        expired = rejected(opener, local, deployment, candidate)
        if not expired:
            raise ValueError("An expired browser handoff ticket was accepted.")
    return {"descriptor_version": deployment["descriptor_version"], "source_commit": deployment["source_commit"],
            "service_id": deployment["service"]["id"], "workspace_path": deployment["service"]["workspace_path"],
            "ssh_read": "passed", "browser_cookie_handoff": "passed", "duplicate_ticket_rejected": True,
            "fresh_session_handoff": "passed", "owned_tunnel_reconnect": "passed", "ticket_expiry_rejected": expired,
            "mac_finder": "pending", "mac_browser_viewer_gamepad_audio": "pending", "physical_actions": 0}


def restore_transport(server: SSHHarness, control: str, local: str, deployment: dict, opener) -> None:
    server.ssh(["-S", control, "-O", "exit", "homebrain-test"])
    time.sleep(0.2)
    open_tunnel(server, control, urllib.parse.urlsplit(local).port, deployment)
    health(opener, local, deployment)
    with opener.open(local + deployment["service"]["workspace_path"], timeout=4) as response:
        if response.status != 200:
            raise ValueError("The existing workspace did not reopen after transport restoration.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--handover", type=Path, default=Path.home() / ".local/share/homebrain-lab/handover")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check-ticket-expiry", action="store_true")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="launcher-live-", dir=ROOT.parents[1]) as temporary:
        server = SSHHarness(Path(temporary))
        with tempfile.TemporaryDirectory(prefix="hb-launcher-socket-") as sockets:
            control = str(Path(sockets) / "ssh")
            try:
                report = validate(server, args.handover, control, args.check_ticket_expiry)
            finally:
                subprocess.run(["ssh", "-F", str(server.config), "-S", control, "-O", "exit", "homebrain-test"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                server.close()
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
