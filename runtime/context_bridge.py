# ============================================================
# IMPORTS
# ============================================================

import asyncio
from pipecat.frames.frames import (
    AggregatedTextFrame,
    Frame,
    InterruptionFrame,
    InterruptionTaskFrame,
    LLMContextFrame,
    LLMFullResponseEndFrame,
    TranscriptionFrame,
    TTSStartedFrame,
    VADUserStartedSpeakingFrame,
    VADUserStoppedSpeakingFrame,
)
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from runtime.playback_state import PlaybackState, is_likely_echo
from runtime.session import CallSession


# ============================================================
# STT TO LLM BRIDGE
# ============================================================

class STTToLLMBridge(FrameProcessor):

    def __init__(
        self,
        session: CallSession,
        system_prompt: str,
        playback: PlaybackState,
        *,
        finalize_wait_secs: float = 0.45,
        llm_reply_delay_secs: float = 0.6,
        min_user_chars: int = 3,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._session = session
        self._system_prompt = system_prompt
        self._playback = playback
        self._finalize_wait_secs = finalize_wait_secs
        self._llm_reply_delay_secs = llm_reply_delay_secs
        self._min_user_chars = min_user_chars

        self._utterance_buffer = ""
        self._commit_task: asyncio.Task | None = None
        self._llm_task: asyncio.Task | None = None
        self._llm_busy = False

        print("✅ STTToLLMBridge initialized (speakerphone-safe turn-taking)")

    def add_assistant_message(self, text: str, direction=None):
        if text.strip():
            self._session.add_message("agent", text.strip())
            self._playback.set_last_agent_text(text.strip())
            self._llm_busy = False
            self._try_drain_pending_turn(direction)

    def _try_drain_pending_turn(self, direction: FrameDirection | None) -> None:
        if self._llm_busy or self._playback.is_listen_muted():
            return
        pending = self._playback.pop_pending_user_turn()
        if pending:
            print(f"📨 Processing queued user turn: {pending}")
            self._llm_task = asyncio.create_task(
                self._respond_to_user(pending, direction or FrameDirection.DOWNSTREAM)
            )

    def _merge_transcript(self, new_text: str) -> None:
        new_text = new_text.strip()
        if not new_text:
            return
        if not self._utterance_buffer:
            self._utterance_buffer = new_text
            return
        if new_text.startswith(self._utterance_buffer) or len(new_text) >= len(
            self._utterance_buffer
        ):
            self._utterance_buffer = new_text
        else:
            self._utterance_buffer = f"{self._utterance_buffer} {new_text}".strip()

    def _cancel_pending_tasks(self) -> None:
        if self._commit_task and not self._commit_task.done():
            self._commit_task.cancel()
        self._commit_task = None
        if self._llm_task and not self._llm_task.done():
            self._llm_task.cancel()
        self._llm_task = None

    async def _interrupt_agent(self) -> None:
        await self.push_frame(InterruptionTaskFrame(), FrameDirection.UPSTREAM)

    async def _commit_user_turn(self, direction: FrameDirection) -> None:
        try:
            await asyncio.sleep(self._finalize_wait_secs)
            if self._playback.is_listen_muted():
                return

            text = self._utterance_buffer.strip()
            self._utterance_buffer = ""
            if len(text) < self._min_user_chars:
                print(f"🔇 Ignored short fragment ({len(text)} chars): '{text}'")
                return
            if is_likely_echo(text, self._playback.last_agent_text):
                print(f"🔇 Ignored echo turn: '{text}'")
                return

            print(f"\n🎙️  User (full turn): {text}")

            if self._llm_busy or self._playback.is_listen_muted():
                self._playback.queue_user_turn(text)
                print("📝 Queued — agent still speaking")
                return

            self._llm_task = asyncio.create_task(
                self._respond_to_user(text, direction)
            )
            await self._llm_task

        except asyncio.CancelledError:
            pass

    async def _respond_to_user(self, text: str, direction: FrameDirection) -> None:
        try:
            self._session.add_message("user", text)
            self._llm_busy = True
            await asyncio.sleep(self._llm_reply_delay_secs)

            context = LLMContext(
                messages=self._session.get_llm_messages(self._system_prompt)
            )
            await self.push_frame(LLMContextFrame(context=context), direction)
        except asyncio.CancelledError:
            print("⏭️  LLM response cancelled — user spoke again")
            self._llm_busy = False

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, VADUserStartedSpeakingFrame):
            if self._playback.is_listen_muted():
                await self.push_frame(frame, direction)
                return
            self._cancel_pending_tasks()
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, VADUserStoppedSpeakingFrame):
            if self._playback.is_listen_muted():
                await self.push_frame(frame, direction)
                return
            self._cancel_pending_tasks()
            self._commit_task = asyncio.create_task(
                self._commit_user_turn(direction)
            )
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, TranscriptionFrame) and frame.text:
            if self._playback.is_listen_muted():
                await self.push_frame(frame, direction)
                return
            self._merge_transcript(frame.text.strip())
            # Real barge-in: user speech with words while agent talks (after unmute fails)
            if (
                self._playback.agent_playing
                and self._utterance_buffer.strip()
                and not is_likely_echo(
                    self._utterance_buffer, self._playback.last_agent_text
                )
            ):
                await self._interrupt_agent()
            await self.push_frame(frame, direction)
            return

        await self.push_frame(frame, direction)


# ============================================================
# RESPONSE CAPTURE
# ============================================================

class ResponseCapture(FrameProcessor):

    def __init__(self, bridge: STTToLLMBridge, playback: PlaybackState, **kwargs):
        super().__init__(**kwargs)
        self._bridge = bridge
        self._playback = playback
        self._turn_text = ""
        print("✅ ResponseCapture initialized")

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, InterruptionFrame):
            self._turn_text = ""
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, AggregatedTextFrame) and frame.text:
            self._turn_text += frame.text
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, TTSStartedFrame):
            self._playback.on_bot_started_speaking()
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, LLMFullResponseEndFrame):
            full = self._turn_text.strip()
            self._turn_text = ""
            if full:
                print(f"🤖 Priya: {full}")
                self._bridge.add_assistant_message(full, direction)
            await self.push_frame(frame, direction)
            return

        await self.push_frame(frame, direction)
