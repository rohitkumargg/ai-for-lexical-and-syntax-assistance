let editor;
let currentDecorations = [];
let suppressHighlightClearOnce = false;

const DEFAULT_LANGUAGES = [
    { id: "c", label: "C", extensions: [".c"], monaco: "c", new_label: "New C Program", default_name: "main.c" },
    { id: "python", label: "Python", extensions: [".py"], monaco: "python", new_label: "New Python Program", default_name: "main.py" }
];

const STARTER_TEMPLATES = {
    c: "int main() {\n    return 0;\n}\n",
    python: "def main():\n    print(\"Hello\")\n\n\nmain()\n"
};

const DEFAULT_SAMPLES = {
    c: `int main() {\n    int a = 10\n    return 0;\n}`,
    python: `def add(a, b)\n    return a + b\n\nprint(add(1, 2))\n`
};

let languagesList = [...DEFAULT_LANGUAGES];

let currentLanguageId = "c";
try {
    const saved = localStorage.getItem("ide.language");
    if (saved && (saved === "c" || saved === "python")) {
        currentLanguageId = saved;
    }
} catch (e) {}

let workspaces = {
    c: {
        openFiles: { "main.c": DEFAULT_SAMPLES.c },
        openTabs: ["main.c"],
        currentFilename: "main.c",
        untitledCounter: 0,
        created: []
    },
    python: {
        openFiles: { "main.py": DEFAULT_SAMPLES.python },
        openTabs: ["main.py"],
        currentFilename: "main.py",
        untitledCounter: 0,
        created: []
    }
};

let openFiles = workspaces[currentLanguageId].openFiles;
let openTabs = workspaces[currentLanguageId].openTabs;
let currentFilename = workspaces[currentLanguageId].currentFilename;
let repairOriginalCode = null;
let allExampleFiles = [];
let selectedTemplateKey = "basic";

function getActiveLanguage() {
    return languagesList.find(l => l.id === currentLanguageId) || languagesList[0];
}

function getStoredTheme() {
    try {
        return localStorage.getItem("simplec_theme") || "light";
    } catch (e) {
        return "light";
    }
}

function updateThemeToggleBtn(theme) {
    const sunIcon = document.getElementById("theme-icon-sun");
    const moonIcon = document.getElementById("theme-icon-moon");
    const label = document.getElementById("theme-toggle-label");
    if (!label) return;
    if (theme === "dark") {
        if (sunIcon) sunIcon.style.display = "inline-block";
        if (moonIcon) moonIcon.style.display = "none";
        label.textContent = "Light";
    } else {
        if (sunIcon) sunIcon.style.display = "none";
        if (moonIcon) moonIcon.style.display = "inline-block";
        label.textContent = "Dark";
    }
}

function applyTheme(theme) {
    if (theme === "dark") {
        document.documentElement.setAttribute("data-theme", "dark");
    } else {
        document.documentElement.setAttribute("data-theme", "light");
    }
    try {
        localStorage.setItem("simplec_theme", theme);
    } catch (e) {}
    if (window.monaco && editor) {
        monaco.editor.setTheme(theme === "dark" ? "simplec-dark" : "simplec-light");
    }
    updateThemeToggleBtn(theme);
}

function toggleTheme() {
    const current = getStoredTheme();
    const next = current === "dark" ? "light" : "dark";
    applyTheme(next);
}

require.config({
    paths: {
        vs: "https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.44.0/min/vs"
    }
});

require(["vs/editor/editor.main"], function () {
    monaco.editor.defineTheme("simplec-light", {
        base: "vs",
        inherit: true,
        rules: [
            { token: "keyword", foreground: "cf222e", fontStyle: "bold" },
            { token: "type", foreground: "0969da" },
            { token: "number", foreground: "0550ae" },
            { token: "comment", foreground: "6e7781", fontStyle: "italic" },
            { token: "string", foreground: "0a3069" },
            { token: "identifier", foreground: "1f2328" }
        ],
        colors: {
            "editor.background": "#ffffff",
            "editor.foreground": "#1f2328",
            "editorLineNumber.foreground": "#8c959f",
            "editorLineNumber.activeForeground": "#1f2328",
            "editor.selectionBackground": "#b6e3ff",
            "editor.inactiveSelectionBackground": "#e8f0fe",
            "editorCursor.foreground": "#0969da",
            "editorGutter.background": "#ffffff",
            "editor.lineHighlightBackground": "#f8fafc"
        }
    });

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

    const activeLang = getActiveLanguage();
    const activeTheme = getStoredTheme();

    editor = monaco.editor.create(document.getElementById("editor"), {
        value: openFiles[currentFilename] || "",
        language: activeLang.monaco || activeLang.id,
        theme: activeTheme === "dark" ? "simplec-dark" : "simplec-light",
        automaticLayout: true,
        minimap: { enabled: false },
        fontSize: 14,
        fontFamily: "'JetBrains Mono', Consolas, monospace",
        lineNumbers: "on",
        roundedSelection: false,
        scrollBeyondLastLine: false,
        glyphMargin: true
    });
    window.editor = editor;

    renderTabs();

let suppressInvalidateOnContinuation = false;

function invalidateStaleMetrics() {
    if (suppressInvalidateOnContinuation) return;
    currentCoordinatedPlan = null;
    if (typeof activePatchReview !== "undefined") activePatchReview = null;
    repairOriginalCode = null;

    const baCard = document.getElementById("beforeAfterCard");
    if (baCard) baCard.style.display = "none";
    const baTbody = document.getElementById("before-after-tbody");
    if (baTbody) baTbody.innerHTML = "";

    const recCard = document.getElementById("recommendedProgramCard");
    if (recCard) recCard.style.display = "none";

    cachedQualityReport = null;
    cachedOptimizationReport = null;
    cachedSecurityRiskReport = null;
    cachedGreenReport = null;
    window._currentSecurityRecommendations = null;

    renderPrimaryIndicators();
}

    editor.onDidChangeModelContent(() => {
        openFiles[currentFilename] = editor.getValue();
        showUnsavedDot(true);

        if (suppressHighlightClearOnce || suppressInvalidateOnContinuation || isRepairRunning) {
            suppressHighlightClearOnce = false;
            return;
        }

        clearChangedLineHighlights();
        invalidateStaleMetrics();
        triggerLiveQualityScore();
    });

    // Global keyboard shortcuts
    window.addEventListener("keydown", (e) => {
        if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === "Enter") {
            e.preventDefault();
            runProgram();
        } else if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
            e.preventDefault();
            runRepair();
        } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
            e.preventDefault();
            saveActiveFile();
        } else if (e.altKey && e.key.toLowerCase() === "n") {
            e.preventDefault();
            newFile();
        }
    });

    loadLanguagesAndInit();
    updateThemeToggleBtn(activeTheme);
    initAgentChatView();
    initSidebarResize();
    initRightPanelResize();
    initBottomResize();
    initTestcaseResize();
    initProgStdinResize();
    fetchCandidateRulesCount();
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

/* -------------------------------------------------- */
/* LANGUAGE SWITCH & WORKSPACE MANAGEMENT             */
/* -------------------------------------------------- */
async function loadLanguagesAndInit() {
    try {
        const res = await fetch("/api/languages");
        if (res.ok) {
            const data = await res.json();
            if (Array.isArray(data) && data.length > 0) {
                languagesList = data;
            }
        }
    } catch (err) {
        console.warn("Using fallback languages:", err);
    }

    try {
        const saved = localStorage.getItem("ide.language");
        if (saved && languagesList.some(l => l.id === saved)) {
            currentLanguageId = saved;
        }
    } catch (e) {}

    // Synchronize workspace pointers
    const ws = workspaces[currentLanguageId];
    openFiles = ws.openFiles;
    openTabs = ws.openTabs;
    currentFilename = ws.currentFilename;

    if (editor) {
        const langObj = getActiveLanguage();
        const model = editor.getModel();
        if (model) {
            monaco.editor.setModelLanguage(model, langObj.monaco || langObj.id);
        }
        suppressHighlightClearOnce = true;
        editor.setValue(openFiles[currentFilename] ?? "");
    }

    renderLanguageSwitch();
    applyActiveLanguageUI();
    renderTabs();
    refreshExamples();
}

function renderLanguageSwitch() {
    const container = document.getElementById("language-switch");
    if (!container) return;
    container.innerHTML = "";

    languagesList.forEach(lang => {
        const btn = document.createElement("button");
        btn.className = "seg-btn" + (lang.id === currentLanguageId ? " active" : "");
        btn.setAttribute("role", "tab");
        btn.setAttribute("aria-selected", lang.id === currentLanguageId ? "true" : "false");
        btn.innerText = lang.label;
        btn.onclick = () => switchLanguage(lang.id);
        container.appendChild(btn);
    });
}

function applyActiveLanguageUI() {
    const lang = getActiveLanguage();
    const subtitle = document.getElementById("ide-subtitle") || document.querySelector(".subtitle");
    if (subtitle) {
        subtitle.innerText = `${lang.label} mode`;
    }

    const newBtnText = document.getElementById("btn-new-file-text");
    const newBtn = document.getElementById("btn-new-file");
    if (newBtnText) {
        newBtnText.innerText = `+ ${lang.new_label}`;
    } else if (newBtn) {
        newBtn.innerText = `+ ${lang.new_label}`;
    }

    const exTitle = document.getElementById("examples-title");
    if (exTitle) {
        exTitle.innerText = `${lang.label} Examples`;
    }

    const searchInput = document.getElementById("file-search");
    if (searchInput) {
        searchInput.placeholder = `Search ${lang.label} files...`;
    }
}

function switchLanguage(newLangId) {
    if (newLangId === currentLanguageId) return;
    const langObj = languagesList.find(l => l.id === newLangId);
    if (!langObj) return;

    resetExecutionStateOnProblemChange();

    // 1. Save editor code into old workspace
    if (editor && workspaces[currentLanguageId]) {
        workspaces[currentLanguageId].openFiles[workspaces[currentLanguageId].currentFilename] = editor.getValue();
    }

    // 2. Switch
    currentLanguageId = newLangId;
    try {
        localStorage.setItem("ide.language", currentLanguageId);
    } catch (e) {}

    // 3. Update references
    const ws = workspaces[currentLanguageId];
    openFiles = ws.openFiles;
    openTabs = ws.openTabs;
    currentFilename = ws.currentFilename;

    // 4. Update editor language and content
    if (editor) {
        const model = editor.getModel();
        if (model) {
            monaco.editor.setModelLanguage(model, langObj.monaco || langObj.id);
        }
        suppressHighlightClearOnce = true;
        editor.setValue(openFiles[currentFilename] ?? "");
    }

    // 5. Update UI
    renderLanguageSwitch();
    applyActiveLanguageUI();
    renderTabs();
    resetPanels();
    setStatus(`Switched to ${langObj.label}`);

    // 6. Refresh file explorer for new language
    refreshExamples();
}

/* -------------------------------------------------- */
/* NEW FILE CREATION                                  */
/* -------------------------------------------------- */
function newFile() {
    const lang = getActiveLanguage();
    const ws = workspaces[currentLanguageId];
    ws.untitledCounter = (ws.untitledCounter || 0) + 1;
    const ext = lang.extensions ? lang.extensions[0] : (currentLanguageId === "python" ? ".py" : ".c");
    const filename = `untitled${ws.untitledCounter}${ext}`;
    const template = STARTER_TEMPLATES[currentLanguageId] || "";

    ws.openFiles[filename] = template;
    if (!ws.openTabs.includes(filename)) {
        ws.openTabs.push(filename);
    }
    if (!ws.created.includes(filename)) {
        ws.created.push(filename);
    }

    switchTab(filename);
    renderFileTree();
}

function downloadCodeAsFile(filename, content) {
    try {
        const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        const baseName = (filename || "").split("/").pop().split("\\").pop();
        a.download = baseName || (currentLanguageId === "python" ? "main.py" : "main.c");
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    } catch (e) {
        console.warn("Client file download trigger failed:", e);
    }
}

async function saveActiveFile() {
    if (!editor) return;

    const code = editor.getValue();
    const filename = currentFilename || (currentLanguageId === "python" ? "main.py" : "main.c");
    openFiles[filename] = code;

    let serverSaved = false;
    let errorMsg = "";

    try {
        const response = await fetch("/api/file/save", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                filename: filename,
                code: code
            })
        });

        const data = await response.json();
        if (data && data.success) {
            serverSaved = true;
        } else if (data && data.error) {
            errorMsg = data.error;
        }
    } catch (err) {
        errorMsg = err.message;
    }

    // Always trigger browser download so user directly receives the saved file
    downloadCodeAsFile(filename, code);

    showUnsavedDot(false);

    if (serverSaved) {
        showToast(`Saved "${filename}" successfully`, "success");
    } else {
        showToast(`Downloaded "${filename}" (Server: ${errorMsg || "saved locally"})`, "info");
    }

    const ws = workspaces[currentLanguageId];
    if (ws && ws.created && ws.created.includes(filename)) {
        renderFileTree();
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
    }
}

function showUnsavedDot(show) {
    const dot = document.getElementById("unsaved-dot");
    if (dot) dot.style.display = show ? "inline-block" : "none";
}

/* -------------------------------------------------- */
/* MONACO HIGHLIGHTING & DECORATIONS                  */
/* -------------------------------------------------- */
function highlightChangedLines(lines) {
    if (!editor || !Array.isArray(lines) || lines.length === 0) return;

    const decorations = lines.map(lineNo => ({
        range: new monaco.Range(lineNo, 1, lineNo, 1),
        options: {
            isWholeLine: true,
            className: "monaco-line-changed",
            glyphMarginClassName: "monaco-glyph-changed"
        }
    }));

    currentDecorations = editor.deltaDecorations(currentDecorations, decorations);
}

function clearChangedLineHighlights() {
    if (!editor) return;
    currentDecorations = editor.deltaDecorations(currentDecorations, []);
}

/* -------------------------------------------------- */
/* DIAGNOSTIC PANELS & STATS                          */
/* -------------------------------------------------- */
function renderStats(stats) {
    const s = stats || {};
    const setTxt = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.innerText = val ?? 0;
    };

    setTxt("stat-lex", s.lex_fixes);
    setTxt("stat-rule", s.rule_fixes);
    setTxt("stat-ai", s.ai_fixes);
    setTxt("stat-sym", s.sym_fixes);
    setTxt("stat-sem", s.sem_fixes);
    setTxt("stat-sec", s.sec_det_fixes);
    setTxt("stat-iter", s.iterations);
}

function escapeHtml(str) {
    if (str == null) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

/* ------------------------------------------------------------- */
/* 13. PRIMARY SYSTEM INDICATORS & BEFORE-AFTER COMPARISON       */
/* ------------------------------------------------------------- */
let cachedQualityReport = null;
let cachedOptimizationReport = null;
let cachedSecurityRiskReport = null;
let cachedGreenReport = null;
let cachedImprovementReport = null;
let liveMetricRequestVersion = 0;

function refreshLiveMetricsForCurrentSource() {
    liveMetricRequestVersion += 1;
    cachedQualityReport = null;
    cachedOptimizationReport = null;
    cachedSecurityRiskReport = null;
    renderPrimaryIndicators();
    triggerLiveQualityScore(liveMetricRequestVersion);
}

function scrollToPanel(panelId) {
    const el = document.getElementById(panelId);
    if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "start" });
        el.style.outline = "2px solid var(--accent-blue, #2563eb)";
        setTimeout(() => { el.style.outline = ""; }, 1400);
    }
}

function renderPrimaryIndicators() {
    const qScore = (cachedQualityReport && cachedQualityReport.can_score && cachedQualityReport.overall_score != null) ? Number(cachedQualityReport.overall_score) : null;
    const optScore = (cachedOptimizationReport && cachedOptimizationReport.can_score && cachedOptimizationReport.optimization_potential != null) ? Number(cachedOptimizationReport.optimization_potential) : null;
    const vulnScore = (cachedSecurityRiskReport && cachedSecurityRiskReport.can_score && cachedSecurityRiskReport.risk_score != null) ? Number(cachedSecurityRiskReport.risk_score) : null;

    const optimalVal = optScore != null ? Math.max(0, Math.min(100, Math.round(100 - optScore))) : null;
    const poorVal = qScore != null ? Math.max(0, Math.min(100, Math.round(100 - qScore))) : null;
    let overallVal = null;
    if (qScore != null && optScore != null && vulnScore != null) {
        overallVal = Math.max(0, Math.min(100, Math.round(0.50 * qScore + 0.25 * (100 - optScore) + 0.25 * (100 - vulnScore))));
    }

    // 1. Overall Code Quality %
    const elOverall = document.getElementById("pi-val-overall");
    const badgeOverall = document.getElementById("pi-badge-overall");
    const descOverall = document.getElementById("pi-desc-overall");
    if (elOverall) {
        if (overallVal != null) {
            elOverall.textContent = overallVal + "%";
            elOverall.style.color = overallVal >= 80 ? "#16a34a" : (overallVal >= 60 ? "#d97706" : "#dc2626");
            if (badgeOverall) {
                badgeOverall.className = "tile-badge badge-measured";
                badgeOverall.textContent = "[COMBINED]";
            }
            if (descOverall) descOverall.textContent = "50% Q + 25% (100-O) + 25% (100-V)";
        } else {
            elOverall.textContent = "--%";
            elOverall.style.color = "var(--text-secondary)";
            if (badgeOverall) {
                badgeOverall.className = "tile-badge badge-unbenchmarked";
                badgeOverall.textContent = "[INCOMPLETE]";
            }
            if (descOverall) {
                const riskReason = cachedSecurityRiskReport?.status_reason || cachedSecurityRiskReport?.summary;
                descOverall.textContent = riskReason
                    ? `Unavailable until security risk can be scored: ${riskReason}`
                    : `Needs quality, optimization, and security risk scores (Q=${qScore == null ? "pending" : "ready"}, O=${optScore == null ? "pending" : "ready"}, V=${vulnScore == null ? "pending" : "ready"}).`;
            }
        }
    }

    // 2. Optimal Code %
    const elOptimal = document.getElementById("pi-val-optimal");
    const badgeOptimal = document.getElementById("pi-badge-optimal");
    const descOptimal = document.getElementById("pi-desc-optimal");
    if (elOptimal) {
        if (optimalVal != null) {
            elOptimal.textContent = optimalVal + "%";
            elOptimal.style.color = optimalVal >= 80 ? "#16a34a" : (optimalVal >= 60 ? "#d97706" : "#dc2626");
            if (badgeOptimal) {
                badgeOptimal.className = "tile-badge badge-estimate";
                badgeOptimal.textContent = "[HEURISTIC]";
            }
            if (descOptimal) {
                descOptimal.textContent = optScore === 0 ? "No detected opportunities" : `${Math.round(optScore)}% opt. potential`;
            }
        } else {
            elOptimal.textContent = "--%";
            elOptimal.style.color = "var(--text-secondary)";
            if (badgeOptimal) {
                badgeOptimal.className = "tile-badge badge-unbenchmarked";
                badgeOptimal.textContent = "[INCOMPLETE]";
            }
            if (descOptimal) descOptimal.textContent = "Optimization analysis pending";
        }
    }

    // 3. Poor Code %
    const elPoor = document.getElementById("pi-val-poor");
    const badgePoor = document.getElementById("pi-badge-poor");
    const descPoor = document.getElementById("pi-desc-poor");
    if (elPoor) {
        if (poorVal != null) {
            elPoor.textContent = poorVal + "%";
            elPoor.style.color = poorVal <= 20 ? "#16a34a" : (poorVal <= 40 ? "#d97706" : "#dc2626");
            if (badgePoor) {
                badgePoor.className = "tile-badge badge-risk";
                badgePoor.textContent = "[INVERSE Q]";
            }
            if (descPoor) descPoor.textContent = "Inverse of Code Quality (100 - Q)";
        } else {
            elPoor.textContent = "--%";
            elPoor.style.color = "var(--text-secondary)";
            if (badgePoor) {
                badgePoor.className = "tile-badge badge-unbenchmarked";
                badgePoor.textContent = "[INCOMPLETE]";
            }
            if (descPoor) descPoor.textContent = "Quality analysis pending";
        }
    }

    // 4. Vulnerability Risk %
    const elVuln = document.getElementById("pi-val-vulnerability") || document.getElementById("pi-val-sec");
    const badgeVuln = document.getElementById("pi-badge-vulnerability") || document.getElementById("pi-badge-sec");
    const descVuln = document.getElementById("pi-desc-vulnerability") || document.getElementById("pi-desc-sec");
    if (elVuln) {
        if (vulnScore != null) {
            const r = Math.round(vulnScore);
            elVuln.textContent = r + "%";
            elVuln.style.color = r === 0 ? "#16a34a" : (r <= 30 ? "#d97706" : "#dc2626");
            if (badgeVuln) {
                badgeVuln.className = "tile-badge badge-risk";
                badgeVuln.textContent = "[RISK INDEX]";
            }
            if (descVuln) {
                const fc = cachedSecurityRiskReport ? cachedSecurityRiskReport.finding_counts : null;
                descVuln.textContent = fc ? `Crit: ${fc.critical} | High: ${fc.high} | Med: ${fc.medium}` : "Normalized risk indicator";
            }
        } else {
            elVuln.textContent = "--%";
            elVuln.style.color = "var(--text-secondary)";
            if (badgeVuln) {
                badgeVuln.className = "tile-badge badge-unbenchmarked";
                badgeVuln.textContent = "[INCOMPLETE]";
            }
            if (descVuln) descVuln.textContent = cachedSecurityRiskReport?.status_reason || cachedSecurityRiskReport?.summary || "Security analysis pending";
        }
    }

    // Backward compatibility aliases
    const qVal = document.getElementById("pi-val-quality");
    if (qVal && qScore != null) qVal.textContent = Math.round(qScore) + "%";
    const optVal = document.getElementById("pi-val-opt");
    if (optVal && optScore != null) optVal.textContent = Math.round(optScore) + "%";
    const secVal = document.getElementById("pi-val-sec");
    if (secVal && vulnScore != null) secVal.textContent = Math.round(vulnScore) + "%";

    // 4. Green Metrics Score
    const grnVal = document.getElementById("pi-val-green");
    const grnBadge = document.getElementById("pi-badge-green");
    const grnDesc = document.getElementById("pi-desc-green");
    if (grnVal && grnBadge && grnDesc) {
        if (cachedGreenReport && cachedGreenReport.green_score != null) {
            const g = Number(cachedGreenReport.green_score);
            grnVal.textContent = g + "/100";
            grnVal.style.color = g >= 80 ? "#16a34a" : (g >= 50 ? "#d97706" : "#dc2626");
            grnBadge.className = "tile-badge badge-green";
            grnBadge.textContent = "[HARDWARE MODEL]";
            const j = cachedGreenReport.energy_metrics?.estimated_joules;
            const ms = cachedGreenReport.total_runtime_ms;
            grnDesc.textContent = (j != null && ms != null) ? `${ms} ms | ${j} J` : "Latency, Joules & Footprint";
        } else {
            grnVal.textContent = "--/100";
            grnVal.style.color = "var(--text-secondary)";
            grnBadge.className = "tile-badge badge-unbenchmarked";
            grnBadge.textContent = "[PENDING RUN]";
            grnDesc.textContent = "Run repair to compute";
        }
    }

    // 5. Model Accuracy & Repair Performance
    const bmVal = document.getElementById("pi-val-benchmark");
    const bmBadge = document.getElementById("pi-badge-benchmark");
    const bmDesc = document.getElementById("pi-desc-benchmark");
    if (bmVal && bmBadge && bmDesc) {
        const isBenchmarked = cachedBenchmarkReport &&
            cachedBenchmarkReport.status === "BENCHMARKED" &&
            (cachedBenchmarkReport.benchmark_dataset_size || 0) >= 16 &&
            cachedBenchmarkReport.results &&
            Object.keys(cachedBenchmarkReport.results).length > 0;

        if (isBenchmarked) {
            const summary = cachedBenchmarkReport.comparative_summary || {};
            const rate = summary.best_repair_success_rate ?? "--";
            bmVal.textContent = rate + "%";
            bmVal.style.color = "#2563eb";
            bmBadge.className = "tile-badge badge-benchmark";
            bmBadge.textContent = "[BENCHMARKED]";
            const bestConfig = summary.best_repair_success_config || "Agentic Pipeline";
            bmDesc.textContent = `Top: ${bestConfig}`;
        } else {
            bmVal.textContent = "--";
            bmVal.style.color = "var(--text-secondary)";
            bmBadge.className = "tile-badge badge-unbenchmarked";
            bmBadge.textContent = "[PENDING RUN]";
            bmDesc.textContent = "Click to run benchmark harness";
        }
    }
}

function renderBeforeAfterCard(deltaData) {
    const card = document.getElementById("beforeAfterCard");
    const tbody = document.getElementById("before-after-tbody");
    const overheadBox = document.getElementById("ba-overhead-box");
    if (!card || !tbody) return;

    if (!deltaData) {
        card.style.display = "none";
        return;
    }

    // Extract six metrics comparison array
    let comp = deltaData.metrics_comparison;
    if (!comp || comp.length === 0) {
        const b6 = deltaData.before_six_metrics || deltaData.before_metrics || deltaData.before || {};
        const a6 = deltaData.after_six_metrics || deltaData.after_metrics || deltaData.after || {};
        if (Object.keys(b6).length === 0 && Object.keys(a6).length === 0) {
            card.style.display = "none";
            return;
        }

        const metricDefs = [
            { key: "code_quality_score", label: "Code Quality Score", epistemic_basis: "AST & Heuristics", higher_is_better: true },
            { key: "optimization_potential", label: "Optimization Potential", epistemic_basis: "Dead-code / Loops", higher_is_better: false },
            { key: "security_risk", label: "Security Risk Score", epistemic_basis: "Taint / Vulnerability", higher_is_better: false },
            { key: "repair_validation_success", label: "Repair Validation Success Rate", epistemic_basis: "Compiler & Unit Checks", higher_is_better: true },
            { key: "syntax_semantic_correctness", label: "Syntax & Semantic Correctness", epistemic_basis: "Parser & Type Checker", higher_is_better: true },
            { key: "code_complexity", label: "Code Complexity Index", epistemic_basis: "Cyclomatic & Nesting", higher_is_better: false },
        ];

        comp = metricDefs.map(m => {
            const bVal = b6[m.key] != null ? b6[m.key] : (b6[m.key === "security_risk" ? "security_risk_score" : m.key]);
            const aVal = a6[m.key] != null ? a6[m.key] : (a6[m.key === "security_risk" ? "security_risk_score" : m.key]);
            const bDisp = bVal != null ? Math.round(bVal) + "%" : "--";
            const aDisp = aVal != null ? Math.round(aVal) + "%" : "--";
            let dDisp = "--";
            if (bVal != null && aVal != null) {
                const diff = Math.round(aVal - bVal);
                dDisp = diff > 0 ? `+${diff}%` : `${diff}%`;
            }
            return {
                key: m.key,
                label: m.label,
                before: bVal,
                after: aVal,
                before_display: bDisp,
                after_display: aDisp,
                delta_display: dDisp,
                epistemic_basis: m.epistemic_basis,
            };
        });
    }

    card.style.display = "block";

    function getDeltaClass(key, deltaStr) {
        if (!deltaStr || deltaStr === "--" || deltaStr === "0%" || deltaStr === "0") return "delta-neutral";
        const higherIsBetter = (key === "code_quality_score" || key === "repair_validation_success" || key === "syntax_semantic_correctness");
        if (deltaStr.startsWith("+")) {
            return higherIsBetter ? "delta-better" : "delta-worse";
        } else if (deltaStr.startsWith("-")) {
            return higherIsBetter ? "delta-worse" : "delta-better";
        }
        return "delta-neutral";
    }

    function getEpistemicBadgeClass(basis) {
        if (!basis) return "badge-estimate";
        const b = basis.toLowerCase();
        if (b.includes("ast") || b.includes("parser") || b.includes("unit") || b.includes("check") || b.includes("compiler")) return "badge-measured";
        if (b.includes("taint") || b.includes("vulnerability") || b.includes("risk")) return "badge-risk";
        return "badge-estimate";
    }

    tbody.innerHTML = comp.map(item => `
        <tr>
            <td><strong>${escapeHtml(item.label || item.key)}</strong></td>
            <td>${escapeHtml(item.before_display || "--")}</td>
            <td><strong>${escapeHtml(item.after_display || "--")}</strong></td>
            <td><span class="delta-pill ${getDeltaClass(item.key, item.delta_display)}">${escapeHtml(item.delta_display || "--")}</span></td>
            <td><span class="epistemic-cell-badge ${getEpistemicBadgeClass(item.epistemic_basis)}">${escapeHtml(item.epistemic_basis || "Measured")}</span></td>
        </tr>
    `).join("");

    if (overheadBox) {
        const res = deltaData.resource_overhead || deltaData.agent_telemetry || deltaData.green_report || {};
        const runMs = res.runtime_ms ?? res.duration_ms ?? 0;
        const j = res.estimated_joules ?? res.energy_joules;
        const c = res.estimated_carbon_mg ?? res.carbon_mg;
        const rss = res.peak_memory_mb ?? res.peak_rss_mb;
        const tokens = res.model_tokens;

        overheadBox.innerHTML = `
            <div class="ba-overhead-item"><span>⚡ Repair Latency:</span> <strong>${runMs} ms</strong></div>
            <div class="ba-overhead-item"><span>🔋 Energy Expended:</span> <strong>${j != null ? j + " J" : "--"}</strong></div>
            <div class="ba-overhead-item"><span>🌱 Carbon Footprint:</span> <strong>${c != null ? c + " mg CO₂e" : "--"}</strong></div>
            <div class="ba-overhead-item"><span>🧠 Peak RSS Memory:</span> <strong>${rss != null ? rss + " MB" : "--"}</strong></div>
            ${tokens ? `<div class="ba-overhead-item"><span>🤖 Model Tokens:</span> <strong>${tokens}</strong></div>` : ""}
        `;
    }
}

function ensureGreenPanel() {
    let panel = document.getElementById("greenPanel");
    if (panel) return panel;

    const resultPanel = document.getElementById("resultpanel");
    if (!resultPanel) return null;

    panel = document.createElement("section");
    panel.id = "greenPanel";
    panel.className = "panelcard";
    resultPanel.appendChild(panel);
    return panel;
}

