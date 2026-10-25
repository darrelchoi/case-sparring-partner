"""Problem 1: prove one gpt-6-luna call works and print its token usage.

    python scripts/hello.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic_ai import Agent

from app.llm import build_model, settings
from app.usage import record


async def main() -> None:
    agent = Agent(build_model(), instructions="You are a terse consulting case interviewer.", model_settings=settings("hello"))
    result = await agent.run("In one sentence, what do you look for in a candidate's case structure?")
    print("Reply:", result.output)
    u = record(result, agent="hello", session_id="hello")
    print(f"Tokens: input {u['input_tokens']} | cached input {u['cache_read_tokens']} | output {u['output_tokens']} | cost ${u['cost_usd']:.6f}")


if __name__ == "__main__":
    asyncio.run(main())
