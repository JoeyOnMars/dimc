#!/usr/bin/env python3
import os
import sys
import time
from pathlib import Path

# Add src to path
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

try:
    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env")
except ImportError:
    pass

from dimcause.extractors.llm_client import create_llm_client  # noqa: E402
from dimcause.utils.cost_tracker import get_tracker  # noqa: E402


def main():
    print("🦈 DeepSeek Integration Verifier")
    print("================================")

    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("❌ DEEPSEEK_API_KEY not found in environment or .env")
        print("Please set it via: export DEEPSEEK_API_KEY='sk-...'")
        sys.exit(1)

    print(f"✅ Key detected: {api_key[:4]}...{api_key[-4:]}")

    client = create_llm_client(
        provider="deepseek",
        model="deepseek-chat",
        api_key=api_key,
        base_url="https://api.deepseek.com/v1",  # Optional, usually auto-detected by litellm
    )

    print("\n⏳ Sending request to DeepSeek-V3...")
    start_time = time.time()

    try:
        response = client.complete("Explain 'Agentic Coding' in one short sentence.")
        duration = time.time() - start_time

        print(f"\n✅ Response ({duration:.2f}s):")
        print(f'   "{response}"')

        stats = get_tracker().get_session_stats()
        print("\n💰 Cost Stats:")
        print(f"   Input Tokens:  {stats['input_tokens']}")
        print(f"   Output Tokens: {stats['output_tokens']}")
        print(f"   Total Cost:    ${stats['total_cost_usd']:.6f}")

    except Exception as e:
        print(f"\n❌ Request failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
