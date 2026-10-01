let editor;
let currentDecorations = [];
let suppressHighlightClearOnce = false;

const openFiles = {};
let openTabs = [];
let currentFilename = "main.c";
let repairOriginalCode = null;
let allExampleFiles = [];
let selectedTemplateKey = "basic";

const TEMPLATES = {
    basic: `int main() {\n    int a = 10;\n    int b = 20;\n    return a + b;\n}\n`,
    pointer: `int main() {\n    int value = 7;\n    int *pointer = &value;\n    int result = *pointer;\n    return result;\n}\n`,
    bitwise: `int main() {\n    int a = 5;\n    int b = 3;\n    int r1 = a & b;\n    int r2 = a | b;\n    int r3 = a ^ b;\n    int r4 = ~a;\n    int r5 = a << 1;\n    int r6 = a >> 1;\n    return r1 + r2 + r3 + r4 + r5 + r6;\n}\n`,
    function: `int add(int a, int b);\n\nint add(int a, int b) {\n    return a + b;\n}\n\nint main() {\n    int res = add(10, 20);\n    return res;\n}\n`,
    empty: `int main() {\n    return 0;\n}\n`
};

require.config({
    paths: {
        vs: "https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.44.0/min/vs"
    }
});

require(["vs/editor/editor.main"], function () {
    // Define custom dark theme matching the IDE
    monaco.editor.defineTheme("simplec-dark", {
        base: "vs-dark",
        inherit: true,
        rules: [
            { token: "keyword", foreground: "ff7b72", fontStyle: "bold" },
            { token: "type", foreground: "79c0ff" },
            { token: "number", foreground: "a5d6ff" },
            { token: "comment", foreground: "8b949e", fontStyle: "italic" },
            { token: "string", foreground: "a5d6ff" }
        ],
        colors: {
            "editor.background": "#0d1117",
            "editor.foreground": "#e6edf3",
            "editorLineNumber.foreground": "#6e7681",
            "editorLineNumber.activeForeground": "#f0f6fc",
            "editor.selectionBackground": "#264f78",
            "editor.inactiveSelectionBackground": "#1f3b5c",
            "editorCursor.foreground": "#58a6ff",
            "editorGutter.background": "#0d1117"
        }
    });

    editor = monaco.editor.create(document.getElementById("editor"), {
        value: `int main() {\n    int a = 10\n    return 0;\n}`,
        language: "c",
        theme: "simplec-dark",
        automaticLayout: true,
        minimap: { enabled: false },
        fontSize: 14,
        fontFamily: "'JetBrains Mono', Consolas, monospace",
        lineNumbers: "on",
        roundedSelection: false,
        scrollBeyondLastLine: false,
        glyphMargin: true
    });

    openFiles["main.c"] = editor.getValue();
    openTabs = ["main.c"];
    currentFilename = "main.c";
    renderTabs();

    editor.onDidChangeModelContent(() => {
        openFiles[currentFilename] = editor.getValue();
        showUnsavedDot(true);

        if (suppressHighlightClearOnce) {
            suppressHighlightClearOnce = false;
            return;
        }

        clearChangedLineHighlights();
    });

    // Global keyboard shortcuts
    window.addEventListener("keydown", (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
            e.preventDefault();
            runRepair();
        } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
            e.preventDefault();
            saveActiveFile();
        } else if (e.altKey && e.key.toLowerCase() === "n") {
            e.preventDefault();
            openNewFileModal();
        }
    });

    refreshExamples();
    initSidebarResize();
    initRightPanelResize();
    initBottomResize();
    initTestcaseResize();
});

/* -------------------------------------------------- */
/* TOAST NOTIFICATIONS                                */
/* -------------------------------------------------- */
function showToast(message, type = "info", duration = 3000) {
    const container = document.getElementById("toast-container");
    if (!container) return;

    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.innerText = message;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = "0";
        setTimeout(() => toast.remove(), 250);
    }, duration);
}

function showUnsavedDot(visible) {
    const dot = document.getElementById("unsaved-dot");
    if (dot) dot.style.display = visible ? "inline-block" : "none";
}

/* -------------------------------------------------- */
/* NEW FILE MODAL & CREATION                          */
/* -------------------------------------------------- */
function openNewFileModal() {
    const modal = document.getElementById("new-file-modal");
    if (!modal) return;

    modal.style.display = "flex";
    const input = document.getElementById("new-file-name");
    if (input) {
        input.value = "";
        setTimeout(() => input.focus(), 50);
    }
}