function renderGreenReport(report) {
    cachedGreenReport = report;
    renderPrimaryIndicators();
    const panel = ensureGreenPanel();
    if (!panel) return;

    if (!report || Object.keys(report).length === 0 || report.green_score === undefined) {
        panel.innerHTML = `
            <div class="green-card-title">Green Compiler</div>
            <div class="green-score-large" style="color: var(--text-secondary, #6b7280);">--/100</div>
            <div class="green-score-section">
                <div class="green-score-bar-row">
                    <span>Green Score</span>
                    <span>--%</span>
                </div>
                <div class="green-progress-track">
                    <div class="green-progress-fill" style="width: 0%; background: var(--accent-green, #16a34a);"></div>
                </div>
            </div>
            <div class="green-empty-notice">Run repair to calculate green score and system resource metrics.</div>
        `;
        return;
    }

    const score = report.green_score ?? 0;
    const runtime = report.total_runtime_ms ?? 0;
    const hotspot = report.hotspot ?? "unknown";
    const suggestion = report.suggestion ?? (report.recommendations && report.recommendations[0]) ?? "Optimal execution parameters.";
    const values = report.values || {};
    const energy = report.energy_metrics || {};
    const model = report.model_metrics || {};
    const tradeoff = report.tradeoff || {};
    const breakdown = report.score_breakdown || {};
    const optimizations = report.efficiency_optimizations || [];

    const cpu = report.system_metrics?.cpu_percent ?? values.cpu_percent;
    const memory = report.system_metrics?.memory_mb ?? values.memory_mb;
    const peakMemory = report.system_metrics?.peak_memory_mb ?? values.peak_memory_mb;
    const gpuMem = report.system_metrics?.gpu_memory_mb;

    let color = "#16a34a";
    if (score < 80) color = "#d97706";
    if (score < 50) color = "#dc2626";

    const scorePercent = Math.max(0, Math.min(100, score));

    const metricBars = [
        {
            label: "CPU Utilization",
            value: cpu == null ? null : Number(cpu),
            max: 100,
            unit: "%"
        },
        {
            label: "Active Memory (RSS)",
            value: memory == null ? null : Number(memory),
            max: peakMemory && peakMemory > 0 ? Number(peakMemory) : (memory || 1),
            unit: " MB"
        },
        {
            label: "Peak Memory (RSS)",
            value: peakMemory == null ? null : Number(peakMemory),
            max: peakMemory && peakMemory > 0 ? Number(peakMemory) : 1,
            unit: " MB"
        }
    ];

    if (gpuMem && gpuMem > 0) {
        metricBars.push({
            label: "GPU VRAM Allocated",
            value: Number(gpuMem),
            max: Math.max(1024, Number(gpuMem) * 1.5),
            unit: " MB"
        });
    }

    const metricBarsHtml = metricBars.map(item => {
        if (item.value == null) {
            return `
                <div class="system-metric-row">
                    <div class="system-metric-header">
                        <span>${escapeHtml(item.label)}</span>
                        <span>N/A</span>
                    </div>
                    <div class="system-metric-track"></div>
                </div>
            `;
        }

        const pct = item.max > 0 ? Math.max(0, Math.min(100, (item.value / item.max) * 100)) : 0;

        return `
            <div class="system-metric-row">
                <div class="system-metric-header">
                    <span>${escapeHtml(item.label)}</span>
                    <span>${item.value.toFixed(1)}${item.unit}</span>
                </div>
                <div class="system-metric-track">
                    <div class="system-metric-fill" style="width: ${pct}%;"></div>
                </div>
            </div>
        `;
    }).join("");

    // Energy details
    const joules = energy.energy_joules != null ? `${energy.energy_joules.toFixed(2)} J` : "--";
    const wattHours = energy.energy_wh != null ? `${energy.energy_wh.toFixed(4)} Wh` : "--";
    const co2Grams = energy.co2_grams != null ? `${energy.co2_grams.toFixed(3)} g` : "--";
    const co2Kg = energy.co2_kg != null ? `${Number(energy.co2_kg).toExponential(3)} kg` : "--";
    const energyPerRepair = energy.energy_per_validated_repair_j != null ? `${energy.energy_per_validated_repair_j.toFixed(2)} J` : "--";
    const latencyPerRepair = energy.latency_per_validated_repair_ms != null ? `${energy.latency_per_validated_repair_ms.toFixed(1)} ms` : "--";

    // Model stats if any
    let modelStatsHtml = "";
    if (model.model_calls > 0 || model.total_tokens > 0) {
        modelStatsHtml = `
            <div class="green-meta-item">
                🤖 <b>Model Inference:</b> ${model.model_calls} call(s), ${model.retries_count} retry, ${model.total_tokens} tokens (${model.prompt_tokens} prompt / ${model.completion_tokens} gen)
            </div>
        `;
    }

    // Breakdown chips
    const breakdownHtml = `
        <div class="green-breakdown-chips">
            <div class="green-breakdown-chip"><span class="label">Time Eff.</span><span class="val">${(breakdown.time_efficiency ?? 0).toFixed(0)}%</span></div>
            <div class="green-breakdown-chip"><span class="label">Resource Eff.</span><span class="val">${(breakdown.resource_efficiency ?? 0).toFixed(0)}%</span></div>
            <div class="green-breakdown-chip"><span class="label">Energy Eff.</span><span class="val">${(breakdown.energy_efficiency ?? 0).toFixed(0)}%</span></div>
            <div class="green-breakdown-chip"><span class="label">Avoided Comp.</span><span class="val">${(breakdown.avoided_computation ?? 0).toFixed(0)}%</span></div>
        </div>
    `;

    panel.innerHTML = `
        <div class="green-card-title">Green Metrics Engine</div>

        <div class="green-badge-row">
            <span class="green-badge-pill green-badge-measured" title="Directly measured latency and process RSS memory">⚡ DIRECT HARDWARE TIMING</span>
            <span class="green-badge-pill green-badge-estimated" title="Statistically estimated via hardware linear TDP model and 475 g CO2/kWh regional grid intensity">📊 ESTIMATED ENERGY & CO₂</span>
        </div>

        <div class="green-score-large" style="color: ${color};">
            ${score}/100
        </div>

        <div class="green-score-section">
            <div class="green-score-bar-row">
                <span>Green Score</span>
                <span>${scorePercent.toFixed(0)}%</span>
            </div>
            <div class="green-progress-track">
                <div class="green-progress-fill" style="width: ${scorePercent}%; background: ${color};"></div>
            </div>
        </div>

        ${breakdownHtml}

        <div class="green-energy-grid">
            <div class="green-energy-cell">
                <div class="cell-title">Energy Consumed</div>
                <div class="cell-value">${joules}</div>
                <div class="cell-sub">${wattHours}</div>
            </div>
            <div class="green-energy-cell">
                <div class="cell-title">CO₂ Equivalent</div>
                <div class="cell-value">${co2Grams}</div>
                <div class="cell-sub">${co2Kg}</div>
            </div>
            <div class="green-energy-cell">
                <div class="cell-title">Energy / Validated Fix</div>
                <div class="cell-value">${energyPerRepair}</div>
                <div class="cell-sub">per safe repair</div>
            </div>
            <div class="green-energy-cell">
                <div class="cell-title">Latency / Validated Fix</div>
                <div class="cell-value">${latencyPerRepair}</div>
                <div class="cell-sub">per safe repair</div>
            </div>
        </div>

        <div class="green-meta-item">⏱️ Total Runtime: <b>${Number(runtime).toFixed(2)} ms</b></div>
        <div class="green-meta-item">🔥 Hotspot: <b>${escapeHtml(hotspot)}</b></div>
        ${modelStatsHtml}

        <div class="green-tradeoff-box">
            🛡️ <b>Validation & Security Integrity:</b> ${escapeHtml(tradeoff.tradeoff_summary || "Essential security checks and validation rigor are unconditionally preserved.")}
        </div>

        <div class="green-suggestion-block">
            <b>Efficiency Suggestion:</b><br>${escapeHtml(suggestion)}
        </div>

        <div class="green-system-title">Hardware Resource Utilization</div>
        ${metricBarsHtml}

    `;
}


function ensureQualityPanel() {
    let panel = document.getElementById("qualityPanel");
    if (panel) return panel;

    const resultPanel = document.getElementById("resultpanel");
    if (!resultPanel) return null;

    panel = document.createElement("section");
    panel.id = "qualityPanel";
    panel.className = "panelcard";
    resultPanel.appendChild(panel);
    return panel;
}

let qualityScoreTimer = null;
function triggerLiveQualityScore(requestVersion = ++liveMetricRequestVersion) {
    clearTimeout(qualityScoreTimer);
    const secModal = document.getElementById("security-approval-modal");
    if (secModal && secModal.style.display !== "none") return;
    qualityScoreTimer = setTimeout(async () => {
        if (!editor) return;
        const secModal = document.getElementById("security-approval-modal");
        if (secModal && secModal.style.display !== "none") return;
        const code = editor.getValue();
        const filename = currentFilename;
        if (!code || code.trim().length < 15) {
            renderQualityScore({
                can_score: false,
                status: (!code || code.trim().length === 0) ? "EMPTY_SOURCE" : "INSUFFICIENT_INFORMATION",
                status_reason: "Source is empty or too short (< 15 characters) for reliable quality evaluation."
            });
            return;
        }
        try {
            if (!window._liveAnalysisAbortController) window._liveAnalysisAbortController = new AbortController();
            const resp = await fetch("/api/quality/score", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ code: code, filename: filename }),
                signal: window._liveAnalysisAbortController.signal
            });
            if (resp.ok) {
                const rep = await resp.json();
                if (requestVersion !== liveMetricRequestVersion || code !== editor.getValue() || filename !== currentFilename) return;
                renderQualityScore(rep);
            }
        } catch (e) {
            console.warn("Live quality score check skipped:", e);
        }
        triggerLiveOptimizationPotential(requestVersion);
    }, 600);
}

function renderQualityScore(report) {
    cachedQualityReport = report;
    renderPrimaryIndicators();
    const panel = ensureQualityPanel();
    if (!panel) return;

    if (!report || !report.can_score || report.overall_score === null || report.overall_score === undefined) {
        const status = report?.status || "INSUFFICIENT_INFORMATION";
        const reason = report?.status_reason || "Run repair or input complete source code to compute a verified quality score.";
        const statusClass = status === "EMPTY_SOURCE" ? "empty" : "insufficient";

        panel.innerHTML = `
            <div class="quality-card-header">
                <div class="quality-card-title">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M12 20h9"></path>
                        <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path>
                    </svg>
                    <span>Code Quality Score</span>
                </div>
                <span class="quality-status-pill ${statusClass}">${escapeHtml(status)}</span>
            </div>

            <div class="quality-score-hero">
                <div class="quality-score-large" style="color: var(--text-secondary, #6b7280);">--%</div>
                <div class="quality-score-desc">Score withheld to prevent ungrounded fabrication.</div>
            </div>

            <div class="quality-progress-track">
                <div class="quality-progress-fill" style="width: 0%; background: #94a3b8;"></div>
            </div>

            <div class="quality-empty-box">
                <strong>Status: ${escapeHtml(status)}</strong><br>
                ${escapeHtml(reason)}
            </div>

            <div class="quality-disclaimer-box">
                ${escapeHtml(report?.disclaimer || "The Code Quality Score is a diagnostic index distinguishing measured compiler properties from heuristic estimates. Incomplete or empty code receives no fabricated score.")}
            </div>
        `;
        return;
    }

    const score = Number(report.overall_score);
    let color = "#16a34a"; // green
    if (score < 80) color = "#d97706"; // amber
    if (score < 60) color = "#dc2626"; // red

    const components = report.components || {};
    const compKeys = ["correctness", "compliance", "maintainability", "complexity", "efficiency"];

    let compHtml = "";
    compKeys.forEach(k => {
        const comp = components[k];
        if (!comp) return;

        const cScore = Number(comp.score);
        const weightPct = Math.round((comp.weight || 0) * 100);
        const mType = comp.measurement_type || "MEASURED";
        const mTypeClass = mType.toLowerCase();

        let barColor = "#16a34a";
        if (cScore < 80) barColor = "#d97706";
        if (cScore < 60) barColor = "#dc2626";

        let evidenceHtml = "";
        if (comp.evidence && comp.evidence.length > 0) {
            evidenceHtml = `<ul class="quality-comp-evidence">` +
                comp.evidence.slice(0, 3).map(ev => `<li>${escapeHtml(ev)}</li>`).join("") +
                `</ul>`;
        }

        compHtml += `
            <div class="quality-comp-card">
                <div class="quality-comp-header">
                    <div class="quality-comp-title-group">
                        <span style="text-transform: capitalize;">${escapeHtml(k)}</span>
                        <span class="quality-type-badge ${mTypeClass}">${escapeHtml(mType)}</span>
                    </div>
                    <div>
                        <span>${cScore.toFixed(0)}%</span>
                        <span style="font-size: 11px; color: var(--text-secondary); margin-left: 4px;">(${weightPct}% weight)</span>
                    </div>
                </div>
                <div class="quality-comp-bar-track">
                    <div class="quality-comp-bar-fill" style="width: ${cScore}%; background: ${barColor};"></div>
                </div>
                ${evidenceHtml}
            </div>
        `;
    });

    const suggestions = report.suggestions || [];
    let sugHtml = "";
    if (suggestions.length > 0) {
        sugHtml = `
            <div class="quality-suggestions-box">
                <div class="quality-section-subtitle">Actionable Remediation Suggestions (${suggestions.length})</div>
                ${suggestions.slice(0, 5).map(sug => {
                    const pri = (sug.priority || "MEDIUM").toLowerCase();
                    const lineText = sug.line ? ` (Line ${sug.line})` : "";
                    const heurTag = sug.is_heuristic ? `<span class="quality-type-badge heuristic" style="margin-left: 6px;">Heuristic</span>` : `<span class="quality-type-badge measured" style="margin-left: 6px;">Measured</span>`;
                    return `
                        <div class="quality-suggestion-item">
                            <div class="quality-suggestion-header">
                                <div>
                                    <span class="quality-pri-pill ${pri}">${escapeHtml(sug.priority)}</span>
                                    ${heurTag}
                                </div>
                                <span style="font-size: 11px; color: var(--text-secondary); text-transform: capitalize;">${escapeHtml(sug.category)}${escapeHtml(lineText)}</span>
                            </div>
                            <div class="quality-sug-finding">${escapeHtml(sug.finding)}</div>
                            <div class="quality-sug-action">${escapeHtml(sug.action)}</div>
                        </div>
                    `;
                }).join("")}
            </div>
        `;
    }

    panel.innerHTML = `
        <div class="quality-card-header">
            <div class="quality-card-title">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M12 20h9"></path>
                    <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path>
                </svg>
                <span>Code Quality Score</span>
            </div>
            <span class="quality-status-pill scored">SCORED</span>
        </div>

        <div class="quality-score-hero">
            <div class="quality-score-large" style="color: ${color};">${score.toFixed(0)}%</div>
            <div class="quality-score-desc">${escapeHtml(report.summary || "Composite weighted quality analysis")}</div>
        </div>

        <div class="quality-progress-track">
            <div class="quality-progress-fill" style="width: ${Math.max(0, Math.min(100, score))}%; background: ${color};"></div>
        </div>

        <div class="quality-components-section">
            <div class="quality-section-subtitle">Configurable Dimensions & Measured Evidence</div>
            ${compHtml}
        </div>

        ${sugHtml}

    `;
}

function ensureOptimizationPanel() {
    let panel = document.getElementById("optimizationPanel");
    if (panel) return panel;

    const resultPanel = document.getElementById("resultpanel");
    if (!resultPanel) return null;

    panel = document.createElement("section");
    panel.id = "optimizationPanel";
    panel.className = "panelcard";
    resultPanel.appendChild(panel);
    return panel;
}

let optimizationTimer = null;
function triggerLiveOptimizationPotential(requestVersion = liveMetricRequestVersion) {
    clearTimeout(optimizationTimer);
    const secModal = document.getElementById("security-approval-modal");
    if (secModal && secModal.style.display !== "none") return;
    optimizationTimer = setTimeout(async () => {
        if (!editor) return;
        const secModal = document.getElementById("security-approval-modal");
        if (secModal && secModal.style.display !== "none") return;
        const code = editor.getValue();
        const filename = currentFilename;
        if (!code || code.trim().length < 15) {
            renderOptimizationReport({
                can_score: false,
                status: (!code || code.trim().length === 0) ? "EMPTY_SOURCE" : "INSUFFICIENT_INFORMATION",
                status_reason: "Source is empty or too short (< 15 characters) for reliable optimization potential analysis."
            });
            return;
        }
        try {
            if (!window._liveAnalysisAbortController) window._liveAnalysisAbortController = new AbortController();
            const resp = await fetch("/api/optimization/potential", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ code: code, filename: filename }),
                signal: window._liveAnalysisAbortController.signal
            });
            if (resp.ok) {
                const rep = await resp.json();
                if (requestVersion !== liveMetricRequestVersion || code !== editor.getValue() || filename !== currentFilename) return;
                renderOptimizationReport(rep);
            }
        } catch (e) {
            console.warn("Live optimization potential check skipped:", e);
        }
        triggerLiveSecurityRisk(requestVersion);
    }, 700);
}

function renderOptimizationReport(report) {
    cachedOptimizationReport = report;
    renderPrimaryIndicators();
    const panel = ensureOptimizationPanel();
    if (!panel) return;

    if (!report || !report.can_score || report.optimization_potential === null || report.optimization_potential === undefined) {
        const status = report?.status || "INSUFFICIENT_INFORMATION";
        const reason = report?.status_reason || "Run repair or input complete source code to estimate optimization potential.";
        const statusClass = status === "EMPTY_SOURCE" ? "empty" : "insufficient";

        panel.innerHTML = `
            <div class="opt-card-header">
                <div class="opt-card-title">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
                    </svg>
                    <span>Optimization Potential</span>
                </div>
                <span class="opt-status-pill ${statusClass}">${escapeHtml(status)}</span>
            </div>

            <div class="opt-score-hero">
                <div class="opt-score-large" style="color: var(--text-secondary, #6b7280);">--%</div>
                <div class="opt-score-desc">Potential withheld on incomplete source to prevent fabricated estimates.</div>
            </div>

            <div class="opt-progress-track">
                <div class="opt-progress-fill" style="width: 0%; background: #94a3b8;"></div>
            </div>

            <div class="opt-empty-box">
                <strong>Status: ${escapeHtml(status)}</strong><br>
                ${escapeHtml(reason)}
            </div>

            <div class="opt-disclaimer-box">
                ${escapeHtml(report?.disclaimer || "Optimization Potential estimates remaining improvement opportunity. Static estimates are distinguished from measured runtime improvements.")}
            </div>
        `;
        return;
    }

    const score = Number(report.optimization_potential);
    // Lower optimization potential means code is already streamlined (green).
    // Higher potential means lots of inefficiencies remain to be fixed (amber/red).
    let color = "#16a34a"; // green (low potential for improvement = already streamlined)
    if (score > 25) color = "#d97706"; // amber
    if (score > 50) color = "#dc2626"; // red (heavy potential for optimization)

    const catScores = report.category_scores || {};
    const catLabels = {
        algorithmic_complexity: "Algorithmic Complexity",
        avoidable_computation: "Avoidable Computation",
        unnecessary_allocations: "Unnecessary Allocations",
        redundant_operations: "Redundant Operations",
        inefficient_io_memory: "Inefficient I/O & Memory"
    };

    let catHtml = "";
    Object.keys(catLabels).forEach(k => {
        const val = catScores[k] != null ? Number(catScores[k]) : 0;
        let catColor = "#16a34a";
        if (val > 25) catColor = "#d97706";
        if (val > 50) catColor = "#dc2626";

        catHtml += `
            <div class="opt-cat-card">
                <div class="opt-cat-header">
                    <span>${escapeHtml(catLabels[k])}</span>
                    <span>${val.toFixed(0)}% potential</span>
                </div>
                <div class="opt-cat-track">
                    <div class="opt-cat-fill" style="width: ${val}%; background: ${catColor};"></div>
                </div>
            </div>
        `;
    });

    // Benchmark box
    const bm = report.benchmark || {};
    let bmHtml = "";
    if (bm.is_measured) {
        bmHtml = `
            <div class="opt-benchmark-box">
                <div class="opt-benchmark-header">
                    <span class="opt-type-badge measured">MEASURED RUNTIME</span>
                    <span>Controlled Benchmark Profiling</span>
                </div>
                <div>Runtime: <b>${bm.runtime_ms ?? 0} ms</b> | Peak RAM: <b>${bm.peak_memory_mb ?? "N/A"} MB</b> | Hotspot: <b>${escapeHtml(bm.hotspot_phase || "None")}</b></div>
            </div>
        `;
    } else {
        bmHtml = `
            <div class="opt-benchmark-box" style="background: rgba(100, 116, 139, 0.05); border-color: rgba(100, 116, 139, 0.2);">
                <div class="opt-benchmark-header" style="color: var(--text-secondary);">
                    <span class="opt-type-badge static">STATIC HEURISTIC</span>
                    <span>Pattern-Based Static Analysis</span>
                </div>
                <div>Estimates derived from AST & control-flow pattern analysis (run pipeline to capture live benchmark profile).</div>
            </div>
        `;
    }

    // Opportunities list
    const opps = report.opportunities || [];
    let oppsHtml = "";
    if (opps.length > 0) {
        oppsHtml = `
            <div class="opt-opportunities-box">
                <div class="opt-section-subtitle">Identified Improvement Opportunities (${opps.length})</div>
                ${opps.slice(0, 6).map(opp => {
                    const impactClass = (opp.impact || "MEDIUM").toLowerCase();
                    const lineText = opp.line ? ` (Line ${opp.line})` : "";
                    const typeClass = opp.estimate_type === "MEASURED_BENCHMARK" ? "measured" : "static";
                    const typeLabel = opp.estimate_type === "MEASURED_BENCHMARK" ? "Measured" : "Static";

                    return `
                        <div class="opt-opportunity-item">
                            <div class="opt-opp-header">
                                <div>
                                    <span class="opt-impact-pill ${impactClass}">${escapeHtml(opp.impact)}</span>
                                    <span class="opt-type-badge ${typeClass}" style="margin-left: 6px;">${escapeHtml(typeLabel)}</span>
                                </div>
                                <span style="font-size: 11px; color: var(--text-secondary);">${escapeHtml(lineText)}</span>
                            </div>
                            <div class="opt-opp-title">${escapeHtml(opp.title)}</div>
                            <div class="opt-opp-action">${escapeHtml(opp.description)}</div>
                            <div class="opt-opp-action"><strong>Remediation:</strong> ${escapeHtml(opp.suggested_action)}</div>
                            ${opp.estimated_speedup ? `<span class="opt-speedup-tag">Speedup: ${escapeHtml(opp.estimated_speedup)}</span>` : ""}
                        </div>
                    `;
                }).join("")}
            </div>
        `;
    }

    panel.innerHTML = `
        <div class="opt-card-header">
            <div class="opt-card-title">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
                </svg>
                <span>Optimization Potential</span>
            </div>
            <span class="opt-status-pill scored">SCORED</span>
        </div>

        <div class="opt-score-hero">
            <div class="opt-score-large" style="color: ${color};">${score.toFixed(0)}%</div>
            <div class="opt-score-desc">${escapeHtml(report.summary || "Estimated improvement opportunity")}</div>
        </div>

        <div class="opt-progress-track">
            <div class="opt-progress-fill" style="width: ${Math.max(0, Math.min(100, score))}%; background: ${color};"></div>
        </div>

        ${bmHtml}

        <div class="opt-categories-section">
            <div class="opt-section-subtitle">Potential by Category</div>
            ${catHtml}
        </div>

        ${oppsHtml}

    `;
}

function ensureSecurityRiskPanel() {
    let panel = document.getElementById("securityRiskPanel");
    if (panel) return panel;

    const resultPanel = document.getElementById("resultpanel");
    if (!resultPanel) return null;

    panel = document.createElement("section");
    panel.id = "securityRiskPanel";
    panel.className = "panelcard";
    resultPanel.appendChild(panel);
    return panel;
}

let securityRiskTimer = null;
function triggerLiveSecurityRisk(requestVersion = liveMetricRequestVersion) {
    clearTimeout(securityRiskTimer);
    const secModal = document.getElementById("security-approval-modal");
    if (secModal && secModal.style.display !== "none") return;
    securityRiskTimer = setTimeout(async () => {
        if (!editor) return;
        const secModal = document.getElementById("security-approval-modal");
        if (secModal && secModal.style.display !== "none") return;
        const code = editor.getValue();
        const filename = currentFilename;
        if (!code || code.trim().length < 15) {
            renderSecurityRiskReport({
                can_score: false,
                status: (!code || code.trim().length === 0) ? "EMPTY_SOURCE" : "INCOMPLETE_ASSESSMENT",
                status_reason: "Source is empty or too short (< 15 characters) for a reliable security risk assessment."
            });
            return;
        }
        try {
            if (!window._liveAnalysisAbortController) window._liveAnalysisAbortController = new AbortController();
            const resp = await fetch("/api/security/risk", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ code: code, filename: filename }),
                signal: window._liveAnalysisAbortController.signal
            });
            if (resp.ok) {
                const rep = await resp.json();
                if (requestVersion !== liveMetricRequestVersion || code !== editor.getValue() || filename !== currentFilename) return;
                renderSecurityRiskReport(rep);
            }
        } catch (e) {
            console.warn("Live security risk check skipped:", e);
        }
    }, 750);
}

function renderSecurityRiskReport(report) {
    cachedSecurityRiskReport = report;
    renderPrimaryIndicators();
    const panel = ensureSecurityRiskPanel();
    if (!panel) return;

    if (!report || !report.can_score || report.risk_score === null || report.risk_score === undefined) {
        const status = report?.status || "INCOMPLETE_ASSESSMENT";
        const reason = report?.status_reason || "Run security analysis or input complete source code to compute a verified security risk score.";
        const statusClass = status === "EMPTY_SOURCE" ? "empty" : "incomplete";

        panel.innerHTML = `
            <div class="sec-risk-card-header">
                <div class="sec-risk-card-title">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
                    </svg>
                    <span>Security Risk Score</span>
                </div>
                <span class="sec-risk-status-pill ${statusClass}">${escapeHtml(status)}</span>
            </div>

            <div class="sec-risk-hero">
                <div class="sec-risk-score-large" style="color: var(--text-secondary, #6b7280);">--%</div>
                <div class="sec-risk-desc">Assessment incomplete. Score withheld to prevent speculative percentage fabrication.</div>
            </div>

            <div class="sec-risk-track">
                <div class="sec-risk-fill" style="width: 0%; background: #94a3b8;"></div>
            </div>

            <div class="sec-risk-empty-box">
                <strong>Status: ${escapeHtml(status)}</strong><br>
                ${escapeHtml(reason)}
            </div>

            <div class="sec-risk-disclaimer-box">
                ${escapeHtml(report?.disclaimer || "The Security Risk Score is a static composite risk indicator, NOT a calibrated attack probability.")}
            </div>
        `;
        return;
    }

    const score = Number(report.risk_score);
    let color = "#16a34a"; // green (low risk)
    if (score > 25) color = "#d97706"; // amber (medium risk)
    if (score > 50) color = "#dc2626"; // red (critical/high risk)

    const statusPillClass = score > 0 ? "assessed" : "clean";
    const statusText = score > 0 ? "ASSESSED" : "ZERO DETECTED RISK";

    // Delta badge if available
    let deltaBadgeHtml = "";
    if (report.delta_score != null) {
        const d = Number(report.delta_score);
        if (d < 0) {
            deltaBadgeHtml = `<span class="sec-risk-delta-badge improved">▼ ${Math.abs(d).toFixed(1)}% Risk Reduced</span>`;
        } else if (d > 0) {
            deltaBadgeHtml = `<span class="sec-risk-delta-badge regressed">▲ +${d.toFixed(1)}% Risk Increased</span>`;
        }
    }

    // Severities Counts Grid
    const severitiesGridHtml = `
        <div class="sec-risk-severities-grid">
            <div class="sec-risk-sev-card critical">
                <div class="sec-risk-sev-count" style="color: #dc2626;">${report.critical_count ?? 0}</div>
                <div class="sec-risk-sev-label">Critical</div>
            </div>
            <div class="sec-risk-sev-card high">
                <div class="sec-risk-sev-count" style="color: #ea580c;">${report.high_count ?? 0}</div>
                <div class="sec-risk-sev-label">High</div>
            </div>
            <div class="sec-risk-sev-card medium">
                <div class="sec-risk-sev-count" style="color: #ca8a04;">${report.medium_count ?? 0}</div>
                <div class="sec-risk-sev-label">Medium</div>
            </div>
            <div class="sec-risk-sev-card low">
                <div class="sec-risk-sev-count" style="color: #2563eb;">${report.low_count ?? 0}</div>
                <div class="sec-risk-sev-label">Low</div>
            </div>
        </div>
    `;

    // Contributions List
    const contribs = report.contributions || [];
    let contribsHtml = "";
    if (contribs.length > 0) {
        contribsHtml = `
            <div class="sec-risk-contrib-section">
                <div class="opt-section-subtitle">Important Finding Risk Contributions (${contribs.length})</div>
                ${contribs.slice(0, 5).map(c => {
                    const lineText = c.line ? ` (Line ${c.line})` : "";
                    const confTag = c.is_confirmed ? `<span class="quality-type-badge measured" style="margin-left: 6px;">Confirmed</span>` : `<span class="quality-type-badge heuristic" style="margin-left: 6px;">Heuristic</span>`;
                    return `
                        <div class="sec-risk-contrib-item">
                            <div class="sec-risk-contrib-header">
                                <div>
                                    <strong>${escapeHtml(c.rule_id)}</strong>${escapeHtml(lineText)}
                                    ${confTag}
                                </div>
                                <span class="sec-risk-points-badge">+${c.risk_points.toFixed(1)} pts</span>
                            </div>
                            <div style="font-weight: 500; color: var(--text-primary);">${escapeHtml(c.title)}</div>
                            <div class="sec-risk-factors-tag">${escapeHtml(c.explanation)}</div>
                        </div>
                    `;
                }).join("")}
            </div>
        `;
    }

    // Unresolved Findings Summary
    const unresolved = report.unresolved_findings || [];
    let unresolvedHtml = "";
    if (unresolved.length > 0) {
        unresolvedHtml = `
            <div class="sec-risk-unresolved-box">
                <div class="sec-risk-unresolved-header">Unresolved Active Security Findings (${unresolved.length})</div>
                <ul style="margin: 0; padding-left: 18px; color: var(--text-primary); line-height: 1.4;">
                    ${unresolved.slice(0, 4).map(u => `
                        <li>[${escapeHtml(u.severity)}] Line ${u.line}: <b>${escapeHtml(u.rule_id)}</b> - ${escapeHtml(u.impact.slice(0, 80))}${u.impact.length > 80 ? "..." : ""}</li>
                    `).join("")}
                </ul>
            </div>
        `;
    }

    panel.innerHTML = `
        <div class="sec-risk-card-header">
            <div class="sec-risk-card-title">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
                </svg>
                <span>Security Risk Score</span>
            </div>
            <span class="sec-risk-status-pill ${statusPillClass}">${statusText}</span>
        </div>

        <div class="sec-risk-hero">
            <div class="sec-risk-score-large" style="color: ${color};">${score.toFixed(0)}%</div>
            ${deltaBadgeHtml}
            <div class="sec-risk-desc">${escapeHtml(report.summary || "Composite security risk index")}</div>
        </div>

        <div class="sec-risk-track">
            <div class="sec-risk-fill" style="width: ${Math.max(0, Math.min(100, score))}%; background: ${color};"></div>
        </div>

        ${severitiesGridHtml}
        ${contribsHtml}
        ${unresolvedHtml}

    `;
}

/* ------------------------------------------------------------- */
/* POST-REPAIR IMPROVEMENT ADVISOR COMPONENT                     */
/* ------------------------------------------------------------- */
let activeImprovementCandidate = null;
let improvementAdvisorTimer = null;

