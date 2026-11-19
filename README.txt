================================================================================
           SimpleC AI-Assisted Compiler & Security IDE
================================================================================

Welcome to SimpleC! This guide walks you through setting up and running the
entire system from scratch on a new machine.


--------------------------------------------------------------------------------
TABLE OF CONTENTS
--------------------------------------------------------------------------------
1. System Requirements & Prerequisites
2. Step 1: Install Python Dependencies
3. Step 2: Install and Set Up the Local AI Model (Ollama)
4. Step 3: Run the Application
5. How to Use the System (Quick Tour)
6. Troubleshooting & Common Issues


================================================================================
1. SYSTEM REQUIREMENTS & PREREQUISITES
================================================================================

Ensure you have the following tools installed and available on your PATH:

1. Python 3.10, 3.11, 3.12, 3.13, or 3.14
   - Download: https://www.python.org/downloads/
   - Note: On Windows, check "Add Python to PATH" during installation.
   - Verify in terminal:
       python --version

2. GCC (GNU Compiler Collection)
   - Required for native C compilation and verification.
   - Windows: Install MinGW-w64 (via MSYS2, WinLibs, or `winget install -e --id MSYS2.MSYS2`)
   - Linux (Ubuntu/Debian):
       sudo apt update && sudo apt install build-essential
   - macOS:
       xcode-select --install
   - Verify in terminal:
       gcc --version

3. Java Runtime (JRE / JDK 11 or higher)
   - Required for the ANTLR4 syntax parsing runtime.
   - Windows: Download from https://adoptium.net/ or via winget:
       winget install EclipseAdoptium.Temurin.17.JRE
   - Linux:
       sudo apt install default-jre
   - macOS:
       brew install openjdk
   - Verify in terminal:
       java -version

4. Ollama (Local AI Model Runner)
   - Runs local neural code repair models completely offline and securely.
   - Download and install from: https://ollama.com/download
   - Verify in terminal:
       ollama --version


================================================================================
2. STEP 1: INSTALL PYTHON DEPENDENCIES
================================================================================

Open a terminal (PowerShell, Command Prompt, or bash) in the extracted project
folder (where app.py and requirements.txt are located), and run:

    pip install -r requirements.txt

Core packages installed:
  - Flask (Web interface server)
  - antlr4-python3-runtime (Syntax tree parsing)
  - psutil (System metrics & process management)
  - pytest (Automated verification)

Optional (only needed if you plan to run automated browser test suites):
    pip install playwright
    playwright install chromium


================================================================================
3. STEP 2: INSTALL AND SET UP THE LOCAL AI MODEL (OLLAMA)
================================================================================

SimpleC uses a local, privacy-first Qwen2.5-Coder model for intelligent code
repair and security remediation. No API keys or cloud connections are required.

1. Ensure Ollama is running:
   - On Windows/macOS: Make sure the Ollama application is launched and running
     in your system tray.
   - On Linux: Run `ollama serve` in a background terminal.

2. Pull the recommended model:
   Open a terminal and run:

       ollama pull qwen2.5-coder:3b

   (Note: If you have a dedicated GPU with 8GB+ VRAM, you can optionally pull
   `qwen2.5-coder:7b` instead. The system automatically detects and uses it.)

3. Verify the model is ready:
   Run:
       ollama list
   You should see `qwen2.5-coder:3b` listed.


================================================================================
4. STEP 3: RUN THE APPLICATION
================================================================================

You can run SimpleC either as a Web IDE in your browser (quickest) or as an
Electron desktop application.

--- METHOD A: WEB IDE (RECOMMENDED & FASTEST) ---

1. In the project root directory, run:

       python app.py

2. Your default web browser will automatically open to:
       http://127.0.0.1:5000

   If it doesn't open automatically, simply open your browser and navigate to
   http://127.0.0.1:5000.

--- METHOD B: ELECTRON DESKTOP APP (OPTIONAL) ---

If you have Node.js installed and wish to run the native desktop shell:
1. Run:
       npm install
       npm start

2. Or if running from a prebuilt package:
   Double-click `dist/win-unpacked/SimpleC AI-Assisted Compiler IDE.exe`.


================================================================================
5. HOW TO USE THE SYSTEM (QUICK TOUR)
================================================================================

1. Loading or Writing Code:
   - Use the code editor on the left to write or paste C or Python source code.
   - Or click the "Examples" dropdown at the top to load pre-configured test
     cases (e.g., syntax errors, security vulnerabilities, or agent attacks).

2. Running Analysis & Automated Repair:
   - Click the green "Run Program" button.
   - The tiered compilation pipeline executes automatically:
       [1] Lexical Analysis   -> Scans tokens & invalid characters.
       [2] Syntax Parsing     -> Parses grammar AST via ANTLR4.
       [3] Semantic Analysis  -> Checks types, variable scopes & symbols.
       [4] Security Gate      -> Detects buffer overflows, prompt injection,
                                 leaked credentials, and exploits.
       [5] Repair Engine      -> Proposes verified fixes (deterministic rules
                                 first, escalates to local Qwen when needed).
       [6] Green Metrics      -> Measures execution efficiency and score.

3. Security Review Gate:
   - If the code contains high-risk operations, adversarial comments, or
     credentials, a "Security Review" dialog appears for safety.
   - Click "Approve" to permit the pipeline to proceed with execution/repair.

4. Results & Proposed Repair Screen:
   - When analysis completes, the Results Screen opens displaying:
       * 4 Core Code Quality Metrics:
           - Overall Code Quality % [COMBINED]
           - Optimal Code % [HEURISTIC]
           - Poor Code % [INVERSE Q]
           - Vulnerability Risk % [RISK INDEX]
         (with color-coded vertical animated indicator bars)
       * Active Defects Found with detailed descriptions & line numbers.
       * Side-by-side Diff showing original code vs. proposed safe repair.
   - Click "Apply Patch" to insert the verified fix back into the editor,
     or "Reject Patch" to keep the original code.


================================================================================
6. TROUBLESHOOTING & COMMON ISSUES
================================================================================

Problem: "Ollama service unavailable" or AI repairs not generating.
Solution:
  - Check that Ollama is running: open http://127.0.0.1:11434 in your browser.
    It should say "Ollama is running".
  - Verify you pulled the model by running `ollama list` in terminal.
  - Pull the model if missing: `ollama pull qwen2.5-coder:3b`.

Problem: "GCC not found" or compilation step fails.
Solution:
  - Make sure `gcc` is installed and added to your system environment PATH.
  - Test by opening a new terminal and typing `gcc --version`.

Problem: "Java runtime not detected" or syntax parser errors.
Solution:
  - Install Java (JRE/JDK 11+) and ensure `java` is in your PATH.
  - Test with `java -version`.

Problem: Port 5000 is already in use.
Solution:
  - Check if another instance of app.py is running and close it.
  - On Windows, you can free port 5000 in PowerShell:
      Stop-Process -Id (Get-NetTCPConnection -LocalPort 5000).OwningProcess -Force

Problem: Browser doesn't open automatically.
Solution:
  - Manually visit http://127.0.0.1:5000 in Chrome, Firefox, Edge, or Brave.


================================================================================
For further architecture documentation, see: docs/ARCHITECTURE.md
================================================================================
