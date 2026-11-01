# Completely Local Model Deployment & Offline Operations Guide

This guide specifies the architecture, hardware memory budget, local model pipeline, escalation hierarchy, and offline setup procedures for the Antigravity compiler assistant.

---

## 1. Architecture & Local-First Security Boundary

Antigravity operates in a **strictly local, offline-first deployment mode**:
* **Zero External Cloud Calls**: Source code, ASTs, compilation errors, and repair candidates are **never** transmitted to external AI providers (such as OpenAI, Anthropic, or external inference APIs).
* **Network Guard**: Internal network assertion `_assert_local_url` blocks any attempt to configure non-loopback endpoints.
* **Frontend Isolation**: The browser frontend interacts exclusively with the local Flask backend at `http://127.0.0.1:5000`. The frontend contains no references, ports, or URLs to underlying model servers.

---

## 2. Target Hardware & Realistic Memory Budget

| Hardware Component | Capacity | Allocation & Strategy |
| :--- | :--- | :--- |
| **GPU (NVIDIA RTX 4050 Laptop)** | **6 GB VRAM** | Dedicated primarily to **Qwen2.5-Coder-Instruct (3B Q4_K_M)** via Ollama (~1.9 GB VRAM). |
| **System Memory (Host RAM)** | **16 GB RAM** | Houses OS, Python runtime, ANTLR parser, and **CodeT5-base** (~450MB fp16 / ~900MB fp32). |
| **Sequential Memory Management** | **Enabled** | CodeT5 and Qwen are not assumed to remain co-resident in GPU memory. When switching between heavy models, `unload_model()` cleans VRAM and host memory using `torch.cuda.empty_cache()` and `gc.collect()`. Ollama models are configured with `keep_alive: "5m"` or `keep_alive: 0`. |
| **Context Window Bounding** | **Bounded** | Context is strictly capped at `num_ctx = 2048` with `temperature = 0.1` to prevent VRAM spikes. |

---

## 3. Model Roles & Escalation Hierarchy

The repair pipeline executes sequentially through three tiers. Escalation occurs only if the preceding tier fails validation:

```
[ Error Detected ]
        │
        ▼
┌───────────────────────────────────────────────┐
│ Tier 1: Deterministic Rules                   │  Latency: 0 - 85 ms
│ (Missing tokens, delimiters, banned APIs)     │  Hallucination: 0%
└──────────────────────┬────────────────────────┘
                       │ (Unresolved)
                       ▼
┌───────────────────────────────────────────────┐
│ Tier 2: CodeT5-base + LoRA Adapters           │  Latency: ~750 ms (CPU)
│ (Token patches, bracket mismatch, undeclared) │  Size: 14 MB LoRA
└──────────────────────┬────────────────────────┘
                       │ (Unresolved)
                       ▼
┌───────────────────────────────────────────────┐
│ Tier 3: Qwen2.5-Coder-Instruct (3B / 7B)      │  Runtime: Local Ollama
│ (Multi-line logic, complex expressions)       │  VRAM: ~1.9 GB (3B)
└───────────────────────────────────────────────┘
```

### Category-Specific Routing Matrix
Based on empirical benchmark results from `tools/benchmark_models.py`:

| Error Category / Family | Tier 1 (Deterministic) | Tier 2 (CodeT5 + LoRA) | Tier 3 (Qwen2.5-Coder) |
| :--- | :--- | :--- | :--- |
| **Missing Semicolon / Comma** | **Primary** (Instant pass) | Secondary fallback | Final fallback |
| **Banned Functions (`gets`, `strcpy`)** | **Primary** (`SecurityAutoFixer`) | Secondary (`codet5_security`) | Final fallback |
| **Undeclared Variable Insertion** | Secondary | **Primary** (`INS_LC <line> <col> int`) | Final fallback |
| **Bracket / Paren Mismatch** | Secondary | **Primary** (`REP_LC <line> <col> ]`) | Final fallback |
| **Multi-line Complex Logic** | N/A | Unsupported | **Primary** (Ollama reasoning) |