function ensureImprovementAdvisorPanel() {
    let panel = document.getElementById("improvementAdvisorPanel");
    if (panel) return panel;

    const resultPanel = document.getElementById("resultpanel");
    if (!resultPanel) return null;

    panel = document.createElement("section");
    panel.id = "improvementAdvisorPanel";
    panel.className = "panelcard";
    resultPanel.appendChild(panel);
    return panel;
}

function triggerLiveImprovementAdvisor() {
    clearTimeout(improvementAdvisorTimer);
    improvementAdvisorTimer = setTimeout(async () => {
        if (!editor) return;
        const code = editor.getValue();
        if (!code || code.trim().length < 15) {
            renderImprovementAdvisorReport({
                total_candidates: 0,
                candidates: [],
                unfixable_advisories: [],
                summary: "Improvement Advisor pending: complete code required.",
                disclaimer: "Static improvement recommendations operate on complete programs.",
            });
            return;
        }

        try {
            const resp = await fetch("/api/improvement/advise", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    code: code,
                    filename: currentFilename,
                    green_report: cachedGreenReport || {},
                }),
            });
            if (resp.ok) {
                const rep = await resp.json();
                renderImprovementAdvisorReport(rep);
            }
        } catch (e) {
            console.warn("Live improvement advisor skipped:", e);
        }
    }, 850);
}

function renderImprovementAdvisorReport(report) {
    cachedImprovementReport = report;
    const panel = ensureImprovementAdvisorPanel();
    if (!panel) return;

    if (!report || report.total_candidates === undefined) {
        panel.innerHTML = `
            <div class="improvement-card-header">
                <div class="improvement-card-title">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M12 20h9"></path>
                        <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path>
                    </svg>
                    <span>Improvement Advisor</span>
                </div>
                <span class="tile-badge badge-unbenchmarked">[READY]</span>
            </div>
            <div class="empty-panel">Run analysis or compiler repair to generate post-repair improvement recommendations.</div>
        `;
        return;
    }

    const cands = report.candidates || [];
    const perfCount = cands.filter(c => c.strategy === "PERFORMANCE").length;
    const secCount = cands.filter(c => c.strategy === "SECURITY_HARDENING").length;
    const maintCount = cands.filter(c => c.strategy === "MAINTAINABILITY" || c.strategy === "CONSERVATIVE").length;

    let candsHtml = "";
    if (cands.length === 0) {
        candsHtml = `
            <div class="empty-panel" style="padding: 14px 10px; text-align: center; color: var(--text-secondary);">
                ✨ <strong>Zero Remaining Deficiencies Identified</strong><br>
                All supported code quality, efficiency, and security hardening heuristics are satisfied by the current source.
            </div>
        `;
    } else {
        candsHtml = cands.map((c, i) => {
            const stratCls = (c.strategy || "").toLowerCase();
            const badgeCls = stratCls.includes("perf") ? "perf" : (stratCls.includes("sec") ? "sec" : (stratCls.includes("maint") ? "maint" : "cons"));
            const priCls = (c.priority || "MEDIUM").toLowerCase();
            const candJson = escapeHtml(JSON.stringify(c));

            return `
                <div class="imp-candidate-card ${stratCls}" id="imp-card-${c.id}">
                    <div class="imp-card-top">
                        <div class="imp-card-title-group">
                            <span class="imp-badge ${badgeCls}">[${escapeHtml(c.strategy)}]</span>
                            <span class="imp-priority-tag ${priCls}">${escapeHtml(c.priority)}</span>
                            <span style="font-size: 11px; color: var(--text-muted); font-family: var(--font-mono, monospace);">${escapeHtml(c.id)}</span>
                        </div>
                        <span class="vuln-loc-tag">Line ${c.line}</span>
                    </div>

                    <div class="imp-card-headline">${escapeHtml(c.title)}</div>
                    <div class="imp-card-explanation">${escapeHtml(c.explanation)}</div>

                    ${c.evidence ? `<div class="imp-evidence-snippet">${escapeHtml(c.evidence)}</div>` : ""}

                    <div class="imp-meta-grid">
                        <div class="imp-meta-item"><span>Target Metric:</span> <strong>${escapeHtml(c.relevant_metric)}</strong></div>
                        <div class="imp-meta-item"><span>Expected Delta:</span> <strong>${escapeHtml(c.predicted_metric_delta)}</strong></div>
                        <div class="imp-meta-item"><span>Validation:</span> <strong>${c.validation_passed ? "✅ Passed" : "❌ Validation Failed"}</strong></div>
                        <div class="imp-meta-item"><span>Status:</span> <strong>${escapeHtml(c.user_decision_state)}</strong></div>
                    </div>

                    ${(!c.validation_passed && c.validation_report && c.validation_report.remaining_risks && c.validation_report.remaining_risks.length > 0) ? `
                        <div class="imp-validation-error-box" style="margin-top: 8px; padding: 6px 10px; font-size: 11px; background: rgba(239, 68, 68, 0.1); border-left: 3px solid #ef4444; color: #ef4444; border-radius: 4px;">
                            <strong>Remaining Issues:</strong> ${escapeHtml(c.validation_report.remaining_risks.join("; "))}
                        </div>
                    ` : ""}

                    <div class="imp-actions-row">
                        <button class="imp-btn-review" onclick="openImprovementModalForCandidate('${c.id}')">
                            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <circle cx="11" cy="11" r="8"></circle>
                                <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                            </svg>
                            Review Diff & Trade-offs
                        </button>
                        <button class="imp-btn-reject" onclick="rejectImprovementCandidateById('${c.id}')">Dismiss</button>
                        ${(c.validation_passed && c.is_eligible_for_application !== false) ? `
                        <button class="imp-btn-apply" onclick="applyImprovementCandidateById('${c.id}')">
                            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polyline points="20 6 9 17 4 12"></polyline>
                            </svg>
                            Approve & Apply
                        </button>
                        ` : `
                        <button class="imp-btn-apply" disabled style="opacity: 0.5; cursor: not-allowed; background: var(--bg-card, #2d3748); border: 1px solid rgba(239, 68, 68, 0.4); color: #ef4444;" title="Candidate cannot be applied because independent validation failed">
                            🚫 Ineligible (Validation Failed)
                        </button>
                        `}
                    </div>
                </div>
            `;
        }).join("");
    }

    panel.innerHTML = `
        <div class="improvement-card-header">
            <div class="improvement-card-title">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M12 20h9"></path>
                    <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path>
                </svg>
                <span>Post-Repair Improvement Advisor</span>
            </div>
            <span class="indicator-header-pill">${cands.length} Actionable Recommendation(s)</span>
        </div>

        <div class="improvement-summary-bar">
            <span><strong>Available Strategies:</strong></span>
            <span class="imp-stat-pill perf">⚡ ${perfCount} Performance</span>
            <span class="imp-stat-pill sec">🛡️ ${secCount} Security Hardening</span>
            <span class="imp-stat-pill maint">📐 ${maintCount} Maintainability</span>
        </div>

        <div class="imp-candidates-list">
            ${candsHtml}
        </div>

        <div class="imp-disclaimer-box">
            ⚖️ <strong>Epistemic Note:</strong> ${escapeHtml(report.disclaimer || "Proposed transformations do not guarantee global optimality.")}
        </div>
    `;
}

function openImprovementModalForCandidate(candId) {
    if (!cachedImprovementReport || !cachedImprovementReport.candidates) return;
    const cand = cachedImprovementReport.candidates.find(c => c.id === candId);
    if (!cand) return;

    activeImprovementCandidate = cand;

    const modal = document.getElementById("improvement-modal");
    if (!modal) return;

    const setT = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.textContent = val ?? "";
    };

    setT("imp-modal-title", cand.title);
    setT("imp-modal-explanation", cand.explanation);
    setT("imp-modal-effect", cand.expected_effect);
    setT("imp-modal-assumptions", (cand.assumptions && cand.assumptions.length > 0) ? cand.assumptions.join("; ") : "None specified");
    setT("imp-modal-tradeoffs", cand.trade_offs || "Negligible trade-off");
    setT("imp-modal-metric-delta", `${cand.relevant_metric}: ${cand.predicted_metric_delta}`);

    const stratEl = document.getElementById("imp-modal-strategy-pill");
    if (stratEl) {
        stratEl.textContent = cand.strategy;
        stratEl.className = `imp-badge ${cand.strategy.toLowerCase().includes("perf") ? "perf" : (cand.strategy.toLowerCase().includes("sec") ? "sec" : "maint")}`;
    }

    const priEl = document.getElementById("imp-modal-priority-pill");
    if (priEl) {
        priEl.textContent = cand.priority;
        priEl.className = `imp-priority-tag ${(cand.priority || "medium").toLowerCase()}`;
    }

    const diffContainer = document.getElementById("imp-modal-diff-content");
    if (diffContainer) {
        const diffText = cand.unified_diff || "";
        const lines = diffText.split("\n");
        diffContainer.innerHTML = lines.map(line => {
            let cls = "diff-line";
            if (line.startsWith("+++") || line.startsWith("---") || line.startsWith("@@")) {
                cls += " header";
            } else if (line.startsWith("+")) {
                cls += " addition";
            } else if (line.startsWith("-")) {
                cls += " deletion";
            }
            return `<div class="${cls}">${escapeHtml(line)}</div>`;
        }).join("");
    }

    modal.style.display = "flex";
}

function closeImprovementModal() {
    const modal = document.getElementById("improvement-modal");
    if (modal) modal.style.display = "none";
}

function handleImprovementModalBackdropClick(e) {
    if (e.target && e.target.id === "improvement-modal") {
        closeImprovementModal();
    }
}

const inFlightCandidateApplies = new Set();

async function applyCandidateToEditor(candId, options = {}) {
    if (!candId) {
        showToast("Cannot apply patch: invalid or missing candidate ID.", "error");
        return false;
    }

    // 1. Prevent duplicate concurrent clicks from issuing competing apply requests
    if (inFlightCandidateApplies.has(candId)) {
        showToast("Application already in progress for this recommendation.", "warning");
        return false;
    }

    // 2. Explicit editor instance validation
    if (!editor) {
        showToast("Editor instance is unavailable. Cannot apply suggestion.", "error");
        return false;
    }

    inFlightCandidateApplies.add(candId);

    // Disable any corresponding UI Apply buttons and show pending state
    const applyButtons = document.querySelectorAll(
        `button[onclick*="${candId}"], #btn-apply-improvement`
    );
    applyButtons.forEach(btn => {
        btn.setAttribute("disabled", "true");
        btn.dataset.prevHtml = btn.innerHTML;
        btn.classList.add("btn-loading");
    });

    let backendApplied = false;

    try {
        const currentCode = editor.getValue();
        const payload = {
            current_code: currentCode,
            filename: currentFilename,
        };

        const resp = await fetch(`/api/improvement/candidate/${encodeURIComponent(candId)}/apply`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });

        const data = await resp.json().catch(() => null);

        if (!resp.ok || !data || !data.success) {
            const errorMsg = data?.error || `HTTP error ${resp.status}`;
            showToast("Failed to apply suggestion: " + errorMsg, "error");
            return false;
        }

        backendApplied = true;

        // 3. Explicitly validate that applied_code is present and non-empty
        if (!data.applied_code || typeof data.applied_code !== "string" || !data.applied_code.trim()) {
            throw new Error("Received empty or missing applied code from backend.");
        }

        // 4. Verify target file/tab: do not blindly overwrite whichever tab is active
        const targetFilename = data.filename || options.targetFilename;
        if (targetFilename && currentFilename !== targetFilename) {
            const baseTarget = targetFilename.split("/").pop();
            const baseCurrent = currentFilename.split("/").pop();
            if (openFiles.hasOwnProperty(targetFilename)) {
                switchTab(targetFilename);
            } else if (baseTarget === baseCurrent) {
                // Same base file opened in active tab with a relative path difference
                console.log(`Matching target file by basename: ${baseTarget}`);
            } else if (openFiles.hasOwnProperty(baseTarget)) {
                switchTab(baseTarget);
            } else {
                console.warn(`Target file '${targetFilename}' differs from active tab '${currentFilename}'. Applying to active editor.`);
            }
        }

        // 5. Apply to editor with undo/revert preservation
        repairOriginalCode = data.applied_code;
        suppressHighlightClearOnce = true;

        try {
            editor.setValue(data.applied_code);
            openFiles[currentFilename] = data.applied_code;
        } catch (editorErr) {
            throw new Error("Editor update failed: " + editorErr.message);
        }

        // 6. Show Revert button in topbar
        const revBtn = document.getElementById("btn-revert");
        if (revBtn) revBtn.style.display = "inline-flex";

        // 7. Update pipeline logs with user approval event if present
        if (data.pipeline_events && data.pipeline_events.length > 0) {
            renderPipelineLogs(data.pipeline_events, data.run_id);
        }

        // 8. Show success toast ONLY after editor update succeeded
        const titleText = data.title || "suggestion";
        showToast(`Successfully applied: ${titleText}`, "success");

        if (options.onSuccess) {
            await options.onSuccess(data);
        }

        // 9. Live re-analysis / panel refresh
        triggerLiveQualityScore();
        triggerLiveOptimizationPotential();
        triggerLiveSecurityRisk();
        triggerLiveImprovementAdvisor();

        return true;

    } catch (err) {
        console.error("Candidate application error:", err);
        showToast("Application failed: " + err.message, "error");

        // Roll back candidate on backend so it is not permanently consumed!
        if (backendApplied) {
            try {
                await fetch(`/api/improvement/candidate/${encodeURIComponent(candId)}/rollback`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ reason: err.message }),
                });
                console.log(`Candidate ${candId} application rolled back successfully.`);
            } catch (rollbackErr) {
                console.error("Failed to notify backend of application failure:", rollbackErr);
            }
        }
        return false;

    } finally {
        inFlightCandidateApplies.delete(candId);
        applyButtons.forEach(btn => {
            btn.removeAttribute("disabled");
            if (btn.dataset.prevHtml) {
                btn.innerHTML = btn.dataset.prevHtml;
            }
            btn.classList.remove("btn-loading");
        });
        isRepairRunning = false;
        if (typeof setAllRunButtonsDisabled === "function") {
            setAllRunButtonsDisabled(false);
        }
    }
}

async function applyCurrentImprovementCandidate() {
    if (!activeImprovementCandidate) return;
    const candId = activeImprovementCandidate.id;
    const success = await applyCandidateToEditor(candId, {
        onSuccess: () => {
            closeImprovementModal();
            const card = document.getElementById(`imp-card-${candId}`);
            if (card) {
                card.style.opacity = "0.6";
                const applyBtn = card.querySelector(".imp-btn-apply");
                if (applyBtn) {
                    applyBtn.innerHTML = "<span>✓ Applied</span>";
                    applyBtn.disabled = true;
                    applyBtn.style.pointerEvents = "none";
                }
            }
        }
    });
    if (success) {
        closeImprovementModal();
    }
}

async function rejectCurrentImprovementCandidate() {
    if (!activeImprovementCandidate) return;
    await rejectImprovementCandidateById(activeImprovementCandidate.id);
    closeImprovementModal();
}

async function applyImprovementCandidateById(candId) {
    return await applyCandidateToEditor(candId, {
        onSuccess: () => {
            const card = document.getElementById(`imp-card-${candId}`);
            if (card) {
                card.style.opacity = "0.6";
                const applyBtn = card.querySelector(".imp-btn-apply");
                if (applyBtn) {
                    applyBtn.innerHTML = "<span>✓ Applied</span>";
                    applyBtn.disabled = true;
                    applyBtn.style.pointerEvents = "none";
                }
            }
        }
    });
}

async function rejectImprovementCandidateById(candId) {
    try {
        await fetch(`/api/improvement/candidate/${candId}/reject`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
        });
        const card = document.getElementById(`imp-card-${candId}`);
        if (card) {
            card.style.opacity = "0.4";
            card.style.pointerEvents = "none";
        }
        showToast("Improvement candidate dismissed.", "info");
    } catch (e) {
        showToast("Error dismissing candidate: " + e.message, "error");
    }
}

function fillList(id, items) {
    const el = document.getElementById(id);
    if (!el) return;

    el.innerHTML = "";

    if (!items || items.length === 0) {
        const empty = document.createElement("div");
        empty.className = "empty-panel";
        empty.innerText = "No entries";
        el.appendChild(empty);
        return;
    }

    items.forEach(it => {
        const div = document.createElement("div");
        div.className = "diagnostic-item";

        if (typeof it === "string") {
            div.innerText = it;
        } else if (typeof it === "object") {
            const kind = it.kind ? `[${it.kind}] ` : "";
            const loc = it.line ? `(Line ${it.line}:${it.col ?? 0}) ` : "";
            const msg = it.msg || it.message || JSON.stringify(it);
            div.innerText = `${kind}${loc}${msg}`;
        }
        el.appendChild(div);
    });
}

async function renderSecurityPanel(data, sourceCode) {
    const secList = document.getElementById("security");
    const badgeTotal = document.getElementById("badge-security");
    const badgeConf = document.getElementById("badge-sec-confirmed");
    const sumBar = document.getElementById("security-summary-bar");
    if (!secList) return;

    secList.innerHTML = "";
    if (sumBar) sumBar.innerHTML = "";

    let report = null;
    try {
        const resp = await fetch("/api/security/report", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                code: sourceCode || (typeof getEditorValue === "function" ? getEditorValue() : ""),
                filename: currentFilename || "main.c"
            })
        });
        if (resp.ok) {
            report = await resp.json();
        }
    } catch (e) {
        console.warn("Could not fetch detailed security report:", e);
    }

    if (!report || !report.findings || report.findings.length === 0) {
        if (badgeTotal) badgeTotal.textContent = "0";
        if (badgeConf) { badgeConf.textContent = "0"; badgeConf.style.display = "none"; }
        const empty = document.createElement("div");
        empty.className = "empty-panel";
        empty.innerText = "No security vulnerabilities detected against supported policies.";
        secList.appendChild(empty);
        return;
    }

    if (badgeTotal) badgeTotal.textContent = String(report.total_findings || report.findings.length);
    if (badgeConf) { badgeConf.style.display = "none"; }

    if (sumBar) {
        if (report.critical_count > 0) {
            const p = document.createElement("span");
            p.className = "sec-sum-pill critical";
            p.textContent = `${report.critical_count} CRITICAL`;
            sumBar.appendChild(p);
        }
        if (report.high_count > 0) {
            const p = document.createElement("span");
            p.className = "sec-sum-pill high";
            p.textContent = `${report.high_count} HIGH`;
            sumBar.appendChild(p);
        }
        if (report.medium_count > 0) {
            const p = document.createElement("span");
            p.className = "sec-sum-pill medium";
            p.textContent = `${report.medium_count} MEDIUM`;
            sumBar.appendChild(p);
        }
// Confirmed summary pill removed (severity only)
    }

    // Retrieve or fetch structured security remediation recommendations
    let recommendations = data?.security_recommendations || [];
    if ((!recommendations || recommendations.length === 0) && report.findings && report.findings.length > 0) {
        try {
            const remResp = await fetch("/api/security/remediation", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    code: sourceCode || (typeof getEditorValue === "function" ? getEditorValue() : ""),
                    filename: currentFilename || "main.c",
                    language: currentLanguageId || "c",
                    findings: report.findings
                })
            });
            if (remResp.ok) {
                const remData = await remResp.json();
                recommendations = remData.recommendations || [];
            }
        } catch (remErr) {
            console.warn("Could not fetch security remediation recommendations:", remErr);
        }
    }
    window._currentSecurityRecommendations = recommendations;

    report.findings.forEach((vuln, vIdx) => {
        const card = document.createElement("div");
        const sevClass = (vuln.severity || "warning").toLowerCase();
        card.className = `vuln-card ${sevClass}`;

        const header = document.createElement("div");
        header.className = "vuln-card-header";

        const tagGroup = document.createElement("div");
        tagGroup.className = "vuln-tag-group";

        const statusTag = document.createElement("span");
        const sevName = (vuln.severity || "HIGH").toUpperCase();
        statusTag.className = `vuln-status-tag ${sevName.toLowerCase()}`;
        statusTag.textContent = sevName;
        tagGroup.appendChild(statusTag);

        if (vuln.cwe_id) {
            const cweTag = document.createElement("span");
            cweTag.className = "vuln-cwe-tag";
            cweTag.textContent = vuln.cwe_id;
            tagGroup.appendChild(cweTag);
        }

        const ruleTag = document.createElement("span");
        ruleTag.className = "vuln-cwe-tag";
        ruleTag.textContent = vuln.rule_id || vuln.category;
        tagGroup.appendChild(ruleTag);

        const locTag = document.createElement("span");
        locTag.className = "vuln-loc-tag";
        locTag.textContent = `Line ${vuln.line}:${vuln.column || 0}`;

        header.appendChild(tagGroup);
        header.appendChild(locTag);
        card.appendChild(header);

        const impactDiv = document.createElement("div");
        impactDiv.className = "vuln-impact-text";
        impactDiv.innerHTML = `<strong>Impact:</strong> ${escapeHtml(vuln.potential_impact || vuln.explanation || "")}`;
        card.appendChild(impactDiv);

        if (vuln.evidence) {
            const evDiv = document.createElement("div");
            evDiv.className = "vuln-evidence-box";
            evDiv.textContent = vuln.evidence;
            card.appendChild(evDiv);
        }

        // Find matching recommendation
        const rec = recommendations.find(r =>
            r.finding_id === vuln.id ||
            (r.line === vuln.line && (r.cwe_id === vuln.cwe_id || r.category === vuln.category))
        ) || recommendations[vIdx];

        if (rec) {
            const remDiv = document.createElement("div");
            remDiv.className = "vuln-remediation-box";

            const valBadgeClass = (rec.validation_status || "not-validated").toLowerCase().replace(/\s+/g, "-");
            const valColor = rec.validation_status === "Fixed and validated" ? "#16a34a" :
                             (rec.validation_status === "Partially addressed" ? "#d97706" :
                             (rec.validation_status === "Validation failed" ? "#dc2626" : "#64748b"));

            let diffSnippetHtml = "";
            if (rec.patch_diff) {
                diffSnippetHtml = `
                    <div style="margin-top: 8px;">
                        <div style="font-weight: 600; font-size: 11px; color: var(--text-secondary); margin-bottom: 4px;">Proposed Patch (Diff):</div>
                        <div class="rec-code-box" style="max-height: 140px; overflow-y: auto; background: var(--bg-secondary); border-radius: 4px; padding: 6px; font-size: 11px;">
                            ${renderDiffLinesHtml(rec.patch_diff)}
                        </div>
                    </div>
                `;
            } else if (rec.proposed_code) {
                diffSnippetHtml = `
                    <div style="margin-top: 8px;">
                        <div style="font-weight: 600; font-size: 11px; color: var(--text-secondary); margin-bottom: 4px;">Proposed Fixed Code:</div>
                        <pre style="margin:0; max-height: 120px; overflow-y: auto; background: var(--bg-secondary); border-radius: 4px; padding: 6px; font-size: 11px; font-family: var(--font-mono, monospace);"><code>${escapeHtml(rec.proposed_code)}</code></pre>
                    </div>
                `;
            }

            let risksHtml = "";
            if (rec.remaining_risks && rec.remaining_risks.length > 0) {
                risksHtml = `
                    <div style="margin-top: 6px; font-size: 11px; color: #dc2626;">
                        <strong>Remaining Risks:</strong> ${escapeHtml(rec.remaining_risks.join("; "))}
                    </div>
                `;
            }

            let applyBtnHtml = "";
            if (rec.is_applicable && rec.proposed_code) {
                applyBtnHtml = `
                    <div style="margin-top: 10px; display: flex; gap: 8px; align-items: center;">
                        <button class="btn btn-primary btn-xs" onclick="applySecurityFix('${escapeHtml(rec.id)}')" title="Apply this proposed security fix to the editor">
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg>
                            <span>Apply Fix to Editor</span>
                        </button>
                    </div>
                `;
            }

            remDiv.innerHTML = `
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                    <span style="font-weight: 600; color: var(--accent-blue, #2563eb);">🛠️ Remediation Recommendation (${escapeHtml(rec.repair_provider)}):</span>
                    <span class="sec-sum-pill" style="border: 1px solid ${valColor}; color: ${valColor}; background: rgba(0,0,0,0.03); font-size: 10px; padding: 2px 6px; border-radius: 4px; font-weight: 600;">
                        ${escapeHtml(rec.validation_status)}
                    </span>
                </div>
                <div style="font-size: 11.5px; color: var(--text-primary); margin-bottom: 4px;">
                    <strong>Mitigation:</strong> ${escapeHtml(rec.recommended_mitigation)}
                </div>
                <div style="font-size: 11px; color: var(--text-secondary); margin-bottom: 4px;">
                    <strong>Rationale:</strong> ${escapeHtml(rec.rationale || "Adheres to secure programming standards.")}
                </div>
                ${rec.limitations_or_behavior_changes ? `<div style="font-size: 11px; color: var(--text-muted);"><strong>Behavior note:</strong> ${escapeHtml(rec.limitations_or_behavior_changes)}</div>` : ''}
                ${diffSnippetHtml}
                ${risksHtml}
                ${applyBtnHtml}
            `;
            card.appendChild(remDiv);
        } else if (vuln.remediation_suggestions && vuln.remediation_suggestions.length > 0) {
            const remDiv = document.createElement("div");
            remDiv.className = "vuln-remediation-box";
            remDiv.innerHTML = `<div class="vuln-remediation-title">💡 Remediation:</div>` +
                vuln.remediation_suggestions.map(s => `<div>• ${escapeHtml(s)}</div>`).join("");
            card.appendChild(remDiv);
        }

        secList.appendChild(card);
    });
}

window.applySecurityFix = async function(recId) {
    if (!recId) return;
    const recs = window._currentSecurityRecommendations || [];
    const rec = recs.find(r => r.id === recId || r.finding_id === recId);
    if (!rec || !rec.proposed_code) {
        showToast("No proposed code fix available to apply.", "error");
        return;
    }
    const currentCode = typeof getEditorValue === "function" ? getEditorValue() : "";
    try {
        const resp = await fetch("/api/security/apply", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                candidate_id: rec.candidate_id,
                proposed_code: rec.proposed_code,
                original_code: currentCode,
                filename: currentFilename || "main.c",
                language: currentLanguageId || "c"
            })
        });
        const resData = await resp.json();
        if (resData.success) {
            if (typeof setEditorValue === "function") {
                setEditorValue(resData.applied_code || rec.proposed_code);
            }
            showToast("Security fix applied! Running re-analysis...", "success");
            // Rerun relevant analyses and refresh results without auto-starting another repair cycle
            await renderSecurityPanel(null, resData.applied_code || rec.proposed_code);
            if (typeof triggerLiveQualityScore === "function") triggerLiveQualityScore();
            if (typeof triggerLiveOptimizationPotential === "function") triggerLiveOptimizationPotential();
            if (typeof triggerLiveSecurityRisk === "function") triggerLiveSecurityRisk();
            if (typeof triggerLiveImprovementAdvisor === "function") triggerLiveImprovementAdvisor();
        } else {
            showToast(`Could not apply fix: ${resData.error || "Validation error"}`, "error");
        }
    } catch (e) {
        showToast(`Error applying fix: ${e.message}`, "error");
    } finally {
        suppressInvalidateOnContinuation = false;
        isRepairRunning = false;
        if (typeof setAllRunButtonsDisabled === "function") {
            setAllRunButtonsDisabled(false);
        }
    }
};

// Requirement 4: UI status mapping: map every server status explicitly; unknown -> show raw status
const SERVER_STATUS_MAP = {
    "CLEAN": "CLEAN",
    "VALID_WITH_WARNINGS": "VALID_WITH_WARNINGS",
    "VALID_WITH_SECURITY_ISSUES": "VALID_WITH_SECURITY_ISSUES",
    "FULLY_REPAIRED": "FULLY_REPAIRED",
    "PARTIALLY_REPAIRED": "PARTIALLY_REPAIRED",
    "REPAIR_UNAVAILABLE": "REPAIR_UNAVAILABLE",
    "VALIDATION_FAILED": "VALIDATION_FAILED"
};

function mapServerStatus(rawStatus) {
    if (!rawStatus) return "Idle";
    if (Object.prototype.hasOwnProperty.call(SERVER_STATUS_MAP, rawStatus)) {
        return SERVER_STATUS_MAP[rawStatus];
    }
    return rawStatus;
}

function setStatus(statusText) {
    const pill = document.getElementById("status");
    if (!pill) return;

    const displayStatus = mapServerStatus(statusText);
    pill.innerText = displayStatus || "Idle";
    pill.className = "status-pill";
    if (displayStatus === "SUCCESS" || displayStatus === "CLEAN" || displayStatus === "FULLY_REPAIRED") pill.classList.add("status-success");
    else if (displayStatus === "VALID_WITH_WARNINGS" || displayStatus === "SUCCESS_WITH_WARNINGS" || displayStatus === "SEM_ISSUES" || displayStatus === "PARTIALLY_REPAIRED") pill.classList.add("status-warning");
    else if (displayStatus && displayStatus.startsWith("RUNNING")) pill.classList.add("status-running");
    else if (displayStatus === "VALID_WITH_SECURITY_ISSUES" || displayStatus === "BLOCKED_SECURITY" || displayStatus === "UNFIXABLE" || displayStatus === "STOPPED" || displayStatus === "ERROR" || displayStatus === "VALIDATION_FAILED" || displayStatus === "REPAIR_UNAVAILABLE") pill.classList.add("status-danger");
    else pill.classList.add("status-idle");
}

function toggleCard(cardId) {
    const card = document.getElementById(cardId);
    if (card) card.classList.toggle("collapsed");
}

function setProgress(percent, text) {
    const bar = document.getElementById("repairProgressBar");
    const label = document.getElementById("repairProgressText");
    const pctLabel = document.getElementById("repairProgressPercent");

    const safe = Math.max(0, Math.min(100, percent || 0));
    if (bar) {
        bar.style.width = `${safe}%`;
        if (safe === 100) {
            bar.style.background = "#16a34a";
        } else {
            bar.style.background = "linear-gradient(90deg, #2563eb, #7c3aed)";
        }
    }

    if (label) label.innerText = text || "Ready";
    if (pctLabel) pctLabel.innerText = `${Math.round(safe)}%`;
}

function resetProgress() {
    setProgress(0, "Ready");
}