function closeNewFileModal() {
    const modal = document.getElementById("new-file-modal");
    if (modal) modal.style.display = "none";
}

function handleModalBackdropClick(e) {
    if (e.target && e.target.classList.contains("modal-backdrop")) {
        closeNewFileModal();
    }
}

function handleNewFileKeyDown(e) {
    if (e.key === "Enter") {
        e.preventDefault();
        confirmCreateFile();
    } else if (e.key === "Escape") {
        closeNewFileModal();
    }
}

async function confirmCreateFile() {
    const input = document.getElementById("new-file-name");
    let name = (input ? input.value : "").trim();

    if (!name) {
        showToast("Please enter a file name", "warning");
        if (input) input.focus();
        return;
    }

    if (!name.endsWith(".c")) {
        name += ".c";
    }

    try {
        const response = await fetch("/api/file/create", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                filename: name
            })
        });

        const data = await response.json();
        if (data.error) {
            showToast("Error creating file: " + data.error, "error");
            return;
        }

        closeNewFileModal();
        showToast(`Created "${data.filename}"`, "success");

        // Refresh file tree to include newly created file
        await refreshExamples();

        // Open newly created file in editor
        openFileInTab(data.filename, data.code);
        showUnsavedDot(false);
    } catch (err) {
        showToast("Failed to create file: " + err.message, "error");
    }
}

async function saveActiveFile() {
    if (!editor) return;

    const code = editor.getValue();
    openFiles[currentFilename] = code;

    try {
        const response = await fetch("/api/file/save", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                filename: currentFilename,
                code: code
            })
        });

        const data = await response.json();
        if (data.error) {
            showToast("Error saving: " + data.error, "error");
            return;
        }

        showUnsavedDot(false);
        showToast(`Saved "${currentFilename}"`, "success");
    } catch (err) {
        showToast("Failed to save file: " + err.message, "error");
    }
}

function copyEditorCode() {
    if (!editor) return;
    navigator.clipboard.writeText(editor.getValue()).then(() => {
        showToast("Code copied to clipboard", "info");
    });
}

function resetEditorContent() {
    if (!editor) return;
    if (repairOriginalCode != null) {
        editor.setValue(repairOriginalCode);
        showToast("Reset to pre-repair code", "info");
    } else if (openFiles.hasOwnProperty(currentFilename)) {
        editor.setValue(openFiles[currentFilename]);
        showToast("Reset editor", "info");
    }
    showUnsavedDot(false);
}

/* -------------------------------------------------- */
/* RESULTS & UI HELPERS                               */
/* -------------------------------------------------- */
function fillList(id, items, formatter = null) {
    const el = document.getElementById(id);
    if (!el) return;

    el.innerHTML = "";

    const badge = document.getElementById(`badge-${id}`);
    if (badge) badge.innerText = items ? items.length : 0;

    if (!items || items.length === 0) {
        const li = document.createElement("li");
        li.className = "empty-notice";
        li.innerText = "None";
        el.appendChild(li);
        return;
    }

    items.forEach(item => {
        const li = document.createElement("li");
        li.innerText = formatter ? formatter(item) : item;
        el.appendChild(li);
    });
}

function toggleCard(cardId) {
    const card = document.getElementById(cardId);
    if (card) card.classList.toggle("collapsed");
}

function renderStats(stats) {
    const box = document.getElementById("stats");
    if (!box) return;

    box.innerHTML = "";

    if (!stats) {
        box.innerText = "No stats available";
        return;
    }

    const items = [
        { label: "Lexical Fixes", val: stats.lex_fixes ?? 0 },
        { label: "Syntax Repairs", val: stats.rule_fixes ?? 0 },
        { label: "Semantic Fixes", val: stats.sem_fixes ?? 0 },
        { label: "Symbol Fixes", val: stats.sym_fixes ?? 0 },
        { label: "AI Fixes", val: stats.ai_fixes ?? 0 },
        { label: "Iterations", val: stats.iterations ?? 0 }
    ];

    items.forEach(it => {
        const div = document.createElement("div");
        div.className = "stat-item";
        div.innerHTML = `
            <span class="stat-label">${it.label}</span>
            <span class="stat-val">${it.val}</span>
        `;
        box.appendChild(div);
    });
}

/* -------------------------------------------------- */
/* GREEN REPORT PANEL                                 */
/* -------------------------------------------------- */
function ensureGreenPanel() {
    let panel = document.getElementById("greenPanel");
    if (panel) return panel;

    const resultPanel = document.getElementById("resultpanel");
    if (!resultPanel) return null;

    panel = document.createElement("div");
    panel.id = "greenPanel";
    panel.className = "panelcard green-report-box";

    resultPanel.appendChild(panel);
    return panel;
}

