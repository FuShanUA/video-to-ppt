#!/bin/sh
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP_NAME="${APP_NAME:-图片视频合成PPT}"
APP_PATH="$ROOT/$APP_NAME.app"

command -v osacompile >/dev/null 2>&1 || {
    echo "需要 macOS 的 osacompile。" >&2
    exit 1
}
command -v codesign >/dev/null 2>&1 || {
    echo "需要 macOS 的 codesign。" >&2
    exit 1
}

rm -rf "$APP_PATH"
osacompile -o "$APP_PATH" "$ROOT/app/main.applescript"

cp "$ROOT/app/Info.plist" "$APP_PATH/Contents/Info.plist"
cp "$ROOT/app/make_ppt.py" "$APP_PATH/Contents/Resources/make_ppt.py"
cp "$ROOT/skill/scripts/video_to_ppt.py" "$APP_PATH/Contents/Resources/video_to_ppt.py"
cp "$ROOT/app/find_python.sh" "$APP_PATH/Contents/Resources/find_python.sh"
chmod +x "$APP_PATH/Contents/Resources/find_python.sh"

codesign --force --deep --sign - "$APP_PATH"
printf '已生成：%s\n' "$APP_PATH"