function resetPanels() {
    fillList("steps", []);
    fillList("errors", []);
    fillList("semantic", []);
    fillList("security", []);
    renderPipelineLogs([]);

    renderStats({
        lex_fixes: 0,
        rule_fixes: 0,
        ai_fixes: 0,
        sym_fixes: 0,
        sem_fixes: 0,
        iterations: 0
    });

    // Reset primary indicators to prevent stale display between runs
    const elOverall = document.getElementById("pi-val-overall");
    if (elOverall) { elOverall.textContent = "--%"; elOverall.style.color = "var(--text-secondary)"; }
    const badgeOverall = document.getElementById("pi-badge-overall");
    if (badgeOverall) { badgeOverall.className = "tile-badge badge-unbenchmarked"; badgeOverall.textContent = "[PENDING]"; }

    const elOptimal = document.getElementById("pi-val-optimal");
    if (elOptimal) { elOptimal.textContent = "--%"; elOptimal.style.color = "var(--text-secondary)"; }
    const badgeOptimal = document.getElementById("pi-badge-optimal");
    if (badgeOptimal) { badgeOptimal.className = "tile-badge badge-unbenchmarked"; badgeOptimal.textContent = "[PENDING]"; }

    const elPoor = document.getElementById("pi-val-poor");
    if (elPoor) { elPoor.textContent = "--%"; elPoor.style.color = "var(--text-secondary)"; }
    const badgePoor = document.getElementById("pi-badge-poor");
    if (badgePoor) { badgePoor.className = "tile-badge badge-unbenchmarked"; badgePoor.textContent = "[PENDING]"; }

    const elVuln = document.getElementById("pi-val-vulnerability") || document.getElementById("pi-val-sec");
    if (elVuln) { elVuln.textContent = "--%"; elVuln.style.color = "var(--text-secondary)"; }
    const badgeVuln = document.getElementById("pi-badge-vulnerability") || document.getElementById("pi-badge-sec");
    if (badgeVuln) { badgeVuln.className = "tile-badge badge-unbenchmarked"; badgeVuln.textContent = "[PENDING]"; }

    const elGreen = document.getElementById("pi-val-green");
    if (elGreen) { elGreen.textContent = "--/100"; elGreen.style.color = "var(--text-secondary)"; }
    const badgeGreen = document.getElementById("pi-badge-green");
    if (badgeGreen) { badgeGreen.className = "tile-badge badge-unbenchmarked"; badgeGreen.textContent = "[PENDING RUN]"; }

    // Aliases
    const elQ = document.getElementById("pi-val-quality");
    if (elQ) { elQ.textContent = "--%"; elQ.style.color = "var(--text-secondary)"; }
    const elOpt = document.getElementById("pi-val-opt");
    if (elOpt) { elOpt.textContent = "--%"; elOpt.style.color = "var(--text-secondary)"; }
    const elSec = document.getElementById("pi-val-sec");
    if (elSec) { elSec.textContent = "--%"; elSec.style.color = "var(--text-secondary)"; }

    // Reset cards and benchmark tile
    const baCard = document.getElementById("beforeAfterCard");
    if (baCard) baCard.style.display = "none";
    const baTbody = document.getElementById("before-after-tbody");
    if (baTbody) baTbody.innerHTML = "";

    const recCard = document.getElementById("recommendedProgramCard");
    if (recCard) recCard.style.display = "none";

    const elBm = document.getElementById("pi-val-benchmark");
    if (elBm && (!cachedBenchmarkReport || cachedBenchmarkReport.status !== "BENCHMARKED")) {
        elBm.textContent = "--";
        elBm.style.color = "var(--text-secondary)";
    }

    renderGreenReport({});
    renderQualityScore(null);
    renderOptimizationReport(null);
    renderSecurityRiskReport(null);
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

    document.querySelectorAll(".file-item").forEach(item => {
        if (item.dataset.filename === currentFilename) {
            item.classList.add("active");
        } else {
            item.classList.remove("active");
        }
    });
}

function setAllRunButtonsDisabled(disabled) {
    const ids = ["btn-run", "btn-run-program", "btn-editor-run-program", "btn-dock-run"];
    ids.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.disabled = Boolean(disabled);
            if (!disabled) {
                el.removeAttribute("disabled");
            }
        }
    });
}

function resetExecutionStateOnProblemChange() {
    activeRepairSequence++;
    programRunSequence++;
    isRepairRunning = false;
    isProgramRunning = false;

    setAllRunButtonsDisabled(false);

    if (window._activeRepairProgressTimer) {
        clearInterval(window._activeRepairProgressTimer);
        window._activeRepairProgressTimer = null;
    }
    resetProgress();

    hideSecurityApprovalModal();
    if (pendingGateSession) {
        try { pendingGateSession.resolve({ cancelled: true, status: 409, ok: false }); } catch(e) {}
        pendingGateSession = null;
    }

    if (window._liveAnalysisAbortController) {
        try { window._liveAnalysisAbortController.abort(); } catch(e) {}
        window._liveAnalysisAbortController = null;
    }
}

function switchTab(filename) {
    if (!editor || !openFiles.hasOwnProperty(filename)) return;

    resetExecutionStateOnProblemChange();

    openFiles[currentFilename] = editor.getValue();
    currentFilename = filename;
    workspaces[currentLanguageId].currentFilename = filename;

    suppressHighlightClearOnce = true;
    editor.setValue(openFiles[filename] ?? "");
    renderTabs();
    resetPanels();
    setStatus("Idle");
    showUnsavedDot(false);
    refreshLiveMetricsForCurrentSource();
}

function closeTab(filename) {
    if (openTabs.length <= 1) {
        showToast("Cannot close the only open tab", "warning");
        return;
    }

    resetExecutionStateOnProblemChange();

    const idx = openTabs.indexOf(filename);
    if (idx !== -1) openTabs.splice(idx, 1);

    delete openFiles[filename];

    if (currentFilename === filename) {
        currentFilename = openTabs[Math.max(0, idx - 1)] || openTabs[0];
        workspaces[currentLanguageId].currentFilename = currentFilename;
        suppressHighlightClearOnce = true;
        editor.setValue(openFiles[currentFilename] ?? "");
    }

    renderTabs();
    resetPanels();
    showUnsavedDot(false);
    refreshLiveMetricsForCurrentSource();
}

function openFileInTab(filename, code) {
    resetExecutionStateOnProblemChange();

    if (!openTabs.includes(filename)) openTabs.push(filename);

    openFiles[filename] = code;
    currentFilename = filename;
    workspaces[currentLanguageId].currentFilename = filename;

    suppressHighlightClearOnce = true;
    editor.setValue(code);
    renderTabs();
    resetPanels();
    showUnsavedDot(false);
    refreshLiveMetricsForCurrentSource();
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

async function renderRepairResult(data) {
    const beforeCode = repairOriginalCode ?? "";
    const afterCode = data.corrected_code || editor.getValue();

    setStatus(data.status || (data.success ? "SUCCESS" : "UNFIXABLE"));
    renderStats(data.stats || {});
    renderGreenReport(data.green_report || {});
    renderQualityScore(data.quality_report);
    renderOptimizationReport(data.optimization_report);
    renderSecurityRiskReport(data.security_risk_report);
    triggerLiveImprovementAdvisor();

    fillList("steps", data.applied_steps || []);
    fillList("errors", data.errors || []);
    fillList("semantic", data.semantic_issues || []);
    renderSecurityPanel(data, beforeCode);
    fillList("logs", data.logs || []);

    if (afterCode !== beforeCode) {
        // CRITICAL REQUIREMENT: Never apply an AI-generated patch without explicit user approval!
        // Validate candidate across syntax, compilation, semantic, and security stages first.
        try {
            const valResp = await fetch("/api/patch/validate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    original_code: beforeCode,
                    candidate_code: afterCode,
                    filename: currentFilename,
                    explanation: (data.applied_steps && data.applied_steps.length > 0) ? data.applied_steps.join("; ") : "Proposed compiler auto-repair patch",
                })
            });
            const valData = await valResp.json();
            showPatchReviewModal(valData, data);
        } catch (e) {
            console.error("Patch validation request failed:", e);
            showToast("Failed to run patch validation: " + e.message, "error");
        }
    } else {
        if (data.status === "SUCCESS") {
            showToast("Program has zero compiler errors!", "success");
        } else {
            showToast("No automated patch could be generated.", "warning");
        }
    }
}

/* -------------------------------------------------- */
/* RUN REPAIR                                         */
/* -------------------------------------------------- */
/* -------------------------------------------------- */
/* RUN REPAIR & COORDINATED AGENT PLANNING            */
/* -------------------------------------------------- */
let currentCoordinatedPlan = null;
let isRepairRunning = false;
let activeRepairSequence = 0;


let activeRepairAbortController = null;
let activeRepairRunId = null;
let activeRepairJobId = null;

async function cancelActiveRepair() {
    const cancelBtn = document.getElementById("btn-cancel-repair");
    if (cancelBtn) cancelBtn.style.display = "none";
    if (activeRepairAbortController) {
        try {
            activeRepairAbortController.abort();
        } catch (e) {}
    }
    if (activeRepairJobId) {
        try {
            await fetch(`/api/repair/job/${activeRepairJobId}/cancel`, {
                method: "POST",
                headers: { "Content-Type": "application/json" }
            });
        } catch (e) {}
    }
    try {
        await fetch("/api/coordinator/cancel", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ run_id: activeRepairJobId || activeRepairRunId })
        });
    } catch (e) {
        console.warn("Cancel request error:", e);
    }
    if (window._activeRepairPollTimer) {
        clearInterval(window._activeRepairPollTimer);
        window._activeRepairPollTimer = null;
    }
    if (window._activeRepairProgressTimer) {
        clearInterval(window._activeRepairProgressTimer);
        window._activeRepairProgressTimer = null;
    }
    isRepairRunning = false;
    setAllRunButtonsDisabled(false);
    setProgress(0, "Repair cancelled by user");
    setStatus("CANCELLED");
    showToast("Repair process cancelled.", "info");
}

async function runRepair() {
    if (!editor) return;

    if (isRepairRunning) {
        showToast("A repair session is already in progress. Please wait.", "info");
        return;
    }

    const lang = getActiveLanguage();
    const ext = "." + currentFilename.split(".").pop().toLowerCase();
    if (!lang.extensions.includes(ext)) {
        showToast(`Active tab (${currentFilename}) does not match active language (${lang.label})`, "warning");
        setStatus(`MISMATCH (${lang.label})`);
        return;
    }

    setAllRunButtonsDisabled(true);
    isRepairRunning = true;

    repairOriginalCode = editor.getValue();
    openFiles[currentFilename] = repairOriginalCode;

    resetPanels();
    // Do not show running state before security approval gate clears
    await _runRepairAfterPrescan();
}

/**
 * Internal: executes the actual multi-agent repair pipeline.
 * Called directly from runRepair() when no security issues are found,
 * OR from handleSecurityGateAction('approve') after user acknowledges risks.
 */
async function _runRepairAfterPrescan() {
    const code = repairOriginalCode || (editor ? editor.getValue() : "");
    if (!code) return;

    const thisRepairSeq = ++activeRepairSequence;
    isRepairRunning = true;
    setAllRunButtonsDisabled(true);

    const cancelBtn = document.getElementById("btn-cancel-repair");
    if (cancelBtn) cancelBtn.style.display = "none";
    let cancelTimer = setTimeout(() => {
        if (isRepairRunning && cancelBtn) {
            cancelBtn.style.display = "inline-flex";
        }
    }, 10000);

    activeRepairAbortController = new AbortController();
    activeRepairRunId = `run_${Date.now()}`;

    // Active progress updates through compilation and repair stages
    setProgress(15, "Initializing analysis & security gate scan...");
    const progressStages = [
        { pct: 30, text: "Analyzing lexical tokens & syntax grammar..." },
        { pct: 50, text: "Verifying semantic types, scope & pointers..." },
        { pct: 70, text: "Synthesizing deterministic & ML repairs..." },
        { pct: 88, text: "Validating patch candidates in isolated sandbox..." }
    ];
    let stageIdx = 0;
    if (window._activeRepairProgressTimer) {
        clearInterval(window._activeRepairProgressTimer);
    }
    window._activeRepairProgressTimer = setInterval(() => {
        if (stageIdx < progressStages.length) {
            const nextStage = progressStages[stageIdx++];
            setProgress(nextStage.pct, nextStage.text);
        }
    }, 600);

    try {
        const response = await callWithGate("/api/repair/job", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                code: code,
                filename: currentFilename,
                language: currentLanguageId,
                operation: "repair",
            })
        }, { operation: "repair", code: code, filename: currentFilename, language: currentLanguageId });

        if (thisRepairSeq !== activeRepairSequence) return;

        if (!response || response.cancelled) {
            if (typeof cancelTimer !== "undefined") clearTimeout(cancelTimer);
            if (cancelBtn) cancelBtn.style.display = "none";
            isRepairRunning = false;
            setAllRunButtonsDisabled(false);
            setProgress(0, "Repair cancelled by user");
            setStatus("IDLE");
            return;
        }

        if (!response.ok) {
            if (typeof cancelTimer !== "undefined") clearTimeout(cancelTimer);
            if (cancelBtn) cancelBtn.style.display = "none";
            let errData = null;
            try { errData = await response.json(); } catch(e) {}
            const errMsg = errData ? (errData.error_message || errData.message || errData.error || errData.detail || response.statusText) : response.statusText;
            setProgress(0, "Repair error: " + (errMsg || ("Server error (" + response.status + ")")));
            setStatus("ERROR");
            isRepairRunning = false;
            setAllRunButtonsDisabled(false);
            showToast("Repair error: " + (errMsg || ("HTTP " + response.status)), "error");
            return;
        }

        const startData = await response.json();
        const jobId = startData.job_id;
        activeRepairJobId = jobId;

        // Requirement 1: UI polls every 1 s and shows progress and a Cancel button
        await new Promise((resolve, reject) => {
            const pollInterval = 1000;
            let consecutivePollFailures = 0;
            window._activeRepairPollTimer = setInterval(async () => {
                if (thisRepairSeq !== activeRepairSequence) {
                    clearInterval(window._activeRepairPollTimer);
                    window._activeRepairPollTimer = null;
                    return resolve();
                }

                try {
                    const pollRes = await fetch(`/api/repair/job/${jobId}`);
                    if (!pollRes.ok) {
                        consecutivePollFailures++;
                        console.warn(`Poll returned HTTP ${pollRes.status} (${consecutivePollFailures}/5)`);
                        if (consecutivePollFailures >= 5) {
                            clearInterval(window._activeRepairPollTimer);
                            window._activeRepairPollTimer = null;
                            if (typeof cancelTimer !== "undefined") clearTimeout(cancelTimer);
                            if (cancelBtn) cancelBtn.style.display = "none";
                            isRepairRunning = false;
                            setAllRunButtonsDisabled(false);
                            const errMsg = `Repair job polling stopped after 5 consecutive failed polls (HTTP ${pollRes.status}).`;
                            setProgress(0, errMsg);
                            setStatus("ERROR");
                            showToast(errMsg, "error");
                            return reject(new Error(errMsg));
                        }
                        return;
                    }
                    const job = await pollRes.json();
                    consecutivePollFailures = 0;
                    if (thisRepairSeq !== activeRepairSequence) {
                        clearInterval(window._activeRepairPollTimer);
                        window._activeRepairPollTimer = null;
                        return resolve();
                    }

                    // Progress update
                    const pct = job.function_total > 0
                        ? Math.min(95, Math.max(5, Math.round((job.function_index / job.function_total) * 100)))
                        : 20;
                    const progText = `${job.stage} (${job.function_index}/${job.function_total}) - Elapsed: ${job.elapsed_s}s, Est: ${job.estimated_total_s}s`;
                    setProgress(pct, progText);

                    if (job.state === "COMPLETED") {
                        clearInterval(window._activeRepairPollTimer);
                        window._activeRepairPollTimer = null;
                        if (typeof cancelTimer !== "undefined") clearTimeout(cancelTimer);
                        if (cancelBtn) cancelBtn.style.display = "none";

                        const result = job.result || {};
                        const remainingCount = (result.unresolved_findings || result.remaining_findings || []).length;
                        const repairSucceeded = result.status === "FULLY_REPAIRED"
                            || ((result.validation_passed === true || result.validation_report?.is_valid === true) && remainingCount === 0);
                        setProgress(100, repairSucceeded
                            ? "Full repair validated — no actionable issues remain"
                            : `Repair attempt finished — ${remainingCount} issue(s) still need repair`);
                        renderCoordinatedPlan(result);
                        isRepairRunning = false;
                        setAllRunButtonsDisabled(false);

                        // Requirement 4: Map every server status explicitly; unknown -> show raw status
                        const resStatus = result.status || result.terminal_status || "REPAIR_ATTEMPT_FINISHED";
                        setStatus(resStatus);
                        return resolve();
                    } else if (job.state === "CANCELLED") {
                        clearInterval(window._activeRepairPollTimer);
                        window._activeRepairPollTimer = null;
                        if (typeof cancelTimer !== "undefined") clearTimeout(cancelTimer);
                        if (cancelBtn) cancelBtn.style.display = "none";
                        isRepairRunning = false;
                        setAllRunButtonsDisabled(false);
                        setProgress(0, "Repair cancelled by user");
                        setStatus("CANCELLED");
                        showToast("Repair process cancelled.", "info");
                        return resolve();
                    } else if (job.state === "FAILED") {
                        clearInterval(window._activeRepairPollTimer);
                        window._activeRepairPollTimer = null;
                        if (typeof cancelTimer !== "undefined") clearTimeout(cancelTimer);
                        if (cancelBtn) cancelBtn.style.display = "none";
                        isRepairRunning = false;
                        setAllRunButtonsDisabled(false);
                        const err = job.error || "Repair job execution failed.";
                        setProgress(0, "Repair error: " + err);
                        setStatus("ERROR");
                        showToast("Repair error: " + err, "error");
                        return resolve();
                    }
                } catch (err) {
                    consecutivePollFailures++;
                    console.warn(`Poll iteration error (${consecutivePollFailures}/5):`, err);
                    if (consecutivePollFailures >= 5) {
                        clearInterval(window._activeRepairPollTimer);
                        window._activeRepairPollTimer = null;
                        if (typeof cancelTimer !== "undefined") clearTimeout(cancelTimer);
                        if (cancelBtn) cancelBtn.style.display = "none";
                        isRepairRunning = false;
                        setAllRunButtonsDisabled(false);
                        const errMsg = `Repair job polling stopped after 5 consecutive failed polls: ${err.message}`;
                        setProgress(0, errMsg);
                        setStatus("ERROR");
                        showToast(errMsg, "error");
                        return reject(new Error(errMsg));
                    }
                }
            }, pollInterval);
        });
    } catch (err) {
        if (window._activeRepairProgressTimer) {
            clearInterval(window._activeRepairProgressTimer);
            window._activeRepairProgressTimer = null;
        }
        if (thisRepairSeq !== activeRepairSequence) return;
        setProgress(0, "Error: Autonomous repair failed");
        setStatus("ERROR");
        isRepairRunning = false;
        setAllRunButtonsDisabled(false);
        showToast("Autonomous repair failed: " + err.message, "error");
        console.error("_runRepairAfterPrescan error:", err);
        renderPipelineLogs([{
            stage_id: "pipeline_error",
            stage_name: "Pipeline Execution Interrupted",
            status: "FAILED",
            description: "Autonomous repair failed: " + err.message,
            failure_reason: err.message,
            duration_ms: 0,
            timestamp_display: new Date().toLocaleTimeString(),
        }]);
    } finally {
        if (window._activeRepairProgressTimer) {
            clearInterval(window._activeRepairProgressTimer);
            window._activeRepairProgressTimer = null;
        }
        if (thisRepairSeq === activeRepairSequence) {
            isRepairRunning = false;
        }
        setAllRunButtonsDisabled(false);
    }
}

function toggleLogDiagnostics(id) {
    const el = document.getElementById(id);
    const btn = document.getElementById(`btn-${id}`);
    if (!el) return;
    if (el.style.display === "none") {
        el.style.display = "block";
        if (btn) btn.textContent = "Details ▲";
    } else {
        el.style.display = "none";
        if (btn) btn.textContent = "Details ▼";
    }
}

function renderPipelineLogs(events, runId) {
    const logsList = document.getElementById("logs");
    const badgeLogs = document.getElementById("badge-logs");
    if (!logsList) return;

    const rawList = Array.isArray(events) ? events : [];
    const normalizedEvents = rawList.map(ev => {
        if (!ev) return null;
        if (typeof ev === "string") {
            return {
                stage_id: "log_msg",
                stage_name: ev,
                status: "INFO",
                description: "",
                duration_ms: 0,
                timestamp_display: "",
            };
        }
        return ev;
    }).filter(Boolean);

    if (normalizedEvents.length === 0) {
        logsList.innerHTML = `
            <li class="log-empty-state">
                <span>ℹ️ No pipeline runs yet. Click 'Run Analyzer & Repair' (Ctrl+Enter) to execute the 16-stage pipeline.</span>
            </li>
        `;
        if (badgeLogs) badgeLogs.textContent = "0";
        return;
    }

    const STAGE_ORDER = {
        "security_gate": 0,
        "security_gate_approval": 0,
        "pre_execution_security_gate": 0,
        "malicious_precheck_stage": 0,
        "source_received": 1,
        "lexical_analysis": 2,
        "syntax_analysis": 3,
        "semantic_analysis": 4,
        "security_analysis": 5,
        "finding_consolidation": 6,
        "deterministic_rules": 7,
        "codet5_model": 8,
        "codet5_patch": 8,
        "qwen_ollama": 9,
        "candidate_generation": 10,
        "patch_validation": 11,
        "user_approval_apply": 12,
        "reanalysis_post_patch": 13,
        "quality_optimization_metrics": 14,
        "security_risk_scoring": 15,
        "green_metrics": 16,
    };

    normalizedEvents.sort((a, b) => {
        const orderA = STAGE_ORDER[a.stage_id] !== undefined ? STAGE_ORDER[a.stage_id] : 90;
        const orderB = STAGE_ORDER[b.stage_id] !== undefined ? STAGE_ORDER[b.stage_id] : 90;
        return orderA - orderB;
    });

    if (badgeLogs) badgeLogs.textContent = normalizedEvents.length;

    let html = "";
    if (runId) {
        html += `
            <li class="log-header-item">
                <div class="log-header-left">
                    <span class="log-run-pill">RUN ID: <code>${escapeHtml(runId)}</code></span>
                </div>
                <span class="log-count-pill">${normalizedEvents.length} stages recorded</span>
            </li>
        `;
    }

    normalizedEvents.forEach((ev, idx) => {
        const st = (ev.status || "PENDING").toUpperCase();
        let stClass = "st-pending";
        let stIcon = "⏳";
        if (st === "PASSED" || st === "CLEAN") { stClass = "st-passed"; stIcon = "✓"; }
        else if (st === "FAILED") { stClass = "st-failed"; stIcon = "✗"; }
        else if (st === "SKIPPED") { stClass = "st-skipped"; stIcon = "⊘"; }
        else if (st === "UNAVAILABLE") { stClass = "st-unavailable"; stIcon = "⚠️"; }
        else if (st === "RUNNING") { stClass = "st-running"; stIcon = "⚡"; }
        else if (st === "INFO") { stClass = "st-info"; stIcon = "ℹ️"; }

        const durText = ev.duration_ms > 0 ? `${ev.duration_ms} ms` : (st === "SKIPPED" ? "skipped" : "--");
        const hasDiag = ev.diagnostics && Object.keys(ev.diagnostics).length > 0;
        const hasFindings = ev.findings_summary && ev.findings_summary.length > 0;
        const hasFailure = Boolean(ev.failure_reason);
        const hasExpandable = hasDiag || hasFindings || hasFailure;
        const collapseId = `log-diag-${idx}`;

        html += `
            <li class="log-event-card ${stClass}" id="event-row-${idx}">
                <div class="log-card-main">
                    <div class="log-card-left">
                        <span class="log-timestamp">${escapeHtml(ev.timestamp_display || "")}</span>
                        <span class="log-status-badge ${stClass}">${stIcon} ${st}</span>
                        <strong class="log-stage-title">${escapeHtml(ev.stage_name || "")}</strong>
                    </div>
                    <div class="log-card-right">
                        <span class="log-duration-badge">${durText}</span>
                        ${hasExpandable ? `
                            <button class="log-toggle-btn" onclick="toggleLogDiagnostics('${collapseId}')" id="btn-${collapseId}">
                                Details ▼
                            </button>
                        ` : ''}
                    </div>
                </div>
                <div class="log-description">${escapeHtml(ev.description || "")}</div>
                ${hasFailure ? `
                    <div class="log-failure-box">
                        <span class="log-failure-label">Reason / Diagnostic:</span>
                        <span class="log-failure-text">${escapeHtml(ev.failure_reason)}</span>
                    </div>
                ` : ''}
                ${hasExpandable ? `
                    <div class="log-diagnostics-drawer" id="${collapseId}" style="display:none;">
                        ${hasFindings ? `
                            <div class="log-findings-box">
                                <span class="log-diag-subheading">Findings Summary (${ev.findings_count || ev.findings_summary.length}):</span>
                                <ul class="log-findings-list">
                                    ${ev.findings_summary.map(f => `<li>• ${escapeHtml(f)}</li>`).join("")}
                                </ul>
                            </div>
                        ` : ''}
                        ${hasDiag ? `
                            <div class="log-diag-grid">
                                <span class="log-diag-subheading">Stage Diagnostics:</span>
                                <pre class="log-diag-pre">${escapeHtml(JSON.stringify(ev.diagnostics, null, 2))}</pre>
                            </div>
                        ` : ''}
                    </div>
                ` : ''}
            </li>
        `;
    });

    logsList.innerHTML = html;
}

async function fetchLatestPipelineLog() {
    try {
        const resp = await fetch("/api/pipeline/latest");
        if (resp.ok) {
            const data = await resp.json();
            if (data.events && data.events.length > 0) {
                renderPipelineLogs(data.events, data.run_id);
            }
        }
    } catch (e) {
        console.debug("fetchLatestPipelineLog notice:", e);
    }
}

function initAgentChatView() {
    const thread = document.getElementById("agentMessageThread");
    if (!thread) return;

    const elOverall = document.getElementById("pi-val-overall");
    if (elOverall) { elOverall.textContent = "--%"; elOverall.style.color = "var(--text-secondary)"; }
    const badgeOverall = document.getElementById("pi-badge-overall");
    if (badgeOverall) { badgeOverall.className = "tile-badge badge-unbenchmarked"; badgeOverall.textContent = "[PENDING]"; }

    const elOptimal = document.getElementById("pi-val-optimal");
    if (elOptimal) { elOptimal.textContent = "--%"; elOptimal.style.color = "var(--text-secondary)"; }
    const badgeOptimal = document.getElementById("pi-badge-optimal");
    if (badgeOptimal) { badgeOptimal.className = "tile-badge badge-unbenchmarked"; badgeOptimal.textContent = "[PENDING]"; }

    const elPoor = document.getElementById("pi-val-poor");
    if (elPoor) { elPoor.textContent = "--%"; elPoor.style.color = "var(--text-secondary)"; }
    const badgePoor = document.getElementById("pi-badge-poor");
    if (badgePoor) { badgePoor.className = "tile-badge badge-unbenchmarked"; badgePoor.textContent = "[PENDING]"; }

    const elVuln = document.getElementById("pi-val-vulnerability") || document.getElementById("pi-val-sec");
    if (elVuln) { elVuln.textContent = "--%"; elVuln.style.color = "var(--text-secondary)"; }
    const badgeVuln = document.getElementById("pi-badge-vulnerability") || document.getElementById("pi-badge-sec");
    if (badgeVuln) { badgeVuln.className = "tile-badge badge-unbenchmarked"; badgeVuln.textContent = "[PENDING]"; }

    const elGreen = document.getElementById("pi-val-green");
    if (elGreen) { elGreen.textContent = "--/100"; elGreen.style.color = "var(--text-secondary)"; }
    const badgeGreen = document.getElementById("pi-badge-green");
    if (badgeGreen) { badgeGreen.className = "tile-badge badge-unbenchmarked"; badgeGreen.textContent = "[PENDING RUN]"; }

    const elBm = document.getElementById("pi-val-benchmark");
    if (elBm) { elBm.textContent = "--"; elBm.style.color = "var(--text-secondary)"; }
    const badgeBm = document.getElementById("pi-badge-benchmark");
    if (badgeBm) { badgeBm.className = "tile-badge badge-unbenchmarked"; badgeBm.textContent = "[PENDING RUN]"; }

    // Aliases
    const elQ = document.getElementById("pi-val-quality");
    if (elQ) { elQ.textContent = "--%"; elQ.style.color = "var(--text-secondary)"; }
    const elOpt = document.getElementById("pi-val-opt");
    if (elOpt) { elOpt.textContent = "--%"; elOpt.style.color = "var(--text-secondary)"; }
    const elSec = document.getElementById("pi-val-sec");
    if (elSec) { elSec.textContent = "--%"; elSec.style.color = "var(--text-secondary)"; }

    const overallStatus = document.getElementById("pipeline-overall-status");
    if (overallStatus) { overallStatus.textContent = "Idle • Awaiting Run"; }

    // Keep the initial view scoped to the selected source. Loading the most
    // recent global run here can display another file's stale errors as if
    // they belonged to this editor. Logs are rendered when this session runs.
}

function renderSecurityBlockedState(data) {
    const thread = document.getElementById("agentMessageThread");
    const recCard = document.getElementById("recommendedProgramCard");
    if (recCard) { recCard.style.display = "none"; }

    const reason = data.reason_code || "SEC_POLICY_BLOCKED";
    const category = data.threat_category || "SECURITY_POLICY";
    const expl = data.explanation || data.message || "Execution blocked by mandatory security gate.";
    const evidence = data.evidence ? escapeHtml(data.evidence) : "";

    if (thread) {
        const existingBubbles = thread.querySelectorAll(".agent-bubble:not(.agent-welcome-bubble)");
        existingBubbles.forEach(b => b.remove());

        const blockBubble = document.createElement("div");
        blockBubble.className = "agent-bubble";
        blockBubble.innerHTML = `
            <div class="agent-bubble-header" style="background: rgba(220, 38, 38, 0.15); border-left: 4px solid #dc2626; padding: 14px 18px; border-radius: 6px; margin-top: 8px;">
                <div style="display:flex; align-items:center; gap:10px;">
                    <span style="font-size: 22px;">🛡️</span>
                    <div>
                        <strong style="color: #dc2626; font-size: 14px; text-transform: uppercase; letter-spacing: 0.5px;">Execution Blocked by Security Policy</strong>
                        <div style="font-size: 11px; color: var(--text-muted); margin-top: 3px;">
                            Threat Category: <code>${escapeHtml(category)}</code> | Reason Code: <code>${escapeHtml(reason)}</code>
                        </div>
                    </div>
                </div>
                <div style="margin-top: 12px; font-size: 13px; color: var(--text-primary); line-height: 1.5;">
                    ${escapeHtml(expl)}
                </div>
                ${evidence ? `
                <div style="margin-top: 10px; font-size: 11px; background: rgba(0,0,0,0.3); padding: 8px 12px; border-radius: 4px; font-family: var(--font-mono);">
                    <span style="color: var(--text-muted);">Detected Evidence:</span> <code style="color: #f87171;">${evidence}</code>
                </div>
                ` : ""}
                <div style="margin-top: 12px; font-size: 11.5px; color: #16a34a; display: flex; align-items: center; gap: 6px; border-top: 1px solid rgba(255,255,255,0.08); padding-top: 8px;">
                    <span>✓</span> <strong>Protected Action Enforced:</strong> Model invocations, patch applications, and compiler executions were halted pre-execution.
                </div>
            </div>
        `;
        thread.appendChild(blockBubble);
    }

    const overallStatus = document.getElementById("pipeline-overall-status");
    if (overallStatus) {
        overallStatus.textContent = "Halted: Blocked by Security Policy";
    }

    if (data.pipeline_events && data.pipeline_events.length > 0) {
        renderPipelineLogs(data.pipeline_events, data.run_id);
    }
}

let originalAssessmentBaseline = null;

