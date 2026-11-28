"""Build the portable Homebrain app bundle and its recovery menu."""

import argparse
import io
import plistlib
import shutil
import struct
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.2.0"
SOURCES = [
    "core.js", "macos-system.js", "macos-settings.js", "macos-connection.js",
    "macos-browser.js", "macos-ui.js", "main.js",
]


def copy_recovery(destination: Path) -> None:
    shutil.copy2(ROOT / "Robot_Lab.command", destination)
    shutil.copytree(ROOT / "src", destination / "src", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(ROOT / "configs", destination / "configs", ignore=shutil.ignore_patterns("local.json"))


def make_icon() -> bytes:
    from PIL import Image, ImageDraw

    records = []
    for size, kind in [(128, b"ic07"), (256, b"ic08"), (512, b"ic09"), (1024, b"ic10")]:
        image = Image.new("RGBA", (1024, 1024))
        drawing = ImageDraw.Draw(image)
        drawing.rounded_rectangle((72, 72, 952, 952), radius=208, fill="#102b3e")
        drawing.line([(260, 470), (512, 258), (764, 470)], fill="#9bdfcc", width=68, joint="curve")
        for points in [[(330, 475), (330, 758)], [(694, 475), (694, 758)], [(330, 608), (694, 608)]]:
            drawing.line(points, fill="#eef5f5", width=68)
            for x, y in points:
                drawing.ellipse((x - 34, y - 34, x + 34, y + 34), fill="#eef5f5")
        drawing.ellipse((458, 554, 566, 662), fill="#9bdfcc")
        stream = io.BytesIO()
        image.resize((size, size), Image.Resampling.LANCZOS).save(stream, format="PNG")
        payload = stream.getvalue()
        records.append(kind + struct.pack(">I", len(payload) + 8) + payload)
    return b"icns" + struct.pack(">I", 8 + sum(map(len, records))) + b"".join(records)


def app_info() -> dict:
    return {
        "CFBundleIdentifier": "com.vladromenko.homebrain.launcher",
        "CFBundleName": "Homebrain", "CFBundleDisplayName": "Homebrain",
        "CFBundleExecutable": "Homebrain", "CFBundleIconFile": "Homebrain.icns",
        "CFBundlePackageType": "APPL", "CFBundleVersion": VERSION,
        "CFBundleShortVersionString": VERSION, "LSMinimumSystemVersion": "12.0",
        "LSMultipleInstancesProhibited": True, "NSHighResolutionCapable": True,
        "NSAppleEventsUsageDescription": "Homebrain reuses its workspace tab in your chosen browser.",
        "NSLocalNetworkUsageDescription": "Homebrain connects to your saved laboratory SSH host.",
    }


def write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def build_app(destination: Path) -> None:
    bundle = destination / "Homebrain.app/Contents"
    executable = bundle / "MacOS"
    resources = bundle / "Resources"
    executable.mkdir(parents=True)
    resources.mkdir()
    (bundle / "Info.plist").write_bytes(plistlib.dumps(app_info()))
    (bundle / "PkgInfo").write_bytes(b"APPL????")
    script = "\n".join((ROOT / "native" / name).read_text() for name in SOURCES)
    (resources / "homebrain.js").write_text(script, encoding="utf-8")
    headless = script[:script.index("/* Application entry point.")]
    configure = (ROOT / "native/main.js").read_text().split("function eventLoop")[0]
    (resources / "headless.js").write_text(headless + configure + (ROOT / "native/headless.js").read_text())
    shutil.copy2(ROOT / "native/launcher.applescript", resources)
    for name in ("remote.py", "ssh-askpass"):
        shutil.copy2(ROOT / "native" / name, resources / name)
    (resources / "Homebrain.icns").write_bytes(make_icon())
    write_executable(executable / "Homebrain", """#!/bin/bash
set -eu
resources="$(cd -- "$(dirname "$0")/../Resources" && pwd)"
exec /usr/bin/osascript -l JavaScript "$resources/headless.js" "$resources" "$@"
""")


def shortcuts(destination: Path) -> None:
    write_executable(destination / "Homebrain.command", """#!/bin/bash
set -eu
bundle="$(cd -- "$(dirname "$0")" && pwd)/Homebrain.app"
exec /usr/bin/open "$bundle" --args "$@"
""")
    write_executable(destination / "Install Homebrain.command", (ROOT / "native/install.sh").read_text())
    write_executable(destination / "Homebrain Settings.command", """#!/bin/bash
set -eu
resources="$(cd -- "$(dirname "$0")" && pwd)/Homebrain.app/Contents/Resources"
exec /usr/bin/osascript -l JavaScript "$resources/headless.js" "$resources" --settings
""")


def archive(directory: Path, target: Path) -> None:
    with ZipFile(target, "w", ZIP_DEFLATED) as output:
        for path in sorted(directory.rglob("*")):
            if path.is_file():
                entry = ZipInfo("Homebrain/" + path.relative_to(directory).as_posix())
                entry.external_attr = path.stat().st_mode << 16
                entry.compress_type = ZIP_DEFLATED
                output.writestr(entry, path.read_bytes())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    directory = args.output / "Homebrain"
    if directory.exists():
        raise FileExistsError(directory)
    directory.mkdir(parents=True)
    build_app(directory)
    shortcuts(directory)
    copy_recovery(directory)
    for name in ("INSTALL_RU.md", "MAC_LAUNCHER.md"):
        shutil.copy2(ROOT / "docs" / name, directory)
    archive(directory, args.output / ("Homebrain_Mac_" + VERSION + ".zip"))


if __name__ == "__main__":
    main()
