# ============================================================
# AGENT CONFIG — Priya (Demo Agent)
# Technical configuration only. No prompts here.
# ============================================================

from dataclasses import dataclass


@dataclass
class AgentConfig:
    # -------------------------
    # Identifiers
    # -------------------------
    agent_id: str
    agent_name: str
    organization_id: str

    # -------------------------
    # Voice & Language
    # -------------------------
    voice: str
    language: str

    # -------------------------
    # LLM Settings
    # -------------------------
    model: str

    # -------------------------
    # STT / TTS Providers
    # -------------------------
    stt_provider: str = "deepgram"
    tts_provider: str = "deepgram"
    llm_provider: str = "gemini"

    # -------------------------
    # Prompt Reference
    # Points to which prompt this agent uses
    # -------------------------
    prompt_id: str = ""

    # -------------------------
    # Turn-taking & VAD (local demo)
    # -------------------------
    vad_confidence: float = 0.55
    vad_start_secs: float = 0.12
    vad_stop_secs: float = 2.0
    vad_min_volume: float = 0.45
    vad_speech_activity_period: float = 0.1
    stt_model: str = "nova-2-general"
    stt_endpointing_ms: int = 400
    finalize_wait_secs: float = 0.45
    llm_reply_delay_secs: float = 0.6
    echo_tail_secs: float = 0.5


PRIYA_CONFIG = AgentConfig(
    agent_id="agt_priya_001",
    agent_name="Priya",
    organization_id="org_supervoice_demo",
    voice="aura-asteria-en",
    language="en-IN",
    model="gemini-2.5-flash",
    prompt_id="pmt_supervoice_sales_001",
)