function renderGreenReport(report) {
    const panel = ensureGreenPanel();
    if (!panel) return;

    if (!report || Object.keys(report).length === 0) {
        panel.innerHTML = `
            <div class="card-header">
                <h3>Green Compiler Efficiency</h3>
            </div>
            <div style="font-size:12px;color:var(--text-muted);margin-top:8px;">Run a repair to compute green energy metrics.</div>
        `;
        return;
    }

    const score = report.green_score ?? 0;
    const runtime = report.total_runtime_ms ?? 0;
    const hotspot = report.hotspot ?? "none";
    const suggestion = report.suggestion ?? "No recommendation.";
    const phase = report.phase_ms || {};
    const values = report.values || {};

    const co2 = values.co2_kg;
    let color = "#3fb950";
    if (score < 70) color = "#d29922";
    if (score < 45) color = "#f85149";

    const scorePercent = Math.max(0, Math.min(100, score));

    panel.innerHTML = `
        <div class="card-header">
            <h3>Green Compiler Efficiency</h3>
            <span class="badge" style="background:${color}22;color:${color}">${scorePercent.toFixed(0)}/100</span>
        </div>
        <div class="progress-wrap" style="margin:10px 0 12px;">
            <div class="progress-bar" style="width:${scorePercent}%;background:${color};"></div>
        </div>
        <div style="font-size:12px;line-height:1.6;color:var(--text-secondary);">
            <div>Execution Runtime: <b style="color:var(--text-primary);">${Number(runtime).toFixed(2)} ms</b></div>
            <div>CO₂ Footprint: <b style="color:var(--text-primary);">${co2 == null ? "N/A" : Number(co2).toExponential(3)} kg</b></div>
            <div>Execution Hotspot: <b style="color:var(--accent-amber);">${hotspot}</b></div>
            <div style="margin-top:8px;padding:8px;background:var(--bg-secondary);border-radius:4px;border-left:3px solid var(--accent-blue);">
                <b style="color:var(--text-primary);">Green Tip:</b> ${suggestion}
            </div>
        </div>
    `;
}

function highlightLines(changedLines, securityLines) {
    if (!editor) return;

    currentDecorations = editor.deltaDecorations(currentDecorations, []);

    const changed = changedLines || [];
    const security = new Set(securityLines || []);
    const allLines = [...new Set([...changed, ...(securityLines || [])])];

    if (allLines.length === 0) return;

    const decorations = allLines.map(line => ({
        range: new monaco.Range(line, 1, line, 1),
        options: {
            isWholeLine: true,
            className: security.has(line) ? "securityHighlight" : "normalHighlight",
            glyphMarginClassName: security.has(line) ? "securityGlyph" : "changedGlyph"
        }
    }));

    currentDecorations = editor.deltaDecorations([], decorations);
}

function clearChangedLineHighlights() {
    if (!editor) return;
    currentDecorations = editor.deltaDecorations(currentDecorations, []);
}

function setStatus(statusText) {
    const el = document.getElementById("status");
    const pill = document.getElementById("status-pill");
    if (!el || !pill) return;

    el.innerText = statusText || "Idle";

    pill.className = "status-pill";
    if (statusText === "SUCCESS") pill.classList.add("status-success");
    else if (statusText === "SUCCESS_WITH_WARNINGS" || statusText === "SEM_ISSUES") pill.classList.add("status-warning");
    else if (statusText === "RUNNING") pill.classList.add("status-running");
    else if (statusText === "BLOCKED_SECURITY" || statusText === "UNFIXABLE" || statusText === "STOPPED") pill.classList.add("status-danger");
    else pill.classList.add("status-idle");
}

function setProgress(percent, text) {
    const bar = document.getElementById("repairProgressBar");
    const label = document.getElementById("repairProgressText");

    if (bar) {
        const safe = Math.max(0, Math.min(100, percent || 0));
        bar.style.width = `${safe}%`;
    }

    if (label) label.innerText = text || "Ready";
}

function resetProgress() {
    setProgress(0, "Ready");
}

function resetPanels() {
    fillList("steps", []);
    fillList("errors", []);
    fillList("semantic", []);
    fillList("security", []);
    fillList("logs", []);

    renderStats({
        lex_fixes: 0,
        rule_fixes: 0,
        ai_fixes: 0,
        sym_fixes: 0,
        sem_fixes: 0,
        iterations: 0
    });

    renderGreenReport({});
    clearChangedLineHighlights();
    resetProgress();
}

