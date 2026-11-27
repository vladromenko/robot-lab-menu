"""Passive snapshots of the installed workflows."""

import http.client
import json
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .config import Config, Target

MAX_RESPONSE_BYTES = 16 * 1024 * 1024


@dataclass(frozen=True)
class Result:
    state: str
    detail: str
    data: Optional[dict] = None


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def get(url: str, want_json: bool = True) -> Result:
    if not url:
        return Result("unconfigured", "No URL configured.")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    request = urllib.request.Request(url, method="GET", headers={"User-Agent": "Robot-Lab/0.1"})
    try:
        with opener.open(request, timeout=2.5) as response:
            if not want_json:
                return Result("available", f"HTTP {response.status}")
            content = response.read(MAX_RESPONSE_BYTES + 1)
            if len(content) > MAX_RESPONSE_BYTES:
                return Result("unverified", "Status response exceeds the size limit.")
            payload = json.loads(content)
            if not isinstance(payload, dict):
                return Result("unverified", "Expected a status object.")
            return Result("available", f"HTTP {response.status}", payload)
    except urllib.error.HTTPError as error:
        with error:
            if 300 <= error.code < 400 and not want_json:
                return Result("available", f"HTTP {error.code} redirect offered")
            if error.code in (401, 403):
                return Result("access_restricted", f"HTTP {error.code}")
            return Result("unavailable", f"HTTP {error.code}")
    except urllib.error.URLError as error:
        if isinstance(error.reason, ConnectionRefusedError):
            return Result("service_not_listening", "The configured HTTP port refused the connection.")
        state = "service_unreachable" if isinstance(error.reason, OSError) else "unverified"
        return Result(state, f"Passive GET failed. {error.reason}")
    except OSError as error:
        return Result("service_unreachable", f"Passive GET failed. {error}")
    except http.client.HTTPException as error:
        return Result("unverified", f"Incomplete HTTP response ({type(error).__name__}).")
    except (ValueError, UnicodeError):
        return Result("unverified", "Status response is not valid JSON.")


def obj(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def wrist_summary(result: Result) -> Result:
    if result.data is None:
        return result
    data = result.data
    resources = obj(data.get("resources"))
    inventory = obj(resources.get("device_inventory"))
    missing = [name for name, device in inventory.items() if obj(device).get("present") is False]
    busy = any(obj(data.get(key)).get("active") is True for key in ("recording", "teleoperation"))
    busy = busy or bool(resources.get("hardware_owners"))
    policy = {True: "checkpoint ready", False: "model unavailable"}.get(
        data.get("policy_ready") if isinstance(data.get("policy_ready"), bool) else None, "model unverified"
    )
    detail = f"Studio responding; {policy}."
    if busy:
        return Result("resource_busy", "Studio reports active recording, teleoperation or a hardware holder. " + detail, data)
    if missing:
        return Result("hardware_missing", f"Missing device nodes: {', '.join(missing)}. " + detail, data)
    if not inventory:
        return Result("unverified", "Studio responded without device inventory. " + detail, data)
    return Result("available", detail + " Device inventory reported; use native preflight.", data)


def explorer_summary(result: Result) -> Result:
    if result.data is None:
        return result
    data = result.data
    if data.get("armed") is True or obj(data.get("session")).get("recording") is True:
        return Result("resource_busy", "Explorer reports an active owner or recording.", data)
    return Result("available", "Explorer responds. Use native preflight for device readiness.", data)


def cube_summary(result: Result) -> Result:
    if result.detail == "HTTP 503":
        return Result("hardware_unavailable", "Explorer responds; ROSMASTER observation proxy returned HTTP 503.")
    if result.data is None:
        return result
    if result.data.get("armed") is True:
        profiles = {"rosmaster_dock": "base only", "rosmaster_pick_place": "stationary arm",
                    "rosmaster_manual": "combined manual"}
        profile = result.data.get("profile")
        label = profiles.get(profile, "profile unverified") if isinstance(profile, str) else "profile unverified"
        return Result("resource_busy", f"Explorer's ROSMASTER agent is armed ({label}).", result.data)
    return Result("available", "Explorer's ROSMASTER agent responds; use its native preflight.", result.data)


def tank_summary(result: Result) -> Result:
    if result.data is None:
        return result
    tank = obj(obj(result.data.get("robots")).get("tank"))
    streams = tank.get("published_streams")
    if not tank:
        return Result("unverified", "Fleet view has no Tank telemetry.", result.data)
    if result.data.get("running") is False or tank.get("error") or not isinstance(streams, list) or not streams:
        return Result("sensors_unavailable", "Explorer responds; Tank has no confirmed fresh sensor streams.", result.data)
    expected = {"rgb", "depth", "scan", "imu", "battery"}
    reported = {item for item in streams if isinstance(item, str)}
    missing = expected - reported
    detail = "Reported Tank streams: " + ", ".join(sorted(expected & reported) or ["none"]) + "."
    if missing:
        detail += " Unavailable: " + ", ".join(sorted(missing)) + "."
    return Result("degraded" if missing else "available", detail, result.data)


def legacy_summary(result: Result) -> Result:
    if result.data is None:
        return result
    return Result("available", "Legacy state responded. Verify native ownership before opening its console.", result.data)


def snapshots(config: Config, full: bool = False) -> Dict[str, Result]:
    target = config.targets
    explorer = target["explorer"]
    probes = {
        "wrist": (wrist_summary, target["wrist"].url("/api/status"), True),
        "explorer": (explorer_summary, explorer.url("/api/health"), True),
        "cube": (cube_summary, explorer.url("/api/rosmaster/observation"), True),
        "tank": (tank_summary, explorer.url("/api/fleet/live"), True),
        "legacy_cube": (legacy_summary, target["legacy_cube"].url("/api/state"), True),
        "mlflow": (lambda result: result, target["mlflow"].url("/"), False),
    }
    if full:
        probes["explorer_catalog"] = (lambda result: result, explorer.url("/api/status"), True)
    with ThreadPoolExecutor(max_workers=len(probes)) as pool:
        pending = {key: pool.submit(get, url, json_mode) for key, (_, url, json_mode) in probes.items()}
        return {key: probes[key][0](future.result()) for key, future in pending.items()}
