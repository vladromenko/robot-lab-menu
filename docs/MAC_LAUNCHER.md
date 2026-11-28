# Homebrain Mac launcher

Homebrain.app opens the common Homebrain Lab workspace through one loopback SSH tunnel. The server owns the workspace, session restoration and native robot behavior. The Mac entry point is a small stay-open AppleScript applet using the existing validated JavaScript and OpenSSH helpers. It does not create a separate laboratory window.

Install Homebrain.command compiles the app with built-in macOS tools into ~/Applications/Homebrain Launcher. Homebrain.command opens it from Terminal. Homebrain Settings.command opens the saved connection dialogs. Robot_Lab.command remains the independent recovery menu.

The bootstrap locator is saved at ~/Library/Application Support/Homebrain/locator.json. It contains the existing SSH alias or destination, remote handover directory, explicit local port, installed browser and browser opening mode. Existing OpenSSH keys, passphrases and known-host rules are reused. HOMEBRAIN_LAB_HANDOVER_DIR overrides the remote directory for a launch.

The integration project publishes homebrain-lab.json in ~/.local/share/homebrain-lab/handover on Homebrain. The launcher consumes homebrain.lab.v1 separately from the preserved robot-platform fixture. Its fixed SSH helper validates allowlisted pinned scripts and arguments. The tunneled health response must identify the actual declared service and source commit.

Standard opening uses macOS Launch Services and does not require browser Automation permission. Each explicit opening may create a browser tab for the same common workspace. Optional automation mode reuses a matching workspace tab when the browser responds to Apple events. On the attended Mac, Chrome Apple events timed out, so the installed locator selects Safari with standard opening. Safari viewer, gamepad and audio capabilities have not been accepted; the deployment currently declares Chrome. This fallback validates entry to the common page only.

The SSH handoff ticket stays in a private form POST. It is never put in a URL. Standard opening retains the private form for up to 30 seconds to let the browser read it, then deletes it. Reopening obtains a fresh ticket after session expiry. Cookies and task restoration belong to the server. The browser owns microphone permissions.

The applet checks the viewing connection every 20 seconds. This idle operation only restores its owned tunnel and checks service health. It does not issue authentication, bootstrap or control operations. Native arming remains an explicit server action. Quitting Homebrain leaves the owned tunnel for reuse and preserves host programs and recordings.

The local address defaults to http://127.0.0.1:18490. A busy port fails explicitly. Use Homebrain Settings.command to change it. The main app requires no Mac Python, robotics packages or model files.

## Validation

Seventeen JavaScript checks and fifteen Python checks cover connection logic, pinned dispatch and isolated real OpenSSH transport. macOS 15.6.1 compilation, signature verification, existing LAN SSH credentials, the actual tunneled service identity and one persistent Dock item were checked on the Mac. A Linux Chromium check passed the real file-form POST and two authenticated workspace loads. Visual Safari page acceptance, viewer/gamepad/audio and sleep recovery remain separate pending checks.

See browser-handoff-check.json and mac-install-check.json in this repository's docs directory for dated results. Native opening uses the system applet instead of the earlier custom Cocoa event loop. The earlier native source and the recovery menu are preserved.

## Build and checks

Run npm ci, npm test, npm run check, python3 scripts/check_style.py, and PYTHONPATH=src python3 -m unittest discover -s tests -v. Build into a new directory with python3 scripts/build_mac.py --output /absolute/output/path. Pillow is needed only on the build host for the original Homebrain icon.