/* -------------------------------------------------- */
/* TABS MANAGEMENT                                    */
/* -------------------------------------------------- */
function renderTabs() {
    const tabbar = document.getElementById("tabbar");
    if (!tabbar) return;

    tabbar.innerHTML = "";

    openTabs.forEach(filename => {
        const tab = document.createElement("div");
        tab.className = "filetab" + (filename === currentFilename ? " active" : "");
        tab.onclick = () => switchTab(filename);

        const name = document.createElement("span");
        name.innerText = filename.split("/").pop();

        const close = document.createElement("span");
        close.className = "filetab-close";
        close.innerText = "×";
        close.title = "Close Tab";
        close.onclick = (e) => {
            e.stopPropagation();
            closeTab(filename);
        };

        tab.appendChild(name);
        tab.appendChild(close);
        tabbar.appendChild(tab);
    });

    const label = document.getElementById("active-file-label");
    if (label) label.innerText = currentFilename;

    // Highlight active in sidebar
    document.querySelectorAll(".file-item").forEach(item => {
        if (item.dataset.filename === currentFilename) {
            item.classList.add("active");
        } else {
            item.classList.remove("active");
        }
    });
}

function switchTab(filename) {
    if (!editor || !openFiles.hasOwnProperty(filename)) return;

    openFiles[currentFilename] = editor.getValue();
    currentFilename = filename;

    suppressHighlightClearOnce = true;
    editor.setValue(openFiles[filename] ?? "");
    renderTabs();
    resetPanels();
    setStatus("Idle");
    showUnsavedDot(false);
}

function closeTab(filename) {
    if (openTabs.length === 1) return;

    const idx = openTabs.indexOf(filename);
    if (idx !== -1) openTabs.splice(idx, 1);

    delete openFiles[filename];

    if (currentFilename === filename) {
        currentFilename = openTabs[Math.max(0, idx - 1)] || openTabs[0];
        suppressHighlightClearOnce = true;
        editor.setValue(openFiles[currentFilename] ?? "");
    }

    renderTabs();
    resetPanels();
    showUnsavedDot(false);
}

function openFileInTab(filename, code) {
    if (!openTabs.includes(filename)) openTabs.push(filename);

    openFiles[filename] = code;
    currentFilename = filename;

    suppressHighlightClearOnce = true;
    editor.setValue(code);
    renderTabs();
    resetPanels();
    showUnsavedDot(false);
}

function computeChangedLines(beforeCode, afterCode) {
    const before = (beforeCode || "").split("\n");
    const after = (afterCode || "").split("\n");

    const maxLen = Math.max(before.length, after.length);
    const changed = [];

    for (let i = 0; i < maxLen; i++) {
        if ((before[i] || "") !== (after[i] || "")) changed.push(i + 1);
    }

    return changed;
}

function renderRepairResult(data) {
    const beforeCode = repairOriginalCode ?? "";
    const afterCode = data.corrected_code || editor.getValue();

    suppressHighlightClearOnce = true;
    editor.setValue(afterCode);
    openFiles[currentFilename] = afterCode;

    setStatus(data.status || "Unknown");

    fillList("steps", data.applied_steps || []);
    fillList("errors", data.errors || []);

    fillList(
        "semantic",
        data.semantic_issues || [],
        (item) => {
            const kind = item.kind || "issue";
            const line = item.line ?? "?";
            const col = item.col ?? "?";
            const msg = item.msg || "";
            const name = item.name ? ` (${item.name})` : "";
            return `${kind}${name} @ L${line}:${col} → ${msg}`;
        }
    );

    fillList("security", data.security_warnings || []);
    fillList("logs", data.logs || []);
    renderStats(data.stats || {});
    renderGreenReport(data.green_report || {});

    const changedLines = computeChangedLines(beforeCode, afterCode);
    highlightLines(changedLines, data.security_changed_lines || []);

    repairOriginalCode = null;
    showToast(`Repair finished: ${data.status || "Done"}`, data.status === "SUCCESS" ? "success" : "info");
}