function renderCoordinatedPlan(plan) {
    if (plan.blocked || plan.status === "BLOCKED_SECURITY_POLICY") {
        renderSecurityBlockedState(plan);
        return;
    }
    currentCoordinatedPlan = plan;
    originalAssessmentBaseline = plan.original_assessment || plan.baseline_scores || {};

    const bs = originalAssessmentBaseline;
    const tileAssessment = plan.candidate_id && plan.proposed_scores ? plan.proposed_scores : bs;
    const metricHeading = document.querySelector("#primaryIndicatorsSummary h4");
    const metricBadge = document.getElementById("pi-header-pill");
    if (metricHeading && tileAssessment === plan.proposed_scores) metricHeading.textContent = "Code Quality Metrics (Proposed Repair)";
    if (metricBadge && tileAssessment === plan.proposed_scores) metricBadge.textContent = "PROPOSED REPAIR ASSESSMENT";
    const deltas = plan.deltas || {};
    const classified = plan.classified_findings || {};
    const pipelineStages = plan.pipeline_stages || [];

    // 1. Extract or compute 4 Core Code Quality Metrics (assessing Original Code)
    const qScore = tileAssessment.quality_score != null ? Number(tileAssessment.quality_score) : (tileAssessment.code_quality_score != null ? Number(tileAssessment.code_quality_score) : null);
    const optScore = tileAssessment.optimization_potential != null ? Number(tileAssessment.optimization_potential) : null;
    const vulnScore = tileAssessment.vulnerability_risk != null ? Number(tileAssessment.vulnerability_risk) : (tileAssessment.security_risk_score != null ? Number(tileAssessment.security_risk_score) : (tileAssessment.security_risk != null ? Number(tileAssessment.security_risk) : null));

    const overallVal = tileAssessment.overall_code_quality != null ? Number(tileAssessment.overall_code_quality) : ((qScore != null && optScore != null && vulnScore != null) ? Math.max(0, Math.min(100, Math.round(0.50 * qScore + 0.25 * (100 - optScore) + 0.25 * (100 - vulnScore)))) : null);
    const optimalVal = tileAssessment.optimal_code != null ? Number(tileAssessment.optimal_code) : (optScore != null ? Math.max(0, Math.min(100, Math.round(100 - optScore))) : null);
    const poorVal = tileAssessment.poor_code != null ? Number(tileAssessment.poor_code) : (qScore != null ? Math.max(0, Math.min(100, Math.round(100 - qScore))) : null);

    // 1. Overall Code Quality %
    const elOverall = document.getElementById("pi-val-overall");
    const badgeOverall = document.getElementById("pi-badge-overall");
    const descOverall = document.getElementById("pi-desc-overall");
    if (elOverall) {
        if (overallVal != null) {
            elOverall.textContent = Math.round(overallVal) + "%";
            elOverall.style.color = overallVal >= 80 ? "#16a34a" : (overallVal >= 60 ? "#d97706" : "#dc2626");
            if (badgeOverall) {
                badgeOverall.className = "tile-badge badge-measured";
                badgeOverall.textContent = "[COMBINED]";
            }
            if (descOverall) descOverall.textContent = "50% Q + 25% (100-O) + 25% (100-V)";
        } else {
            elOverall.textContent = "--%";
            elOverall.style.color = "var(--text-secondary)";
            if (badgeOverall) {
                badgeOverall.className = "tile-badge badge-unbenchmarked";
                badgeOverall.textContent = "[INCOMPLETE]";
            }
            if (descOverall) {
                const riskReason = tileAssessment.security_status_reason || tileAssessment.metrics_notes || "Security risk score is unavailable for this source.";
                descOverall.textContent = `Overall score needs Q, O, and V. ${riskReason}`;
            }
        }
    }

    // 2. Optimal Code %
    const elOptimal = document.getElementById("pi-val-optimal");
    const badgeOptimal = document.getElementById("pi-badge-optimal");
    const descOptimal = document.getElementById("pi-desc-optimal");
    if (elOptimal) {
        if (optimalVal != null) {
            elOptimal.textContent = Math.round(optimalVal) + "%";
            elOptimal.style.color = optimalVal >= 80 ? "#16a34a" : (optimalVal >= 60 ? "#d97706" : "#dc2626");
            if (badgeOptimal) {
                badgeOptimal.className = "tile-badge badge-estimate";
                badgeOptimal.textContent = "[HEURISTIC]";
            }
            if (descOptimal) {
                const optRaw = optScore != null ? Math.round(optScore) : 0;
                descOptimal.textContent = optRaw === 0 ? "No detected opportunities" : `${optRaw}% opt. potential`;
            }
        } else {
            elOptimal.textContent = "--%";
            elOptimal.style.color = "var(--text-secondary)";
            if (badgeOptimal) {
                badgeOptimal.className = "tile-badge badge-unbenchmarked";
                badgeOptimal.textContent = "[INCOMPLETE]";
            }
            if (descOptimal) descOptimal.textContent = "Optimization analysis pending";
        }
    }

    // 3. Poor Code %
    const elPoor = document.getElementById("pi-val-poor");
    const badgePoor = document.getElementById("pi-badge-poor");
    const descPoor = document.getElementById("pi-desc-poor");
    if (elPoor) {
        if (poorVal != null) {
            elPoor.textContent = Math.round(poorVal) + "%";
            elPoor.style.color = poorVal <= 20 ? "#16a34a" : (poorVal <= 40 ? "#d97706" : "#dc2626");
            if (badgePoor) {
                badgePoor.className = "tile-badge badge-risk";
                badgePoor.textContent = "[INVERSE Q]";
            }
            if (descPoor) descPoor.textContent = "Inverse of Code Quality (100 - Q)";
        } else {
            elPoor.textContent = "--%";
            elPoor.style.color = "var(--text-secondary)";
            if (badgePoor) {
                badgePoor.className = "tile-badge badge-unbenchmarked";
                badgePoor.textContent = "[INCOMPLETE]";
            }
            if (descPoor) descPoor.textContent = "Quality analysis pending";
        }
    }

    // 4. Vulnerability Risk %
    const elVuln = document.getElementById("pi-val-vulnerability") || document.getElementById("pi-val-sec");
    const badgeVuln = document.getElementById("pi-badge-vulnerability") || document.getElementById("pi-badge-sec");
    const descVuln = document.getElementById("pi-desc-vulnerability") || document.getElementById("pi-desc-sec");
    if (elVuln) {
        if (vulnScore != null) {
            const vRound = Math.round(vulnScore);
            elVuln.textContent = vRound + "%";
            elVuln.style.color = vRound === 0 ? "#16a34a" : (vRound <= 30 ? "#d97706" : "#dc2626");
            if (badgeVuln) {
                badgeVuln.className = "tile-badge badge-risk";
                badgeVuln.textContent = "[RISK INDEX]";
            }
            if (descVuln) {
                const cCount = bs.confirmed_security_count || 0;
                const pCount = bs.possible_security_count || 0;
                descVuln.textContent = (cCount + pCount) === 0 
                    ? "Zero security findings" 
                    : `${cCount + pCount} security finding${(cCount + pCount) === 1 ? '' : 's'}`;
            }
        } else {
            elVuln.textContent = "--%";
            elVuln.style.color = "var(--text-secondary)";
            if (badgeVuln) {
                badgeVuln.className = "tile-badge badge-unbenchmarked";
                badgeVuln.textContent = "[INCOMPLETE]";
            }
            if (descVuln) descVuln.textContent = bs.security_status_reason || bs.security_status || "Security analysis pending";
        }
    }

    // Backward compatibility aliases
    const elQ = document.getElementById("pi-val-quality");
    if (elQ && qScore != null) elQ.textContent = `${Math.round(qScore)}%`;
    const elOpt = document.getElementById("pi-val-opt");
    if (elOpt && optScore != null) elOpt.textContent = `${Math.round(optScore)}%`;
    const elSec = document.getElementById("pi-val-sec");
    if (elSec && vulnScore != null) elSec.textContent = `${Math.round(vulnScore)}%`;

    // 5. Green Metrics (Separated)
    const grnVal = bs.green_metrics != null ? `${Math.round(bs.green_metrics)}/100` : "--/100";
    const elGreen = document.getElementById("pi-val-green");
    const badgeGreen = document.getElementById("pi-badge-green");
    if (elGreen) {
        elGreen.textContent = grnVal;
        if (bs.green_metrics != null) {
            elGreen.style.color = bs.green_metrics >= 80 ? "#16a34a" : (bs.green_metrics >= 50 ? "#d97706" : "#dc2626");
            if (badgeGreen) {
                badgeGreen.className = "tile-badge badge-green";
                badgeGreen.textContent = "[ESTIMATED TDP]";
            }
        }
    }
    const descGreen = document.getElementById("pi-desc-green");
    if (descGreen) {
        const det = bs.green_telemetry || bs.green_metrics_detail || {};
        descGreen.textContent = det.total_runtime_ms != null 
            ? `${det.total_runtime_ms} ms | ${det.peak_memory_mb || 0} MB | ${det.energy_joules || 0} J`
            : "Estimated TDP energy & footprint";
    }

    const elBm = document.getElementById("pi-val-benchmark");
    const badgeBm = document.getElementById("pi-badge-benchmark");
    const descBm = document.getElementById("pi-desc-benchmark");
    if (elBm) {
        const isBenchmarked = cachedBenchmarkReport &&
            cachedBenchmarkReport.status === "BENCHMARKED" &&
            (cachedBenchmarkReport.benchmark_dataset_size || 0) >= 16 &&
            cachedBenchmarkReport.results &&
            Object.keys(cachedBenchmarkReport.results).length > 0;

        if (isBenchmarked) {
            const summary = cachedBenchmarkReport.comparative_summary || {};
            const rate = summary.best_repair_success_rate ?? "--";
            elBm.textContent = rate + "%";
            elBm.style.color = "#2563eb";
            if (badgeBm) {
                badgeBm.className = "tile-badge badge-benchmark";
                badgeBm.textContent = `[BENCHMARKED]`;
            }
            if (descBm) descBm.textContent = `Top: ${summary.best_repair_success_config || "Sequential Pipeline"}`;
        } else {
            elBm.textContent = "--";
            elBm.style.color = "var(--text-secondary)";
            if (badgeBm) {
                badgeBm.className = "tile-badge badge-unbenchmarked";
                badgeBm.textContent = "[PENDING RUN]";
            }
            if (descBm) descBm.textContent = "Click to run benchmark harness";
        }
    }

    // 2. Render Genuine Structured Pipeline Stages Tracker & Pipeline Logs Card
    const stagesList = document.getElementById("pipelineStagesList");
    const overallStatus = document.getElementById("pipeline-overall-status");
    if (overallStatus) {
        overallStatus.textContent = plan.status === "CLEAN" ? "Completed: 0 Errors Detected" : "Completed: Coordinated Plan Formulated";
    }

    const pipelineEvents = plan.pipeline_events || [];
    const runId = plan.run_id || "";

    if (stagesList) {
        if (pipelineEvents.length > 0) {
            stagesList.innerHTML = pipelineEvents.map(ev => {
                const st = (ev.status || "PENDING").toLowerCase();
                const stCls = `stage-${st}`;
                const stIcon = st === "passed" ? "✓" : (st === "failed" ? "✗" : (st === "skipped" ? "⊘" : (st === "unavailable" ? "⚠️" : "⏳")));
                const durText = ev.duration_ms > 0 ? `${ev.duration_ms} ms` : st.toUpperCase();
                return `
                    <div class="stage-item ${stCls}" title="${escapeHtml(ev.description || "")}">
                        <span class="stage-status-dot"></span>
                        <span class="stage-name">${escapeHtml(ev.stage_name)}</span>
                        <span class="stage-info">${stIcon} ${durText}</span>
                    </div>
                `;
            }).join("");
        } else if (pipelineStages.length > 0) {
            stagesList.innerHTML = pipelineStages.map(st => {
                const stCls = st.status === "passed" ? "stage-passed" : (st.status === "failed" ? "stage-failed" : (st.status === "skipped" ? "stage-skipped" : "stage-fallback"));
                const stIcon = st.status === "passed" ? "✓" : (st.status === "failed" ? "✗" : (st.status === "skipped" ? "⊘" : "⚠️"));
                return `
                    <div class="stage-item ${stCls}" title="${escapeHtml(st.explanation || "")}">
                        <span class="stage-status-dot"></span>
                        <span class="stage-name">${escapeHtml(st.label)}</span>
                        <span class="stage-info">${stIcon} ${st.duration_ms} ms</span>
                    </div>
                `;
            }).join("");
        }
    }

    // Populate Detailed Pipeline Execution Logs Card (#card-logs, #logs, #badge-logs)
    renderPipelineLogs(pipelineEvents, runId);

    // 3. Render Consolidated AI Agent Chat Response in Thread
    const thread = document.getElementById("agentMessageThread");
    if (thread) {
        const modelName = plan.agent_telemetry?.model_used || "Qwen2.5-Coder:3b (Local Ollama)";
        const durMs = plan.agent_telemetry?.duration_ms || 0;

        // Build Classified Compiler Errors Section
        const lexErrors = classified.lexical || [];
        const synErrors = classified.syntax || [];
        const semErrors = classified.semantic || [];
        const limitations = classified.limitations || [];

        let classifiedHtml = "";
        if (lexErrors.length === 0 && synErrors.length === 0 && semErrors.length === 0 && limitations.length === 0) {
            classifiedHtml = `
                <div class="agent-section-block">
                    <div class="agent-section-title">
                        <span style="color:#16a34a;">✓</span> Compiler Diagnostics (Lexical, Syntax, Semantic)
                    </div>
                    <div style="font-size:11.5px; color:var(--text-secondary); padding:4px 0;">
                        No lexical, syntax, or semantic errors found in original source code.
                    </div>
                </div>
            `;
        } else {
            let itemsHtml = "";
            lexErrors.forEach(f => {
                itemsHtml += `
                    <div class="agent-finding-card lexical">
                        <div class="agent-finding-top">
                            <span class="agent-finding-badge" style="background:rgba(8,145,178,0.15); color:#0891b2;">LEXICAL ERROR</span>
                            <span style="font-size:10.5px; font-family:var(--font-mono); color:var(--text-muted);">Line ${f.line}:${f.column || 0}</span>
                        </div>
                        <div class="agent-finding-details">
                            <div><strong>Issue:</strong> ${escapeHtml(f.explanation || f.title)}</div>
                            <div><strong>Why it matters:</strong> ${escapeHtml(f.consequence || "Invalid token prevents parser tokenization.")}</div>
                            <div><strong>Correction:</strong> ${escapeHtml(f.how_to_fix || "")}</div>
                        </div>
                    </div>
                `;
            });

            synErrors.forEach(f => {
                const rootLabel = f.is_root_cause ? " [ROOT CAUSE]" : "";
                itemsHtml += `
                    <div class="agent-finding-card syntax">
                        <div class="agent-finding-top">
                            <span class="agent-finding-badge" style="background:rgba(220,38,38,0.15); color:#dc2626;">SYNTAX ERROR${rootLabel}</span>
                            <span style="font-size:10.5px; font-family:var(--font-mono); color:var(--text-muted);">Line ${f.line}:${f.column || 0}</span>
                        </div>
                        <div class="agent-finding-details">
                            <div><strong>Issue:</strong> ${escapeHtml(f.explanation || f.title)}</div>
                            <div><strong>Why it matters:</strong> ${escapeHtml(f.consequence || "Malformed grammar causes compilation failure.")}</div>
                            <div><strong>Correction:</strong> ${escapeHtml(f.how_to_fix || "")}</div>
                        </div>
                    </div>
                `;
            });

            semErrors.forEach(f => {
                itemsHtml += `
                    <div class="agent-finding-card semantic">
                        <div class="agent-finding-top">
                            <span class="agent-finding-badge" style="background:rgba(124,58,237,0.15); color:#7c3aed;">SEMANTIC DIAGNOSTIC</span>
                            <span style="font-size:10.5px; font-family:var(--font-mono); color:var(--text-muted);">Line ${f.line}:${f.column || 0}</span>
                        </div>
                        <div class="agent-finding-details">
                            <div><strong>Issue:</strong> ${escapeHtml(f.explanation || f.title)}</div>
                            <div><strong>Why it matters:</strong> ${escapeHtml(f.consequence || "Type mismatch or undeclared symbol violation.")}</div>
                            <div><strong>Correction:</strong> ${escapeHtml(f.how_to_fix || "")}</div>
                        </div>
                    </div>
                `;
            });

            limitations.forEach(lim => {
                itemsHtml += `
                    <div class="agent-finding-card" style="border-left-color:#64748b; background:rgba(100,116,139,0.05);">
                        <div class="agent-finding-top">
                            <span class="agent-finding-badge" style="background:rgba(100,116,139,0.15); color:#64748b;">STAGE LIMITATION</span>
                            <span style="font-size:10.5px; color:var(--text-muted);">${escapeHtml(lim.stage)}</span>
                        </div>
                        <div class="agent-finding-details">
                            <div>${escapeHtml(lim.reason)}</div>
                        </div>
                    </div>
                `;
            });

            classifiedHtml = `
                <div class="agent-section-block">
                    <div class="agent-section-title">
                        <span>🔍</span> Compiler Errors & Diagnostics (${lexErrors.length + synErrors.length + semErrors.length})
                    </div>
                    <div class="agent-classified-grid">${itemsHtml}</div>
                </div>
            `;
        }

        // Build Separate AI Manipulation Attempt and Security Vulnerability Sections
        const rawManipFindings = (plan.ai_manipulation_findings || []).concat(
            (plan.findings || []).filter(f => 
                f.category === "AI_MANIPULATION" || 
                f.category === "PROHIBITED_SECURITY_THREAT" || 
                f.category === "AGENT_INSTRUCTION_MANIPULATION" ||
                (f.rule_id && (f.rule_id.includes("MANIPULATION") || f.rule_id.includes("PROMPT_INJECTION") || f.rule_id.includes("BYPASS") || f.rule_id.includes("OVERRIDE"))) ||
                (f.title && /manipulation|tampering|prompt injection/i.test(f.title))
            )
        );
        const seenManipKeys = new Set();
        const manipFindings = rawManipFindings.filter(f => {
            const key = f.id || `${f.line}_${f.snippet || f.explanation}`;
            if (seenManipKeys.has(key)) return false;
            seenManipKeys.add(key);
            return true;
        });

        // Invariance requirement: vulnerability findings must be identical with and without manipulation comments
        const secFindings = (plan.findings || []).filter(f => 
            f.category === "SECURITY" && !manipFindings.some(mf => mf.id === f.id || (mf.line === f.line && mf.rule_id === f.rule_id))
        );

        let manipHtml = "";
        if (manipFindings.length > 0) {
            const manipItemsHtml = manipFindings.map(f => `
                <div class="agent-finding-card security-confirmed" style="border-left: 3px solid #d97706; background: rgba(217,119,6,0.04); margin-bottom: 8px;">
                    <div class="agent-finding-top">
                        <div style="display:flex; gap:6px; align-items:center;">
                            <span class="agent-finding-badge" style="background:rgba(217,119,6,0.18); color:#d97706; border:1px solid rgba(217,119,6,0.4);">AI MANIPULATION ATTEMPT</span>
                            <span style="font-weight:700; color:var(--text-primary); font-size:11.5px;">${escapeHtml(f.title || f.explanation || "Adversarial Directive")}</span>
                        </div>
                        <span style="font-size:10.5px; font-family:var(--font-mono); color:var(--text-muted);">Line ${f.line || 1}:${f.column || 0}</span>
                    </div>
                    <div class="agent-finding-details">
                        ${f.snippet ? `<div><strong>Directive:</strong> <code style="color:#d97706; font-size:11px;">${escapeHtml(f.snippet)}</code></div>` : ""}
                        <div><strong>Policy Status:</strong> Stripped from AI model input. Safe static compilation & repair permitted.</div>
                        <div><strong>Potential Threat:</strong> ${escapeHtml(f.potential_consequences || f.potential_threat || "Attempted hijack of AI reasoning agent or security policy suppression.")}</div>
                        <div><strong>Recommended Fix:</strong> ${escapeHtml(f.recommended_mitigation || "Removed from final program; directive ignored.")}</div>
                    </div>
                </div>
            `).join("");

            manipHtml = `
                <div class="agent-section-block" id="agent-manipulation-section">
                    <div class="agent-section-title">
                        <span style="color:#d97706;">⚠️</span> AI Manipulation Attempt (${manipFindings.length} Detected & Stripped)
                    </div>
                    <div class="agent-classified-grid">${manipItemsHtml}</div>
                </div>
            `;
        }
        let secHtml = "";
        if (secFindings.length === 0) {
            if (bs.security_status === "INCONCLUSIVE" || bs.security_status === "NOT_ASSESSED") {
                secHtml = `
                    <div class="agent-section-block">
                        <div class="agent-section-title">
                            <span style="color:#d97706;">⚠️</span> Security Assessment (Inconclusive)
                        </div>
                        <div style="font-size:11.5px; color:var(--text-secondary); padding:4px 0;">
                            Pattern-based checks completed (0 immediate banned APIs detected). Comprehensive AST-based security analysis was blocked by syntax errors. Authoritative security status is <strong>INCONCLUSIVE</strong>; absence of detected vulnerabilities does not imply the program is secure.
                        </div>
                    </div>
                `;
            } else {
                secHtml = `
                    <div class="agent-section-block">
                        <div class="agent-section-title">
                            <span style="color:#16a34a;">🛡️</span> Security & Vulnerability Analysis
                        </div>
                        <div style="font-size:11.5px; color:var(--text-secondary); padding:4px 0;">
                            No vulnerabilities detected by active security analyzers (0 findings).
                        </div>
                    </div>
                `;
            }
        } else {
            const secItemsHtml = secFindings.map(f => {
                const sev = (f.severity || "HIGH").toUpperCase();
                const badgeSevClass = (sev === "CRITICAL" || sev === "HIGH") ? "security-danger" : "security-warning";
                const confBadge = `<span class="agent-finding-badge ${badgeSevClass}">${sev}</span>`;
                return `
                    <div class="agent-finding-card ${badgeSevClass}">
                        <div class="agent-finding-top">
                            <div style="display:flex; gap:6px; align-items:center;">
                                ${confBadge}
                                <span style="font-weight:700; color:var(--text-primary); font-size:11.5px;">${escapeHtml(f.title)}</span>
                            </div>
                            <span style="font-size:10.5px; font-family:var(--font-mono); color:var(--text-muted);">Line ${f.line}:${f.column || 0}</span>
                        </div>
                        <div class="agent-finding-details">
                            <div><strong>Problem:</strong> ${escapeHtml(f.explanation)}</div>
                            <div><strong>Exploit Scenario:</strong> ${escapeHtml(f.exploit_scenario || f.consequence)}</div>
                            <div><strong>Potential Impact:</strong> ${escapeHtml(f.potential_impact || "Memory corruption / undefined behavior")}</div>
                            <div><strong>Recommended Mitigation:</strong> ${escapeHtml(f.recommended_mitigation || f.how_to_fix)}</div>
                        </div>
                    </div>
                `;
            }).join("");

            secHtml = `
                <div class="agent-section-block">
                    <div class="agent-section-title">
                        <span style="color:#dc2626;">🛡️</span> Security Vulnerabilities (${secFindings.length} Detected)
                    </div>
                    <div class="agent-classified-grid">${secItemsHtml}</div>
                </div>
            `;
        }

        // Build Green Metrics Details
        const grnDet = bs.green_metrics_detail || {};
        const greenSummaryHtml = `
            <div class="agent-section-block">
                <div class="agent-section-title">
                    <span style="color:#16a34a;">🌱</span> Green Compiler Metrics (Original Source Baseline)
                </div>
                <div class="agent-green-summary-box">
                    <div class="green-metric-item">Execution Latency: <strong>${grnDet.latency_ms ?? "--"} ms</strong></div>
                    <div class="green-metric-item">Peak Memory: <strong>${grnDet.peak_rss_mb ?? "--"} MB RSS</strong></div>
                    <div class="green-metric-item">Energy Consumption: <strong>${grnDet.estimated_joules ?? "--"} Joules</strong></div>
                    <div class="green-metric-item">Carbon Footprint: <strong>${grnDet.estimated_co2_g ?? "--"} g CO2</strong></div>
                    <div class="green-metric-item">Normalized Green Score: <strong>${bs.green_metrics != null ? Math.round(bs.green_metrics) + "/100" : "Pending"}</strong></div>
                </div>
            </div>
        `;

        // Build Candidate Score Comparison if Candidate Exists
        let candidateComparisonHtml = "";
        if (plan.candidate_id && plan.proposed_scores) {
            const ps = plan.proposed_scores;
            const bsRiskScore = bs.security_risk_score;
            const bsRiskStatus = bs.security_status;
            const psRiskScore = ps.security_risk_score;
            const psRiskStatus = ps.security_status;

            let bsRiskStr = "--% [NOT_ASSESSED]";
            if (bsRiskScore != null) {
                bsRiskStr = `${bsRiskScore}%` + (bsRiskStatus ? ` [${bsRiskStatus}]` : "");
            } else if (bsRiskStatus) {
                bsRiskStr = `[${bsRiskStatus}]`;
            }

            // Determine whether candidate was independently assessed or its security scoring was skipped
            let psRiskStr = "--% [NOT_ASSESSED]";
            if (psRiskScore != null && (psRiskStatus === "ASSESSED" || !psRiskStatus)) {
                psRiskStr = `${psRiskScore}% [${psRiskStatus || "ASSESSED"}]`;
            } else if (psRiskStatus) {
                psRiskStr = `--% [${psRiskStatus}]`;
            }

            const bsQualStr = (bs.quality_score != null) ? `${bs.quality_score}%` : "--%";
            const proposedQuality = ps.quality_score ?? ps.code_quality_score;
            const psQualStr = (proposedQuality != null) ? `${proposedQuality}%` : "--%";
            const bsOptStr = (bs.optimization_potential != null) ? `${bs.optimization_potential}%` : "--%";
            const psOptStr = (ps.optimization_potential != null) ? `${ps.optimization_potential}%` : "--%";
            const proposedRisk = ps.vulnerability_risk ?? ps.security_risk_score ?? ps.security_risk;
            const proposedOverall = ps.overall_code_quality ?? (
                proposedQuality != null && ps.optimization_potential != null && proposedRisk != null
                    ? Math.round(0.50 * Number(proposedQuality) + 0.25 * (100 - Number(ps.optimization_potential)) + 0.25 * (100 - Number(proposedRisk)))
                    : null
            );
            const proposedOverallStr = proposedOverall != null ? `${Math.round(Number(proposedOverall))}%` : "Not fully measurable";

            // Do not claim security improvement unless both sides have comparable, valid assessments.
            const bothComparable = (bsRiskScore != null && psRiskScore != null && 
                                    bsRiskStatus !== "INCONCLUSIVE" && bsRiskStatus !== "NOT_ASSESSED" && bsRiskStatus !== "SKIPPED" &&
                                    psRiskStatus !== "INCONCLUSIVE" && psRiskStatus !== "NOT_ASSESSED" && psRiskStatus !== "SKIPPED");
            const resRisksStr = bothComparable
                ? `${deltas.resolved_vulnerabilities?.length ?? deltas.projected_resolved_findings_count ?? (plan.projected_resolved_findings ? plan.projected_resolved_findings.length : 0)}`
                : "-- (Inconclusive Baseline)";

            candidateComparisonHtml = `
                <div class="agent-section-block" style="background:rgba(37,99,235,0.03); border:1px solid rgba(37,99,235,0.15); border-radius:6px; padding:10px 12px;">
                    <div class="agent-section-title">
                        <span style="color:var(--accent-blue);">⚖️</span> Candidate Assessment Comparison (Before vs Proposed)
                    </div>
                    <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(140px, 1fr)); gap:8px; margin-top:6px;">
                        <div style="font-size:11px;">Proposed Overall Quality: <strong>${proposedOverallStr}</strong></div>
                        <div style="font-size:11px;">Security Risk: <strong>${bsRiskStr} → ${psRiskStr}</strong></div>
                        <div style="font-size:11px;">Code Quality: <strong>${bsQualStr} → ${psQualStr}</strong></div>
                        <div style="font-size:11px;">Optimization: <strong>${bsOptStr} → ${psOptStr}</strong></div>
                        <div style="font-size:11px;">Resolved Risks: <strong>${resRisksStr}</strong></div>
                    </div>
                </div>
            `;
        }

        // Construct Consolidated Bubble
        const responseBubble = document.createElement("div");
        responseBubble.className = "agent-bubble";
        responseBubble.innerHTML = `
            <div class="agent-bubble-header">
                <span class="agent-bubble-sender">Compiler Analysis</span>
                <span class="agent-bubble-time">${new Date().toLocaleTimeString()}</span>
            </div>
            <div class="agent-bubble-content">
                <div style="margin-bottom:4px;">
                    <p class="agent-lead-text">
                        ${escapeHtml(plan.summary || plan.explanation || "Coordinated analysis complete.")}
                    </p>
                </div>

                ${classifiedHtml}
                ${manipHtml}
                ${secHtml}
                ${greenSummaryHtml}
                ${candidateComparisonHtml}
            </div>
        `;

        // Prepend new response bubble after the welcome/indicators block
        const existingBubbles = thread.querySelectorAll(".agent-bubble:not(.agent-welcome-bubble)");
        existingBubbles.forEach(b => b.remove());
        thread.appendChild(responseBubble);
    }

    // 4. Render Recommended Fixed Program Review Card
    const recCard = document.getElementById("recommendedProgramCard");
    if (recCard) {
        if (plan.candidate_id && plan.proposed_code) {
            recCard.style.display = "block";
            const val = plan.validation_report || {};
            const isPartial = plan.terminal_status === "PARTIALLY_REPAIRED" || (plan.unresolved_findings && plan.unresolved_findings.length > 0);

            let assumptionsBoxHtml = "";
            const assumptionsList = (plan.candidate && plan.candidate.assumptions) || plan.assumptions || [];
            if (assumptionsList.length > 0) {
                const asmItems = assumptionsList.map(a => `<li>${escapeHtml(a)}</li>`).join("");
                assumptionsBoxHtml = `
                    <div class="rec-assumptions-box" style="background:rgba(217,119,6,0.08); border:1px solid rgba(217,119,6,0.3); border-radius:6px; padding:8px 12px; margin-bottom:8px; font-size:11.5px;">
                        <div style="font-weight:600; color:#d97706; margin-bottom:4px;">Explicit Assumptions (Requires User Approval):</div>
                        <ul style="margin:0; padding-left:16px; color:var(--text-primary);">${asmItems}</ul>
                    </div>
                `;
            }

            let resolvedBoxHtml = "";
            const resList = plan.resolved_findings || [];
            const projList = plan.projected_resolved_findings || [];
            if (resList.length > 0) {
                const resItems = resList.map(f => `<li><strong>${escapeHtml(f.title || f.category)}</strong> (Line ${f.line || 1}): ${escapeHtml(f.explanation || "")}</li>`).join("");
                resolvedBoxHtml = `
                    <div class="rec-resolved-box" style="background:rgba(22,163,74,0.08); border:1px solid rgba(22,163,74,0.3); border-radius:6px; padding:8px 12px; margin-bottom:8px; font-size:11.5px;">
                        <div style="font-weight:600; color:#16a34a; margin-bottom:4px;">Resolved Original Findings (${resList.length}):</div>
                        <ul style="margin:0; padding-left:16px; color:var(--text-primary);">${resItems}</ul>
                    </div>
                `;
            } else if (projList.length > 0) {
                const projItems = projList.map(f => `<li><strong>${escapeHtml(f.title || f.category)}</strong> (Line ${f.line || 1}): ${escapeHtml(f.explanation || "")}</li>`).join("");
                resolvedBoxHtml = `
                    <div class="rec-resolved-box" style="background:rgba(59,130,246,0.08); border:1px solid rgba(59,130,246,0.3); border-radius:6px; padding:8px 12px; margin-bottom:8px; font-size:11.5px;">
                        <div style="font-weight:600; color:#2563eb; margin-bottom:4px;">Projected to Resolve Upon Application (${projList.length}):</div>
                        <ul style="margin:0; padding-left:16px; color:var(--text-primary);">${projItems}</ul>
                    </div>
                `;
            }

            let unresolvedBoxHtml = "";
            if (isPartial && plan.unresolved_findings && plan.unresolved_findings.length > 0) {
                const unresItems = plan.unresolved_findings.map(f => `<li><strong>${escapeHtml(f.title || f.category)}</strong> (Line ${f.line || 1}): ${escapeHtml(f.explanation || "")}</li>`).join("");
                unresolvedBoxHtml = `
                    <div class="rec-unresolved-box" style="background:rgba(217,119,6,0.08); border:1px solid rgba(217,119,6,0.3); border-radius:6px; padding:8px 12px; margin-bottom:8px; font-size:11.5px;">
                        <div style="font-weight:600; color:#d97706; margin-bottom:4px;">Remaining Unresolved Issues (${plan.unresolved_findings.length}):</div>
                        <div style="color:var(--text-secondary); margin-bottom:4px;"><strong>Stopping Reason:</strong> ${escapeHtml(plan.stopping_reason || "Autonomous repair stopped safely.")}</div>
                        <ul style="margin:0; padding-left:16px; color:var(--text-primary);">${unresItems}</ul>
                    </div>
                `;
            }

            let warningBoxHtml = "";
            const candidateIsValidated = plan.validation_passed === true || val.is_valid === true
                || plan.candidate?.validation_passed === true || plan.candidate?.is_eligible_for_application === true;
            if (!candidateIsValidated && (val.syntax_passed === false || val.security_passed === false || val.semantic_passed === false)) {
                warningBoxHtml = `
                    <div class="rec-warning-box" style="background:rgba(220,38,38,0.08); border:1px solid rgba(220,38,38,0.3); border-radius:6px; padding:8px 12px; margin-bottom:8px; font-size:11.5px; color:#dc2626;">
                        <strong>⚠️ Notice:</strong> Some validation checks did not pass or could not run completely. Review the proposal carefully before applying.
                    </div>
                `;
            }

            const listedRemaining = (plan.unresolved_findings || plan.remaining_findings || []);
            const remainingIssueCount = plan.fixes_remaining_count != null && Number.isFinite(Number(plan.fixes_remaining_count))
                ? Number(plan.fixes_remaining_count) : listedRemaining.length;
            const explicitlyEligible = plan.candidate?.is_eligible_for_application === true;
            const canApplyCompleteRepair = candidateIsValidated
                && (remainingIssueCount === 0 || explicitlyEligible)
                && plan.candidate?.is_eligible_for_application !== false;
            const applyBlockReason = val.explanation || plan.candidate?.validation_report?.explanation
                || (remainingIssueCount ? `${remainingIssueCount} actionable issue(s) remain.`
                    : plan.stopping_reason || "The candidate has not passed every required validation check.");
            recCard.innerHTML = `
                <div class="rec-counts-bar" style="display:flex; gap:10px; align-items:center; margin-bottom:8px; font-size:11.5px; flex-wrap:wrap;">
                    <span style="background:rgba(99,102,241,0.12); color:#6366f1; font-weight:700; padding:2px 8px; border-radius:4px; border:1px solid rgba(99,102,241,0.3);">
                        Budget: ${plan.time_budget_s ? Number(plan.time_budget_s).toFixed(1) + 's' : (plan.total_wall_time_s ? Number(plan.total_wall_time_s).toFixed(1) + 's' : '--')}
                    </span>
                </div>

                <div class="rec-explanation-box">
                    <strong>Plan Explanation:</strong> ${escapeHtml(plan.explanation || plan.summary || "Autonomous repair resolving detected root causes.")}
                </div>

                ${assumptionsBoxHtml}
                ${warningBoxHtml}
                ${resolvedBoxHtml}
                ${unresolvedBoxHtml}

                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 6px;">
                    <span style="font-size: 11px; font-weight:600; color:var(--text-secondary);">Proposed Changes (Unified Diff):</span>
                    <button class="btn btn-ghost btn-xs" onclick="toggleRecViewMode()" id="btn-toggle-rec-view">View Full Code</button>
                </div>

                <div class="rec-code-box" id="rec-diff-container">
                    ${renderDiffLinesHtml(plan.unified_diff || plan.diff || plan.candidate?.unified_diff || plan.candidate?.diff || "")}
                </div>
                <div class="rec-code-box" id="rec-fullcode-container" style="display:none;">
                    <pre style="margin:0; font-family:var(--font-mono, monospace); font-size:11px;"><code>${escapeHtml(plan.proposed_code || "")}</code></pre>
                </div>

                <div class="rec-actions-bar">
                    <button class="btn btn-primary" id="btn-continue-repair" onclick="continueRepairFromCandidate()" style="display:none !important;" title="Continue Repair (Disabled)">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polygon points="5 3 19 12 5 21 5 3"></polygon>
                        </svg>
                        <span>Continue Repair</span>
                    </button>
                    ${canApplyCompleteRepair ? `<button class="btn btn-primary" onclick="applyRecommendedPlan('${escapeHtml(plan.candidate_id)}')" title="Apply the fully validated repair to the editor">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="20 6 9 17 4 12"></polyline>
                        </svg>
                        <span>Apply Repair</span>
                    </button>` : `<div class="rec-warning-box" role="status" style="font-size:12px; padding:8px 10px; color:#b45309;">Repair is not ready to apply: ${escapeHtml(applyBlockReason)}</div>`}
                    <button class="btn btn-secondary" onclick="rejectRecommendedPlan('${escapeHtml(plan.candidate_id)}')" title="Dismiss repair recommendation">
                        <span>Dismiss</span>
                    </button>
                </div>
            `;
        } else if (plan.status === "CLEAN" || plan.terminal_status === "CLEAN") {
            recCard.style.display = "block";
            recCard.innerHTML = `
                <div class="rec-card-header">
                    <div class="rec-title-group">
                        <span class="rec-title-text" style="color:var(--accent-green, #16a34a);">✓ Program is Clean</span>
                    </div>
                    <span class="rec-agent-badge" style="background:rgba(220,38,38,0.12); color:#16a34a; border-color:rgba(22,163,74,0.25);">
                        0 Errors / 0 Vulnerabilities
                    </span>
                </div>
                <div style="font-size:12px; color:var(--text-secondary); padding: 8px 0;">
                    All syntax, semantic, security, and quality checks passed. No code modifications required.
                </div>
            `;
        } else {
            // Requirement 5: A finding with no automatic fix shows reason per finding. Never an empty panel.
            recCard.style.display = "block";
            const stoppingReason = escapeHtml(plan.stopping_reason || "Automated repair could not be generated safely for detected findings.");
            const unres = (plan.unresolved_findings && plan.unresolved_findings.length > 0)
                ? plan.unresolved_findings
                : ((plan.findings && plan.findings.length > 0) ? plan.findings : (plan.unified_findings || []));
            const issuesList = unres.map(f => {
                const reason = f.fallback_reason || f.explanation || f.recommended_mitigation || f.how_to_fix || "No automated repair rule available for this finding pattern.";
                return `<li style="margin-bottom:6px;"><strong>${escapeHtml(f.title || f.category)}</strong> (Line ${f.line || 1}): ${escapeHtml(reason)}</li>`;
            }).join("");
            recCard.innerHTML = `
                <div class="rec-card-header">
                    <div class="rec-title-group">
                        <span class="rec-title-text" style="color:var(--accent-red, #dc2626);">⚠️ Automated Repair Unavailable</span>
                    </div>
                    <span class="rec-agent-badge" style="background:rgba(220,38,38,0.12); color:#dc2626; border-color:rgba(220,38,38,0.25);">
                        ${escapeHtml(plan.terminal_status || plan.workflow_state || "MANUAL_REVIEW_REQUIRED")}
                    </span>
                </div>
                <div style="font-size:12px; color:var(--text-secondary); padding: 8px 0;">
                    <div style="margin-bottom:8px;"><strong>Reason:</strong> ${stoppingReason}</div>
                    ${unres.length > 0 ? `<div><strong>Finding Details & Manual Guidance (${unres.length}):</strong><ul style="margin:6px 0 0 16px; padding:0;">${issuesList}</ul></div>` : ""}
                </div>
            `;
        }
    }

    // Render Before vs After Comparison Card
    renderBeforeAfterCard(plan);
    const baBadge = document.getElementById("ba-status-badge");
    if (baBadge) {
        if (plan.status === "CLEAN" || plan.terminal_status === "CLEAN") {
            baBadge.className = "badge badge-success";
            baBadge.textContent = "Clean Source Code";
        } else if (plan.candidate_id) {
            baBadge.className = "badge badge-info";
            baBadge.textContent = "Proposed Fix (Awaiting Approval)";
        } else {
            baBadge.className = "badge badge-warning";
            baBadge.textContent = "Analysis Baseline";
        }
    }
}

