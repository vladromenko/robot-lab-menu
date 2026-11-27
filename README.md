# Homebrain

Open one common laboratory workspace from your Mac. [Download Homebrain for Mac](https://github.com/vladromenko/robot-lab-menu/releases/download/v0.2.0/Homebrain_Mac_0.2.0.zip), extract it, and open Install Homebrain.command once. The installer creates Homebrain.app in ~/Applications/Homebrain Launcher. Open that app or pin it in the Dock for later launches.

Initial setup asks for your existing Homebrain SSH alias or destination, the remote deployment handover directory, and an installed browser. Settings are saved on the Mac. The integration project publishes the common service descriptor and owns browser sessions and task restoration. Homebrain.app uses macOS Cocoa, JavaScript for Automation and OpenSSH. No Mac Python installation is needed for the main app.

See [Mac setup and recovery](docs/MAC_LAUNCHER.md) and the [short Russian installation guide](docs/INSTALL_RU.md).

Preview status on 27 November 2026. Packaging and isolated SSH checks pass. The full authenticated launch is waiting for the integration project's actual deployment descriptor. The latest [real service check](docs/live-launcher-check.json) records that dependency. Mac Finder installation, browser Automation, viewer/gamepad/audio and sleep recovery still require attended Mac validation.

The Robot Lab terminal menu remains available as a recovery option.

# Robot Lab recovery menu

Open five existing Homebrain programs from one Mac or terminal menu.

1. [Download the Mac ZIP](https://github.com/vladromenko/robot-lab-menu/releases/latest/download/Robot_Lab_Menu_Mac.zip) and extract it. Keep the folder together.
2. Connect to the network where your existing programs run and open `Robot_Lab.command`. The launcher uses Python 3.9 or newer from your PATH.
3. Pick one program. From Terminal, run `./Robot_Lab.command` in the same folder.

| Menu choice | Opens |
| --- | --- |
| Wrist / SO101 LeRobot | Studio on port 8020 |
| Cube / ROSMASTER | Explorer ROSMASTER control and observation on port 8030, plus an optional legacy console |
| Tank | Explorer's live fleet view and main console on port 8030 |
| Smart Swarm | The command declared in your local Smart Swarm `experiment.json` |
| Explorer | Explorer on port 8030 |

Browser targets use `homebrain.local` by default. Copy `configs/runtime.example.json` to `configs/local.json` to set the service URLs for your installation. The local file can also set `targets.legacy_cube.url` to the origin of a separate legacy console. Environment variables such as `ROBOT_LAB_WRIST_URL` and `ROBOT_LAB_EXPLORER_URL` override the file.

Set `swarm_handover` to the directory containing your Smart Swarm `experiment.json`. Its `project_path` and `entrypoint` identify the existing project and executable. For a Mac that uses a copy of Robot Lab on Homebrain, set both `homebrain_ssh` to an existing SSH destination and `homebrain_launcher` to the absolute path of that copy's `Robot_Lab.command`. The SSH connection uses your existing credentials and trusted host key.

Use `--print-urls` to print the chosen URL or command and `--check` for passive availability checks. Opening the menu itself does not launch a program. This repository contains the launcher only.

## Checks

```sh
bash -n Robot_Lab.command
python3 scripts/check_style.py
PYTHONPATH=src python3 -m unittest discover -s tests -v
```