/* -------------------------------------------------- */
/* RUN REPAIR                                         */
/* -------------------------------------------------- */
async function runRepair() {
    if (!editor) return;

    repairOriginalCode = editor.getValue();
    openFiles[currentFilename] = repairOriginalCode;

    resetPanels();
    setStatus("RUNNING");
    setProgress(5, "Analyzing source code...");

    try {
        const response = await fetch("/api/repair_stream", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                code: repairOriginalCode,
                filename: currentFilename
            })
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const chunks = buffer.split("\n\n");
            buffer = chunks.pop();

            for (const chunk of chunks) {
                if (!chunk.startsWith("data: ")) continue;

                const data = JSON.parse(chunk.slice(6));

                if (data.type === "start") {
                    setProgress(10, data.message || "Lexical analysis...");
                }

                if (data.type === "detect") {
                    const iter = data.stats?.iterations ?? 0;
                    const percent = Math.min(85, 15 + iter * 10);
                    setProgress(percent, data.message || "Diagnostic detected...");
                    renderStats(data.stats || {});
                    fillList("steps", data.applied_steps || []);
                }

                if (data.type === "fix") {
                    const totalRepairs = data.total_repairs ?? 0;
                    const percent = Math.min(95, 20 + totalRepairs * 15);
                    setProgress(percent, data.message || "Applying repair...");
                    renderStats(data.stats || {});
                    fillList("steps", data.applied_steps || []);
                }

                if (data.type === "done") {
                    setProgress(100, `Done (${data.total_repairs || 0} repairs)`);
                    renderRepairResult(data);
                }
            }
        }
    } catch (err) {
        setStatus("STOPPED");
        showToast("Repair stream error: " + err.message, "error");
    }
}

/* -------------------------------------------------- */
/* TEST CASE SANDBOX                                  */
/* -------------------------------------------------- */
async function runTestCase() {
    const input = document.getElementById("testcase-input").value;
    const output = document.getElementById("testcase-output");

    if (!input.trim()) {
        showToast("Please enter test code", "warning");
        return;
    }

    output.value = "Running compiler & auto-repair pipeline on testcase...";

    try {
        const response = await fetch("/api/testcase", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                code: input,
                filename: "test_case.c"
            })
        });

        const data = await response.json();

        output.value =
            `=======================================================\n` +
            `STATUS: ${data.status || "Unknown"}\n` +
            `APPLIED REPAIRS: ${(data.applied_steps || []).length}\n` +
            `GREEN SCORE: ${data.green_report?.green_score ?? "N/A"}/100\n` +
            `=======================================================\n\n` +
            `CORRECTED CODE:\n${data.corrected_code || input}\n\n` +
            `DIAGNOSTICS & REPAIR STEPS:\n` +
            (data.applied_steps && data.applied_steps.length > 0
                ? data.applied_steps.map(s => `  • ${s}`).join("\n")
                : "  (No syntax changes applied)") + "\n";
    } catch (err) {
        output.value = "Error executing test case: " + err.message;
    }
}

function clearTestCase() {
    document.getElementById("testcase-input").value = "";
    document.getElementById("testcase-output").value = "";
}

/* -------------------------------------------------- */
/* FILE EXPLORER & SEARCH                             */
/* -------------------------------------------------- */
async function refreshExamples() {
    try {
        const listRes = await fetch("/api/examples");
        allExampleFiles = await listRes.json();

        const countEl = document.getElementById("file-count");
        if (countEl) countEl.innerText = allExampleFiles.length;

        const searchInput = document.getElementById("file-search");
        const query = searchInput ? searchInput.value : "";
        filterFiles(query);
    } catch (err) {
        console.error("Failed to refresh file tree:", err);
    }
}

function filterFiles(query) {
    const tree = document.getElementById("file-tree");
    if (!tree) return;

    tree.innerHTML = "";
    const q = (query || "").toLowerCase().trim();

    const filtered = allExampleFiles.filter(fn => fn.toLowerCase().includes(q));

    if (filtered.length === 0) {
        const empty = document.createElement("div");
        empty.style.padding = "8px";
        empty.style.color = "var(--text-muted)";
        empty.style.fontSize = "12px";
        empty.style.fontStyle = "italic";
        empty.innerText = "No matching C files";
        tree.appendChild(empty);
        return;
    }

    filtered.forEach(filename => {
        const item = document.createElement("div");
        item.className = "file-item" + (filename === currentFilename ? " active" : "");
        item.innerText = filename;
        item.dataset.filename = filename;

        item.onclick = async () => {
            const res = await fetch("/api/example/" + encodeURIComponent(filename));
            const data = await res.json();
            openFileInTab(data.filename || filename, data.code || "");
        };

        tree.appendChild(item);
    });
}

