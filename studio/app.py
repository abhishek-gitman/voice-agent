# ============================================================
# SuperVoice Studio — local dashboard API
# ============================================================

from dataclasses import fields
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agents.configs.priya_agent import AgentConfig, PRIYA_CONFIG
from agents.runtime_config import (
    DEFAULT_RUNTIME_PATH,
    agent_config_to_dict,
    load_agent_config,
    load_prompt_override,
    save_runtime,
)
from studio.agent_supervisor import AgentSupervisor
from studio.preflight import run_preflight

app = FastAPI(title="SuperVoice Studio", version="0.2.0")
supervisor = AgentSupervisor()
STATIC_DIR = Path(__file__).parent / "static"

NUMERIC_FIELDS = {
    "vad_confidence",
    "vad_start_secs",
    "vad_stop_secs",
    "vad_min_volume",
    "vad_speech_activity_period",
    "stt_endpointing_ms",
    "finalize_wait_secs",
    "llm_reply_delay_secs",
    "echo_tail_secs",
}


class RuntimePayload(BaseModel):
    agent: dict = Field(default_factory=dict)
    prompt: dict = Field(default_factory=dict)


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "supervoice-studio"}


@app.get("/api/preflight")
def preflight():
    return run_preflight()


@app.get("/api/config")
def get_config():
    config = load_agent_config(DEFAULT_RUNTIME_PATH)
    prompt = load_prompt_override(DEFAULT_RUNTIME_PATH) or ""
    return {
        "agent": agent_config_to_dict(config),
        "prompt": {"system_prompt": prompt},
        "defaults": agent_config_to_dict(PRIYA_CONFIG),
        "field_groups": _field_groups(),
        "options": {
            "stt_models": ["nova-2-general", "nova-3-general", "nova-2-phonecall"],
            "llm_models": [
                "gemini-2.5-flash",
                "gemini-2.0-flash",
                "gemini-2.5-pro",
            ],
            "tts_voices": [
                "aura-asteria-en",
                "aura-luna-en",
                "aura-stella-en",
                "aura-athena-en",
            ],
            "languages": ["en-IN", "en-US", "hi"],
        },
    }


def _field_groups():
    return {
        "identity": [
            {"key": "agent_name", "label": "Agent display name", "type": "text"},
            {"key": "agent_id", "label": "Agent ID", "type": "text"},
            {"key": "organization_id", "label": "Organization ID", "type": "text"},
        ],
        "models": [
            {"key": "model", "label": "LLM (Gemini)", "type": "select", "optionKey": "llm_models"},
            {"key": "stt_model", "label": "STT (Deepgram)", "type": "select", "optionKey": "stt_models"},
            {"key": "voice", "label": "TTS voice", "type": "select", "optionKey": "tts_voices"},
            {"key": "language", "label": "Language", "type": "select", "optionKey": "languages"},
        ],
        "vad": [
            {"key": "vad_confidence", "label": "VAD confidence", "type": "number", "step": 0.05, "min": 0.1, "max": 1},
            {"key": "vad_start_secs", "label": "Detect speech start (sec)", "type": "number", "step": 0.01, "min": 0.05, "max": 1},
            {"key": "vad_stop_secs", "label": "Wait before user finished (sec)", "type": "number", "step": 0.1, "min": 0.3, "max": 4},
            {"key": "vad_min_volume", "label": "Min mic volume", "type": "number", "step": 0.05, "min": 0.1, "max": 1},
            {"key": "vad_speech_activity_period", "label": "VAD activity period (sec)", "type": "number", "step": 0.05, "min": 0.05, "max": 1},
        ],
        "turn_taking": [
            {"key": "stt_endpointing_ms", "label": "STT endpointing (ms)", "type": "number", "step": 50, "min": 100, "max": 2000},
            {"key": "finalize_wait_secs", "label": "STT finalize wait (sec)", "type": "number", "step": 0.05, "min": 0, "max": 2},
            {"key": "llm_reply_delay_secs", "label": "Reply delay after you stop (sec)", "type": "number", "step": 0.1, "min": 0, "max": 3},
            {"key": "echo_tail_secs", "label": "Speaker echo guard tail (sec)", "type": "number", "step": 0.05, "min": 0.2, "max": 1.5},
        ],
    }


@app.put("/api/config")
def put_config(payload: RuntimePayload):
    allowed = {f.name for f in fields(AgentConfig)}
    agent = {}
    for key, value in payload.agent.items():
        if key not in allowed:
            continue
        if key in NUMERIC_FIELDS and value is not None and value != "":
            agent[key] = float(value) if "." in str(value) else int(value)
        else:
            agent[key] = value
    system_prompt = payload.prompt.get("system_prompt", "")
    save_runtime(agent, system_prompt, DEFAULT_RUNTIME_PATH)
    return {"ok": True, "message": "Settings saved to config/agent_runtime.json"}


@app.get("/api/agent/status")
def agent_status():
    return supervisor.status()


@app.post("/api/agent/start")
def agent_start():
    pre = run_preflight()
    if not pre["ready"]:
        raise HTTPException(
            status_code=400,
            detail="Setup incomplete. Fix items in the Setup checklist, then try again.",
        )
    result = supervisor.start()
    if not result.get("ok"):
        raise HTTPException(status_code=409, detail=result.get("error", "Start failed"))
    return result


@app.post("/api/agent/stop")
def agent_stop():
    return supervisor.stop()


@app.post("/api/agent/restart")
def agent_restart():
    supervisor.stop()
    pre = run_preflight()
    if not pre["ready"]:
        raise HTTPException(status_code=400, detail="Setup incomplete.")
    result = supervisor.start()
    if not result.get("ok"):
        raise HTTPException(status_code=409, detail=result.get("error", "Restart failed"))
    return {"ok": True, "message": "Agent restarted with latest settings.", **result}


@app.get("/api/agent/logs")
def agent_logs(tail: int = 250):
    lines = supervisor.logs(tail=tail)
    return {"lines": lines, "transcript": _parse_transcript(lines)}


def _parse_transcript(lines: list[str]) -> list[dict]:
    items = []
    for line in lines:
        if "🎙️  User (full turn):" in line:
            items.append({"role": "user", "text": line.split(":", 1)[-1].strip()})
        elif line.startswith("🤖 Priya:"):
            items.append({"role": "agent", "text": line.replace("🤖 Priya:", "").strip()})
        elif "] USER:" in line:
            items.append({"role": "user", "text": line.split("]:", 1)[-1].strip()})
        elif "] AGENT:" in line:
            items.append({"role": "agent", "text": line.split("]:", 1)[-1].strip()})
    deduped = []
    for item in items:
        if deduped and deduped[-1] == item:
            continue
        deduped.append(item)
    return deduped[-40:]


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
