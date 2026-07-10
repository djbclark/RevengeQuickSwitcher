#!/usr/bin/env bash
# Install UI-TARS-1.5-7B GGUF + mmproj for local QSS vision gates.
set -euo pipefail

MODEL_DIR="${UI_TARS_MODEL_DIR:-${UI_TARS_HOME:-${HOME}/.local/share/ui-tars}/models/1.5-7b}"
BASE_URL="https://huggingface.co/adriabama06/UI-TARS-1.5-7B-GGUF/resolve/main"

echo "==> brew install ollama llama.cpp (if needed)"
brew list ollama >/dev/null 2>&1 || brew install ollama
brew list llama.cpp >/dev/null 2>&1 || brew install llama.cpp

mkdir -p "$MODEL_DIR"
cd "$MODEL_DIR"

download() {
  local name="$1"
  if [[ -f "$name" ]]; then
    echo "  ok  $name"
    return 0
  fi
  echo "  get $name …"
  curl -L --fail --continue-at - -o "$name" "${BASE_URL}/${name}"
}

echo "==> Download UI-TARS weights to $MODEL_DIR (~5.9 GB total)"
download "ByteDance-Seed_UI-TARS-1.5-7B-Q4_K_M.gguf"
download "mmproj-ByteDance-Seed_UI-TARS-1.5-7B.gguf"

echo "==> Done."
echo "    Models:  ${MODEL_DIR}"
echo "    Install launchd agent: scripts/vlm_service.sh install"
echo "    Test:    python3 scripts/vlm_check.py"
