# scripts/run_all_examples_ui.py
"""Automated UI runner for Antigravity example programs.

Uses Playwright to drive the local web UI (Flask server) and execute the
"Run Analyzer & Repair" pipeline on every *.c and *.py file under
`examples/` (and `held_out/` if present).

For each file the script:
1. Loads the source into the editor.
2. Clicks **Run**, waits for the analysis to finish.
3. If a security‑approval modal appears, clicks **Approve**.
4. Captures the panel output (raw text and tier usage).
5. Clicks **Apply** and records the HTTP status.
6. Retrieves the final editor content.
7. Compiles the code locally with `gcc -Wall -Wextra -std=c11` (warnings
   are allowed, errors are not).
8. Runs the project parser on the final source to ensure it parses.
9. Extracts the six metrics shown in the UI.
10. Writes a row to `results/results.csv` and builds a JSON entry.

The script is resumable – it reads the existing CSV and skips already
processed files. Large files are processed last (sorted by size).

Prerequisites
--------------
* Python 3.10+ with `playwright` installed (`pip install playwright`).
* Run `playwright install` once to download browser binaries.
* The Antigravity Flask server must be running at http://127.0.0.1:5000.
* `gcc` must be available on PATH for compilation.

Usage
-----
```bash
python scripts/run_all_examples_ui.py
```
"""

import asyncio
import csv
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Dict, Any

from playwright.async_api import async_playwright, Page, Browser

# ---------------------------------------------------------------------------
# Configuration (adjust if your UI uses different selectors)
# ---------------------------------------------------------------------------
BASE_URL = "http://127.0.0.1:5000"
EDITOR_SELECTOR = "#editor"  # the textarea / code editor element
RUN_BUTTON_SELECTOR = "button[data-test='run']"
APPLY_BUTTON_SELECTOR = "button[data-test='apply']"
SECURITY_MODAL_SELECTOR = "div.security-modal"
SECURITY_APPROVE_SELECTOR = "button[data-test='security-approve']"
METRICS_PANEL_SELECTOR = "#metrics-panel"
OUTPUT_PANEL_SELECTOR = "#output-panel"

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------
def find_example_files(root: Path) -> List[Path]:
    """Return a list of *.c and *.py files under ``root`` (including held_out)."""
    patterns = ["**/*.c", "**/*.py"]
    files = []
    for pat in patterns:
        files.extend(root.glob(pat))
    # Filter out any non‑file entries (e.g. directories named *.c)
    files = [p for p in files if p.is_file()]
    # Sort by size – small first, large last
    files.sort(key=lambda p: p.stat().st_size)
    return files

async def load_source(page: Page, source: str) -> None:
    """Load ``source`` into the editor.

    The UI currently provides a hidden textarea (``#editor``).  We set its
    value via JavaScript and then trigger the ``input`` event so the
    application recognises the change.
    """
    await page.evaluate(
        """(editorSel, code) => {
            const el = document.querySelector(editorSel);
            if (!el) return;
            el.value = code;
            const ev = new Event('input', { bubbles: true });
            el.dispatchEvent(ev);
        }""",
        EDITOR_SELECTOR,
        source,
    )

async def click_run(page: Page) -> None:
    await page.click(RUN_BUTTON_SELECTOR)

async def wait_for_analysis(page: Page) -> None:
    """Wait until the output panel contains the string 'Coordinated analysis complete'."""
    await page.wait_for_function(
        """selector => {
            const el = document.querySelector(selector);
            return el && el.innerText.includes('Coordinated analysis complete');
        }""",
        OUTPUT_PANEL_SELECTOR,
        timeout=120000,  # 2 minutes – adjust if needed
    )

async def handle_security_modal(page: Page) -> None:
    try:
        await page.wait_for_selector(SECURITY_MODAL_SELECTOR, timeout=5000)
        # Modal appeared – click approve
        await page.click(SECURITY_APPROVE_SELECTOR)
    except Exception:
        # No modal – nothing to do
        pass

async def click_apply(page: Page) -> int:
    # Playwright returns the response status when we intercept the network call.
    # A simple way is to listen for the POST to /api/patch/apply.
    async with page.expect_response("**/api/patch/apply") as resp_info:
        await page.click(APPLY_BUTTON_SELECTOR)
    response = await resp_info.value
    return response.status

async def get_editor_content(page: Page) -> str:
    return await page.evaluate(
        """selector => {
            const el = document.querySelector(selector);
            return el ? el.value : '';
        }""",
        EDITOR_SELECTOR,
    )

def compile_with_gcc(source_path: Path) -> Dict[str, Any]:
    """Compile ``source_path`` with gcc.

    Returns a dict with ``rc``, ``stdout`` and ``stderr``.
    """
    cmd = ["gcc", "-Wall", "-Wextra", "-std=c11", str(source_path), "-o", str(source_path.with_suffix(""))]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return {
        "rc": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }

