#!/bin/bash
set -eu
source_dir="$(cd -- "$(dirname "$0")" && pwd)"
destination="$HOME/Applications/Homebrain Launcher"
mkdir -p "$destination"
if [ "$source_dir" != "$destination" ]; then
    /usr/bin/ditto "$source_dir" "$destination"
fi
build_dir="$(mktemp -d "$destination/.native-build.XXXXXX")"
trap 'rm -rf "$build_dir"' EXIT
compiled="$build_dir/Homebrain.app"
/usr/bin/osacompile -l JavaScript -o "$compiled"     "$source_dir/Homebrain.app/Contents/Resources/homebrain.js"
/usr/bin/ditto "$source_dir/Homebrain.app/Contents/Resources" "$compiled/Contents/Resources"
plist="$compiled/Contents/Info.plist"
set_plist() {
    /usr/libexec/PlistBuddy -c "Set :$1 $3" "$plist" 2>/dev/null ||
        /usr/libexec/PlistBuddy -c "Add :$1 $2 $3" "$plist"
}
set_plist CFBundleName string Homebrain
set_plist CFBundleDisplayName string Homebrain
set_plist CFBundleIconFile string Homebrain.icns
set_plist CFBundleIdentifier string com.vladromenko.homebrain.launcher
set_plist NSAppleEventsUsageDescription string 'Homebrain reuses its workspace tab in your chosen browser.'
set_plist NSLocalNetworkUsageDescription string 'Homebrain connects to your saved laboratory SSH host.'
set_plist LSMultipleInstancesProhibited bool true
set_plist NSHighResolutionCapable bool true
set_plist LSMinimumSystemVersion string 12.0
set_plist CFBundleShortVersionString string 0.2.0
set_plist CFBundleVersion string 0.2.0
/usr/bin/codesign --force --sign - "$compiled"
if [ -d "$destination/Homebrain.app" ]; then
    /bin/mv "$destination/Homebrain.app" "$build_dir/previous.app"
fi
if ! /bin/mv "$compiled" "$destination/Homebrain.app"; then
    if [ -d "$build_dir/previous.app" ]; then
        /bin/mv "$build_dir/previous.app" "$destination/Homebrain.app"
    fi
    exit 1
fi
/usr/bin/open "$destination/Homebrain.app"
printf '%s\n' 'Installed in Applications/Homebrain Launcher. Open Homebrain.app to launch.'
