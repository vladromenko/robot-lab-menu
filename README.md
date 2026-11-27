# Robot Lab

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