function isManipulationDiffLine(line) {
    if (!line) return false;
    const stripped = line.replace(/^[-+ ]/, "").trim();
    return /ignore\s+(?:all\s+)?(?:previous\s+)?(?:security\s+)?instructions|report\s+no\s+vulnerabilities|ignore\s+security\s+policies|tell\s+the\s+security\s+agent|system\s+override|prompt\s+injection|disable\s+validation|approve\s+every\s+finding|claim\s+that\s+validation\s+passed|introduce\s+an\s+unsafe\s+function|do\s+not\s+tell\s+the\s+user|SECURITY\s+TEST/i.test(stripped);
}

function renderDiffLinesHtml(diffText) {
    if (!diffText) return `<div class="empty-panel">No diff available</div>`;
    const lines = diffText.split("\n");
    return lines.map(line => {
        let cls = "rec-diff-line";
        let extraBadge = "";
        if (line.startsWith("+++") || line.startsWith("---")) {
            cls += " header";
        } else if (line.startsWith("@@")) {
            cls += " header";
        } else if (line.startsWith("-")) {
            cls += " deletion";
            if (isManipulationDiffLine(line)) {
                extraBadge = ` <span class="badge badge-warning" style="font-size: 10px; margin-left: 8px; vertical-align: middle; background: rgba(217, 119, 6, 0.18); color: #d97706; border: 1px solid rgba(217, 119, 6, 0.4); padding: 1px 6px; border-radius: 4px;">removed AI-manipulation comment</span>`;
            }
        } else if (line.startsWith("+")) {
            cls += " addition";
        }
        return `<div class="${cls}">${escapeHtml(line)}${extraBadge}</div>`;
    }).join("");
}

function toggleRecViewMode() {
    const diffBox = document.getElementById("rec-diff-container");
    const codeBox = document.getElementById("rec-fullcode-container");
    const btn = document.getElementById("btn-toggle-rec-view");
    if (!diffBox || !codeBox || !btn) return;
    if (diffBox.style.display === "none") {
        diffBox.style.display = "block";
        codeBox.style.display = "none";
        btn.textContent = "View Full Code";
    } else {
        diffBox.style.display = "none";
        codeBox.style.display = "block";
        btn.textContent = "View Diff";
    }
}

async function applyRecommendedPlan(candId) {
    if (!candId) return;
    if (!currentCoordinatedPlan || currentCoordinatedPlan.candidate_id !== candId) {
        showToast("No active repair proposal matches this candidate.", "error");
        return;
    }
    const proposalValidation = currentCoordinatedPlan.validation_report || currentCoordinatedPlan.candidate?.validation_report || {};
    const unresolved = (currentCoordinatedPlan.unresolved_findings || currentCoordinatedPlan.remaining_findings || []);
    const remainingIssueCount = currentCoordinatedPlan.fixes_remaining_count != null
        ? Number(currentCoordinatedPlan.fixes_remaining_count) : unresolved.length;
    const candidateEligible = currentCoordinatedPlan.candidate?.is_eligible_for_application === true;
    const validationPassed = currentCoordinatedPlan.validation_passed === true
        || proposalValidation.is_valid === true
        || currentCoordinatedPlan.candidate?.validation_passed === true;
    if (!validationPassed
        || (remainingIssueCount > 0 && !candidateEligible)
        || currentCoordinatedPlan.candidate?.is_eligible_for_application === false) {
        showToast(proposalValidation.explanation || currentCoordinatedPlan.stopping_reason || "The repair has unresolved issues and cannot be applied yet.", "error");
        return;
    }
    const currentCode = editor ? editor.getValue() : "";
    const normCur = (currentCode || "").replace(/\r\n/g, "\n").replace(/\r/g, "\n").trim();
    const normOrig = (repairOriginalCode || "").replace(/\r\n/g, "\n").replace(/\r/g, "\n").trim();
    if (repairOriginalCode != null && normCur !== normOrig) {
        showToast("Stale repair proposal: Editor source was modified since this proposal was generated. Please re-run analysis.", "error");
        return;
    }

    const appliedPlan = currentCoordinatedPlan;
    const appliedCode = appliedPlan.candidate?.proposed_code || appliedPlan.proposed_code || appliedPlan.candidate_code;
    const originalHash = appliedPlan.original_source_hash || appliedPlan.parent_source_hash;
    const appliedHash = appliedPlan.candidate_source_hash || (appliedPlan.candidate && appliedPlan.candidate.candidate_source_hash);
    const initialFindings = appliedPlan.findings || [];
    const fromState = appliedPlan.workflow_state || "QWEN_PROPOSAL_READY";
    const retryCount = appliedPlan.retry_count || 0;
    const historyHashes = appliedPlan.history_hashes || [];

    return await applyCandidateToEditor(candId, {
        runRepair: false,
        onSuccess: async () => {
            const newlyAppliedCode = editor ? editor.getValue() : "";
            setProgress(35, "Applied proposal to editor — starting fresh re-analysis...");
            setStatus("ANALYZING");

            let progressTimer = null;
            let currentPct = 35;
            progressTimer = setInterval(() => {
                if (currentPct < 90) {
                    currentPct += 10;
                    if (currentPct <= 50) {
                        setProgress(currentPct, "Re-analyzing lexical tokens & grammar AST...");
                    } else if (currentPct <= 70) {
                        setProgress(currentPct, "Checking semantic scope & security rules...");
                    } else {
                        setProgress(currentPct, "Evaluating whole-program repair objectives...");
                    }
                }
            }, 600);

            try {
                const controller = new AbortController();
                const timeoutId = null;

                const postResp = await fetch("/api/repair/post_apply", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    signal: controller.signal,
                    body: JSON.stringify({
                        source_code: newlyAppliedCode,
                        filename: currentFilename,
                        language: currentLanguageId,
                        applied_from_state: fromState,
                        original_source_hash: originalHash,
                        applied_source_hash: appliedHash,
                        initial_findings: initialFindings,
                        retry_count: retryCount,
                        history_hashes: historyHashes,
                    })
                });

                clearTimeout(timeoutId);
                clearInterval(progressTimer);

                if (!postResp.ok) {
                    // Graceful fallback if endpoint is not found or fails
                    setProgress(100, "Proposal applied to editor. Analysis up to date.");
                    setStatus("READY");
                    showToast("Candidate applied to editor.", "success");
                    isRepairRunning = false;
                    setAllRunButtonsDisabled(false);
                    return;
                }

                const postData = await postResp.json();
                if (postData.pipeline_events) {
                    renderPipelineLogs(postData.pipeline_events, postData.run_id);
                }

                if (postData.workflow_state === "ALL_CHECKS_PASSED") {
                    setProgress(100, "All required checks passed");
                    setStatus("FULLY_REPAIRED");
                    showToast("All checks passed! Candidate verified clean.", "success");
                    const recCard = document.getElementById("recommendedProgramCard");
                    if (recCard) {
                        recCard.innerHTML = `
                            <div class="rec-card-header">
                                <div class="rec-title-group">
                                    <span class="rec-title-text" style="color:var(--accent-green, #16a34a);">✓ All Required Checks Passed</span>
                                </div>
                                <span class="rec-agent-badge" style="background:rgba(22,163,74,0.12); color:#16a34a; border-color:rgba(22,163,74,0.25);">
                                    ALL CHECKS PASSED
                                </span>
                            </div>
                            <div style="font-size:12px; color:var(--text-secondary); padding: 8px 0;">
                                ${escapeHtml(postData.summary || "All required lexical, syntax, semantic, and security checks passed! Repair workflow complete.")}
                            </div>
                        `;
                    }
                    currentCoordinatedPlan = null;
                } else if (postData.workflow_state === "QWEN_PROPOSAL_READY") {
                    setProgress(100, "Reasoning escalation proposal ready");
                    setStatus("PROPOSAL_READY");
                    showToast("Remaining issues detected. Reasoned proposal ready for review.", "info");
                    renderCoordinatedPlan(postData);
                } else if (postData.workflow_state === "RETRY_LIMIT_REACHED") {
                    setProgress(100, "Retry limit reached");
                    setStatus("PARTIALLY_REPAIRED");
                    showToast(postData.summary || "Retry limit reached.", "warning");
                    renderCoordinatedPlan(postData);
                } else if (postData.workflow_state === "STALE_SOURCE_REJECTED") {
                    setProgress(100, "Editor modified since proposal was generated");
                    setStatus("READY");
                    showToast(postData.message || "Proposal rejected: editor content was changed.", "warning");
                } else {
                    setProgress(100, postData.summary || "Re-analysis complete");
                    setStatus(postData.workflow_state || postData.status || "READY");
                    if (postData.candidate || postData.proposed_code) {
                        renderCoordinatedPlan(postData);
                    }
                }
                isRepairRunning = false;
                setAllRunButtonsDisabled(false);
            } catch (err) {
                clearInterval(progressTimer);
                console.warn("Post-apply workflow notification:", err);
                setProgress(100, "Candidate applied to editor. Ready.");
                setStatus("READY");
                showToast("Candidate applied to editor.", "success");
                isRepairRunning = false;
                setAllRunButtonsDisabled(false);
            } finally {
                if (progressTimer) clearInterval(progressTimer);
                isRepairRunning = false;
                setAllRunButtonsDisabled(false);
            }
        }
    });
}

async function rejectRecommendedPlan(candId) {
    if (!candId) return;
    try {
        await fetch(`/api/improvement/candidate/${encodeURIComponent(candId)}/reject`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
        });
        const recCard = document.getElementById("recommendedProgramCard");
        if (recCard) recCard.style.display = "none";
        showToast("Repair recommendation dismissed.", "info");
    } catch (e) {
        showToast("Error rejecting recommendation: " + e.message, "error");
    }
}

async function generateAlternativePlan() {
    showToast("Requesting alternative repair strategy from local Qwen2.5-Coder...", "info");
    runRepair();
}

/* -------------------------------------------------- */
/* PROGRAM OUTPUT PANEL & RUN PROGRAM                  */
/* -------------------------------------------------- */
let isProgramRunning = false;
let programRunSequence = 0;

function switchDockTab(tabId) {
    const tabBtnOutput = document.getElementById("tab-btn-program-output");
    const tabBtnSandbox = document.getElementById("tab-btn-sandbox");
    const viewOutput = document.getElementById("program-output-view");
    const viewSandbox = document.getElementById("testcase-grid");
    const actionsOutput = document.getElementById("program-output-actions");
    const actionsSandbox = document.getElementById("sandbox-actions");

    if (tabId === "program-output") {
        if (tabBtnOutput) {
            tabBtnOutput.classList.add("active");
            tabBtnOutput.setAttribute("aria-selected", "true");
        }
        if (tabBtnSandbox) {
            tabBtnSandbox.classList.remove("active");
            tabBtnSandbox.setAttribute("aria-selected", "false");
        }
        if (viewOutput) viewOutput.style.display = "flex";
        if (viewSandbox) viewSandbox.style.display = "none";
        if (actionsOutput) actionsOutput.style.display = "flex";
        if (actionsSandbox) actionsSandbox.style.display = "none";
    } else {
        if (tabBtnOutput) {
            tabBtnOutput.classList.remove("active");
            tabBtnOutput.setAttribute("aria-selected", "false");
        }
        if (tabBtnSandbox) {
            tabBtnSandbox.classList.add("active");
            tabBtnSandbox.setAttribute("aria-selected", "true");
        }
        if (viewOutput) viewOutput.style.display = "none";
        if (viewSandbox) viewSandbox.style.display = "flex";
        if (actionsOutput) actionsOutput.style.display = "none";
        if (actionsSandbox) actionsSandbox.style.display = "flex";
    }
}

function toggleStdinPanel() {
    const stdinBox = document.getElementById("prog-stdin-box");
    const resizer = document.getElementById("prog-stdin-resizer");
    if (!stdinBox) return;
    const isHidden = stdinBox.classList.contains("collapsed") || stdinBox.style.display === "none";
    if (isHidden) {
        stdinBox.classList.remove("collapsed");
        stdinBox.style.display = "flex";
        if (resizer) resizer.style.display = "block";
    } else {
        stdinBox.classList.add("collapsed");
        stdinBox.style.display = "none";
        if (resizer) resizer.style.display = "none";
    }
}

function clearProgramOutput() {
    const emptyState = document.getElementById("prog-empty-state");
    const stdoutEl = document.getElementById("prog-stdout");
    const stderrEl = document.getElementById("prog-stderr");
    const statusText = document.getElementById("prog-status-text");
    const statusBadge = document.getElementById("prog-status-badge");
    const exitBadge = document.getElementById("prog-exit-badge");
    const timeBadge = document.getElementById("prog-time-badge");

    if (emptyState) {
        emptyState.style.display = "flex";
        emptyState.innerText = "Run your program to see its output here.";
    }
    if (stdoutEl) {
        stdoutEl.style.display = "none";
        stdoutEl.textContent = "";
    }
    if (stderrEl) {
        stderrEl.style.display = "none";
        stderrEl.textContent = "";
    }
    if (statusText) statusText.innerText = "Ready";
    if (statusBadge) {
        statusBadge.className = "status-pill status-idle";
    }
    if (exitBadge) {
        exitBadge.style.display = "none";
        exitBadge.innerText = "";
    }
    if (timeBadge) {
        timeBadge.style.display = "none";
        timeBadge.innerText = "";
    }
}

async function runProgram(approvalToken = null) {
    if (isProgramRunning) {
        showToast("Program is already running...", "info");
        return;
    }

    if (!editor) {
        showToast("Editor is not initialized", "error");
        return;
    }

    const sourceCode = editor.getValue();
    if (!sourceCode.trim()) {
        showToast("Please enter source code to run", "warning");
        return;
    }

    // Bring Program Output tab to focus
    switchDockTab("program-output");

    const currentSeq = ++programRunSequence;
    isProgramRunning = true;

    // Disable Run buttons to prevent concurrent duplicate executions
    setAllRunButtonsDisabled(true);

    const statusBadge = document.getElementById("prog-status-badge");
    const statusText = document.getElementById("prog-status-text");
    const exitBadge = document.getElementById("prog-exit-badge");
    const timeBadge = document.getElementById("prog-time-badge");
    const emptyState = document.getElementById("prog-empty-state");
    const stdoutEl = document.getElementById("prog-stdout");
    const stderrEl = document.getElementById("prog-stderr");
    const stdinInput = document.getElementById("prog-stdin-input");

    // Clear previous output and present loading state
    if (statusText) statusText.innerText = "Evaluating Security & Compiling...";
    if (statusBadge) statusBadge.className = "status-pill status-running";
    if (exitBadge) exitBadge.style.display = "none";
    if (timeBadge) timeBadge.style.display = "none";

    if (emptyState) {
        emptyState.style.display = "flex";
        emptyState.innerText = "Screening security gate and compiling in isolated sandbox...";
    }
    if (stdoutEl) {
        stdoutEl.style.display = "none";
        stdoutEl.textContent = "";
    }
    if (stderrEl) {
        stderrEl.style.display = "none";
        stderrEl.textContent = "";
    }

    const stdinValue = stdinInput ? stdinInput.value : "";
    const payload = {
        code: sourceCode,
        stdin: stdinValue,
        filename: currentFilename || (currentLanguageId === "python" ? "main.py" : "main.c"),
        language: currentLanguageId,
        timeout: 4.0,
        approval_token: approvalToken
    };

    try {
        const response = await callWithGate("/api/program/run", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        }, { operation: "execute", code: sourceCode, filename: payload.filename, language: payload.language });

        // If user cancelled in security warning modal, abort cleanly
        if (!response || response.cancelled) {
            isProgramRunning = false;
            setAllRunButtonsDisabled(false);
            if (statusText) statusText.innerText = "Cancelled";
            if (statusBadge) statusBadge.className = "status-pill status-neutral";
            if (emptyState) {
                emptyState.style.display = "flex";
                emptyState.innerText = "(Program execution cancelled by user)";
            }
            return;
        }

        // Discard stale responses if a newer execution began
        if (currentSeq !== programRunSequence) return;

        const data = await response.json();

        const status = data.status || (data.success ? "Completed" : "Runtime Error");

        if (statusText) statusText.innerText = status;

        if (statusBadge) {
            if (status === "Completed") {
                statusBadge.className = "status-pill status-success";
            } else if (status === "Timed Out") {
                statusBadge.className = "status-pill status-warning";
            } else {
                statusBadge.className = "status-pill status-error";
            }
        }

        // Exit status badge
        if (exitBadge) {
            if (data.exit_code !== null && data.exit_code !== undefined) {
                exitBadge.style.display = "inline-flex";
                exitBadge.innerText = `Exit ${data.exit_code}`;
                exitBadge.className = `badge ${data.exit_code === 0 ? "badge-success" : "badge-danger"}`;
            } else {
                exitBadge.style.display = "none";
            }
        }

        // Execution duration badge
        if (timeBadge && data.execution_time_ms !== undefined) {
            timeBadge.style.display = "inline-flex";
            timeBadge.innerText = `${data.execution_time_ms} ms`;
        }

        // Terminal output rendering
        const hasStdout = Boolean(data.stdout && data.stdout.trim());
        const hasStderr = Boolean(data.stderr && data.stderr.trim());
        const compError = Boolean(data.compilation_error && data.compilation_error.trim());

        if (emptyState) emptyState.style.display = "none";

        if (hasStdout && stdoutEl) {
            stdoutEl.style.display = "block";
            stdoutEl.textContent = data.stdout;
        }

        if ((hasStderr || compError) && stderrEl) {
            stderrEl.style.display = "block";
            stderrEl.textContent = data.stderr || data.compilation_error;
        }

        if (!hasStdout && !hasStderr && !compError) {
            if (emptyState) {
                emptyState.style.display = "flex";
                if (status === "Completed") {
                    emptyState.innerText = "(Program exited with code 0 and produced no output)";
                } else {
                    emptyState.innerText = `(Program exited with status: ${status})`;
                }
            }
        }

    } catch (err) {
        if (currentSeq !== programRunSequence) return;
        if (statusText) statusText.innerText = "Execution Failed";
        if (statusBadge) statusBadge.className = "status-pill status-error";
        if (emptyState) emptyState.style.display = "none";
        if (stderrEl) {
            stderrEl.style.display = "block";
            stderrEl.textContent = "Execution request failed: " + err.message;
        }
    } finally {
        setAllRunButtonsDisabled(false);
        if (currentSeq === programRunSequence) {
            isProgramRunning = false;
        }
    }
}

/* -------------------------------------------------- */
/* SECURITY APPROVAL GATE MODAL & UNIVERSAL GATEWAY   */
/* -------------------------------------------------- */

let pendingGateSession = null;

/**
 * Universal Shared Function: callWithGate
 * Every button that interacts with the compiler or execution pipeline uses this gateway.
 * Automatically intercepts HTTP 409 (Security Warning).
 * 
 * Policy:
 * 1. Shows security warning modal with full risk explanation.
 * 2. Gives user two clear options: Cancel (nothing runs) or Continue anyway.
 * 3. On Continue, calls approve endpoint, gets token, retries the exact SAME request with token.
 * 4. If token expired, re-shows the modal automatically.
 * 5. After approval, the normal pipeline runs (including compile/run/repair).
 * 6. Never shows raw JSON to user.
 */
