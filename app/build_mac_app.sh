#!/bin/sh
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${VIDEO_TO_PPT_PYTHON:-python3}"
VENV="${VIDEO_TO_PPT_BUILD_VENV:-$ROOT/.venv-macos-build}"
ARCH="$(uname -m)"
APP_PATH="$ROOT/dist/VideoToPPT.app"
ZIP_PATH="$ROOT/dist/VideoToPPT-macOS-$ARCH.zip"

command -v "$PYTHON" >/dev/null 2>&1 || {
    echo "需要 Python 3.11 或更新版本。" >&2
    exit 1
}
command -v ffmpeg >/dev/null 2>&1 || {
    echo "需要 ffmpeg，可用 brew install ffmpeg 安装。" >&2
    exit 1
}
command -v ffprobe >/dev/null 2>&1 || {
    echo "需要 ffprobe，可用 brew install ffmpeg 安装。" >&2
    exit 1
}
command -v ditto >/dev/null 2>&1 || {
    echo "需要 macOS 的 ditto。" >&2
    exit 1
}
command -v codesign >/dev/null 2>&1 || {
    echo "需要 macOS 的 codesign。" >&2
    exit 1
}

if [ ! -x "$VENV/bin/python" ]; then
    "$PYTHON" -m venv "$VENV"
fi
"$VENV/bin/python" -m pip install -r "$ROOT/requirements.txt" pyinstaller

FFMPEG="$(command -v ffmpeg)"
FFPROBE="$(command -v ffprobe)"

"$VENV/bin/pyinstaller" \
    --noconfirm --clean --windowed \
    --name VideoToPPT \
    --specpath "$ROOT/build/VideoToPPT-macos" \
    --paths "$ROOT/skill/scripts" \
    --paths "$ROOT/app" \
    --add-binary "$FFMPEG:." \
    --add-binary "$FFPROBE:." \
    "$ROOT/app/gui.py"

codesign --verify --deep --strict "$APP_PATH"
ditto -c -k --keepParent "$APP_PATH" "$ZIP_PATH"
printf '已生成：%s\n' "$ZIP_PATH"
