#!/usr/bin/env python
"""
Phase 1 Test Runner
====================
Runs all Phase 1 pipeline tests sequentially with clear progress output.

Each test file covers one pipeline stage:
  01 — JD Basic Analysis     (LLM: gemini-2.5-flash)
  02 — Rubric Generation     (LLM: gemini-2.5-flash, 2-pass)
  03 — Resume PDF Parsing    (pdfplumber / Gemini OCR, no LLM in most cases)
  04 — Candidate Extraction  (LLM: gemini-2.5-flash-lite)
  05 — Resume Scoring        (LLM: gemini-2.5-flash-lite + post-processor)

Intermediate output files are saved to:
  tests/phase1/outputs/

Usage:
  python run_phase1_tests.py           # run all
  python run_phase1_tests.py --fast    # skip rubric re-generation in 02 (re-uses cached)
  python run_phase1_tests.py 01 03     # run only tests 01 and 03
"""

import os
import sys
import time
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# ── Load env BEFORE anything else ─────────────────────────────────────────────
load_dotenv(Path(__file__).parent / ".env")

# ── Config ─────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent
TESTS_DIR = ROOT / "tests" / "phase1"
OUTPUTS_DIR = TESTS_DIR / "outputs"

STAGES = [
    ("01", "JD Basic Analysis",    "test_01_jd_basic_analysis.py"),
    ("02", "Rubric Generation",    "test_02_rubric_generation.py"),
    ("03", "Resume PDF Parsing",   "test_03_resume_parsing.py"),
    ("04", "Candidate Extraction", "test_04_candidate_extraction.py"),
    ("05", "Resume Scoring",       "test_05_resume_scoring.py"),
]

BANNER_WIDTH = 65

# ── ANSI colours ───────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"


def banner(text: str, char: str = "="):
    line = char * BANNER_WIDTH
    print(f"\n{BOLD}{BLUE}{line}{RESET}")
    print(f"{BOLD}{BLUE}  {text}{RESET}")
    print(f"{BOLD}{BLUE}{line}{RESET}")


def stage_header(num: str, name: str):
    print(f"\n{BOLD}{CYAN}{'─' * BANNER_WIDTH}{RESET}")
    print(f"{BOLD}{CYAN}  Stage {num}: {name}{RESET}")
    print(f"{BOLD}{CYAN}{'─' * BANNER_WIDTH}{RESET}")


def result_line(label: str, value: str, ok: bool):
    icon  = f"{GREEN}✓{RESET}" if ok else f"{RED}✗{RESET}"
    color = GREEN if ok else RED
    print(f"  {icon}  {label:<30} {color}{value}{RESET}")


def list_outputs():
    """Print all saved intermediate files after the run."""
    if not OUTPUTS_DIR.exists():
        return
    files = sorted(OUTPUTS_DIR.glob("*.json"))
    if not files:
        return
    print(f"\n{BOLD}Intermediate files saved:{RESET}")
    for f in files:
        size_kb = f.stat().st_size / 1024
        print(f"  {DIM}{f.relative_to(ROOT)}{RESET}  ({size_kb:.1f} KB)")


# ── Runner ─────────────────────────────────────────────────────────────────────

def run_stage(num: str, name: str, file: str) -> tuple[bool, float]:
    """Run a single test file with pytest. Returns (passed, elapsed_seconds)."""
    stage_header(num, name)

    test_path = TESTS_DIR / file
    if not test_path.exists():
        print(f"  {RED}[SKIP] {file} not found{RESET}")
        return False, 0.0

    cmd = [
        sys.executable, "-m", "pytest",
        str(test_path),
        "-v",
        "--tb=short",
        "--no-header",
        "-p", "no:warnings",
        "--asyncio-mode=auto",
    ]

    start = time.time()
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=False)
    elapsed = time.time() - start

    passed = proc.returncode == 0
    return passed, elapsed


def main():
    # Parse CLI args: optional stage numbers e.g. "01 03"
    requested = [a for a in sys.argv[1:] if not a.startswith("--")]
    fast_mode = "--fast" in sys.argv

    stages_to_run = [
        s for s in STAGES if (not requested or s[0] in requested)
    ]

    banner(f"DeskZero — Phase 1 Pipeline Tests  ({len(stages_to_run)} stages)")

    print(f"\n  {DIM}Fixtures : tests/fixtures/{RESET}")
    print(f"  {DIM}Outputs  : tests/phase1/outputs/{RESET}")
    if fast_mode:
        print(f"  {YELLOW}--fast mode: LLM calls are real but rubric may be re-used from cache{RESET}")

    OUTPUTS_DIR.mkdir(exist_ok=True)

    summary: list[tuple[str, str, bool, float]] = []
    total_start = time.time()

    for num, name, file in stages_to_run:
        passed, elapsed = run_stage(num, name, file)
        summary.append((num, name, passed, elapsed))

    total_elapsed = time.time() - total_start

    # ── Summary ─────────────────────────────────────────────────────────────────
    banner("Summary")
    all_passed = True
    for num, name, passed, elapsed in summary:
        result_line(f"Stage {num}: {name}", f"{'PASSED' if passed else 'FAILED'}  ({elapsed:.1f}s)", passed)
        if not passed:
            all_passed = False

    print(f"\n  Total time: {total_elapsed:.1f}s")

    list_outputs()

    if all_passed:
        print(f"\n{BOLD}{GREEN}All stages passed.{RESET}\n")
    else:
        failed = [f"Stage {n}" for n, _, ok, _ in summary if not ok]
        print(f"\n{BOLD}{RED}Failed: {', '.join(failed)}{RESET}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
