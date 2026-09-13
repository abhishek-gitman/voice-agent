# SuperVoice — Voice Agent (local demo)

Configurable voice agent demo for **SuperVoice**: Pipecat pipeline with **Deepgram** (STT/TTS), **Google Gemini** (LLM), and **Priya** sales persona. Includes a **browser Studio** to configure and run test calls on a Mac (mic + speakers).

**Repository:** [github.com/abhishek-gitman/voice-agent](https://github.com/abhishek-gitman/voice-agent)

Product requirements and roadmap live in [`docs/PRD-V1.md`](docs/PRD-V1.md).

---

## Prerequisites (Mac)

- macOS with microphone and speakers (or headphones; loudspeaker mode uses echo guard)
- Python 3.12+
- [Homebrew](https://brew.sh/) (for PortAudio): `brew install portaudio`
- API keys:
  - [Deepgram](https://console.deepgram.com/) — STT + TTS
  - [Google AI / Gemini](https://aistudio.google.com/apikey) — LLM

---

## First-time setup

```bash
git clone https://github.com/abhishek-gitman/voice-agent.git
cd voice-agent
```

Create a `.env` file in the project root (never commit this file):

```env
DEEPGRAM_API_KEY=your_deepgram_key
GEMINI_API_KEY=your_gemini_key
```

Install Python dependencies and local audio support:

```bash
chmod +x run.sh run_studio.sh
./run.sh
```

The first run creates `.venv`, installs packages (including PyAudio), and starts the agent. Press **Ctrl+C** to stop. You only need this once to bootstrap the environment (or if Setup in Studio reports a missing venv).

---

## Daily use — SuperVoice Studio (recommended)

Start the dashboard:

```bash
./run_studio.sh
```

Opens **http://127.0.0.1:8765** in your browser.

| Tab | Purpose |
|-----|---------|
| **Control** | Start / stop / restart test call; save settings |
| **Setup** | Checklist (`.env`, venv, PyAudio) — fix before first Start |
| **Settings** | LLM, STT, TTS voice, VAD, turn-taking, speaker echo guard |
| **Prompt** | System prompt (empty = default Priya prompt in code) |
| **Session** | Live transcript + technical logs |

**Typical flow:** Setup (all green) → Settings / Prompt → **Save settings** → **Start test call** → allow microphone → **Stop** when done.

Stopping Studio with **Ctrl+C** closes only the UI. Use **Stop** in the Control tab to end the voice agent.

---

## Terminal-only (no browser)

```bash
./run.sh
```

Uses settings from [`config/agent_runtime.json`](config/agent_runtime.json). Stop with **Ctrl+C**.

---

## How configuration works

| File | Role |
|------|------|
| [`config/agent_runtime.json`](config/agent_runtime.json) | Saved settings from Studio (models, VAD, delays, prompt override) |
| [`agents/configs/priya_agent.py`](agents/configs/priya_agent.py) | Code defaults when JSON omits a field |
| `.env` | API keys only (local, gitignored) |

After changing settings in Studio, click **Save**. If a call is already running, use **Restart with saved settings** on the Control tab.

---

## Project layout

```
voice-agent/
├── run_studio.sh          # Start web UI
├── run.sh                 # Start voice agent in terminal
├── config/
│   └── agent_runtime.json # UI-managed runtime config
├── studio/                # FastAPI + dashboard static files
├── runtime/
│   ├── bot.py             # Agent entrypoint
│   ├── pipeline_factory.py
│   ├── context_bridge.py  # Turn-taking STT → LLM
│   ├── speakerphone_guard.py
│   └── playback_state.py
├── agents/                # Agent config + runtime loader
├── prompts/               # Priya system prompt (default)
└── docs/                  # PRD and product docs
```

---

## Voice pipeline (high level)

```text
Microphone → VAD → Deepgram STT → (turn logic) → Gemini → Deepgram TTS → Speakers
```

While the agent is speaking, **half-duplex** listening reduces loudspeaker echo on Mac. Real phone deployments will use telephony + platform AEC; this local demo is tuned for product iteration.

---

## Troubleshooting

| Issue | What to try |
|-------|-------------|
| Studio Setup fails on venv | Run `./run.sh` once |
| `No module named 'pyaudio'` | `brew install portaudio` then `.venv/bin/pip install 'pipecat-ai[local]==1.3.0'` |
| Deepgram STT 400 on connect | Use `stt_model: nova-2-general` in Settings; avoid invalid STT flag combos |
| Agent cuts off on speaker | Increase **Speaker echo guard tail** in Settings; prefer headphones for testing |
| Changes not applied | Save settings, then **Restart** the agent |

---

## Git workflow

```bash
git pull origin main
# edit, test via Studio
git add .
git commit -m "Describe your change"
git push origin main
```

Do **not** commit `.env` or `.venv/`.

---

## License / status

Internal SuperVoice demo. Not production telephony yet — see PRD for wallet, inbound/outbound, and Knowlarity/Plivo roadmap.
