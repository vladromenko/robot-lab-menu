# Homebrain native launcher

Homebrain.app opens the common Homebrain Lab workspace through one loopback SSH tunnel. The server owns the workspace, session restoration and native robot behavior.

The bootstrap locator is stored on the Mac at ~/Library/Application Support/Homebrain/locator.json. It contains the existing SSH alias or destination, the remote handover directory, a local port and the browser choice. SSH keys, passphrases and known-host rules use the existing OpenSSH configuration. HOMEBRAIN_LAB_HANDOVER_DIR overrides the remote descriptor directory for a launch.

The deployment descriptor is homebrain-lab.json in ~/.local/share/homebrain-lab/handover on Homebrain. The integration project owns its canonical schema, session handoff and operation scripts. The launcher accepts homebrain.lab.v1 separately from the preserved Robot Lab recovery menu.

The launcher reads the descriptor through a fixed Python standard-library helper over SSH. It validates pinned operation scripts and arguments before invoking an authorized status, start or handoff operation. A service identity check must succeed after tunneling. A bound local port or a running SSH process alone cannot establish readiness.

An SSH-issued ticket is sent using a short-lived, private browser form POST. The server consumes the ticket and sets its browser session cookie before redirecting to the common workspace. The launcher deletes the temporary form. Reopening the app after session expiry obtains a new ticket and reuses the workspace tab. The browser owns microphone permissions. The native app does not generate control heartbeats.

Closing the status window hides it. The Homebrain menu provides Open, Connection Settings and Quit. Quitting the launcher leaves the owned tunnel for reuse. A settings change closes only the tunnel identified by its private control socket. Sleep or Wi-Fi loss is checked with bounded backoff, and restoration reconnects transport. Native control arming remains an explicit server operation.

The default local address is http://127.0.0.1:18490. SSH binds the tunnel to 127.0.0.1. A conflicting port returns an error. Use Connection Settings to choose a different explicit port.

The icon is an original vector house/H mark. The ZIP contains Homebrain.app, the installer, Terminal shortcut and the existing Robot Lab recovery menu. Packaging requires Pillow on the build host. The Mac bundle uses built-in Cocoa, JavaScript for Automation and OpenSSH. The installer compiles its native applet with the built-in osacompile tool. The main app needs no Python installation on the Mac.

## Validation

Native Finder, browser Automation, gamepad, viewer/audio and sleep behavior require an attended Mac check. Record actual results here before marking those paths verified. Linux checks cover descriptor parsing, shell quoting, pinned operation dispatch, archive permissions and SSH/tunnel behavior.

## Build and checks

Install the development-only JavaScript parser dependencies with npm ci. Run npm test, npm run check, python3 scripts/check_style.py, and PYTHONPATH=src python3 -m unittest discover -s tests -v. Pillow is needed only for building the icon. Build into a new directory with python3 scripts/build_mac.py --output /absolute/output/path.

The native Cocoa bridge follows Apple’s JavaScript for Automation API. Process arguments use NSTask argument arrays. [Apple JXA reference](https://devstreaming-cdn.apple.com/videos/wwdc/2014/306xxjtg7uz13v0/306/306_javascript_for_automation.pdf), [NSTask arguments](https://developer.apple.com/documentation/foundation/process/arguments?language=objc).
