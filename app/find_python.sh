#!/bin/sh
set -eu

if [ -n "${VIDEO_TO_PPT_PYTHON:-}" ] && [ -x "$VIDEO_TO_PPT_PYTHON" ]; then
    if "$VIDEO_TO_PPT_PYTHON" -c 'import numpy, PIL, pptx' >/dev/null 2>&1; then
        printf '%s\n' "$VIDEO_TO_PPT_PYTHON"
        exit 0
    fi
fi

for candidate in \
    "$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3" \
    "$HOME/.venv/bin/python3" \
    "$HOME/video-to-ppt/.venv/bin/python3" \
    /opt/homebrew/bin/python3 \
    /opt/homebrew/bin/python3.12 \
    /opt/homebrew/bin/python3.11 \
    /usr/local/bin/python3 \
    /usr/bin/python3
do
    if [ -x "$candidate" ] && "$candidate" -c 'import numpy, PIL, pptx' >/dev/null 2>&1; then
        printf '%s\n' "$candidate"
        exit 0
    fi
done

echo "未找到安装了 numpy、Pillow、python-pptx 的 Python。请先运行: python3 -m pip install -r requirements.txt" >&2
exit 1
