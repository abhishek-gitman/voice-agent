import asyncio
import os

from dotenv import load_dotenv

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask, PipelineParams
from context_bridge import STTToLLMBridge, ResponseCapture

from pipecat.processors.audio.vad_processor import VADProcessor
from pipecat.processors.aggregators.llm_response import (
    LLMFullResponseAggregator,
)

from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.deepgram.tts import DeepgramTTSService
from pipecat.services.google.llm import GoogleLLMService

from pipecat.transports.local.audio import (
    LocalAudioTransport,
    LocalAudioTransportParams,
)

from context_bridge import STTToLLMBridge
from prompts import SUPERVOICE_SYSTEM_PROMPT

load_dotenv()


async def main():

    deepgram_api_key = os.getenv("DEEPGRAM_API_KEY")
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    llm_model = os.getenv("LLM_MODEL", "gemini-2.5-flash")

    # -------------------------
    # VAD
    # -------------------------

    from pipecat.audio.vad.vad_analyzer import VADParams
    vad = VADProcessor(
        vad_analyzer=SileroVADAnalyzer(
            params=VADParams(stop_secs=1.2)
        )
    )

    # -------------------------
    # Transport
    # -------------------------

    transport = LocalAudioTransport(
        params=LocalAudioTransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
        )
    )

    # -------------------------
    # STT
    # -------------------------

    stt = DeepgramSTTService(
        api_key=deepgram_api_key,
        language="en",
    )

    # -------------------------
    # Context Bridge
    # -------------------------

    bridge = STTToLLMBridge(
        system_prompt=SUPERVOICE_SYSTEM_PROMPT
    )

    # -------------------------
    # Gemini
    # -------------------------

    llm = GoogleLLMService(
        api_key=gemini_api_key,
        settings=GoogleLLMService.Settings(
            model=llm_model,
        ),
    )

    # -------------------------
    # TTS
    # -------------------------

    tts = DeepgramTTSService(
        api_key=deepgram_api_key,
        settings=DeepgramTTSService.Settings(
            voice="aura-asteria-en",
        ),
    )

    # -------------------------
    # Aggregator
    # -------------------------

    aggregator = LLMFullResponseAggregator()

    # -------------------------
    # RESPONSE CAPTURE — saves assistant replies to conversation history
    # -------------------------
    response_capture = ResponseCapture(bridge=bridge)

    # -------------------------
    # Pipeline
    # -------------------------

    pipeline = Pipeline(
        [
            transport.input(),
            vad,
            stt,
            bridge,            # user text → LLM context
            llm,
            aggregator,
            response_capture,  # captures assistant reply → saves to bridge
            tts,
            transport.output(),
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            allow_interruptions=True,
        ),
    )

    print("\n🎤 SuperVoice by Abhishek")
    print("✅ Deepgram STT")
    print("✅ Gemini LLM")
    print("✅ Deepgram TTS")
    print("Ready...\n")

    runner = PipelineRunner()

    await runner.run(task)


if __name__ == "__main__":
    asyncio.run(main())

