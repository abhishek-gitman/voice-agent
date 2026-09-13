# ============================================================
# Build Pipecat pipeline from AgentConfig
# ============================================================

import os
import uuid

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_text_processor import LLMTextProcessor
from pipecat.processors.audio.vad_processor import VADProcessor
from runtime.full_response_aggregator import FullResponseTextAggregator
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.deepgram.tts import DeepgramTTSService
from pipecat.services.google.llm import GoogleLLMService
from pipecat.transcriptions.language import Language
from pipecat.transports.local.audio import LocalAudioTransport, LocalAudioTransportParams

from agents.configs.priya_agent import AgentConfig
from runtime.context_bridge import STTToLLMBridge, ResponseCapture
from runtime.playback_state import PlaybackState
from runtime.session import CallSession
from runtime.speakerphone_guard import (
    BotPlaybackObserver,
    EchoTranscriptionFilter,
    InputMuteGate,
)


def _resolve_language(code: str) -> Language:
    for lang in Language:
        if str(lang) == code or lang.value == code:
            return lang
    return Language.EN_IN


def build_task(config: AgentConfig, system_prompt: str) -> tuple[PipelineTask, CallSession]:
    playback = PlaybackState(
        echo_tail_secs=getattr(config, "echo_tail_secs", 0.5),
    )
    session = CallSession(
        organization_id=config.organization_id,
        agent_id=config.agent_id,
        call_id=str(uuid.uuid4()),
    )

    transport = LocalAudioTransport(
        LocalAudioTransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_audio_passthrough=True,
        )
    )

    # Deepgram returns 400 if utterance_end_ms is combined with interim_results=false.
    stt = DeepgramSTTService(
        api_key=os.getenv("DEEPGRAM_API_KEY"),
        settings=DeepgramSTTService.Settings(
            model=config.stt_model,
            language=_resolve_language(config.language),
            endpointing=config.stt_endpointing_ms,
            interim_results=True,
            punctuate=True,
            smart_format=True,
        ),
    )

    llm = GoogleLLMService(
        api_key=os.getenv("GEMINI_API_KEY"),
        model=config.model,
    )

    tts = DeepgramTTSService(
        api_key=os.getenv("DEEPGRAM_API_KEY"),
        settings=DeepgramTTSService.Settings(voice=config.voice),
    )

    vad = VADProcessor(
        vad_analyzer=SileroVADAnalyzer(
            params=VADParams(
                confidence=config.vad_confidence,
                start_secs=config.vad_start_secs,
                stop_secs=config.vad_stop_secs,
                min_volume=config.vad_min_volume,
            )
        ),
        speech_activity_period=config.vad_speech_activity_period,
    )

    bridge = STTToLLMBridge(
        session=session,
        system_prompt=system_prompt,
        playback=playback,
        finalize_wait_secs=config.finalize_wait_secs,
        llm_reply_delay_secs=config.llm_reply_delay_secs,
    )

    llm_text = LLMTextProcessor(
        text_aggregator=FullResponseTextAggregator(),
    )

    pipeline = Pipeline([
        transport.input(),
        InputMuteGate(playback),
        vad,
        stt,
        EchoTranscriptionFilter(playback),
        bridge,
        llm,
        llm_text,
        ResponseCapture(bridge=bridge, playback=playback),
        tts,
        BotPlaybackObserver(
            playback,
            on_bot_stopped=lambda: bridge._try_drain_pending_turn(None),
        ),
        transport.output(),
    ])

    task = PipelineTask(pipeline, params=PipelineParams())
    return task, session
