# ============================================================
# Runtime config — loaded from config/agent_runtime.json (Studio UI)
# ============================================================

import json
from dataclasses import asdict, fields
from pathlib import Path

from agents.configs.priya_agent import PRIYA_CONFIG, AgentConfig

DEFAULT_RUNTIME_PATH = Path(__file__).resolve().parent.parent / "config" / "agent_runtime.json"


def _config_field_names() -> set[str]:
    return {f.name for f in fields(AgentConfig)}


def load_agent_config(path: Path | None = None) -> AgentConfig:
    """Merge saved JSON overrides onto PRIYA_CONFIG defaults."""
    path = path or DEFAULT_RUNTIME_PATH
    base = asdict(PRIYA_CONFIG)
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        agent = data.get("agent", data)
        for key, value in agent.items():
            if key in _config_field_names():
                base[key] = value
    return AgentConfig(**base)


def load_prompt_override(path: Path | None = None) -> str | None:
    path = path or DEFAULT_RUNTIME_PATH
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    prompt = data.get("prompt", {})
    text = prompt.get("system_prompt", "").strip()
    return text or None


def save_runtime(
    agent: dict,
    system_prompt: str | None = None,
    path: Path | None = None,
) -> None:
    path = path or DEFAULT_RUNTIME_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"agent": agent}
    if system_prompt is not None:
        payload["prompt"] = {"system_prompt": system_prompt}
    elif path.is_file():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if "prompt" in existing:
            payload["prompt"] = existing["prompt"]
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def agent_config_to_dict(config: AgentConfig) -> dict:
    return asdict(config)