---

## 4. Primary Model: CodeT5-base + LoRA Adapters

The existing CodeT5 infrastructure is retained and integrated cleanly:
* **Base Architecture**: `Salesforce/codet5-base` (Encoder-Decoder Seq2Seq LM, 220M parameters).
* **Adapter Locations**:
  * `models/codet5_patch_adapter`: LoRA rank $r=16$, $\alpha=32$, targeting `[q, k, v, o]`. Predicts token patch commands (`INS_LC`, `DEL_LC`, `REP_LC`).
  * `models/codet5_security_adapter`: LoRA rank $r=8$, $\alpha=16$. Specialized in C standard library API sanitization.
  * `models/codet5_semantic_adapter`: LoRA rank $r=8$, $\alpha=16$. Handles `undeclared`, `redeclared`, and `unknown_member`.
* **Inference Interface**: [compiler/local_models.py](file:///c:/Users/rohit/Downloads/Existing%20codes/Existing%20codes/ai/24CSB0A41_Code/Implementation/Implementation/compiler/local_models.py) via `CodeT5Manager.generate_patch(...)`.
* **Unload Interface**: `CodeT5Manager.unload()` frees model memory on demand.

---

## 5. Fallback Model: Qwen2.5-Coder via Local Ollama

Qwen2.5-Coder-Instruct is integrated through Ollama's local HTTP API (`http://127.0.0.1:11434`):
* **Default Model**: `qwen2.5-coder:3b` (4-bit quantized, ~1.9 GB VRAM).
* **Optional Heavy Model**: `qwen2.5-coder:7b` (4-bit quantized, ~4.5 GB VRAM, fits within 6 GB VRAM budget when CodeT5 is offloaded).
* **Client Implementation**: [compiler/local_models.py](file:///c:/Users/rohit/Downloads/Existing%20codes/Existing%20codes/ai/24CSB0A41_Code/Implementation/Implementation/compiler/local_models.py) via `OllamaClient`.
* **VRAM Release**: Calling `OllamaClient.unload_model()` transmits `keep_alive: 0` to Ollama.

---

## 6. Offline Setup & Startup Instructions

### Step 1: Install Ollama (Windows)
1. Download Ollama for Windows from `https://ollama.com/download/windows`.
2. Run the installer (`OllamaSetup.exe`).
3. Verify installation in PowerShell:
   ```powershell
   ollama --version
   ```

### Step 2: Pre-pull the Quantized Model (One-Time while online)
```powershell
ollama pull qwen2.5-coder:3b
```
*(Optional 7B benchmark model):*
```powershell
ollama pull qwen2.5-coder:7b
```

### Step 3: Verify Model Files on Disk
Run the benchmark/health check harness:
```powershell
python tools/benchmark_models.py
```
Expected output:
* `CodeT5 Available : True`
* `Ollama Available : True (http://127.0.0.1:11434)`
* `Configured Model : qwen2.5-coder:3b`

### Step 4: Configure Environment Variables (Optional)
In your PowerShell session or `.env` file:
```powershell
$env:OFFLINE_MODE = "1"
$env:OLLAMA_HOST = "http://127.0.0.1:11434"
$env:OLLAMA_MODEL = "qwen2.5-coder:3b"
$env:TRANSFORMERS_OFFLINE = "1"
$env:HF_HUB_OFFLINE = "1"
```

### Step 5: Start the Local Application
```powershell
python app.py
```
Open `http://127.0.0.1:5000` in your web browser.

---

## 7. Backend Health & Memory Endpoints

The backend provides administrative endpoints for the GUI:
* `GET /api/models/status`: Returns JSON status of local adapters, Ollama connectivity, VRAM, and offline enforcement.
* `POST /api/models/unload`: Immediately unloads CodeT5 and triggers Ollama VRAM release.
