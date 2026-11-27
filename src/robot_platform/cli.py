"""Robot Lab menu for the existing Homebrain programs."""

import argparse
import json
import os
import webbrowser
from pathlib import Path
from typing import List, Optional, Tuple

from .config import Config, load_config
from .experiment import experiment, launch
from .status import cube_summary, get, snapshots, tank_summary

MENU = """
Robot Lab

  1  Wrist / SO101 LeRobot
  2  Cube / ROSMASTER
  3  Tank
  4  Smart Swarm
  5  Explorer
  q  Quit
"""


def read_choice(prompt: str) -> str:
    try:
        return input(prompt).strip().lower()
    except (EOFError, KeyboardInterrupt):
        return "q"


def links(config: Config, choice: str) -> List[Tuple[str, str]]:
    wrist = config.targets["wrist"]
    explorer = config.targets["explorer"]
    legacy = config.targets["legacy_cube"]
    pages = {
        "1": [("SO101 LeRobot Studio", wrist.url("/"))],
        "2": [("Explorer ROSMASTER controls", explorer.url("/rosmaster/control")),
              ("ROSMASTER observation", explorer.url("/rosmaster")),
              ("Legacy CubeBot console", legacy.url("/"))],
        "3": [("Tank live sensors", explorer.url("/fleet/live")),
              ("Tank control and recording · select Tank in Explorer", explorer.url("/"))],
        "5": [("Explorer", explorer.url("/"))],
    }
    return [(name, url) for name, url in pages.get(choice, []) if url]


def open_page(name: str, url: str) -> None:
    result = get(url, want_json=False)
    if result.state not in ("available", "access_restricted"):
        print(f"{name} · {result.detail}  {url}")
    elif not webbrowser.open(url, new=2):
        print(f"Open in your browser: {url}")


def show_pages(pages: List[Tuple[str, str]], print_urls: bool) -> None:
    if len(pages) == 1 and not print_urls:
        open_page(*pages[0])
    elif pages:
        for index, (name, url) in enumerate(pages, 1):
            print(f"  {index}  {name}  {url}")
        if not print_urls:
            selected = read_choice("Open link number, or Enter to return: ")
            if selected in {str(i) for i in range(1, len(pages) + 1)}:
                open_page(*pages[int(selected) - 1])


def choose(config: Config, choice: str, print_urls: bool) -> None:
    explorer = config.targets["explorer"]
    if choice == "4":
        launch(config, print_command=print_urls)
    if choice == "2" and not print_urls:
        cube = cube_summary(get(explorer.url("/api/rosmaster/observation")))
        legacy = get(config.targets["legacy_cube"].url("/api/state"))
        print(f"  Explorer ROSMASTER · {cube.detail}")
        print(f"  Legacy CubeBot · {legacy.detail}")
    if choice == "3" and not print_urls:
        tank = tank_summary(get(explorer.url("/api/fleet/live")))
        print(f"  Tank · {tank.detail}")
    show_pages(links(config, choice), print_urls)


def check(config: Config) -> None:
    results = snapshots(config)
    results["swarm"], _ = experiment(config.swarm_handover)
    print(json.dumps({
        "configuration_source": config.source,
        "workflows": {name: {"state": status.state, "detail": status.detail}
                      for name, status in results.items()},
    }, indent=2))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Open existing Robot Lab programs.")
    parser.add_argument("--config", type=Path, help="Override service origins and Smart Swarm handover.")
    parser.add_argument("--check", action="store_true", help="Run passive checks and print JSON.")
    parser.add_argument("--print-urls", action="store_true", help="Print URLs or commands without launching.")
    parser.add_argument("--launch-smart-swarm", action="store_true", help="Run the local Smart Swarm entry point.")
    args = parser.parse_args(argv)
    project = Path(os.environ.get("ROBOT_LAB_ROOT", Path.cwd()))
    try:
        config = load_config(args.config, project.parent / "smart-swarm" / "handover")
    except (OSError, ValueError, TypeError) as error:
        parser.exit(2, f"Robot Lab configuration error: {error}\n")
    if args.launch_smart_swarm:
        return launch(config, local_only=True, print_command=args.print_urls)
    if args.check:
        check(config)
        return 0
    choice = ""
    while choice != "q":
        print(MENU)
        choice = read_choice("Choose a program: ")
        choose(config, choice, args.print_urls)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
