# ============================================================
# IMPORTS
# ============================================================

import asyncio
from pipecat.frames.frames import (
    Frame,
    InterruptionFrame,
    LLMContextFrame,
    LLMFullResponseEndFrame,
    LLMTextFrame,
    TranscriptionFrame,
)
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from runtime.session import CallSession


# ============================================================
# STT TO LLM BRIDGE
# Converts final STT transcriptions into LLMContextFrame.
# Maintains conversation history via CallSession.
# Handles delayed responses, cancellation, and text buffering.
# ============================================================

class STTToLLMBridge(FrameProcessor):

    # -------------------------
    # Initialization
    # -------------------------
    def __init__(self, session: CallSession, system_prompt: str, **kwargs):
        super().__init__(**kwargs)
        self._session = session
        self._system_prompt = system_prompt
        self._pending_response = False
        self._buffered_text = ""
        self._response_task = None  # tracks the current delayed response task
        print("✅ STTToLLMBridge initialized")

    # -------------------------
    # Save Assistant Message
    # Called by ResponseCapture after LLM finishes responding.
    # Clears any stale buffer — does NOT trigger new LLM call.
    # -------------------------
    def add_assistant_message(self, text: str, direction=None):
        if text.strip():
            self._session.add_message("agent", text.strip())
            self._pending_response = False

            # Clear any stale buffer after agent responds
            if self._buffered_text.strip():
                print(f"🗑️  Cleared stale buffer: {self._buffered_text.strip()}")
                self._buffered_text = ""

    # -------------------------
    # Delayed LLM Response
    # Waits before responding — cancellable if user speaks again.
    # Smart delay based on punctuation at end of sentence.
    # -------------------------
    async def _delayed_response(self, user_text: str, direction: FrameDirection):
        try:
            last_char = user_text.rstrip()[-1] if user_text.rstrip() else ""

            if last_char in ".?!":
                wait = 1.0   # sentence complete — respond faster
            elif last_char in ",":
                wait = 2.5   # mid-sentence — wait longer
            else:
                wait = 1.8   # default

            await asyncio.sleep(wait)

            # Cancel any queued TTS before new response
            await self.push_frame(InterruptionFrame(), direction)

            # Send full conversation history to LLM
            context = LLMContext(
                messages=self._session.get_llm_messages(self._system_prompt)
            )
            await self.push_frame(LLMContextFrame(context=context), direction)

        except asyncio.CancelledError:
            print("⏭️  Response cancelled — user spoke again")
            self._pending_response = False

    # -------------------------
    # Frame Processing
    # Core logic — handles each incoming TranscriptionFrame from STT
    # -------------------------
    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, TranscriptionFrame) and frame.text:
            user_text = frame.text.strip()

            # Skip empty frames
            if not user_text:
                await self.push_frame(frame, direction)
                return

            # -------------------------
            # Filler Word Filter (disabled — smart delay handles this now)
            # Uncomment to re-enable hard filtering in future
            # -------------------------
            # filler_words = {
            #     "so", "yeah", "mhmm", "uh-huh", "and",
            #     "um", "uh", "hmm", "so basically", "like",
            #     "uh huh", "mm", "mmm"
            # }
            # if user_text.lower().rstrip(".,!?") in filler_words:
            #     print(f"🔇 Ignored filler: {user_text}")
            #     return

            # -------------------------
            # Cancel any pending delayed response (user still speaking)
            # -------------------------
            if self._response_task and not self._response_task.done():
                self._response_task.cancel()
                print(f"🛑 Cancelled pending response — user still speaking")

            # -------------------------
            # Buffer text if LLM is currently processing a response
            # -------------------------
            if self._pending_response:
                self._buffered_text += " " + user_text
                print(f"📝 Buffered (LLM busy): {user_text}")
                await self.push_frame(frame, direction)
                return

            # -------------------------
            # Merge buffered fragments with current text into one message
            # Prevents garbage fragments from polluting the context
            # -------------------------
            if self._buffered_text.strip():
                full_text = (self._buffered_text.strip() + " " + user_text).strip()
                self._buffered_text = ""
                print(f"\n🎙️  User: {full_text}")
                self._session.add_message("user", full_text)
            else:
                # -------------------------
                # No buffer — add current text directly to session
                # -------------------------
                print(f"\n🎙️  User: {user_text}")
                self._session.add_message("user", user_text)

            self._pending_response = True
            self._response_task = asyncio.create_task(
                self._delayed_response(user_text, direction)
            )

        else:
            await self.push_frame(frame, direction)


# ============================================================
# RESPONSE CAPTURE
# Sits after LLM aggregator in pipeline.
# Accumulates LLM text chunks and saves completed replies.
# No silence filter — prompt handles conversation quality.
# ============================================================

class ResponseCapture(FrameProcessor):

    # -------------------------
    # Initialization
    # -------------------------
    def __init__(self, bridge: STTToLLMBridge, **kwargs):
        super().__init__(**kwargs)
        self._bridge = bridge
        self._buffer = ""
        print("✅ ResponseCapture initialized")

    # -------------------------
    # Frame Processing
    # Pushes LLM chunks to TTS immediately, saves on completion
    # -------------------------
    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        # -------------------------
        # Accumulate LLM text chunks — push to TTS immediately
        # -------------------------
        if isinstance(frame, LLMTextFrame) and frame.text:
            self._buffer += frame.text
            await self.push_frame(frame, direction)

        # -------------------------
        # LLM finished — save full reply to session via bridge
        # -------------------------
        elif isinstance(frame, LLMFullResponseEndFrame):
            if self._buffer.strip():
                print(f"🤖 Priya: {self._buffer.strip()}")
                self._bridge.add_assistant_message(self._buffer, direction)
            self._buffer = ""
            await self.push_frame(frame, direction)

        else:
            await self.push_frame(frame, direction)