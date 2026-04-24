#!/usr/bin/env bash
# Ensures Ollama is installed, running, and the required model is pulled.
# Run before starting the FastAPI app (wired as a preLaunchTask in .vscode/launch.json).

set -e

OLLAMA_URL="http://localhost:11434"
MODEL="llama3.1:8b"

# Pick up overrides from .env if present.
if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

OLLAMA_URL="${OLLAMA_BASE_URL:-$OLLAMA_URL}"
MODEL="${OLLAMA_MODEL:-$MODEL}"

log() { echo "[ensure_ollama] $*"; }

# 1. Installed?
if ! command -v ollama >/dev/null 2>&1; then
  log "Ollama is not installed. Install it with: curl -fsSL https://ollama.com/install.sh | sh"
  exit 1
fi

# 2. Server running?
if curl -sf "${OLLAMA_URL}/api/tags" >/dev/null 2>&1; then
  log "Server already running at ${OLLAMA_URL}"
else
  log "Starting Ollama server in background..."
  nohup ollama serve > /tmp/ollama.log 2>&1 &
  disown || true

  for _ in $(seq 1 20); do
    if curl -sf "${OLLAMA_URL}/api/tags" >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done

  if ! curl -sf "${OLLAMA_URL}/api/tags" >/dev/null 2>&1; then
    log "Failed to start Ollama within 20s. See /tmp/ollama.log"
    exit 1
  fi
  log "Server is up at ${OLLAMA_URL}"
fi

# 3. Model pulled?
if curl -sf "${OLLAMA_URL}/api/tags" | grep -q "\"name\":\"${MODEL}\""; then
  log "Model '${MODEL}' already available."
else
  log "Model '${MODEL}' not found. Pulling (this may take a while)..."
  ollama pull "${MODEL}"
fi

log "Ready."
