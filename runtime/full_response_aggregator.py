# ============================================================
# Buffers an entire LLM reply; yields one TTS chunk on flush.
# ============================================================

from collections.abc import AsyncIterator

from pipecat.utils.text.base_text_aggregator import (
    Aggregation,
    AggregationType,
    BaseTextAggregator,
)


class FullResponseTextAggregator(BaseTextAggregator):
    """Hold all LLM tokens until end-of-response (flush), then speak once."""

    def __init__(self):
        super().__init__(aggregation_type=AggregationType.SENTENCE)
        self._text = ""

    @property
    def text(self) -> Aggregation:
        return Aggregation(text=self._text.strip(), type=AggregationType.SENTENCE)

    async def aggregate(self, text: str) -> AsyncIterator[Aggregation]:
        if text:
            self._text += text
        for _ in ():
            yield Aggregation(text="", type=AggregationType.SENTENCE)

    async def flush(self) -> Aggregation | None:
        stripped = self._text.strip()
        self._text = ""
        if not stripped:
            return None
        return Aggregation(text=stripped, type=AggregationType.SENTENCE)

    async def handle_interruption(self):
        self._text = ""

    async def reset(self):
        self._text = ""
