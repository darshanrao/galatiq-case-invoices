#!/usr/bin/env python3
"""Batch extract all invoices to canonical JSON and log failures."""

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

import argparse
import json
import logging
from pathlib import Path

from src.ingestion.service import ingest_invoice, to_canonical_dict, get_missing_critical_fields
from src.core.exceptions import IngestionError, LLMConfigurationError, VisionConfigurationError

# Invoice files to process
INVOICE_DIR = Path(__file__).resolve().parent.parent / "data" / "invoices"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "normalized"
FAILURE_LOG = Path(__file__).resolve().parent.parent / "extraction_failures.log"
WARNINGS_LOG = Path(__file__).resolve().parent.parent / "extraction_warnings.log"

# Setup file logger for failures
_file_handler: logging.FileHandler | None = None
_warnings_handler: logging.FileHandler | None = None


def _ensure_failure_log_handler(append: bool = True) -> None:
    global _file_handler
    if _file_handler is None:
        mode = "a" if append else "w"
        _file_handler = logging.FileHandler(FAILURE_LOG, mode=mode, encoding="utf-8")
        _file_handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
        )
        logger = logging.getLogger("extraction_failures")
        logger.addHandler(_file_handler)
        logger.setLevel(logging.INFO)


def log_failure(path: str | Path, error: BaseException) -> None:
    _ensure_failure_log_handler()
    logger = logging.getLogger("extraction_failures")
    logger.info(
        "path=%s | type=%s | message=%s",
        path,
        type(error).__name__,
        str(error).replace("\n", " "),
    )


def _ensure_warnings_log_handler(append: bool = True) -> None:
    global _warnings_handler
    if _warnings_handler is None:
        mode = "a" if append else "w"
        _warnings_handler = logging.FileHandler(WARNINGS_LOG, mode=mode, encoding="utf-8")
        _warnings_handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
        )
        logger = logging.getLogger("extraction_warnings")
        logger.addHandler(_warnings_handler)
        logger.setLevel(logging.INFO)


def log_missing_critical(path: str | Path, invoice_number: str, missing: list[str]) -> None:
    _ensure_warnings_log_handler()
    logger = logging.getLogger("extraction_warnings")
    logger.info(
        "path=%s | invoice_number=%s | missing_critical=%s",
        path,
        invoice_number or "(none)",
        ", ".join(missing),
    )


def get_invoice_files(invoice_dir: Path) -> list[Path]:
    """Return invoice file paths."""
    files: list[Path] = []
    for p in sorted(invoice_dir.iterdir()):
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        if ext not in (".json", ".csv", ".xml", ".txt", ".pdf", ".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".webp"):
            continue
        files.append(p)
    return files


def run(invoice_dir: Path | None = None, output_dir: Path | None = None, skip_dependency_check: bool = False) -> None:
    invoice_dir = invoice_dir or INVOICE_DIR
    output_dir = output_dir or OUTPUT_DIR

    if not invoice_dir.exists():
        print(f"ERROR: Invoice directory not found: {invoice_dir}")
        sys.exit(1)

    if not skip_dependency_check:
        from scripts.check_dependencies import check_dependencies
        results = check_dependencies()
        failed = [r for r in results if not r.ok]
        if failed:
            print("Dependency check failed (use --skip-deps to run anyway):")
            for r in failed:
                print(f"  [{r.name}] {r.message}")
            print("\nRun: python scripts/check_dependencies.py")
            sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)
    files = get_invoice_files(invoice_dir)
    print(f"Processing {len(files)} invoice files from {invoice_dir}")
    print(f"Output: {output_dir}")

    _ensure_failure_log_handler(append=False)
    _ensure_warnings_log_handler(append=False)

    success_count = 0
    failure_count = 0
    warning_count = 0

    for fp in files:
        try:
            bundle = ingest_invoice(fp)
        except FileNotFoundError as e:
            failure_count += 1
            log_failure(fp, e)
            print(f"  FAIL {fp.name}: {e}")
            continue
        except IngestionError as e:
            failure_count += 1
            log_failure(fp, e)
            print(f"  FAIL {fp.name}: Could not extract complete invoice - {e}")
            continue
        except (LLMConfigurationError, VisionConfigurationError) as e:
            failure_count += 1
            log_failure(fp, e)
            print(f"  FAIL {fp.name}: {e}")
            continue
        except Exception as e:
            failure_count += 1
            log_failure(fp, e)
            print(f"  FAIL {fp.name}: {type(e).__name__} - {e}")
            continue

        canonical = to_canonical_dict(bundle)
        output_path = output_dir / f"{fp.stem}.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(canonical, f, indent=2)

        success_count += 1
        missing = get_missing_critical_fields(bundle)
        if missing:
            warning_count += 1
            log_missing_critical(fp, bundle.invoice.invoice_number, missing)
            print(f"  WARN {fp.name} -> {output_path.name} ({bundle.invoice.invoice_number}) | missing: {', '.join(missing)}")
        else:
            print(f"  OK   {fp.name} -> {output_path.name} ({bundle.invoice.invoice_number})")

    print(f"\nWrote {success_count} canonical JSON files to {output_dir}")
    if failure_count:
        print(f"Failures: {failure_count} (logged to {FAILURE_LOG})")
    if warning_count:
        print(f"Warnings (missing critical fields): {warning_count} (logged to {WARNINGS_LOG})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch extract invoices to canonical JSON")
    parser.add_argument(
        "--invoice_dir",
        default=str(INVOICE_DIR),
        help="Directory containing invoice files",
    )
    parser.add_argument(
        "--output",
        default=str(OUTPUT_DIR),
        help="Output directory for canonical JSON files",
    )
    parser.add_argument(
        "--skip-deps",
        action="store_true",
        help="Skip dependency check (pdfplumber, langchain for LLM fallback)",
    )
    args = parser.parse_args()
    run(
        invoice_dir=Path(args.invoice_dir),
        output_dir=Path(args.output),
        skip_dependency_check=args.skip_deps,
    )


if __name__ == "__main__":
    main()
