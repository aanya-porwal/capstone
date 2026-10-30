# Optional local conversational model (Windows 11, 16 GB RAM)

1. Install Ollama for Windows from https://ollama.com/download/windows
2. Open PowerShell and run: `ollama pull qwen2.5:3b`
3. Start Ollama (usually it runs as a background service).
4. Start DWMS with `run_dwms.bat`.

The prototype calls the local Ollama API at `http://localhost:11434`. No OpenAI API key is used. If Ollama is unavailable, a deterministic local fallback remains available. A 3B quantised model on CPU can be slow; do not run it alongside memory-heavy notebooks or IDE tasks.