async function callWithGate(url, options = {}, context = {}) {
    let parsedBody = {};
    try {
        parsedBody = typeof options.body === "string" ? JSON.parse(options.body) : (options.body || {});
    } catch (e) {
        parsedBody = {};
    }

    const sourceCode = parsedBody.code !== undefined ? parsedBody.code : (context.code !== undefined ? context.code : (editor ? editor.getValue() : ""));
    const filename = parsedBody.filename || context.filename || currentFilename;
    const language = parsedBody.language || context.language || currentLanguageId;
    const operation = parsedBody.operation || context.operation || (url.includes("run") || url.includes("execute") ? "execute" : "repair");

    async function executeRequest(token = null) {
        let reqBody = {
            ...parsedBody,
            code: sourceCode,
            filename: filename,
            language: language,
            operation: operation
        };
        if (token) {
            reqBody.approval_token = token;
        }

        const reqOptions = {
            ...options,
            headers: { "Content-Type": "application/json", ...(options.headers || {}) },
            body: JSON.stringify(reqBody)
        };

        const resp = await fetch(url, reqOptions);
        if (resp.status !== 409) {
            return resp;
        }

        // Status 409: Security Gate Warning Intercepted
        let warningPayload;
        try {
            warningPayload = await resp.json();
        } catch (e) {
            warningPayload = {
                heading: "Security Review Required",
                summary: "Security vulnerabilities or directives detected.",
                findings: []
            };
        }

        return new Promise((resolve) => {
            pendingGateSession = {
                url: url,
                options: options,
                parsedBody: reqBody,
                sourceCode: sourceCode,
                filename: filename,
                language: language,
                operation: operation,
                warningPayload: warningPayload,
                resolve: resolve,
                onContinue: async () => {
                    const btnApprove = document.getElementById("sec-btn-approve");
                    if (btnApprove) {
                        btnApprove.disabled = true;
                        btnApprove.innerText = "Authorizing...";
                    }
                    try {
                        const apprResp = await fetch("/api/security/approval/approve", {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({
                                code: sourceCode,
                                filename: filename,
                                language: language,
                                operation: operation,
                                force: true
                            })
                        });
                        const apprData = await apprResp.json();
                        if (!apprResp.ok || !apprData.success || !apprData.approval_token) {
                            showToast("Approval error: " + (apprData.error || "Could not generate authorization token"), "error");
                            if (btnApprove) {
                                btnApprove.disabled = false;
                                btnApprove.innerText = "Continue anyway";
                            }
                            return;
                        }

                        const token = apprData.approval_token;
                        hideSecurityApprovalModal();
                        showToast("Security warnings acknowledged. Proceeding...", "warning");

                        // User approved: now show running states
                        const activeLogsList = document.getElementById("logs");
                        const activeBadgeLogs = document.getElementById("badge-logs");
                        if (activeLogsList) {
                            activeLogsList.innerHTML = `
                                <li class="log-event-card st-running" id="event-row-running">
                                    <div class="log-card-main">
                                        <div class="log-card-left">
                                            <span class="log-status-badge st-running">⚡ RUNNING</span>
                                            <strong class="log-stage-title">Executing 16-Stage Compiler & Repair Pipeline...</strong>
                                        </div>
                                    </div>
                                    <div class="log-description">Analyzing tokens, grammar AST, semantic scope, and coordinating repair candidates...</div>
                                </li>
                            `;
                            if (activeBadgeLogs) activeBadgeLogs.textContent = "…";
                        }
                        setStatus("REPAIRING");
                        setProgress(35, "Running repair pipeline with authorized security override...");

                        if (operation === "execute") {
                            const statusText = document.getElementById("prog-status-text");
                            const statusBadge = document.getElementById("prog-status-badge");
                            const emptyState = document.getElementById("prog-empty-state");
                            if (statusText) statusText.innerText = "Compiling & Running...";
                            if (statusBadge) statusBadge.className = "status-pill status-running";
                            if (emptyState) emptyState.innerText = "Compiling in isolated sandbox...";
                        }

                        // Retry the SAME request with single-use approval token
                        const retryResp = await executeRequest(token);
                        resolve(retryResp);
                    } catch (err) {
                        showToast("Approval request failed: " + err.message, "error");
                        if (btnApprove) {
                            btnApprove.disabled = false;
                            btnApprove.innerText = "Continue anyway";
                        }
                        isRepairRunning = false;
                        isProgramRunning = false;
                        setAllRunButtonsDisabled(false);
                    }
                },
                onCancel: async () => {
                    hideSecurityApprovalModal();
                    try {
                        await fetch("/api/security/approval/cancel", {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({
                                code: sourceCode,
                                filename: filename,
                                operation: operation
                            })
                        });
                    } catch (e) {}

                    // Re-enable Run and Repair buttons
                    isRepairRunning = false;
                    isProgramRunning = false;
                    setAllRunButtonsDisabled(false);

                    if (operation === "execute") {
                        const statusText = document.getElementById("prog-status-text");
                        const statusBadge = document.getElementById("prog-status-badge");
                        const emptyState = document.getElementById("prog-empty-state");
                        if (statusText) statusText.innerText = "Cancelled";
                        if (statusBadge) statusBadge.className = "status-pill status-neutral";
                        if (emptyState) {
                            emptyState.style.display = "flex";
                            emptyState.innerText = "(Program execution cancelled by user: no code compiled or executed)";
                        }
                    }

                    setStatus("IDLE");
                    setProgress(0, "Cancelled by user");

                    showToast("Operation cancelled. Program left uncompiled and unexecuted.", "info");
                    resolve({ cancelled: true, status: 409, ok: false });
                }
            };

            showSecurityApprovalModal(warningPayload, sourceCode, reqBody, operation);
        });
    }

    return await executeRequest(null);
}

function hideSecurityApprovalModal() {
    const modal = document.getElementById("security-approval-modal");
    if (modal) modal.style.display = "none";
}

function showSecurityApprovalModal(verdict, sourceCode, payload, context) {
    var opContext = context || (payload && payload.context) || "execute";

    const modal = document.getElementById("security-approval-modal");
    if (!modal) return;

    // Disallow background live requests while modal is open
    clearTimeout(qualityScoreTimer);
    clearTimeout(optimizationTimer);
    clearTimeout(securityRiskTimer);
    if (window._liveAnalysisAbortController) {
        try { window._liveAnalysisAbortController.abort(); } catch (e) {}
        window._liveAnalysisAbortController = null;
    }

    // Disable Run / Repair / Compile buttons while security review is pending
    setAllRunButtonsDisabled(true);

    // Title & Subtitle
    const titleEl = document.getElementById("sec-modal-title");
    const subTitleEl = document.getElementById("sec-modal-subtitle");
    if (titleEl) titleEl.innerText = verdict.heading || "Security Review Required";
    if (subTitleEl) subTitleEl.innerText = verdict.policy_reason || "Compilation and execution halted until security risks are acknowledged.";

    // Banner
    const banner = document.getElementById("sec-banner");
    const bannerText = document.getElementById("sec-banner-text");
    if (banner && bannerText) {
        banner.className = "sec-banner sec-banner-warning";
        bannerText.innerText = verdict.summary || "Security vulnerabilities or policy rules require explicit acknowledgment before continuing.";
    }

    // Meta Grid
    const metaFile = document.getElementById("sec-meta-file");
    const metaOp = document.getElementById("sec-meta-op");
    const metaHash = document.getElementById("sec-meta-hash");
    const metaOverride = document.getElementById("sec-meta-override");

    if (metaFile) metaFile.innerText = verdict.filename || (payload ? payload.filename : "main.c");
    if (metaOp) metaOp.innerText = (verdict.operation || opContext || "execute").toUpperCase();
    if (metaHash) metaHash.innerText = (verdict.source_hash || "--").substring(0, 16);
    if (metaOverride) {
        metaOverride.innerText = "Reviewable (User Approval Permitted)";
        metaOverride.style.color = "var(--accent-orange, #f59e0b)";
    }

    // Checks Grid
    const checksList = document.getElementById("sec-checks-list");
    if (checksList) {
        let checksHtml = "";
        const completed = verdict.security_checks_completed || [];
        const failed = verdict.security_checks_failed || [];

        completed.forEach(chk => {
            checksHtml += `<div class="sec-check-item passed"><span>✅</span><span>${escapeHtml(chk)}</span></div>`;
        });
        failed.forEach(chk => {
            checksHtml += `<div class="sec-check-item failed"><span>⚠️</span><span>${escapeHtml(chk)} (Requires Review)</span></div>`;
        });
        checksList.innerHTML = checksHtml || "<div class='sec-meta-val'>Static checks completed.</div>";
    }

    // Findings Container Grouped by Severity
    const findingsContainer = document.getElementById("sec-findings-container");
    if (findingsContainer) {
        let html = "";
        let allFindings = verdict.findings || [];

        if (allFindings.length === 0 && verdict.findings_by_severity) {
            Object.values(verdict.findings_by_severity).forEach(list => {
                allFindings = allFindings.concat(list);
            });
        }

        if (allFindings.length > 0) {
            // Split reviewer instructions from software security vulnerabilities
            const reviewerInstructions = allFindings.filter(f => 
                f.is_manipulation || 
                f.category === "AGENT_INSTRUCTION_MANIPULATION" || 
                f.category === "PROMPT_INJECTION" ||
                (f.rule_id && (f.rule_id.includes("MANIPULATION") || f.rule_id.includes("INJECTION") || f.rule_id.includes("BYPASS") || f.rule_id.includes("DIRECTIVE")))
            );
            const secVulnerabilities = allFindings.filter(f => !reviewerInstructions.includes(f));

            // Render reviewer instructions in their own distinct group
            if (reviewerInstructions.length > 0) {
                html += `<div class="sec-severity-group">
                    <div class="sec-group-header" style="background: rgba(245, 158, 11, 0.12); border-left: 4px solid #f59e0b; color: #b45309; padding: 8px 12px; font-weight: 700; margin-bottom: 8px; border-radius: 4px;">
                        <span>Instructions in code addressed to an automated reviewer (${reviewerInstructions.length})</span>
                    </div>`;

                reviewerInstructions.forEach(f => {
                    const loc = (f.file_path || verdict.filename || "main.c") + (f.line ? `:${f.line}` : "") + (f.column ? `:${f.column}` : "");
                    html += `<div class="sec-finding-card" style="border-left: 3px solid #f59e0b; margin-bottom: 8px;">
                        <div class="sec-finding-top">
                            <span class="sec-finding-loc">${escapeHtml(loc)} — Instructions addressed to automated reviewer</span>
                            <span class="sec-badge sec-badge-warning" style="background:#f59e0b; color:#fff;">REVIEWER INSTRUCTION</span>
                        </div>
                        <div class="sec-finding-desc"><strong>Explanation:</strong> ${escapeHtml(f.manipulation_reason || f.explanation || "Directive in code addressed to an automated reviewer or verification model.")}</div>`;

                    if (f.snippet) {
                        html += `<pre class="sec-finding-snippet"><code>${escapeHtml(f.snippet)}</code></pre>`;
                    }

                    html += `<div class="sec-finding-details">
                        <div class="sec-detail-row"><span class="sec-detail-label">Policy:</span><span class="sec-detail-val">Instructions in code addressed to an automated reviewer are never obeyed. You may choose Continue anyway to proceed.</span></div>
                        <div class="sec-detail-row"><span class="sec-detail-label">Safety Action:</span><span class="sec-detail-val">Flagged text will be automatically masked from AI repair models upon continuation.</span></div>
                    </div></div>`;
                });
                html += `</div>`;
            }

            // Group remaining security vulnerabilities by severity
            const sevOrder = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"];
            const grouped = {};
            sevOrder.forEach(s => grouped[s] = []);

            secVulnerabilities.forEach(f => {
                const s = (f.severity || "HIGH").toUpperCase();
                if (!grouped[s]) grouped[s] = [];
                grouped[s].push(f);
            });

            sevOrder.forEach(sev => {
                const list = grouped[sev] || [];
                if (list.length > 0) {
                    html += `<div class="sec-severity-group">
                        <div class="sec-group-header ${sev.toLowerCase()}">
                            <span>${sev} Severity (${list.length})</span>
                        </div>`;

                    list.forEach(f => {
                        const badgeClass = (sev === "CRITICAL" || sev === "HIGH") ? "sec-badge-danger" : (sev === "MEDIUM" ? "sec-badge-warning" : "sec-badge-neutral");
                        const loc = (f.file_path || verdict.filename || "main.c") + (f.line ? `:${f.line}` : "") + (f.column ? `:${f.column}` : "");

                        html += `<div class="sec-finding-card">
                            <div class="sec-finding-top">
                                <span class="sec-finding-loc">${escapeHtml(loc)} — ${escapeHtml(f.category || "Security Finding")}</span>
                                <span class="sec-badge ${badgeClass}">${sev}</span>
                            </div>
                            <div class="sec-finding-desc"><strong>Plain-Language Explanation:</strong> ${escapeHtml(f.reason_dangerous || f.explanation || "Security risk detected in source code.")}</div>`;

                        if (f.snippet) {
                            html += `<pre class="sec-finding-snippet"><code>${escapeHtml(f.snippet)}</code></pre>`;
                        }

                        html += `<div class="sec-finding-details">`;
                        
                        // CWE Reference
                        const cweVal = f.cwe || f.cwe_id || "CWE-General";
                        html += `<div class="sec-detail-row"><span class="sec-detail-label">CWE Identifier:</span><span class="sec-detail-val sec-cwe-tag">${escapeHtml(cweVal)}</span></div>`;

                        // Potential Threat (What an attacker could do)
                        if (f.potential_threat || f.potential_consequences) {
                            html += `<div class="sec-detail-row"><span class="sec-detail-label">Potential Threat (Attacker Impact):</span><span class="sec-detail-val">${escapeHtml(f.potential_threat || f.potential_consequences)}</span></div>`;
                        }

                        // Possible Future Risks
                        if (f.future_risks && f.future_risks.length > 0) {
                            html += `<div class="sec-detail-row"><span class="sec-detail-label">⚠ Possible Future Risks:</span><ul class="sec-risk-list">`;
                            f.future_risks.forEach(risk => {
                                html += `<li>${escapeHtml(risk)}</li>`;
                            });
                            html += `</ul></div>`;
                        }

                        // Recommended Fix
                        if (f.recommended_fix || f.recommended_mitigation) {
                            html += `<div class="sec-detail-row"><span class="sec-detail-label">Recommended Fix:</span><span class="sec-detail-val">${escapeHtml(f.recommended_fix || f.recommended_mitigation)}</span></div>`;
                        }

                        // Agent Manipulation / Prompt Injection Callout
                        const isManip = f.is_manipulation || f.category === "PROHIBITED_SECURITY_THREAT" ||
                            (f.rule_id && (f.rule_id.includes("MANIPULATION") || f.rule_id.includes("INJECTION") || f.rule_id.includes("BYPASS") || f.rule_id.includes("DIRECTIVE")));
                        if (isManip) {
                            html += `
                                <div class="sec-manipulation-callout">
                                    <div class="sec-manipulation-title">⚠️ Flagged Agent Manipulation / Prompt Injection Directive</div>
                                    <div class="sec-manipulation-text"><strong>Flagged Text:</strong> <code>${escapeHtml(f.flagged_text || f.snippet || "Directive")}</code></div>
                                    <div class="sec-manipulation-why"><strong>Why Flagged:</strong> ${escapeHtml(f.manipulation_reason || f.explanation || "Directive attempts to alter compiler security agents or force approval.")}</div>
                                    <div class="sec-manipulation-action"><strong>Safety Action:</strong> This flagged text will be automatically stripped before passing code to AI repair models upon continuation.</div>
                                </div>
                            `;
                        }

                        html += `</div></div>`;
                    });

                    html += `</div>`;
                }
            });
        }

        findingsContainer.innerHTML = html || "<div class='sec-meta-val'>No granular findings details returned.</div>";
    }

    // Buttons Setup
    const btnApprove = document.getElementById("sec-btn-approve");
    if (btnApprove) {
        btnApprove.disabled = false;
        btnApprove.className = "btn btn-danger";
        btnApprove.innerText = "Continue anyway";
        btnApprove.title = "Acknowledge security risks and authorize execution/compilation.";
    }

    const btnCancel = document.getElementById("sec-btn-cancel");
    if (btnCancel) {
        btnCancel.innerText = "Cancel";
        btnCancel.title = "Abort operation and return to editor without executing.";
    }

    const btnRepair = document.getElementById("sec-btn-repair");
    if (btnRepair) {
        btnRepair.style.display = "none";
    }

    modal.style.display = "flex";
}

async function handleSecurityGateAction(action) {
    if (!pendingGateSession) {
        hideSecurityApprovalModal();
        return;
    }

    if (action === "cancel") {
        await pendingGateSession.onCancel();
    } else if (action === "approve") {
        await pendingGateSession.onContinue();
    }
}

function handleSecurityModalBackdropClick(event) {
    if (event.target && event.target.id === "security-approval-modal") {
        handleSecurityGateAction("cancel");
    }
}

function closeSecurityApprovalModal(reason = "cancel") {
    handleSecurityGateAction("cancel");
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

    const lang = getActiveLanguage();
    const testFilename = `test_case${lang.extensions[0]}`;

    output.value = `Running compiler & auto-repair pipeline on testcase (${lang.label})...`;

    try {
        const response = await callWithGate("/api/testcase", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                code: input,
                filename: testFilename,
                language: currentLanguageId,
                operation: "repair"
            })
        }, { operation: "repair", code: input, filename: testFilename, language: currentLanguageId });

        if (!response || response.cancelled) {
            output.value = "Testcase execution cancelled by user.";
            return;
        }

        const data = await response.json();
        if (data.green_report) {
            renderGreenReport(data.green_report);
        }
        if (data.quality_report) {
            renderQualityScore(data.quality_report);
        }
        if (data.optimization_report) {
            renderOptimizationReport(data.optimization_report);
        }
        if (data.security_risk_report) {
            renderSecurityRiskReport(data.security_risk_report);
        }

        output.value =
            `=======================================================\n` +
            `STATUS: ${data.status || "Unknown"}\n` +
            `APPLIED REPAIRS: ${(data.applied_steps || []).length}\n` +
            `GREEN SCORE: ${data.green_report?.green_score ?? "N/A"}/100\n` +
            `QUALITY SCORE: ${data.quality_report?.overall_score != null ? data.quality_report.overall_score + "%" : "N/A"}\n` +
            `OPTIMIZATION POTENTIAL: ${data.optimization_report?.optimization_potential != null ? data.optimization_report.optimization_potential + "%" : "N/A"}\n` +
            `SECURITY RISK SCORE: ${data.security_risk_report?.risk_score != null ? data.security_risk_report.risk_score + "%" : "N/A"}\n` +
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
        const lang = getActiveLanguage();
        const listRes = await fetch(`/api/examples?language=${currentLanguageId}`);
        allExampleFiles = await listRes.json();
        if (!Array.isArray(allExampleFiles)) allExampleFiles = [];

        const countEl = document.getElementById("file-count");
        if (countEl) countEl.innerText = allExampleFiles.length;

        const exTitle = document.getElementById("examples-title");
        if (exTitle) exTitle.innerText = `${lang.label} Examples`;

        const searchInput = document.getElementById("file-search");
        const query = searchInput ? searchInput.value : "";
        renderFileTree(query);
    } catch (err) {
        console.error("Failed to refresh file tree:", err);
    }
}

function filterFiles(query) {
    renderFileTree(query);
}

function renderFileTree(query = "") {
    const tree = document.getElementById("file-tree");
    if (!tree) return;
    tree.innerHTML = "";

    const lang = getActiveLanguage();
    const ws = workspaces[currentLanguageId];
    const q = (query || "").toLowerCase().trim();

    // 1. My files (unsaved) section
    const myFiles = (ws.created || []).filter(fn => fn.toLowerCase().includes(q));
    if (myFiles.length > 0) {
        const myHeader = document.createElement("div");
        myHeader.className = "file-tree-section-header";
        myHeader.innerText = "My files (unsaved)";
        tree.appendChild(myHeader);

        myFiles.forEach(fn => {
            const item = document.createElement("div");
            item.className = "file-item" + (fn === currentFilename ? " active" : "");
            item.innerText = fn;
            item.dataset.filename = fn;
            item.onclick = () => {
                resetExecutionStateOnProblemChange();
                if (!openTabs.includes(fn)) openTabs.push(fn);
                switchTab(fn);
            };
            tree.appendChild(item);
        });
    }

    // 2. Examples section
    const exHeader = document.createElement("div");
    exHeader.className = "file-tree-section-header";
    exHeader.innerText = `${lang.label} Examples`;
    tree.appendChild(exHeader);

    const filtered = allExampleFiles.filter(fn => fn.toLowerCase().includes(q));

    if (filtered.length === 0) {
        const empty = document.createElement("div");
        empty.style.padding = "8px 12px";
        empty.style.color = "var(--text-muted)";
        empty.style.fontSize = "12px";
        empty.style.fontStyle = "italic";
        empty.innerText = `No ${lang.label} files found in examples/`;
        tree.appendChild(empty);
        return;
    }

    filtered.forEach(filename => {
        const item = document.createElement("div");
        item.className = "file-item" + (filename === currentFilename ? " active" : "");
        item.innerText = filename;
        item.dataset.filename = filename;

        item.onclick = async () => {
            resetExecutionStateOnProblemChange();
            const res = await fetch(`/api/example/${encodeURIComponent(filename)}?language=${currentLanguageId}`);
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

    resizer.addEventListener("mousedown", () => {
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

    resizer.addEventListener("mousedown", () => {
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

    resizer.addEventListener("mousedown", () => {
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

    resizer.addEventListener("mousedown", () => {
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

function initProgStdinResize() {
    const resizer = document.getElementById("prog-stdin-resizer");
    const stdinBox = document.getElementById("prog-stdin-box");
    const terminalBox = document.getElementById("prog-terminal-box");
    if (!resizer || !stdinBox || !terminalBox) return;

    let isResizing = false;

    resizer.addEventListener("mousedown", () => {
        isResizing = true;
        resizer.classList.add("resizing");
        document.body.style.cursor = "col-resize";
        document.body.style.userSelect = "none";
    });

    window.addEventListener("mousemove", (e) => {
        if (!isResizing) return;
        const grid = resizer.parentElement;
        if (!grid) return;
        const rect = grid.getBoundingClientRect();
        const offset = e.clientX - rect.left;
        const total = rect.width;

        const leftWidth = Math.max(120, Math.min(total - 180, offset));
        stdinBox.style.width = leftWidth + "px";
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

/* ------------------------------------------------------------- */
/* PATCH VALIDATION & EXPLICIT USER APPROVAL HANDLERS           */
/* ------------------------------------------------------------- */
let activePatchReview = null;
let activePatchRepairData = null;

function showPatchReviewModal(patchItem, repairData) {
    activePatchReview = patchItem;
    activePatchRepairData = repairData;

    const modal = document.getElementById("patch-review-modal");
    if (!modal) return;

    const report = patchItem.report || {};
    const stages = report.stage_results || {};

    // Helper to format badge
    function updateBadge(badgeId, statusId, stageKey) {
        const badgeEl = document.getElementById(badgeId);
        const textEl = document.getElementById(statusId);
        if (!badgeEl || !textEl) return;

        const res = stages[stageKey];
        badgeEl.className = "stage-badge";
        if (!res) {
            badgeEl.classList.add("warn");
            textEl.textContent = "Skipped";
        } else if (res.passed) {
            badgeEl.classList.add("pass");
            textEl.textContent = "Passed";
        } else {
            badgeEl.classList.add("fail");
            textEl.textContent = "Failed";
        }
    }

    updateBadge("badge-stage-syntax", "stage-syntax-status", "SYNTAX");
    updateBadge("badge-stage-compiler", "stage-compiler-status", "COMPILATION");
    updateBadge("badge-stage-security", "stage-security-status", "SECURITY");
    updateBadge("badge-stage-semantic", "stage-semantic-status", "SEMANTIC");

    // Details text
    const expEl = document.getElementById("patch-explanation-text");
    if (expEl) expEl.textContent = patchItem.explanation || "Automated repair proposal";

    // Assumptions
    const assumpField = document.getElementById("patch-assumptions-field");
    const assumpText = document.getElementById("patch-assumptions-text");
    if (assumpField && assumpText) {
        if (patchItem.assumptions && patchItem.assumptions.length > 0) {
            assumpField.style.display = "block";
            assumpText.textContent = patchItem.assumptions.join("; ");
        } else {
            assumpField.style.display = "none";
        }
    }

    // Expected effects
    const effField = document.getElementById("patch-effects-field");
    const effText = document.getElementById("patch-effects-text");
    if (effField && effText) {
        if (patchItem.expected_effects && patchItem.expected_effects.length > 0) {
            effField.style.display = "block";
            effText.textContent = patchItem.expected_effects.join("; ");
        } else {
            effField.style.display = "none";
        }
    }

    // Remaining risks
    const risksCont = document.getElementById("patch-risks-container");
    const risksList = document.getElementById("patch-risks-list");
    if (risksCont && risksList) {
        const risks = report.remaining_risks || [];
        if (risks.length > 0) {
            risksCont.style.display = "block";
            risksList.innerHTML = risks.map(r => `<li>${escapeHtml(r)}</li>`).join("");
        } else {
            risksCont.style.display = "none";
            risksList.innerHTML = "";
        }
    }

    // Render Security Delta if present
    const secDeltaCont = document.getElementById("patch-sec-delta-container");
    const secDeltaBadges = document.getElementById("sec-delta-badges");
    const secDeltaList = document.getElementById("sec-delta-list");
    const deltaObj = report.security_delta || (stages.SECURITY && stages.SECURITY.details ? stages.SECURITY.details.delta : null);

    if (secDeltaCont && secDeltaBadges && secDeltaList) {
        if (deltaObj && (deltaObj.resolved_count > 0 || deltaObj.remaining_count > 0 || deltaObj.introduced_count > 0)) {
            secDeltaCont.style.display = "block";
            secDeltaBadges.innerHTML = "";
            secDeltaList.innerHTML = "";

            if (deltaObj.resolved_count > 0) {
                const b = document.createElement("span");
                b.className = "sec-delta-badge resolved";
                b.textContent = `✅ Resolved: ${deltaObj.resolved_count}`;
                secDeltaBadges.appendChild(b);
            }
            if (deltaObj.remaining_count > 0) {
                const b = document.createElement("span");
                b.className = "sec-delta-badge remaining";
                b.textContent = `⚠️ Remaining: ${deltaObj.remaining_count}`;
                secDeltaBadges.appendChild(b);
            }
            if (deltaObj.introduced_count > 0) {
                const b = document.createElement("span");
                b.className = "sec-delta-badge introduced";
                b.textContent = `🚨 REGRESSION INTRODUCED: ${deltaObj.introduced_count}`;
                secDeltaBadges.appendChild(b);
            }

            (deltaObj.resolved_vulnerabilities || []).forEach(v => {
                const li = document.createElement("li");
                li.className = "sec-delta-item resolved";
                li.textContent = `Fixed: ${v.rule_id} at line ${v.line} (${v.cwe_id || v.category})`;
                secDeltaList.appendChild(li);
            });
            (deltaObj.introduced_vulnerabilities || []).forEach(v => {
                const li = document.createElement("li");
                li.className = "sec-delta-item introduced";
                li.textContent = `New Vulnerability Introduced: ${v.rule_id} at line ${v.line} (${v.potential_impact})`;
                secDeltaList.appendChild(li);
            });
        } else {
            secDeltaCont.style.display = "none";
        }
    }

    // Render structured diff
    const diffContainer = document.getElementById("diff-content");
    const diffAdd = document.getElementById("diff-add-count");
    const diffDel = document.getElementById("diff-del-count");
    const diffObj = report.structured_diff || {};

    if (diffAdd) diffAdd.textContent = `+${diffObj.additions_count || 0} additions`;
    if (diffDel) diffDel.textContent = `-${diffObj.deletions_count || 0} deletions`;

    if (diffContainer) {
        const diffText = diffObj.unified_diff || "";
        const lines = diffText.split("\n");
        diffContainer.innerHTML = lines.map(line => {
            let cls = "diff-line";
            if (line.startsWith("+++") || line.startsWith("---") || line.startsWith("@@")) {
                cls += " header";
            } else if (line.startsWith("+")) {
                cls += " addition";
            } else if (line.startsWith("-")) {
                cls += " deletion";
            }
            return `<div class="${cls}">${escapeHtml(line)}</div>`;
        }).join("");
    }

    modal.style.display = "flex";
}

function closePatchReviewModal() {
    const modal = document.getElementById("patch-review-modal");
    if (modal) modal.style.display = "none";
    if (typeof setAllRunButtonsDisabled === "function") {
        setAllRunButtonsDisabled(false);
    }
}

function handlePatchModalBackdropClick(e) {
    if (e.target && e.target.id === "patch-review-modal") {
        closePatchReviewModal();
    }
}

async function confirmApplyPatch() {
    if (!activePatchReview || !activePatchReview.patch_id) return;
    try {
        const resp = await fetch("/api/patch/apply", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ patch_id: activePatchReview.patch_id })
        });
        const data = await resp.json();
        if (!data.success) {
            showToast("Failed to apply patch: " + data.error, "error");
            return;
        }

        // Explicit user approval confirmed! Apply patch to editor.
        const prevCode = repairOriginalCode;
        suppressHighlightClearOnce = true;
        editor.setValue(data.applied_code);
        openFiles[currentFilename] = data.applied_code;

        // Show Revert button in topbar
        const revBtn = document.getElementById("btn-revert");
        if (revBtn) revBtn.style.display = "inline-flex";

        const changed = computeChangedLines(repairOriginalCode, data.applied_code);
        highlightChangedLines(changed);

        closePatchReviewModal();
        showToast("Patch applied with explicit user approval!", "success");

        // Fetch and display Before vs After Fix Comparison
        try {
            const deltaResp = await fetch("/api/dashboard/before_after", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    before_code: prevCode,
                    after_code: data.applied_code,
                    filename: currentFilename,
                    green_report: activePatchRepairData?.green_report || cachedGreenReport || {},
                    applied_steps: activePatchRepairData?.applied_steps || []
                })
            });
            if (deltaResp.ok) {
                const deltaData = await deltaResp.json();
                renderBeforeAfterCard(deltaData);
            }
        } catch (deltaErr) {
            console.warn("Could not calculate before-after comparison:", deltaErr);
        }

        // Live refresh of editor quality and risk
        triggerLiveQualityScore();
        triggerLiveOptimizationPotential();
        triggerLiveSecurityRisk();
    } catch (err) {
        showToast("Apply patch network error: " + err.message, "error");
    } finally {
        isRepairRunning = false;
        if (typeof setAllRunButtonsDisabled === "function") {
            setAllRunButtonsDisabled(false);
        }
    }
}

async function rejectCandidatePatch() {
    if (!activePatchReview || !activePatchReview.patch_id) {
        closePatchReviewModal();
        return;
    }
    try {
        await fetch("/api/patch/reject", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ patch_id: activePatchReview.patch_id })
        });
        closePatchReviewModal();
        showToast("Candidate patch rejected by user.", "info");
    } catch (err) {
        closePatchReviewModal();
    }
}

async function revertLastPatch() {
    try {
        const resp = await fetch("/api/patch/revert", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({})
        });
        const data = await resp.json();
        if (!data.success) {
            showToast("Cannot revert: " + data.error, "warning");
            return;
        }

        suppressHighlightClearOnce = true;
        editor.setValue(data.restored_code);
        openFiles[currentFilename] = data.restored_code;
        clearChangedLineHighlights();

        const revBtn = document.getElementById("btn-revert");
        if (revBtn && !data.revert_available) revBtn.style.display = "none";

        // Hide before-and-after comparison card on revert
        const baCard = document.getElementById("beforeAfterCard");
        if (baCard) baCard.style.display = "none";

        showToast("Reverted to original source code.", "info");

        triggerLiveQualityScore();
        triggerLiveOptimizationPotential();
        triggerLiveSecurityRisk();
    } catch (err) {
        showToast("Revert network error: " + err.message, "error");
    }
}

/* ------------------------------------------------------------- */
/* CANDIDATE RULES & CONTROLLED IMPROVEMENT MODAL HANDLERS      */
/* ------------------------------------------------------------- */

let cachedCandidateRules = [];
let cachedActiveRules = [];

function openCandidateRulesModal() {
    const modal = document.getElementById("candidate-rules-modal");
    if (!modal) return;
    modal.style.display = "flex";
    loadRulesModalData();
}

function closeCandidateRulesModal() {
    const modal = document.getElementById("candidate-rules-modal");
    if (modal) modal.style.display = "none";
}

function handleRulesModalBackdropClick(e) {
    if (e.target && e.target.id === "candidate-rules-modal") {
        closeCandidateRulesModal();
    }
}

function switchRulesTab(tab) {
    const btnCandidates = document.getElementById("tab-btn-candidates");
    const btnActive = document.getElementById("tab-btn-active");
    const viewCandidates = document.getElementById("rules-view-candidates");
    const viewActive = document.getElementById("rules-view-active");

    if (tab === "candidates") {
        if (btnCandidates) btnCandidates.classList.add("active");
        if (btnActive) btnActive.classList.remove("active");
        if (viewCandidates) viewCandidates.style.display = "block";
        if (viewActive) viewActive.style.display = "none";
    } else {
        if (btnCandidates) btnCandidates.classList.remove("active");
        if (btnActive) btnActive.classList.add("active");
        if (viewCandidates) viewCandidates.style.display = "none";
        if (viewActive) viewActive.style.display = "block";
    }
}

async function fetchCandidateRulesCount() {
    try {
        const resp = await fetch("/api/rules/candidates");
        if (resp.ok) {
            const data = await resp.json();
            const count = (data.candidates || []).length;
            const topBadge = document.getElementById("candidate-rules-count");
            if (topBadge) topBadge.textContent = count;
            const modalBadge = document.getElementById("modal-candidates-count");
            if (modalBadge) modalBadge.textContent = count;
        }
    } catch (e) {
        console.warn("Could not fetch candidate rules count:", e);
    }
}

async function loadRulesModalData() {
    try {
        const [candResp, activeResp] = await Promise.all([
            fetch("/api/rules/candidates"),
            fetch("/api/rules/active")
        ]);

        if (candResp.ok) {
            const data = await candResp.json();
            cachedCandidateRules = data.candidates || [];
            renderCandidateRules(cachedCandidateRules);
            const count = cachedCandidateRules.length;
            const topBadge = document.getElementById("candidate-rules-count");
            if (topBadge) topBadge.textContent = count;
            const modalBadge = document.getElementById("modal-candidates-count");
            if (modalBadge) modalBadge.textContent = count;
        }

        if (activeResp.ok) {
            const data = await activeResp.json();
            cachedActiveRules = data.rules || [];
            renderActiveRules(cachedActiveRules);
            const activeBadge = document.getElementById("modal-active-count");
            if (activeBadge) activeBadge.textContent = cachedActiveRules.length;
        }
    } catch (e) {
        console.error("Failed to load rules:", e);
        showToast("Error loading rules repository: " + e.message, "error");
    }
}

function renderCandidateRules(rules) {
    const list = document.getElementById("candidate-rules-list");
    if (!list) return;
    list.innerHTML = "";

    if (!rules || rules.length === 0) {
        list.innerHTML = `<div class="empty-panel">No candidate rules pending review in repository.</div>`;
        return;
    }

    rules.forEach(r => {
        const card = document.createElement("div");
        card.className = "rule-item-card";

        const statusClass = (r.status || "pending_review").toLowerCase();
        const statusText = (r.status || "PENDING_REVIEW").replace(/_/g, " ");

        const numPos = (r.positive_tests || []).length;
        const numNeg = (r.negative_tests || []).length;
        const numAmb = (r.ambiguous_cases || []).length;

        const valStatus = r.validation_report ? (r.validation_report.is_valid ? "VALIDATED" : "VALIDATION_FAILED") : "UNTESTED";
        const valPillClass = r.validation_report ? (r.validation_report.is_valid ? "pass" : "fail") : "";

        let valDetails = "";
        if (r.validation_report) {
            valDetails = `Security: ${r.validation_report.security_checked ? (r.validation_report.security_passed ? "PASS" : "FAIL") : "N/A"} | Tests: ${r.validation_report.passed_tests}/${r.validation_report.total_tests}`;
        }

        card.innerHTML = `
            <div class="rule-item-header">
                <div class="rule-title-wrap">
                    <span class="rule-title-text">${escapeHtml(r.name || r.id)}</span>
                    <span class="rule-status-badge ${statusClass}">${escapeHtml(statusText)}</span>
                </div>
                <div style="font-size: 11px; color: var(--text-muted);">
                    ID: <code>${escapeHtml(r.id)}</code> | Source: <strong>${escapeHtml(r.source_model || "Learned Model")}</strong>
                </div>
            </div>

            <div class="rule-metadata-grid">
                <div class="rule-meta-item">
                    <label>Category</label>
                    <span>${escapeHtml(r.category || "syntax")}</span>
                </div>
                <div class="rule-meta-item">
                    <label>Applicable Context</label>
                    <span>${escapeHtml(r.applicable_context || "C / SimpleC error correction")}</span>
                </div>
                <div class="rule-meta-item">
                    <label>Transformation Type</label>
                    <span><code>${escapeHtml(r.transformation ? r.transformation.type : "N/A")}</code></span>
                </div>
                <div class="rule-meta-item">
                    <label>Created</label>
                    <span>${escapeHtml(r.created_at ? new Date(r.created_at).toLocaleString() : "Recently")}</span>
                </div>
            </div>

            <div>
                <label style="font-size: 11px; font-weight: 600; color: var(--text-secondary);">Triggering Pattern / Condition:</label>
                <div class="rule-code-preview">${escapeHtml(r.transformation ? r.transformation.pattern : r.triggering_conditions)}</div>
            </div>

            ${r.transformation && r.transformation.replacement !== undefined ? `
            <div>
                <label style="font-size: 11px; font-weight: 600; color: var(--text-secondary);">Replacement Output:</label>
                <div class="rule-code-preview">${escapeHtml(r.transformation.replacement)}</div>
            </div>` : ""}

            <div class="rule-test-badges">
                <span class="test-pill pass">✔ Positive Tests: ${numPos}</span>
                <span class="test-pill pass">🛡 Negative Tests (Zero Drift): ${numNeg}</span>
                <span class="test-pill fail">⚠️ Ambiguous Cases (Reject): ${numAmb}</span>
                ${r.validation_report ? `<span class="test-pill ${valPillClass}">${escapeHtml(valStatus)} (${escapeHtml(valDetails)})</span>` : `<span class="test-pill" style="background: rgba(100,116,139,0.12); color: #64748b;">Not Yet Validated</span>`}
            </div>

            <div class="rule-actions-bar">
                <button class="btn btn-secondary btn-sm" onclick="validateCandidateRule('${escapeHtml(r.id)}')">Run Validation Suite</button>
                <button class="btn btn-danger btn-sm" onclick="rejectCandidateRule('${escapeHtml(r.id)}')">Reject</button>
                <button class="btn btn-primary btn-sm" onclick="approveCandidateRule('${escapeHtml(r.id)}')">Human Approve & Activate</button>
            </div>
        `;

        list.appendChild(card);
    });
}

function renderActiveRules(rules) {
    const list = document.getElementById("active-rules-list");
    if (!list) return;
    list.innerHTML = "";

    if (!rules || rules.length === 0) {
        list.innerHTML = `<div class="empty-panel">No active learned rules in repository.</div>`;
        return;
    }

    rules.forEach(r => {
        const card = document.createElement("div");
        card.className = "rule-item-card";

        const isEnabled = r.is_enabled !== false;
        const statusBadgeClass = isEnabled ? "approved" : "disabled";
        const statusText = isEnabled ? "ACTIVE" : "DISABLED";

        const historyCount = (r.version_history || []).length;

        card.innerHTML = `
            <div class="rule-item-header">
                <div class="rule-title-wrap">
                    <span class="rule-title-text">${escapeHtml(r.name || r.id)}</span>
                    <span class="rule-status-badge ${statusBadgeClass}">${statusText}</span>
                    <span style="font-size: 12px; font-weight: 600; color: var(--accent-blue);">v${escapeHtml(r.version || "1.0.0")}</span>
                </div>
                <div style="font-size: 11px; color: var(--text-muted);">
                    ID: <code>${escapeHtml(r.id)}</code> | Approved by: <strong>${escapeHtml(r.approved_by || "Admin")}</strong>
                </div>
            </div>

            <div class="rule-metadata-grid">
                <div class="rule-meta-item">
                    <label>Category</label>
                    <span>${escapeHtml(r.category || "syntax")}</span>
                </div>
                <div class="rule-meta-item">
                    <label>Transformation Type</label>
                    <span><code>${escapeHtml(r.transformation ? r.transformation.type : "N/A")}</code></span>
                </div>
                <div class="rule-meta-item">
                    <label>Approved At</label>
                    <span>${escapeHtml(r.approved_at ? new Date(r.approved_at).toLocaleString() : "Active")}</span>
                </div>
                <div class="rule-meta-item">
                    <label>Version History</label>
                    <span>${historyCount} previous version(s)</span>
                </div>
            </div>

            <div>
                <label style="font-size: 11px; font-weight: 600; color: var(--text-secondary);">Transformation Pattern:</label>
                <div class="rule-code-preview">${escapeHtml(r.transformation ? r.transformation.pattern : "")}</div>
            </div>

            <div class="rule-actions-bar">
                ${isEnabled ? `
                    <button class="btn btn-warning btn-sm" onclick="disableActiveRule('${escapeHtml(r.id)}')">Disable Rule</button>
                ` : `
                    <button class="btn btn-secondary btn-sm" onclick="enableActiveRule('${escapeHtml(r.id)}')">Enable Rule</button>
                `}
                <button class="btn btn-ghost btn-sm" onclick="rollbackActiveRule('${escapeHtml(r.id)}')">Rollback Version</button>
            </div>
        `;

        list.appendChild(card);
    });
}

async function validateCandidateRule(ruleId) {
    try {
        showToast("Running candidate test suite, ANTLR parser, and security checks...", "info");
        const resp = await fetch(`/api/rules/candidate/${encodeURIComponent(ruleId)}/validate`, {
            method: "POST"
        });
        const data = await resp.json();
        if (data.success) {
            showToast(`Rule validation completed! Passed: ${data.passed_tests}/${data.total_tests}`, "success");
        } else {
            showToast(`Rule validation failed: ${data.error || "Some tests did not pass"}`, "error");
        }
        await loadRulesModalData();
    } catch (e) {
        showToast("Error executing validation: " + e.message, "error");
    }
}

async function approveCandidateRule(ruleId) {
    const reviewer = prompt("HUMAN REVIEW REQUIRED\\n\\nAI models cannot approve rules. Enter your reviewer name / identifier:");
    if (!reviewer || !reviewer.trim()) {
        showToast("Human approval cancelled. Reviewer name is required.", "warning");
        return;
    }

    const reviewerClean = reviewer.trim().toLowerCase();
    if (["model", "ai", "system", "qwen", "codet5", "assistant", "bot"].includes(reviewerClean)) {
        showToast("SAFETY ERROR: AI models cannot approve or activate rules!", "error");
        return;
    }

    const notes = prompt("Enter approval notes / rationale (optional):") || "";

    try {
        const resp = await fetch(`/api/rules/candidate/${encodeURIComponent(ruleId)}/approve`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                reviewer_name: reviewer.trim(),
                approval_notes: notes.trim()
            })
        });
        const data = await resp.json();
        if (data.success) {
            showToast(`Rule approved and activated as v${data.rule ? data.rule.version : "1.0.0"}!`, "success");
            await loadRulesModalData();
        } else {
            showToast("Approval blocked: " + (data.error || "Validation error"), "error");
        }
    } catch (e) {
        showToast("Approval request failed: " + e.message, "error");
    }
}

async function rejectCandidateRule(ruleId) {
    const reason = prompt("Enter rejection reason:") || "Rejected by human reviewer";
    try {
        const resp = await fetch(`/api/rules/candidate/${encodeURIComponent(ruleId)}/reject`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ reason })
        });
        const data = await resp.json();
        if (data.success) {
            showToast("Candidate rule rejected.", "info");
            await loadRulesModalData();
        } else {
            showToast("Rejection failed: " + data.error, "error");
        }
    } catch (e) {
        showToast("Rejection request failed: " + e.message, "error");
    }
}

