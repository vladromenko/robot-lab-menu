"""Read the fixed Smart Swarm handover without starting the experiment."""

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple

from .config import Config, http_url
from .status import Result, get

EXPERIMENT_STATES = {
    "ready_to_record", "collecting", "ready_to_train", "training",
    "evaluating", "blocked", "complete",
}
RUN_MODES = {"mujoco", "replay", "fixture", "hardware"}


def descriptor(path: Path) -> dict:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("Expected a Smart Swarm descriptor object.")
    if document.get("protocol_version") != "robot-platform/1.0.0" or document.get("experiment_id") != "smart-swarm":
        raise ValueError("Smart Swarm descriptor version or experiment ID does not match.")
    for key in ("display_name", "project_path", "status_location", "data_root"):
        if not isinstance(document.get(key), str) or not document[key].strip():
            raise ValueError(f"Smart Swarm descriptor requires {key}.")
    modes = document.get("supported_run_modes")
    if not isinstance(modes, list) or not modes or any(mode not in RUN_MODES for mode in modes):
        raise ValueError("Smart Swarm descriptor contains an invalid run mode.")
    argv = document.get("entrypoint")
    if not isinstance(argv, list) or not argv or any(not isinstance(item, str) or not item for item in argv):
        raise ValueError("Smart Swarm descriptor requires entrypoint argv.")
    return document


def experiment(folder: Path) -> Tuple[Result, Optional[str]]:
    path = folder / "experiment.json"
    try:
        manifest = descriptor(path)
    except FileNotFoundError:
        return Result("unavailable", f"Waiting for Smart Swarm descriptor at {path}."), None
    except (OSError, ValueError, TypeError):
        return Result("unverified", f"Invalid or unreadable Smart Swarm descriptor at {path}."), None
    location = manifest["status_location"]
    url = None
    try:
        if location.startswith(("http://", "https://")):
            url = http_url(location)
            status = get(url)
            if status.data is None:
                return status, url
            payload = status.data
        else:
            status_path = Path(location).expanduser()
            if not status_path.is_absolute():
                project = Path(manifest["project_path"]).expanduser()
                status_path = path.parent / project / status_path
            payload = json.loads(status_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return Result("unverified", "Smart Swarm status is missing or unreadable."), url
    state = payload.get("state") if isinstance(payload, dict) else None
    if not isinstance(state, str) or state not in EXPERIMENT_STATES:
        return Result("unverified", "Descriptor registered; status has no recognized experiment state."), url
    return Result(state, "Smart Swarm status reported by its own process."), url


def local_command(folder: Path) -> Tuple[list, Path]:
    manifest = descriptor(folder / "experiment.json")
    project = (folder / manifest["project_path"]).resolve()
    program = (project / manifest["entrypoint"][0]).resolve()
    if not project.is_dir() or not program.is_relative_to(project) or not program.is_file():
        raise ValueError("Smart Swarm descriptor must point to an existing executable in its project.")
    if not os.access(program, os.X_OK):
        raise ValueError(f"Smart Swarm entry point is not executable: {program}")
    return [str(program), *manifest["entrypoint"][1:]], project


def launch(config: Config, local_only: bool = False, print_command: bool = False) -> int:
    try:
        try:
            command, cwd = local_command(config.swarm_handover)
        except FileNotFoundError:
            if local_only or not config.homebrain_ssh or not config.homebrain_launcher:
                raise
            remote = shlex.join([config.homebrain_launcher, "--launch-smart-swarm"])
            command = ["ssh", "-T", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
                       "-o", "ConnectTimeout=5", config.homebrain_ssh, remote]
            cwd = None
        if print_command:
            print(shlex.join(command))
            return 0
        result = subprocess.run(command, cwd=cwd, check=False)
        if result.returncode:
            print(f"Smart Swarm launch exited with status {result.returncode}.", file=sys.stderr)
        return result.returncode
    except (OSError, ValueError, TypeError) as error:
        print(f"Smart Swarm launch unavailable. {error}", file=sys.stderr)
        return 2
