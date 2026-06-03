# ============================================================
# IMPORTS
# ============================================================

from dataclasses import dataclass, field
from datetime import datetime, timezone


# ============================================================
# MESSAGE
# Represents a single turn in the conversation.
# Speaker is either "user" or "agent".
# ============================================================

@dataclass
class Message:

    # -------------------------
    # Fields
    # -------------------------
    timestamp: str
    speaker: str    # "user" or "agent"
    message: str

    # -------------------------
    # LLM Format Converter
    # Converts to Pipecat 1.3.0 compatible message dict
    # -------------------------
    def to_llm_format(self) -> dict:
        role = "user" if self.speaker == "user" else "model"
        return {
            "role": role,
            "content": self.message,
        }


# ============================================================
# LEAD DATA
# Structured data captured from the conversation.
# Populated by lead extraction logic (Priority 4 — pending).
# ============================================================

@dataclass
class LeadData:

    # -------------------------
    # Fields — all optional until extracted
    # -------------------------
    name: str = ""
    phone: str = ""
    email: str = ""
    city: str = ""
    company: str = ""
    team_size: str = ""
    use_case: str = ""
    budget: str = ""


# ============================================================
# CALL SESSION
# One instance per call. Holds all conversation state.
# Belongs to an organization and agent — PRD aligned.
# ============================================================

@dataclass
class CallSession:

    # -------------------------
    # Identifiers
    # Every session belongs to an org and agent
    # -------------------------
    organization_id: str = "org_default"
    agent_id: str = "agt_default"
    call_id: str = ""

    # -------------------------
    # Timestamps
    # -------------------------
    call_started_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # -------------------------
    # Conversation History
    # Full list of messages in order
    # -------------------------
    messages: list = field(default_factory=list)

    # -------------------------
    # Lead Data
    # Structured info extracted from conversation
    # -------------------------
    lead_data: LeadData = field(default_factory=LeadData)

    # -------------------------
    # Add Message
    # Saves a new message and prints timestamped log line
    # -------------------------
    def add_message(self, speaker: str, text: str):
        msg = Message(
            timestamp=datetime.now(timezone.utc).isoformat(),
            speaker=speaker,
            message=text,
        )
        self.messages.append(msg)
        print(f"[{msg.timestamp}] {speaker.upper()}: {text}")

    # -------------------------
    # Get LLM Messages
    # Formats full conversation history for Pipecat 1.3.0 + Gemini
    # Injects system prompt as first user/model exchange
    # -------------------------
    def get_llm_messages(self, system_prompt: str) -> list:
        msgs = [
            {"role": "user", "content": system_prompt},
            {"role": "model", "content": "Understood."},
        ]
        for m in self.messages:
            msgs.append(m.to_llm_format())
        return msgs

    # -------------------------
    # Print Transcript
    # Clean, readable conversation log
    # -------------------------
    def print_transcript(self):
        print("\n" + "=" * 50)
        print("📝 CALL TRANSCRIPT")
        print("=" * 50)
        for msg in self.messages:
            ts = msg.timestamp[11:19]   # extract HH:MM:SS
            label = "🤖 Agent  " if msg.speaker == "agent" else "👤 Customer"
            print(f"[{ts}] {label}: {msg.message}")
        print("=" * 50)

    # -------------------------
    # Print Summary
    # Call metadata + lead data + full transcript
    # -------------------------
    def print_summary(self):
        print("\n" + "=" * 50)
        print("📋 CALL SUMMARY")
        print(f"Call ID        : {self.call_id}")
        print(f"Organization   : {self.organization_id}")
        print(f"Agent          : {self.agent_id}")
        print(f"Started        : {self.call_started_at}")
        print(f"Messages       : {len(self.messages)}")
        print(f"Lead Data      : {self.lead_data}")
        print("=" * 50)
        self.print_transcript()