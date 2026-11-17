# scripts/verify_sim_examples_playwright.py
import os
import sys
import time
from playwright.sync_api import sync_playwright

SCREENSHOT_PATH = os.path.join(
    os.environ.get("LOCALAPPDATA", "C:\\Users\\rohit\\AppData\\Local"),
    "..",
    ".gemini",
    "antigravity",
    "brain",
    "bfbfbc5a-deb1-4cf9-87d6-8c474fa869e4",
    "sim_examples_verified.png"
)
os.makedirs(os.path.dirname(os.path.abspath(SCREENSHOT_PATH)), exist_ok=True)


def main():
    print("Launching Playwright...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        
        print("Navigating to http://127.0.0.1:5000/...")
        page.goto("http://127.0.0.1:5000/", wait_until="networkidle", timeout=30000)

        # Wait for file-tree items
        page.wait_for_selector("#file-tree .file-item", timeout=10000)

        # Inspect file items
        file_items = page.eval_on_selector_all(
            "#file-tree .file-item",
            "els => els.map(e => e.textContent.trim())"
        )
        print("Top 6 files in UI sidebar:", file_items[:6])

        # Verify the top 4 simulation examples appear first
        expected_top_4 = [
            "00_sim_1_cascading_hallucination.c",
            "00_sim_2_memory_poisoning.c",
            "00_sim_3_identity_compromise.c",
            "00_sim_4_resource_overload.c"
        ]
        for idx, expected_fn in enumerate(expected_top_4):
            assert file_items[idx] == expected_fn, f"Expected {expected_fn} at position {idx}, got {file_items[idx]}!"
        print("CONFIRMED: All 4 C simulation examples appear at the very top of the list in order.")

        # Click on the first simulation example
        print(f"Clicking on {expected_top_4[0]}...")
        page.click(f"#file-tree .file-item:has-text('{expected_top_4[0]}')")
        time.sleep(2)

        # Click the Run button (#btn-run)
        print("Clicking #btn-run...")
        page.click("#btn-run")

        # Wait for the run to complete (results or completed badge)
        print("Waiting for run execution to complete...")
        time.sleep(8)

        # Take full-page screenshot
        page.screenshot(path=SCREENSHOT_PATH, full_page=True)
        print(f"Saved screenshot to: {SCREENSHOT_PATH}")
        browser.close()


if __name__ == "__main__":
    main()