/* -------------------------------------------------- */
/* INTERACTIVE DRAG RESIZERS                          */
/* -------------------------------------------------- */
function initSidebarResize() {
    const resizer = document.getElementById("sidebar-resizer");
    const sidebar = document.getElementById("sidebar");
    if (!resizer || !sidebar) return;

    let isResizing = false;

    resizer.addEventListener("mousedown", (e) => {
        isResizing = true;
        resizer.classList.add("resizing");
        document.body.style.cursor = "col-resize";
        document.body.style.userSelect = "none";
    });

    window.addEventListener("mousemove", (e) => {
        if (!isResizing) return;
        const newWidth = Math.max(180, Math.min(500, e.clientX));
        sidebar.style.width = newWidth + "px";
    });

    window.addEventListener("mouseup", () => {
        if (isResizing) {
            isResizing = false;
            resizer.classList.remove("resizing");
            document.body.style.cursor = "";
            document.body.style.userSelect = "";
            if (editor) editor.layout();
        }
    });
}

function initRightPanelResize() {
    const resizer = document.getElementById("rightpanel-resizer");
    const editorPanel = document.getElementById("editorpanel");
    const resultPanel = document.getElementById("resultpanel");
    if (!resizer || !editorPanel || !resultPanel) return;

    let isResizing = false;

    resizer.addEventListener("mousedown", (e) => {
        isResizing = true;
        resizer.classList.add("resizing");
        document.body.style.cursor = "col-resize";
        document.body.style.userSelect = "none";
    });

    window.addEventListener("mousemove", (e) => {
        if (!isResizing) return;
        const container = resizer.parentElement;
        const containerRect = container.getBoundingClientRect();
        const offset = e.clientX - containerRect.left;
        const total = containerRect.width;

        const leftWidth = Math.max(220, Math.min(total - 260, offset));
        editorPanel.style.width = leftWidth + "px";
        resultPanel.style.width = (total - leftWidth - 5) + "px";
    });

    window.addEventListener("mouseup", () => {
        if (isResizing) {
            isResizing = false;
            resizer.classList.remove("resizing");
            document.body.style.cursor = "";
            document.body.style.userSelect = "";
            if (editor) editor.layout();
        }
    });
}

function initBottomResize() {
    const resizer = document.getElementById("bottom-resizer");
    const topSection = document.getElementById("top-section");
    const testcasePanel = document.getElementById("testcase-panel");
    if (!resizer || !topSection || !testcasePanel) return;

    let isResizing = false;

    resizer.addEventListener("mousedown", (e) => {
        isResizing = true;
        resizer.classList.add("resizing");
        document.body.style.cursor = "row-resize";
        document.body.style.userSelect = "none";
    });

    window.addEventListener("mousemove", (e) => {
        if (!isResizing) return;
        const mainRect = topSection.parentElement.getBoundingClientRect();
        const offset = e.clientY - mainRect.top;
        const total = mainRect.height;

        const newTopHeight = Math.max(160, Math.min(total - 100, offset));
        topSection.style.height = newTopHeight + "px";
        testcasePanel.style.height = (total - newTopHeight - 5) + "px";
    });

    window.addEventListener("mouseup", () => {
        if (isResizing) {
            isResizing = false;
            resizer.classList.remove("resizing");
            document.body.style.cursor = "";
            document.body.style.userSelect = "";
            if (editor) editor.layout();
        }
    });
}

function initTestcaseResize() {
    const resizer = document.getElementById("testcase-resizer");
    const inputBox = document.getElementById("testcase-input-box");
    const outputBox = document.getElementById("testcase-output-box");
    if (!resizer || !inputBox || !outputBox) return;

    let isResizing = false;

    resizer.addEventListener("mousedown", (e) => {
        isResizing = true;
        resizer.classList.add("resizing");
        document.body.style.cursor = "col-resize";
        document.body.style.userSelect = "none";
    });

    window.addEventListener("mousemove", (e) => {
        if (!isResizing) return;
        const grid = resizer.parentElement;
        const rect = grid.getBoundingClientRect();
        const offset = e.clientX - rect.left;
        const total = rect.width;

        const leftWidth = Math.max(120, Math.min(total - 120, offset));
        inputBox.style.width = leftWidth + "px";
        outputBox.style.width = (total - leftWidth - 5) + "px";
    });

    window.addEventListener("mouseup", () => {
        if (isResizing) {
            isResizing = false;
            resizer.classList.remove("resizing");
            document.body.style.cursor = "";
            document.body.style.userSelect = "";
        }
    });
}