def run_parser_on_source(source_path: Path) -> Dict[str, Any]:
    """Execute the project's parser on ``source_path``.

    The repository ships a helper module ``compiler.test_parser`` that can be
    invoked as ``python -m compiler.test_parser <file>``.  It prints parsing
    errors to stdout/stderr and exits with ``0`` on success.
    """
    cmd = [sys.executable, "-m", "compiler.test_parser", str(source_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return {
        "rc": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }

async def extract_metrics(page: Page) -> Dict[str, str]:
    """Pull the six metric values from the metrics panel.

    The panel contains labelled ``<div>``s; a simple approach is to query the
    text content and split on new‑lines.  Adjust the selector logic if the UI
    changes.
    """
    raw = await page.inner_text(METRICS_PANEL_SELECTOR)
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    metrics = {}
    for line in lines:
        if ":" in line:
            key, val = line.split(":", 1)
            metrics[key.strip()] = val.strip()
    return metrics

async def process_file(page: Page, file_path: Path) -> Dict[str, Any]:
    # 1. Load source
    with open(file_path, "r", encoding="utf-8") as f:
        source = f.read()
    await load_source(page, source)

    # 2. Run analysis
    await click_run(page)
    await wait_for_analysis(page)
    await handle_security_modal(page)

    # 3. Capture output panel text
    output_text = await page.inner_text(OUTPUT_PANEL_SELECTOR)

    # 4. Apply patch
    apply_status = await click_apply(page)

    # 5. Get final source
    final_source = await get_editor_content(page)
    tmp_path = file_path.with_suffix(".patched.tmp")
    tmp_path.write_text(final_source, encoding="utf-8")

    # 6. Compile with gcc
    gcc_res = compile_with_gcc(tmp_path)

    # 7. Run parser on final source
    parser_res = run_parser_on_source(tmp_path)

    # 8. Extract metrics
    metrics = await extract_metrics(page)

    # 9. Clean up temporary file
    try:
        os.remove(tmp_path)
    except OSError:
        pass

    return {
        "file": str(file_path.relative_to(Path.cwd())),
        "lines": source.count("\n") + 1,
        "expected_class": "unknown",  # placeholder – can be derived later
        "run_output": output_text,
        "apply_http_status": apply_status,
        "gcc_rc": gcc_res["rc"],
        "gcc_stdout": gcc_res["stdout"],
        "gcc_stderr": gcc_res["stderr"],
        "parser_rc": parser_res["rc"],
        "parser_stdout": parser_res["stdout"],
        "parser_stderr": parser_res["stderr"],
        "metrics": metrics,
    }

async def main() -> None:
    root_examples = Path.cwd() / "examples"
    if not root_examples.is_dir():
        print("Examples directory not found – aborting.")
        sys.exit(1)
    files = find_example_files(root_examples)

    results_dir = Path.cwd() / "results"
    results_dir.mkdir(exist_ok=True)
    csv_path = results_dir / "results.csv"
    json_path = results_dir / "results.json"

    # Load already processed entries (if any)
    processed = set()
    if csv_path.exists():
        with open(csv_path, newline="", encoding="utf-8") as csvf:
            reader = csv.DictReader(csvf)
            for row in reader:
                processed.add(row["file"])

    all_json: List[Dict[str, Any]] = []
    if json_path.exists():
        with open(json_path, "r", encoding="utf-8") as jf:
            all_json = json.load(jf)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(BASE_URL)

        # Ensure the UI is ready – wait for editor element
        await page.wait_for_selector(EDITOR_SELECTOR)

        for fp in files:
            rel = str(fp.relative_to(Path.cwd()))
            if rel in processed:
                continue
            print(f"Processing {rel} …")
            result = await process_file(page, fp)
            # Append to CSV
            fieldnames = [
                "file",
                "lines",
                "expected_class",
                "run_output",
                "apply_http_status",
                "gcc_rc",
                "gcc_stdout",
                "gcc_stderr",
                "parser_rc",
                "parser_stdout",
                "parser_stderr",
                "metrics",
            ]
            write_header = not csv_path.exists()
            with open(csv_path, "a", newline="", encoding="utf-8") as csvf:
                writer = csv.DictWriter(csvf, fieldnames=fieldnames)
                if write_header:
                    writer.writeheader()
                # Flatten metrics dict into a JSON string for CSV readability
                row = result.copy()
                row["metrics"] = json.dumps(row["metrics"])
                writer.writerow(row)
            # Append to JSON list and rewrite file
            all_json.append(result)
            with open(json_path, "w", encoding="utf-8") as jf:
                json.dump(all_json, jf, indent=2)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
