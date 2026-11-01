# Manual QA Checklist for Multi-Language IDE UI

Please run through these steps in a web browser:

1. **Start application**: Run `python app.py`. The page loads in C mode (or the previously saved language from `localStorage`).
2. **C Mode File List**: Verify that the file tree under "C Examples" displays only `.c` files and no `.py` files.
3. **Switch to Python**: Click the **Python** button in the segmented language switch control:
   - File list refreshes and shows only `.py` files under "Python Examples".
   - The tab strip switches to show only Python tabs (e.g. `main.py`).
   - The editor syntax highlighting switches to Python.
   - The subtitle displays "Python mode".
   - The new file button text changes to "+ New Python Program".
4. **Repair Python File**: Open `python/syntax/s01_missing_colon.py` from the file explorer and click **Run Repair** (or Ctrl+Enter):
   - The missing colon is automatically added to line 2 (`if x > 3:`).
   - Status badge shows `SUCCESS`.
5. **New Python Files**: Click **+ New Python Program** twice:
   - `untitled1.py` and `untitled2.py` are created and opened in tabs.
   - They appear under the "My files (unsaved)" section in the sidebar.
   - They contain the Python starter template (`def main(): ...`).
6. **Workspace Preservation**: Type some custom text in `untitled1.py`. Switch to **C** mode, then switch back to **Python** mode:
   - Verify that your custom text in `untitled1.py` is still preserved.
7. **C Mode New File**: In C mode, verify that the new file button reads "+ New C Program". Click it:
   - `untitled1.c` is created with the C starter template (`int main() { ... }`).
8. **Language Persistence**: Reload the browser page:
   - Verify that the last active language is restored automatically.
9. **C Mode Repair**: Open any broken C example (e.g., `missing_semi.c`) in C mode and click **Run Repair**:
   - Verify that repair behavior, green report, and diagnostics operate exactly as before.
10. **Path Traversal Protection**: In your browser, navigate to:
    `http://127.0.0.1:5000/api/example/..%2Fapp.py`
    - Verify that it returns HTTP 404 with an error JSON.
