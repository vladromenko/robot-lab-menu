"""Isolated loopback SSH server for launcher transport verification."""

import getpass
import os
import socket
import subprocess
import time
from pathlib import Path


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def command(args: list, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, **kwargs)


class SSHHarness:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.port = free_port()
        self.hostkey = root / "host-key"
        self.key = root / "client-key"
        for target in (self.hostkey, self.key):
            command(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(target)])
        (root / "authorized_keys").write_bytes(self.key.with_suffix(".pub").read_bytes())
        self.config = root / "client.conf"
        self.known = root / "known_hosts"
        host_public = self.hostkey.with_suffix(".pub").read_text().strip()
        self.known.write_text(f"[127.0.0.1]:{self.port} {host_public}\n")
        self.config.write_text(self.client_config())
        self.server_config = root / "sshd.conf"
        self.server_config.write_text(self.server_settings())
        self.log = (root / "sshd.log").open("w")
        self.server = subprocess.Popen(["/usr/sbin/sshd", "-D", "-e", "-f", str(self.server_config)],
                                       stdout=self.log, stderr=self.log)
        self.ready()

    def client_config(self) -> str:
        return f"""Host homebrain-test
    HostName 127.0.0.1
    User {getpass.getuser()}
    Port {self.port}
    IdentityFile "{self.key}"
    UserKnownHostsFile "{self.known}"
    StrictHostKeyChecking yes
    IdentitiesOnly yes
    BatchMode yes
    ConnectTimeout 3
"""

    def server_settings(self) -> str:
        return f"""Port {self.port}
ListenAddress 127.0.0.1
HostKey "{self.hostkey}"
AuthorizedKeysFile "{self.root / 'authorized_keys'}"
PidFile "{self.root / 'sshd.pid'}"
PasswordAuthentication no
KbdInteractiveAuthentication no
UsePAM no
PermitRootLogin no
AllowUsers {getpass.getuser()}
LogLevel ERROR
"""

    def ready(self) -> None:
        deadline = time.monotonic() + 4
        alive = False
        while time.monotonic() < deadline and not alive:
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=0.1):
                    alive = True
            except OSError:
                if self.server.poll() is not None:
                    raise RuntimeError("The isolated SSH server exited. Read its private test log.")
                time.sleep(0.05)
        if not alive:
            raise TimeoutError("The isolated SSH test server did not start.")

    def ssh(self, arguments: list, **kwargs):
        return command(["ssh", "-F", str(self.config), *arguments], **kwargs)

    def close(self) -> None:
        self.server.terminate()
        self.server.wait(timeout=5)
        self.log.close()
