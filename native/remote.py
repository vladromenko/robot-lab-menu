"""Fixed SSH reader and pinned Homebrain Lab operation dispatcher."""

import hashlib
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

MAX_BYTES = 65536
OPERATION_ARGUMENTS = {"status": "status", "start": "start", "handoff": "handoff"}


def descriptor(folder: str) -> dict:
    if not isinstance(folder, str) or len(folder) > 1024 or any(ord(c) < 32 for c in folder):
        raise ValueError("Invalid remote handover directory.")
    directory = Path(folder).expanduser()
    if not directory.is_absolute():
        raise ValueError("Remote handover directory must be absolute.")
    target = directory / "homebrain-lab.json"
    with target.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Deployment descriptor exceeds the size limit.")
    value = json.loads(raw)
    if not isinstance(value, dict) or value.get("descriptor_version") != "homebrain.lab.v1":
        raise ValueError("Unsupported deployment descriptor.")
    return value


def arguments(deployment: dict, operation: str) -> tuple:
    entry = deployment.get("operations", {}).get(operation, {})
    argv = entry.get("argv")
    if not isinstance(argv, list) or len(argv) != 2 or argv[1] != OPERATION_ARGUMENTS[operation]:
        raise ValueError("Unsupported deployment operation.")
    script = Path(argv[0])
    if not script.is_absolute() or script.name not in ("homebrain-lab-launcher", "homebrain-lab-launcher.py"):
        raise ValueError("Unrecognized Homebrain Lab launcher script.")
    information = script.stat()
    if not stat.S_ISREG(information.st_mode) or information.st_mode & stat.S_IWOTH:
        raise ValueError("The launcher operation script is not a regular protected file.")
    digest = hashlib.sha256(script.read_bytes()).hexdigest()
    if digest != entry.get("sha256") or not os.access(script, os.X_OK):
        raise ValueError("The launcher operation script hash or executable mode does not match.")
    cwd = Path(entry.get("cwd", script.parent.parent))
    if not cwd.is_absolute() or cwd.resolve() != script.parent.parent.resolve():
        raise ValueError("The operation working directory does not match its project.")
    return argv, cwd


def operation(deployment: dict, name: str) -> None:
    command, cwd = arguments(deployment, name)
    completed = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True, timeout=45, check=False, cwd=cwd)
    if completed.returncode:
        raise ValueError(f"Homebrain Lab {name} failed with exit code {completed.returncode}.")
    if len(completed.stdout) > MAX_BYTES:
        raise ValueError("Homebrain Lab operation response exceeds the size limit.")
    response = {"operation": "start", "accepted": True} if name == "start" else json.loads(completed.stdout)
    if not isinstance(response, dict):
        raise ValueError("Homebrain Lab operation returned an invalid response.")
    print(json.dumps(response, allow_nan=False))


def main() -> None:
    try:
        request = json.loads(sys.stdin.buffer.read(4096))
        name = request.get("operation")
        if name not in ("descriptor", *OPERATION_ARGUMENTS):
            raise ValueError("Unknown Homebrain Lab operation.")
        value = descriptor(request.get("directory"))
        if name == "descriptor":
            print(json.dumps(value, allow_nan=False))
        else:
            operation(value, name)
    except FileNotFoundError:
        print("Homebrain Lab has not published its deployment descriptor or launcher script.", file=sys.stderr)
        raise SystemExit(4)
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError):
        print("Homebrain Lab rejected the launcher operation. Check the deployment descriptor.", file=sys.stderr)
        raise SystemExit(5)


if __name__ == "__main__":
    main()
