# ============================================================
# Half-duplex guards for loudspeaker use (no echo → STT / VAD)
# ============================================================

from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    Frame,
    InputAudioRawFrame,
    TranscriptionFrame,
    VADUserStartedSpeakingFrame,
    VADUserStoppedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from runtime.playback_state import PlaybackState


class InputMuteGate(FrameProcessor):
    """Drop microphone frames while the agent is speaking (+ short echo tail)."""

    def __init__(self, playback: PlaybackState, **kwargs):
        super().__init__(**kwargs)
        self._playback = playback

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, InputAudioRawFrame) and self._playback.is_listen_muted():
            return
        await self.push_frame(frame, direction)


class BotPlaybackObserver(FrameProcessor):
    """Track real speaker output so listen gate matches what the user hears."""

    def __init__(self, playback: PlaybackState, on_bot_stopped=None, **kwargs):
        super().__init__(**kwargs)
        self._playback = playback
        self._on_bot_stopped = on_bot_stopped

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, BotStartedSpeakingFrame):
            self._playback.on_bot_started_speaking()
        elif isinstance(frame, BotStoppedSpeakingFrame):
            self._playback.on_bot_stopped_speaking()
            if self._on_bot_stopped:
                self._on_bot_stopped()
        await self.push_frame(frame, direction)


class EchoTranscriptionFilter(FrameProcessor):
    """Drop transcriptions that are clearly the agent's voice echoed from speakers."""

    def __init__(self, playback: PlaybackState, **kwargs):
        super().__init__(**kwargs)
        self._playback = playback

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, TranscriptionFrame) and frame.text:
            from runtime.playback_state import is_likely_echo

            if self._playback.is_listen_muted():
                return
            if is_likely_echo(frame.text, self._playback.last_agent_text):
                print(f"🔇 Echo filtered: {frame.text.strip()}")
                return
        if isinstance(frame, VADUserStartedSpeakingFrame) and self._playback.is_listen_muted():
            return
        if isinstance(frame, VADUserStoppedSpeakingFrame) and self._playback.is_listen_muted():
            return
        await self.push_frame(frame, direction)
