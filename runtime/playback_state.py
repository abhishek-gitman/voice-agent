# ============================================================
# Shared state: speakerphone / half-duplex listen control
# ============================================================

import time
from dataclasses import dataclass, field


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def is_likely_echo(user_text: str, agent_text: str) -> bool:
    """Reject STT that is mostly the agent's own voice from the loudspeaker."""
    if not user_text or not agent_text:
        return False
    u = _normalize(user_text)
    a = _normalize(agent_text)
    if len(u) < 4:
        return False
    if u in a or a in u:
        return True
    u_words = u.split()
    a_words = set(a.split())
    if not u_words:
        return False
    overlap = sum(1 for w in u_words if w in a_words) / len(u_words)
    return overlap >= 0.55


@dataclass
class PlaybackState:
    """Mute inbound audio processing while the bot plays (speaker echo guard)."""

    echo_tail_secs: float = 0.5
    agent_playing: bool = False
    last_agent_text: str = ""
    _cooldown_until: float = field(default=0.0, repr=False)
    _pending_user_turn: str = ""

    def on_bot_started_speaking(self) -> None:
        self.agent_playing = True

    def on_bot_stopped_speaking(self) -> None:
        self.agent_playing = False
        self._cooldown_until = time.monotonic() + self.echo_tail_secs

    def set_last_agent_text(self, text: str) -> None:
        self.last_agent_text = text.strip()

    def is_listen_muted(self) -> bool:
        if self.agent_playing:
            return True
        return time.monotonic() < self._cooldown_until

    def queue_user_turn(self, text: str) -> None:
        self._pending_user_turn = (
            f"{self._pending_user_turn} {text}".strip()
            if self._pending_user_turn
            else text.strip()
        )

    def pop_pending_user_turn(self) -> str | None:
        if not self._pending_user_turn:
            return None
        text = self._pending_user_turn.strip()
        self._pending_user_turn = ""
        return text or None
