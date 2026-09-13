# ============================================================
# Local voice agent entrypoint (mic + speakers)
# ============================================================

import argparse
import asyncio
from pathlib import Path

from dotenv import load_dotenv
from pipecat.pipeline.runner import PipelineRunner

from agents.runtime_config import DEFAULT_RUNTIME_PATH, load_agent_config, load_prompt_override
from prompts.supervoice_sales_prompt import SUPERVOICE_SALES_PROMPT
from runtime.pipeline_factory import build_task

load_dotenv()


async def main(config_path: Path | None = None):
    path = config_path or DEFAULT_RUNTIME_PATH
    config = load_agent_config(path)
    prompt_override = load_prompt_override(path)
    system_prompt = prompt_override or SUPERVOICE_SALES_PROMPT.system_prompt

    print(f"\n🎤 SuperVoice by Abhishek")
    print(f"🤖 Agent: {config.agent_name}  [{config.agent_id}]")
    print(f"🧠 LLM: {config.model}  |  STT: {config.stt_model}  |  TTS voice: {config.voice}")
    print(f"🌐 Language: {config.language}\n")

    task, session = build_task(config, system_prompt)
    runner = PipelineRunner()
    print("✅ Ready — speak into your microphone\n")

    await runner.run(task)
    session.print_summary()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run SuperVoice local agent")
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_RUNTIME_PATH,
        help="Path to agent_runtime.json",
    )
    args = parser.parse_args()
    asyncio.run(main(args.config))
