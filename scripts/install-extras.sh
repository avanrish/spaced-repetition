#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
MAN_DIR="$HOME/.local/share/man/man1"
ZSH_DIR="$HOME/.local/share/zsh/site-functions"

mode="symlink"
if [[ "${1:-}" == "--copy" ]]; then
    mode="copy"
fi

mkdir -p "$MAN_DIR" "$ZSH_DIR"

if [[ "$mode" == "copy" ]]; then
    cp "$REPO_DIR/man/srs.1" "$MAN_DIR/srs.1"
    cp "$REPO_DIR/completions/_srs" "$ZSH_DIR/_srs"
    echo "Copied man page and zsh completions."
else
    ln -sf "$REPO_DIR/man/srs.1" "$MAN_DIR/srs.1"
    ln -sf "$REPO_DIR/completions/_srs" "$ZSH_DIR/_srs"
    echo "Symlinked man page and zsh completions (edits update live)."
fi

echo "  man srs        — view man page"
echo "  compinit       — reload completions (or restart shell)"
