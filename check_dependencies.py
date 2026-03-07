#!/usr/bin/env python3
"""
Check that extraction dependencies are installed and importable.

- pdfplumber: required for PDF files that have no companion .txt
- langchain_openai: required for LLM fallback when deterministic parsing fails
  (e.g. invoice_1010 if TXT regex didn't match; any incomplete parse)

LangSmithParams ImportError: caused by version mismatch between langchain-core and
langchain-openai. Upgrade both to compatible versions, e.g.:
  pip install -U langchain-core langchain-openai
"""

from __future__ import annotations

import sys
from typing import NamedTuple


class DepCheck(NamedTuple):
    name: str
    ok: bool
    message: str


def check_pdfplumber() -> DepCheck:
    """Check if pdfplumber is installed (needed for PDFs without .txt)."""
    try:
        import pdfplumber
        ver = getattr(pdfplumber, "__version__", "?")
        return DepCheck("pdfplumber", True, f"installed (version {ver})")
    except ImportError as e:
        return DepCheck("pdfplumber", False, f"not installed — {e}")
    except Exception as e:
        return DepCheck("pdfplumber", False, f"import error — {e}")


def check_llm() -> DepCheck:
    """Check if LLM stack (langchain_openai) is importable for fallback extraction."""
    try:
        from langchain_openai import ChatOpenAI
        return DepCheck("langchain_openai", True, "installed (LLM fallback available)")
    except ImportError as e:
        return DepCheck("langchain_openai", False, f"not installed — {e}")
    except Exception as e:
        err = str(e)
        if "LangSmithParams" in err or "langchain_core" in err:
            return DepCheck(
                "langchain_openai",
                False,
                f"version mismatch (e.g. LangSmithParams) — try: pip install -U langchain-core langchain-openai — {e}",
            )
        return DepCheck("langchain_openai", False, f"import error — {e}")


def check_dependencies() -> list[DepCheck]:
    """Run all dependency checks. Returns list of DepCheck results."""
    return [check_pdfplumber(), check_llm()]


def main() -> int:
    print("Checking extraction dependencies...\n")
    results = check_dependencies()
    all_ok = True
    for r in results:
        status = "OK" if r.ok else "FAIL"
        print(f"  [{status}] {r.name}: {r.message}")
        if not r.ok:
            all_ok = False
    print()
    if all_ok:
        print("All dependencies OK.")
        return 0
    print("Some dependencies are missing or broken.")
    print("  - PDF without .txt: install pdfplumber (pip install pdfplumber)")
    print("  - LLM fallback: install langchain-openai; if you see LangSmithParams, upgrade langchain-core and langchain-openai")
    return 1


if __name__ == "__main__":
    sys.exit(main())
