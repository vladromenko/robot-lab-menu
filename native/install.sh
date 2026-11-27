#!/bin/bash
set -eu
source_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
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
/usr/libexec/PlistBuddy -c "Set :CFBundleName Homebrain" "$plist"
/usr/libexec/PlistBuddy -c "Set :CFBundleIconFile Homebrain.icns" "$plist"
/usr/libexec/PlistBuddy -c "Set :CFBundleIdentifier com.vladromenko.homebrain.launcher" "$plist" 2>/dev/null ||
    /usr/libexec/PlistBuddy -c "Add :CFBundleIdentifier string com.vladromenko.homebrain.launcher" "$plist"
/usr/libexec/PlistBuddy -c "Add :NSAppleEventsUsageDescription string Homebrain reuses its workspace tab in your chosen browser." "$plist"
/usr/libexec/PlistBuddy -c "Add :LSMultipleInstancesProhibited bool true" "$plist"
/usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString 0.2.0" "$plist"
/usr/libexec/PlistBuddy -c "Set :CFBundleVersion 0.2.0" "$plist"
/usr/bin/codesign --force --sign - "$compiled"
/usr/bin/ditto "$compiled" "$destination/Homebrain.app"
/usr/bin/open "$destination/Homebrain.app"
printf '%s\n' 'Installed in Applications/Homebrain Launcher. Open Homebrain.app to launch.'
