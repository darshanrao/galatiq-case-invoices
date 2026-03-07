#!/usr/bin/env python3
"""Check that the LLM endpoint (xAI Grok) and API key work."""

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import os

# Load .env so XAI_API_KEY is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def main() -> int:
    key = os.getenv("XAI_API_KEY")
    if not key or not str(key).strip():
        print("XAI_API_KEY is not set. Set it in .env or export XAI_API_KEY=...")
        return 1

    print("Checking LLM endpoint and API key...")
    try:
        from src.ingestion.llm_extract import get_llm
        llm = get_llm()
        response = llm.invoke("Reply with exactly the word OK and nothing else.")
        text = (response.content if hasattr(response, "content") else str(response)).strip()
        if text.upper() == "OK" or "ok" in text.lower():
            print("OK — LLM endpoint and API key are working.")
            return 0
        print(f"Unexpected reply: {text[:200]}")
        return 0  # endpoint responded; key works
    except Exception as e:
        print(f"FAIL — {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
