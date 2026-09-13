# ============================================================
# Environment checks before starting the voice agent
# ============================================================

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run_preflight() -> dict:
    checks = []
    ok = True

    def add(name: str, passed: bool, detail: str, fix: str = ""):
        nonlocal ok
        if not passed:
            ok = False
        checks.append({"name": name, "ok": passed, "detail": detail, "fix": fix})

    venv = ROOT / ".venv" / "bin" / "python"
    add(
        "Python environment",
        venv.is_file(),
        str(venv) if venv.is_file() else "No .venv found",
        "Run ./run.sh once in Terminal to create it",
    )

    env_file = ROOT / ".env"
    has_env = env_file.is_file()
    add("Environment file", has_env, ".env present" if has_env else "Missing .env", "Copy .env with DEEPGRAM_API_KEY and GEMINI_API_KEY")

    if has_env:
        text = env_file.read_text(encoding="utf-8")
        dg = "DEEPGRAM_API_KEY=" in text and len(text.split("DEEPGRAM_API_KEY=", 1)[-1].split("\n")[0].strip()) > 8
        gem = "GEMINI_API_KEY=" in text and len(text.split("GEMINI_API_KEY=", 1)[-1].split("\n")[0].strip()) > 8
        add("Deepgram API key", dg, "Set in .env" if dg else "Missing or empty", "Add DEEPGRAM_API_KEY=...")
        add("Gemini API key", gem, "Set in .env" if gem else "Missing or empty", "Add GEMINI_API_KEY=...")

    cfg = ROOT / "config" / "agent_runtime.json"
    add("Runtime config", cfg.is_file(), str(cfg), "Save settings from Studio once")

    if venv.is_file():
        try:
            import subprocess

            r = subprocess.run(
                [str(venv), "-c", "import pyaudio"],
                capture_output=True,
                timeout=15,
                cwd=str(ROOT),
            )
            add(
                "Microphone audio (PyAudio)",
                r.returncode == 0,
                "Ready" if r.returncode == 0 else "PyAudio not installed",
                "brew install portaudio && .venv/bin/pip install 'pipecat-ai[local]==1.3.0'",
            )
        except Exception as e:
            add("Microphone audio (PyAudio)", False, str(e), "See run.sh setup")

    return {"ready": ok, "checks": checks, "project_root": str(ROOT)}
