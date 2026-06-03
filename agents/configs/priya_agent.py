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


PRIYA_CONFIG = AgentConfig(
    agent_id="agt_priya_001",
    agent_name="Priya",
    organization_id="org_supervoice_demo",
    voice="aura-asteria-en",
    language="en-IN",
    model="gemini-2.5-flash",
    prompt_id="pmt_supervoice_sales_001",
)