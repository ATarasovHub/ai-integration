# Ollama Setup

Local LLM backend for the Jira → LLM → Rocket.Chat pipeline.

## One-time install (WSL2 / Linux)

```bash
sudo apt-get install -y zstd
curl -fsSL https://ollama.com/install.sh | sh
```

Verify:

```bash
ollama --version
```

## Configuration

Model and endpoint come from `.env` (see [`.env.example`](../.env.example)):

```
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
```

Change `OLLAMA_MODEL` to any tag available in the Ollama registry (e.g. `llama3.1:70b`, `mistral:7b`).

## Automatic start before the app

The project ships with [`scripts/ensure_ollama.sh`](../scripts/ensure_ollama.sh), which:

1. Checks that `ollama` is installed.
2. Pings `${OLLAMA_BASE_URL}/api/tags` and starts `ollama serve` in the background if the server is down.
3. Pulls the model declared in `OLLAMA_MODEL` if it is not present locally.

It is wired as a `preLaunchTask` in [`.vscode/launch.json`](../.vscode/launch.json), so every time you press **Run FastAPI** in VS Code the script runs first and blocks the launch until Ollama is ready.

### Manual run (outside VS Code)

```bash
./scripts/ensure_ollama.sh
```

Server logs are written to `/tmp/ollama.log`.

## Smoke-test the model

```bash
curl http://localhost:11434/api/generate \
  -d '{"model":"llama3.1:8b","prompt":"Reply in JSON with field status=ok","stream":false,"format":"json"}'
```
