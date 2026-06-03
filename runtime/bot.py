# ============================================================
# IMPORTS
# ============================================================

import asyncio
import os
import uuid

from dotenv import load_dotenv

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_response import LLMFullResponseAggregator
from pipecat.processors.audio.vad_processor import VADProcessor
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.deepgram.tts import DeepgramTTSService
from pipecat.services.google.llm import GoogleLLMService
from pipecat.transports.local.audio import LocalAudioTransport, LocalAudioTransportParams

from agents.configs.priya_agent import PRIYA_CONFIG
from prompts.supervoice_sales_prompt import SUPERVOICE_SALES_PROMPT
from runtime.context_bridge import STTToLLMBridge, ResponseCapture
from runtime.session import CallSession

load_dotenv()


# ============================================================
# MAIN
# ============================================================

async def main():

    # -------------------------
    # Load Config — will come from database in future
    # -------------------------
    config = PRIYA_CONFIG
    prompt = SUPERVOICE_SALES_PROMPT

    # -------------------------
    # Create Session — one per call
    # -------------------------
    session = CallSession(
        organization_id=config.organization_id,
        agent_id=config.agent_id,
        call_id=str(uuid.uuid4()),
    )

    print(f"\n🎤 SuperVoice by Abhishek")
    print(f"🤖 Agent: {config.agent_name}  [{config.agent_id}]")
    print(f"📋 Prompt: {prompt.prompt_name}  [{prompt.prompt_id}]")
    print(f"📞 Call ID: {session.call_id}")
    print(f"🌐 Language: {config.language}\n")

    # -------------------------
    # Transport — Local Audio (mic + speakers)
    # -------------------------
    transport = LocalAudioTransport(
        LocalAudioTransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_audio_passthrough=True,
        )
    )

    # -------------------------
    # STT — Deepgram Nova-2
    # -------------------------
    stt = DeepgramSTTService(
        api_key=os.getenv("DEEPGRAM_API_KEY"),
        language=config.language,
    )

    # -------------------------
    # LLM — Google Gemini
    # -------------------------
    llm = GoogleLLMService(
        api_key=os.getenv("GEMINI_API_KEY"),
        model=config.model,
    )

    # -------------------------
    # TTS — Deepgram Aura
    # -------------------------
    tts = DeepgramTTSService(
        api_key=os.getenv("DEEPGRAM_API_KEY"),
        voice=config.voice,
    )

    # -------------------------
    # Pipeline Processors
    # -------------------------
    vad = VADProcessor(
        vad_analyzer=SileroVADAnalyzer(
            params=VADParams(
                confidence=0.7,
                start_secs=0.2,
                stop_secs=1.2,
                min_volume=0.6,
            )
        )
    )

    aggregator = LLMFullResponseAggregator()

    bridge = STTToLLMBridge(
        session=session,
        system_prompt=prompt.system_prompt,
    )

    response_capture = ResponseCapture(bridge=bridge)

    # -------------------------
    # Pipeline — ordered processing chain
    # -------------------------
    pipeline = Pipeline([
        transport.input(),
        vad,
        stt,
        bridge,
        llm,
        aggregator,
        response_capture,
        tts,
        transport.output(),
    ])

    # -------------------------
    # Task — runs the pipeline with interruptions enabled
    # -------------------------
    task = PipelineTask(
        pipeline,
        params=PipelineParams(allow_interruptions=True),
    )

    # -------------------------
    # Runner — executes the task
    # -------------------------
    runner = PipelineRunner()
    print("✅ Ready — speak into your microphone\n")

    await runner.run(task)

    # -------------------------
    # Call ended — print summary and transcript
    # -------------------------
    session.print_summary()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    asyncio.run(main())