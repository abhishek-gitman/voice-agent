import asyncio
from pipecat.frames.frames import (
    Frame,
    LLMContextFrame,
    LLMFullResponseEndFrame,
    LLMTextFrame,
    TranscriptionFrame,
)
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.frame_processor import (
    FrameDirection,
    FrameProcessor,
)


class STTToLLMBridge(FrameProcessor):
    def __init__(self, system_prompt: str, **kwargs):
        super().__init__(**kwargs)
        self._system_prompt = system_prompt
        self._messages = [
            {"role": "system", "content": system_prompt}
        ]
        self._pending_response = False
        self._buffered_text = ""
        print("✅ STTToLLMBridge initialized")

    def add_assistant_message(self, text: str):
        if text.strip():
            self._messages.append(
                {"role": "assistant", "content": text.strip()}
            )
            self._pending_response = False

            # If fragments were buffered while LLM was busy,
            # add them as the next user message now
            if self._buffered_text.strip():
                buffered = self._buffered_text.strip()
                self._buffered_text = ""
                print(f"📝 Buffered text added: {buffered}")
                self._messages.append(
                    {"role": "user", "content": buffered}
                )

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, TranscriptionFrame) and frame.text:
            user_text = frame.text.strip()
            if not user_text:
                await self.push_frame(frame, direction)
                return

            # If LLM is busy, buffer the text instead of losing it
            if self._pending_response:
                self._buffered_text += " " + user_text
                print(f"📝 Buffered (LLM busy): {user_text}")
                await self.push_frame(frame, direction)
                return

            print(f"\n🎙️  User: {user_text}")

            self._messages.append(
                {"role": "user", "content": user_text}
            )
            self._pending_response = True
            # Wait 1.5 seconds after user stops — feels natural on a call
            await asyncio.sleep(1.5)
            # If user started speaking again during the wait, skip this response
            if not self._pending_response:
                print("⏭️  Response cancelled — user spoke again")
                return

            context = LLMContext(messages=list(self._messages))
            await self.push_frame(
                LLMContextFrame(context=context), direction
            )
        else:
            await self.push_frame(frame, direction)


class ResponseCapture(FrameProcessor):
    def __init__(self, bridge: STTToLLMBridge, **kwargs):
        super().__init__(**kwargs)
        self._bridge = bridge
        self._buffer = ""
        print("✅ ResponseCapture initialized")

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, LLMTextFrame) and frame.text:
            self._buffer += frame.text
            await self.push_frame(frame, direction)

        elif isinstance(frame, LLMFullResponseEndFrame):
            if self._buffer.strip():
                print(f"🤖 Priya: {self._buffer.strip()}")
                self._bridge.add_assistant_message(self._buffer)
            self._buffer = ""
            await self.push_frame(frame, direction)

        else:
            await self.push_frame(frame, direction)