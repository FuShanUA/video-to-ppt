#!/bin/sh
set -eu

ROOT="$(cd "$(dirname "$0")" && pwd)"
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
DEST="$CODEX_HOME/skills/video-to-ppt"

rm -rf "$DEST"
mkdir -p "$DEST"
cp -R "$ROOT/skill/." "$DEST/"

printf 'Skill 已安装到：%s\n' "$DEST"
