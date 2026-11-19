# SimpleC AI-Assisted Compiler & Security IDE

SimpleC is an intelligent, privacy-first compiler IDE and multi-stage security analysis engine providing automated lexical, syntactic, semantic, and security vulnerability repair for C and Python source code.

---

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Step 1: Install Python Dependencies](#step-1-install-python-dependencies)
3. [Step 2: Install Local AI Model (Ollama)](#step-2-install-local-ai-model-ollama)
4. [Step 3: Run the Application](#step-3-run-the-application)
5. [How to Use the System](#how-to-use-the-system)
6. [Troubleshooting & FAQ](#troubleshooting--faq)
7. [Static Analysis Boundaries & Policies](#static-analysis-boundaries--policies)

---

## Prerequisites

Before starting, ensure the following core tools are installed on your machine and available on your system `PATH`:

| Tool | Minimum Version | Purpose | Installation Guide |
| :--- | :--- | :--- | :--- |
| **Python** | 3.10+ (up to 3.14) | Application runtime | [python.org](https://www.python.org/downloads/) (enable *"Add Python to PATH"*) |
| **GCC** | 9+ | C code compilation & verification | Windows: MinGW-w64 / MSYS2<br>Ubuntu/Debian: `sudo apt install build-essential`<br>macOS: `xcode-select --install` |
| **Java (JRE/JDK)** | 11+ | ANTLR4 syntax parsing runtime | [Adoptium Temurin](https://adoptium.net/) or `winget install EclipseAdoptium.Temurin.17.JRE` |
| **Ollama** | Latest | Local offline AI inference | [ollama.com](https://ollama.com/download) |

---

## Step 1: Install Python Dependencies

Open a terminal in the project directory (where `app.py` and `requirements.txt` are located) and run:

```bash
pip install -r requirements.txt
```

Core dependencies installed:
- `Flask`: Local web IDE backend and API router.
- `antlr4-python3-runtime`: Abstract syntax tree generation and grammar validation.
- `psutil`: Process management, execution limits, and green metrics.
- `pytest`: Automated test verification.

*(Optional)* If running headless browser automated tests:
```bash
pip install playwright
playwright install chromium
```

---

## Step 2: Install Local AI Model (Ollama)

SimpleC uses a local, privacy-first **Qwen2.5-Coder** model for complex, context-aware code repair and security vulnerability remediation. No external API keys or cloud calls are required.

1. **Start Ollama**:
   - Ensure the Ollama application is active in your system tray (or run `ollama serve` in a background terminal).
2. **Download the Recommended Model**:
   ```bash
   ollama pull qwen2.5-coder:3b
   ```
   *(Note: Systems with 8GB+ GPU VRAM can optionally use `qwen2.5-coder:7b`).*
3. **Verify the Model**:
   ```bash
   ollama list
   ```
   Confirm `qwen2.5-coder:3b` appears in the list.

---

## Step 3: Run the Application

### Option A: Web IDE (Recommended & Fastest)

In your terminal, run:

```bash
python app.py
```

The server will initialize and automatically open your default browser to:
👉 **`http://127.0.0.1:5000`**

### Option B: Electron Desktop App (Optional)

If you have Node.js installed and prefer a native desktop window:

```bash
npm install
npm start
```

Or run the packaged executable:
`dist/win-unpacked/SimpleC AI-Assisted Compiler IDE.exe`

---

## How to Use the System

1. **Load or Write Code**:
   - Write or paste C / Python source code into the editor on the left.
   - Or pick any pre-built scenario from the **Examples** menu (e.g. syntax errors, prompt injection tests, memory safety bugs).
2. **Execute Analysis & Automated Repair**:
   - Click the green **Run Program** button.
   - The multi-stage pipeline executes:
     1. **Lexical Analysis**: Token validation and invalid character detection.
     2. **Syntax Parsing**: Full ANTLR4 grammar tree parsing.
     3. **Semantic Analysis**: Symbol resolution, scope auditing, type safety.
     4. **Security & Agent-Security Gate**: Scans for prompt injection attacks, secrets/tokens, memory leaks, and buffer overflows.
     5. **Remediation & Repair Engine**: Applies deterministic rule-based fixes first, escalating to local Qwen2.5-Coder if context repair is needed.
     6. **Green Metrics & Code Quality Scoring**: Computes energy footprint and quality scores.
3. **Security Review Dialog**:
   - If high-risk constructs or adversarial agent instructions are detected, a safety confirmation dialog pops up. Click **Approve** to proceed.
4. **Inspect Results Screen**:
   - The results overlay displays:
     - **4 Core Code Quality Metrics**:
       - *Overall Code Quality %* `[COMBINED]`
       - *Optimal Code %* `[HEURISTIC]`
       - *Poor Code %* `[INVERSE Q]`
       - *Vulnerability Risk %* `[RISK INDEX]`
       *(Featuring synchronized animated vertical gradient bars)*
     - **Active Defects Found**: Categorized breakdown with explanations.
     - **Side-by-Side Diff**: Review proposed repair vs. original code.
   - Click **Apply Patch** to update your editor with the verified fix, or **Reject Patch** to discard.

---

## Troubleshooting & FAQ

- **"Ollama service unavailable"**:
  Ensure Ollama is running (`http://127.0.0.1:11434` should say *"Ollama is running"* in your browser). Run `ollama pull qwen2.5-coder:3b`.
- **"GCC not found"**:
  Verify GCC is installed and on your PATH by running `gcc --version` in a fresh terminal.
- **"Java not found"**:
  Verify Java is installed and on your PATH by running `java -version`.
- **"Port 5000 is in use"**:
  Close any existing `app.py` process, or in PowerShell run:
  `Stop-Process -Id (Get-NetTCPConnection -LocalPort 5000).OwningProcess -Force`
- **Browser does not open automatically**:
  Manually open your browser and go to `http://127.0.0.1:5000`.

---

## Static Analysis Boundaries & Policies

### 1. SEC-01 Integer Overflow: Inter-Statement Dataflow Limitations
- **Current Capability**: The SEC-01 static rule analyzer inspects AST expression trees within declaration initializers and assignment statements. It evaluates constant expressions (e.g., `2147483647 + 1`), detects missing widening casts before promotion (e.g., `(long long)(a + b)`), and catches constant boundary violations.
- **Documented Boundary**: For sequential statements such as:
  ```c
  int x = 2147483647;
  x += 1;
  ```
  The constant evaluator does not maintain an inter-statement abstract interpretation domain across subsequent compound assignment operators (`+=`, `-=`).

### 2. Unsigned Integer Arithmetic & Overflow Policy
- **C Standard Definition**: Per ISO/IEC 9899:1999 (C99) §6.2.5, paragraph 9, unsigned arithmetic does not overflow (it wraps modulo $2^N$).
- **Engine Policy**:
  - Signed integer overflow is undefined behavior (UB) in C: classified as **CONFIRMED / HIGH**.
  - Unsigned modular wraparound is defined behavior, but can cause buffer underflows in boundary checks: classified as **POSSIBLE / MEDIUM**.
