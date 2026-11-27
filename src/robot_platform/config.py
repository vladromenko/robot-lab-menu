"""Resolve launcher configuration without importing native services."""

import json
import os
import re
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Target:
    base: str
    unit: str

    def url(self, path: str) -> str:
        return self.base + path if self.base else ""


@dataclass(frozen=True)
class Config:
    targets: Dict[str, Target]
    swarm_handover: Path
    source: str
    homebrain_ssh: str = ""
    homebrain_launcher: str = ""


def http_url(value: str, origin_only: bool = False) -> str:
    if not isinstance(value, str) or any(c.isspace() or ord(c) < 32 for c in value):
        raise ValueError("Expected an HTTP URL without whitespace.")
    parsed = urlsplit(value)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("Expected an HTTP or HTTPS URL with a host.")
    if parsed.username is not None or parsed.password is not None or parsed.fragment:
        raise ValueError("Credentials and fragments are not accepted in launcher URLs.")
    if parsed.port == 0:
        raise ValueError("Expected a nonzero port.")
    if origin_only and (parsed.path not in ("", "/") or parsed.query):
        raise ValueError("A service target must be an origin such as http://homebrain.local:8030.")
    return value.rstrip("/") if origin_only else value


def load_config(path: Optional[Path], default_handover: Path) -> Config:
    default = json.loads(files("robot_platform").joinpath("homebrain.json").read_text())
    path = path or (Path(os.environ["ROBOT_LAB_CONFIG"]) if "ROBOT_LAB_CONFIG" in os.environ else None)
    if path:
        path = path.expanduser().resolve()
    overrides = json.loads(path.read_text(encoding="utf-8")) if path else {}
    if not isinstance(overrides, dict) or not isinstance(overrides.get("targets", {}), dict):
        raise ValueError("Launcher configuration must contain an object of targets.")
    targets = {}
    for name, defaults in default["targets"].items():
        override = overrides.get("targets", {}).get(name, {})
        if not isinstance(override, dict):
            raise ValueError(f"{name} target must be an object.")
        value = {**defaults, **override}
        origin = os.environ.get(f"ROBOT_LAB_{name.upper()}_URL", value["url"])
        if not isinstance(value["unit"], str):
            raise ValueError(f"{name} unit must be a string.")
        base = "" if name == "legacy_cube" and origin == "" else http_url(origin, origin_only=True)
        targets[name] = Target(base, value["unit"])
    handover = os.environ.get("ROBOT_LAB_SWARM_HANDOVER", overrides.get("swarm_handover", default.get("swarm_handover")))
    folder = Path(handover).expanduser() if handover else default_handover
    if handover and path and not folder.is_absolute():
        folder = path.parent / folder
    ssh = os.environ.get("ROBOT_LAB_HOMEBRAIN_SSH", overrides.get("homebrain_ssh", default["homebrain_ssh"]))
    remote = overrides.get("homebrain_launcher", default["homebrain_launcher"])
    if not isinstance(ssh, str) or (ssh and not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*(?:@[A-Za-z0-9_][A-Za-z0-9_.-]*)?", ssh)):
        raise ValueError("Invalid Homebrain SSH destination.")
    if not isinstance(remote, str) or ((ssh or remote) and not Path(remote).is_absolute()):
        raise ValueError("Homebrain launcher must be an absolute path.")
    return Config(targets, folder.resolve(), str(path) if path else default["source"], ssh, remote)