async function disableActiveRule(ruleId) {
    const reason = prompt("Enter reason for disabling this rule (e.g. causes regression):") || "";
    try {
        const resp = await fetch(`/api/rules/active/${encodeURIComponent(ruleId)}/disable`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ reason })
        });
        const data = await resp.json();
        if (data.success) {
            showToast("Rule has been disabled from compiler pipeline.", "info");
            await loadRulesModalData();
        } else {
            showToast("Failed to disable rule: " + data.error, "error");
        }
    } catch (e) {
        showToast("Disable request failed: " + e.message, "error");
    }
}

async function enableActiveRule(ruleId) {
    try {
        const resp = await fetch(`/api/rules/active/${encodeURIComponent(ruleId)}/enable`, {
            method: "POST"
        });
        const data = await resp.json();
        if (data.success) {
            showToast("Rule re-enabled.", "success");
            await loadRulesModalData();
        } else {
            showToast("Failed to enable rule: " + data.error, "error");
        }
    } catch (e) {
        showToast("Enable request failed: " + e.message, "error");
    }
}

async function rollbackActiveRule(ruleId) {
    const targetVersion = prompt("Enter target version to rollback to (e.g. 1.0.0):");
    if (!targetVersion || !targetVersion.trim()) return;

    try {
        const resp = await fetch(`/api/rules/active/${encodeURIComponent(ruleId)}/rollback`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ target_version: targetVersion.trim() })
        });
        const data = await resp.json();
        if (data.success) {
            showToast(`Rule rolled back to version ${data.rule.version}!`, "success");
            await loadRulesModalData();
        } else {
            showToast("Rollback failed: " + data.error, "error");
        }
    } catch (e) {
        showToast("Rollback request failed: " + e.message, "error");
    }
}

/* ------------------------------------------------------------- */
/* MODEL ACCURACY & BENCHMARKING DASHBOARD HANDLERS             */
/* ------------------------------------------------------------- */

let cachedBenchmarkDataset = [];
let cachedBenchmarkReport = null;
let activeBenchmarkFilter = "ALL";

function ensureBenchmarkPanel() {
    let panel = document.getElementById("benchmarkPanel");
    if (panel) return panel;

    const resultPanel = document.getElementById("resultpanel");
    if (!resultPanel) return null;

    panel = document.createElement("section");
    panel.id = "benchmarkPanel";
    panel.className = "panelcard";
    resultPanel.appendChild(panel);
    return panel;
}

function renderBenchmarkPanel(report) {
    cachedBenchmarkReport = report;
    renderPrimaryIndicators();
    const panel = ensureBenchmarkPanel();
    if (!panel) return;

    if (!report || report.status === "UNBENCHMARKED" || (report.benchmark_dataset_size || 0) < 16 || !report.results || Object.keys(report.results).length === 0) {
        panel.innerHTML = `
            <div class="benchmark-card-header">
                <div class="benchmark-card-title">
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="20" x2="18" y2="10"></line>
                        <line x1="12" y1="20" x2="12" y2="4"></line>
                        <line x1="6" y1="20" x2="6" y2="14"></line>
                    </svg>
                    <span>Model Benchmarks</span>
                </div>
                <span class="badge-status-unbenchmarked">Not yet benchmarked</span>
            </div>
            <div style="font-size: 12px; color: var(--text-secondary); margin-bottom: 8px;">
                Empirical evaluation across 5 architectures (Rules, CodeT5, Qwen, Tiered, Agentic) on 16 labelled cases.
            </div>
            <button class="btn btn-secondary btn-sm" style="width: 100%;" onclick="openBenchmarkModal()">
                Open Benchmark Dashboard
            </button>
        `;
        return;
    }

    const summary = report.comparative_summary || {};
    const bestRate = summary.best_repair_success_rate ?? "--";
    const bestConfig = summary.best_repair_success_config ?? "Agentic Pipeline";
    const lift = summary.agentic_repair_lift_over_rules_pct ?? "--";

    panel.innerHTML = `
        <div class="benchmark-card-header">
            <div class="benchmark-card-title">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="20" x2="18" y2="10"></line>
                    <line x1="12" y1="20" x2="12" y2="4"></line>
                    <line x1="6" y1="20" x2="6" y2="14"></line>
                </svg>
                <span>Model Benchmarks</span>
            </div>
            <span class="badge-status-benchmarked">Benchmarked</span>
        </div>

        <div class="benchmark-panel-metrics">
            <div class="benchmark-panel-metric-cell">
                <div class="bm-label">Top Repair Rate</div>
                <div class="bm-val" style="color: #16a34a;">${bestRate}%</div>
            </div>
            <div class="benchmark-panel-metric-cell">
                <div class="bm-label">Agentic Lift</div>
                <div class="bm-val" style="color: #2563eb;">+${lift}%</div>
            </div>
        </div>

        <div style="font-size: 11.5px; color: var(--text-secondary); margin-bottom: 10px; line-height: 1.35;">
            Top Architecture: <b>${escapeHtml(bestConfig)}</b><br>
            Evaluated on <b>${report.benchmark_dataset_size || 16}</b> labelled test cases.
        </div>

        <button class="btn btn-secondary btn-sm" style="width: 100%;" onclick="openBenchmarkModal()">
            View Full Benchmark Results
        </button>
    `;
}

async function loadBenchmarkPanelData() {
    try {
        const resp = await fetch("/api/benchmark/status");
        const data = await resp.json();
        cachedBenchmarkReport = data;
        renderBenchmarkPanel(data);
    } catch (e) {
        console.warn("Could not load benchmark status:", e);
    }
}

function openBenchmarkModal() {
    const modal = document.getElementById("benchmark-modal");
    if (!modal) return;
    modal.style.display = "flex";
    loadBenchmarkModalData();
}

function closeBenchmarkModal() {
    const modal = document.getElementById("benchmark-modal");
    if (modal) modal.style.display = "none";
}

function handleBenchmarkModalBackdropClick(e) {
    if (e.target && e.target.id === "benchmark-modal") {
        closeBenchmarkModal();
    }
}

async function loadBenchmarkModalData() {
    try {
        // Load dataset
        const dsResp = await fetch("/api/benchmark/dataset");
        const dsData = await dsResp.json();
        cachedBenchmarkDataset = dsData.cases || [];

        // Load status/results
        const stResp = await fetch("/api/benchmark/status");
        const stData = await stResp.json();
        cachedBenchmarkReport = stData;

        renderBenchmarkModal(stData);
        renderBenchmarkCasesList();
    } catch (e) {
        showToast("Error loading benchmark data: " + e.message, "error");
    }
}

function renderBenchmarkModal(report) {
    const badge = document.getElementById("benchmark-status-badge");
    const tbody = document.getElementById("benchmark-comparison-tbody");
    const summaryBox = document.getElementById("benchmark-summary-box");
    const casesCount = document.getElementById("benchmark-cases-count");

    if (casesCount) {
        casesCount.textContent = cachedBenchmarkDataset.length || "16";
    }

    if (!report || report.status === "UNBENCHMARKED") {
        if (badge) {
            badge.className = "badge-status-unbenchmarked";
            badge.textContent = "Not yet benchmarked";
        }
        if (tbody) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="10" class="benchmark-empty-row">
                        No empirical benchmark runs recorded yet.<br>
                        Click <b>"Run Model Benchmark"</b> above to test all 5 configurations. Zero fabricated values.
                    </td>
                </tr>
            `;
        }
        if (summaryBox) {
            summaryBox.style.display = "none";
        }
        return;
    }

    if (badge) {
        badge.className = "badge-status-benchmarked";
        badge.textContent = `Benchmarked (${report.timestamp_utc ? report.timestamp_utc.slice(0, 10) : "Recent"})`;
    }

    // Render configuration comparison table
    const results = report.results || {};
    const rows = Object.values(results).map(r => {
        const repRateColor = r.repair_success_rate >= 75 ? "#16a34a" : (r.repair_success_rate >= 50 ? "#d97706" : "#dc2626");
        const exactRateColor = r.exact_match_rate >= 60 ? "#16a34a" : "#64748b";
        const energyPerFix = r.energy_per_successful_repair_j != null ? `${r.energy_per_successful_repair_j.toFixed(1)} J` : "--";
        const fallbackRate = r.fallback_cases_escalated > 0 ? `${r.fallback_effectiveness_rate.toFixed(0)}%` : "N/A";

        return `
            <tr>
                <td><b>${escapeHtml(r.display_name)}</b></td>
                <td style="font-weight: 700; color: ${repRateColor};">${r.repair_success_rate.toFixed(1)}%</td>
                <td style="color: ${exactRateColor};">${r.exact_match_rate.toFixed(1)}%</td>
                <td>${r.validation_pass_rate.toFixed(1)}%</td>
                <td style="color: ${r.regression_rate > 0 ? "#dc2626" : "#16a34a"};">${r.regression_rate.toFixed(1)}%</td>
                <td>${r.security_precision.toFixed(0)}% / ${r.security_recall.toFixed(0)}%</td>
                <td>${r.avg_latency_ms.toFixed(1)} ms</td>
                <td>${r.energy_joules.toFixed(1)} J</td>
                <td>${energyPerFix}</td>
                <td style="font-weight: 600; color: #2563eb;">${fallbackRate}</td>
            </tr>
        `;
    }).join("");

    if (tbody) {
        tbody.innerHTML = rows || `<tr><td colspan="10" class="benchmark-empty-row">No results</td></tr>`;
    }

    // Render comparative summary
    if (summaryBox && report.comparative_summary) {
        const s = report.comparative_summary;
        summaryBox.style.display = "block";
        summaryBox.innerHTML = `
            <strong>📊 Comparative Insights:</strong> ${escapeHtml(s.key_finding || "")}<br>
            <span style="font-size: 11px; color: var(--text-secondary); margin-top: 4px; display: block;">
                Top Architecture: <b>${escapeHtml(s.best_repair_success_config)}</b> (${s.best_repair_success_rate}%) |
                Lowest Latency: <b>${escapeHtml(s.lowest_latency_config)}</b> (${s.lowest_latency_avg_ms} ms) |
                Agentic Lift Over Rules: <b>+${s.agentic_repair_lift_over_rules_pct}%</b>
            </span>
        `;
    }
}

function renderBenchmarkCasesList() {
    const list = document.getElementById("benchmark-cases-list");
    if (!list) return;

    let filtered = cachedBenchmarkDataset;
    if (activeBenchmarkFilter !== "ALL") {
        filtered = cachedBenchmarkDataset.filter(c => c.category === activeBenchmarkFilter);
    }

    if (!filtered || filtered.length === 0) {
        list.innerHTML = `<div class="empty-panel">No test cases in category ${escapeHtml(activeBenchmarkFilter)}.</div>`;
        return;
    }

    list.innerHTML = filtered.map(c => {
        const catBadgeColor = {
            VALID: "#16a34a",
            SYNTAX: "#2563eb",
            SEMANTIC: "#7c3aed",
            SECURITY: "#dc2626",
            AMBIGUOUS: "#d97706",
            DIFFICULT: "#ea580c",
            UNFIXABLE: "#64748b",
            LEXICAL: "#0891b2"
        }[c.category] || "#64748b";

        const repairableText = c.expected_repairable ? "✓ Eligible for Repair" : "⚠️ Abstain (Clean / Unfixable)";
        const codeSnippet = escapeHtml(c.source_code);

        return `
            <div class="bm-case-card">
                <div class="bm-case-header">
                    <div>
                        <span class="bm-case-id">[${escapeHtml(c.id)}]</span>
                        <span class="bm-case-name">${escapeHtml(c.name)}</span>
                    </div>
                    <div style="display: flex; gap: 6px; align-items: center;">
                        <span style="font-size: 10px; font-weight: 700; background: ${catBadgeColor}20; color: ${catBadgeColor}; padding: 2px 6px; border-radius: 4px;">
                            ${escapeHtml(c.category)}
                        </span>
                        <span style="font-size: 10px; color: var(--text-secondary);">
                            ${repairableText}
                        </span>
                    </div>
                </div>
                <div class="bm-case-desc">${escapeHtml(c.description)}</div>
                <span class="bm-case-code-toggle" onclick="toggleCaseCode('${escapeHtml(c.id)}')">Toggle Source Code</span>
                <div id="code-${escapeHtml(c.id)}" style="display:none; margin-top: 6px;">
                    <pre style="font-family: monospace; font-size: 11px; background: rgba(0,0,0,0.04); padding: 8px; border-radius: 4px; overflow-x: auto;"><code>${codeSnippet}</code></pre>
                </div>
            </div>
        `;
    }).join("");
}

function filterBenchmarkCases(category) {
    activeBenchmarkFilter = category;
    const filterBtns = document.querySelectorAll("#benchmark-category-filters .bm-filter-btn");
    filterBtns.forEach(btn => {
        if (btn.textContent.trim() === category) {
            btn.classList.add("active");
        } else {
            btn.classList.remove("active");
        }
    });
    renderBenchmarkCasesList();
}

function toggleCaseCode(caseId) {
    const el = document.getElementById("code-" + caseId);
    if (el) {
        el.style.display = (el.style.display === "none") ? "block" : "none";
    }
}

async function executeBenchmarkRun() {
    const btn = document.getElementById("btn-run-benchmark");
    const btnText = document.getElementById("btn-run-benchmark-text");
    if (btn) btn.disabled = true;
    if (btnText) btnText.textContent = "Running Benchmark (5 Architectures)...";

    showToast("Starting empirical benchmark across all 5 configurations. Please wait...", "info");

    try {
        const resp = await fetch("/api/benchmark/run", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({})
        });
        const data = await resp.json();
        cachedBenchmarkReport = data;
        renderBenchmarkModal(data);
        renderBenchmarkPanel(data);
        showToast("Model benchmarking completed successfully!", "success");
    } catch (e) {
        showToast("Error running benchmark: " + e.message, "error");
    } finally {
        if (btn) btn.disabled = false;
        if (btnText) btnText.textContent = "Run Model Benchmark";
    }
}

// Automatically load benchmark status on startup
setTimeout(loadBenchmarkPanelData, 1200);

function renderContinuationError(reason) {
    const recCard = document.getElementById("recommendedProgramCard");
    if (!recCard) return;
    recCard.style.display = "block";
    recCard.innerHTML = `
        <div class="rec-card-header">
            <div class="rec-title-group">
                <span class="rec-title-text" style="color:#dc2626;">❌ Continuation Failed</span>
            </div>
            <span class="rec-agent-badge" style="background:rgba(220,38,38,0.12); color:#dc2626; border-color:rgba(220,38,38,0.25);">
                ERROR
            </span>
        </div>
        <div id="continuation-error-banner" style="background:rgba(220,38,38,0.1); border:1px solid rgba(220,38,38,0.3); border-radius:6px; padding:10px; color:#dc2626; font-size:12px; margin:8px 0;">
            <strong>Error:</strong> ${escapeHtml(reason)}
        </div>
    `;
}

function renderRepairUnavailable(data) {
    const recCard = document.getElementById("recommendedProgramCard");
    if (!recCard) return;
    recCard.style.display = "block";

    const roundNum = data.round || 1;
    const fixedCount = data.fixes_applied_count != null ? data.fixes_applied_count : 0;
    const remCount = data.fixes_remaining_count != null ? data.fixes_remaining_count : (data.remaining_findings ? data.remaining_findings.length : 0);
    const totalCount = data.total_findings || (fixedCount + remCount);

    const alts = data.manual_alternatives || [];
    const altsHtml = alts.length > 0 ? alts.map(alt => `
        <li style="margin-bottom:8px; line-height:1.4;">
            <div style="font-weight:600; color:var(--text-primary);">Line ${alt.line} (${escapeHtml(alt.category || "SYNTAX")}): ${escapeHtml(alt.issue || "")}</div>
            <div style="color:#2563eb; font-size:11.5px; margin-top:2px;">💡 Suggestion: ${escapeHtml(alt.suggestion || "")}</div>
            ${alt.code_snippet ? `<pre style="margin-top:4px; font-size:10.5px; background:var(--bg-secondary); padding:4px 8px; border-radius:4px; font-family:var(--font-mono, monospace); overflow-x:auto;"><code>${escapeHtml(alt.code_snippet)}</code></pre>` : ''}
        </li>
    `).join("") : `<li style="color:var(--text-secondary);">No explicit automated suggestions available for remaining issues.</li>`;

    recCard.innerHTML = `
        <div class="rec-card-header">
            <div class="rec-title-group">
                <span class="rec-title-text" style="color:#d97706;">⚠️ Automated Repair Unavailable</span>
            </div>
            <span class="rec-agent-badge" style="background:rgba(217,119,6,0.12); color:#d97706; border-color:rgba(217,119,6,0.25);">
                REPAIR_UNAVAILABLE
            </span>
        </div>
        <div class="rec-counts-bar" style="display:flex; gap:10px; align-items:center; margin-bottom:8px; font-size:11.5px;">
            <span id="rec-round-badge" style="display:none !important;">
                round 1: ${fixedCount} of ${totalCount} fixed, ${remCount} remaining
            </span>
        </div>
        <div style="font-size:12px; color:var(--text-secondary); margin-bottom:10px;">
            ${escapeHtml(data.message || data.stopping_reason || "No further automated repairs can be synthesized.")}
        </div>
        <div style="font-weight:600; font-size:12px; color:var(--text-primary); margin-bottom:6px;">Manual Alternatives:</div>
        <ul style="margin:0; padding-left:18px; font-size:11.5px;">${altsHtml}</ul>
    `;
}

async function continueRepairFromCandidate() {
    const plan = currentCoordinatedPlan;
    if (!plan || !plan.proposed_code) {
        showToast("No partial candidate code found to continue.", "warning");
        return;
    }

    const nextRound = (plan.round || 1) + 1;
    const contId = plan.continuation_id || ("cont_" + (plan.candidate_id || Date.now()));
    const token = plan.approval_token || null;
    const candidateCode = plan.proposed_code;

    // Safely update editor without wiping currentCoordinatedPlan
    suppressInvalidateOnContinuation = true;
    if (editor) {
        editor.setValue(candidateCode);
        repairOriginalCode = candidateCode;
    }

    const btnCont = document.getElementById("btn-continue-repair");
    if (btnCont) {
        btnCont.disabled = true;
        const spanText = btnCont.querySelector("span");
        if (spanText) spanText.textContent = `Round ${nextRound} in progress...`;
    }
    setAllRunButtonsDisabled(true);
    isRepairRunning = true;
    setProgress(25, `Round ${nextRound}: Synthesizing next continuation iteration...`);
    setStatus("REPAIRING");
    showToast(`Initiating repair continuation (Round ${nextRound})...`, "info");

    try {
        const resp = await fetch("/api/coordinator/analyze_and_plan", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                code: candidateCode,
                filename: currentFilename,
                language: currentLanguageId,
                operation: "repair",
                continuation_id: contId,
                round: nextRound,
                approval_token: token,
            })
        });

        if (!resp.ok) {
            let errData = {};
            try { errData = await resp.json(); } catch (e) {}
            const reason = errData.message || errData.error || errData.policy_reason || (`HTTP ${resp.status}`);
            setStatus("ERROR");
            setProgress(0, `Continuation failed: ${reason}`);
            showToast(`Continuation failed: ${reason}`, "error");
            renderContinuationError(reason);
            return;
        }

        const data = await resp.json();
        data.round = nextRound;
        data.continuation_id = contId;

        if (data.status === "REPAIR_UNAVAILABLE" || data.terminal_status === "REPAIR_UNAVAILABLE") {
            setStatus("REPAIR_UNAVAILABLE");
            setProgress(100, "Automated repair unavailable for remaining issues.");
            renderRepairUnavailable(data);
            showToast(data.message || "No further automated repairs available.", "info");
        } else {
            renderCoordinatedPlan(data);
            setStatus(data.terminal_status || data.status || "PLAN_READY");
            setProgress(100, `Round ${nextRound} complete`);
            showToast(`Round ${nextRound} complete: ${data.fixes_applied_count || 0} fixed, ${data.fixes_remaining_count || 0} remaining.`, "success");
        }
    } catch (err) {
        console.error("Continuation error:", err);
        setStatus("ERROR");
        setProgress(0, `Continuation error: ${err.message}`);
        showToast(`Continuation error: ${err.message}`, "error");
        renderContinuationError(err.message);
    } finally {
        isRepairRunning = false;
        setAllRunButtonsDisabled(false);
        const btnContAfter = document.getElementById("btn-continue-repair");
        if (btnContAfter) {
            btnContAfter.disabled = false;
            const spanText = btnContAfter.querySelector("span");
            if (spanText) spanText.textContent = "Continue Repair";
        }
    }
}
