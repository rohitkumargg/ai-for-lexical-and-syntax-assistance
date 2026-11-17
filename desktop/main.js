const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn, execSync } = require('child_process');
const readline = require('readline');

// Enforce single-instance lock
const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
  app.quit();
  process.exit(0);
}

let mainWindow = null;
let pyProcess = null;
let isQuitting = false;
let reqSeq = 0;
const pendingRequests = new Map();

// Helper to kill entire process tree on Windows/POSIX
function killProcessTree(pid) {
  if (!pid) return;
  if (process.platform === 'win32') {
    try {
      execSync(`taskkill /pid ${pid} /T /F`, { stdio: 'ignore' });
    } catch (e) { }
  } else {
    try {
      process.kill(-pid, 'SIGKILL');
    } catch (e) {
      try { process.kill(pid, 'SIGKILL'); } catch (e2) { }
    }
  }
}

// Prerequisite check for gcc, java, ollama
function checkPrerequisites() {
  const missing = [];
  const isWin = process.platform === 'win32';
  const checkCmd = (cmd) => {
    try {
      execSync(isWin ? `where ${cmd}` : `which ${cmd}`, { stdio: 'ignore' });
      return true;
    } catch (e) {
      return false;
    }
  };

  if (!checkCmd('gcc')) missing.push('GCC (GNU Compiler Collection)');
  if (!checkCmd('java')) missing.push('Java Runtime (JRE/JDK for ANTLR)');
  if (!checkCmd('ollama')) missing.push('Ollama (Local LLM runner)');

  if (missing.length > 0) {
    dialog.showMessageBox({
      type: 'warning',
      title: 'Prerequisite Notice',
      message: 'The following external tools were not detected on your system PATH:\n\n' +
        missing.map(m => ` • ${m}`).join('\n') +
        '\n\nSimpleC relies on these local tools for native compilation, syntax parsing, and AI-assisted repairs. Please install them and ensure they are accessible on your system PATH.'
    });
  }

  return missing;
}

// Resolve backend executable or script path
function getBackendLaunchConfig() {
  const possibleExePaths = [
    path.join(process.resourcesPath || '', 'backend_ipc', 'backend_ipc.exe'),
    path.join(process.resourcesPath || '', 'bin', 'backend_ipc', 'backend_ipc.exe'),
    path.join(__dirname, 'bin', 'backend_ipc', 'backend_ipc.exe'),
    path.join(__dirname, '..', 'bin', 'backend_ipc', 'backend_ipc.exe'),
    path.join(app.getAppPath(), 'desktop', 'bin', 'backend_ipc', 'backend_ipc.exe')
  ];

  for (const exePath of possibleExePaths) {
    if (fs.existsSync(exePath)) {
      return {
        cmd: exePath,
        args: [],
        cwd: path.dirname(exePath)
      };
    }
  }

  // Development fallback: invoke python directly on backend_ipc.py
  const scriptPath = path.join(__dirname, 'backend_ipc.py');
  const pythonCmd = process.env.PYTHON_PATH || 'python';
  return {
    cmd: pythonCmd,
    args: [scriptPath],
    cwd: path.join(__dirname, '..')
  };
}

function startBackendIPC() {
  const launchCfg = getBackendLaunchConfig();
  const userDataPath = app.getPath('userData');

  const backendEnv = {
    ...process.env,
    PYTHONUNBUFFERED: '1',
    APP_DATA_DIR: userDataPath,
    DATA_DIR: userDataPath
  };

  // If local models adapter exists, set env var
  const modelsDir = path.join(launchCfg.cwd, 'models');
  const patchAdapterDir = path.join(modelsDir, 'codet5_patch_adapter');
  const baseModelDir = path.join(modelsDir, 'codet5-base');
  if (fs.existsSync(patchAdapterDir)) {
    backendEnv.CD_PATCH_ADAPTER_DIR = patchAdapterDir;
  }
  if (fs.existsSync(baseModelDir)) {
    backendEnv.CD_BASE_MODEL_NAME = baseModelDir;
  }

  try {
    pyProcess = spawn(launchCfg.cmd, launchCfg.args, {
      cwd: launchCfg.cwd,
      stdio: ['pipe', 'pipe', 'inherit'],
      env: backendEnv
    });
  } catch (err) {
    dialog.showErrorBox(
      'Backend Initialization Failed',
      `Failed to launch SimpleC backend process: ${err.message}`
    );
    return;
  }

  const rl = readline.createInterface({
    input: pyProcess.stdout,
    crlfDelay: Infinity
  });

  rl.on('line', (line) => {
    line = line.trim();
    if (!line) return;
    try {
      const res = JSON.parse(line);
      const reqId = res.id;
      if (reqId && pendingRequests.has(reqId)) {
        const { resolve } = pendingRequests.get(reqId);
        pendingRequests.delete(reqId);
        resolve(res);
      }
    } catch (err) {
      console.error('[main.js] Error parsing Python IPC output:', err, line);
    }
  });

  pyProcess.on('exit', (code, signal) => {
    console.log(`[main.js] Python IPC process exited with code ${code}, signal ${signal}`);
    for (const [id, { reject }] of pendingRequests.entries()) {
      reject(new Error(`Backend IPC terminated before response for request ${id}`));
    }
    pendingRequests.clear();

    if (!isQuitting) {
      dialog.showErrorBox(
        'Backend Process Terminated',
        `The SimpleC backend process terminated unexpectedly (code: ${code}, signal: ${signal}). Application functionality may be impacted.`
      );
    }
  });
}

function sendIPCRequest(route, args = {}) {
  return new Promise((resolve, reject) => {
    if (!pyProcess || pyProcess.killed) {
      return reject(new Error('Python backend IPC is not running.'));
    }
    const id = String(++reqSeq);
    pendingRequests.set(id, { resolve, reject });
    const payload = JSON.stringify({ id, route, args }) + '\n';
    pyProcess.stdin.write(payload, 'utf-8');
  });
}

// All known routes to register
const ROUTES = [
  'languages', 'examples', 'load_example', 'create_file', 'save_file',
  'models_status', 'models_unload', 'quality_score', 'quality_config',
  'optimization_potential', 'optimization_config', 'security_risk',
  'security_risk_delta', 'security_risk_config', 'security_report',
  'security_compare', 'security_benchmark', 'security_remediation',
  'security_apply', 'security_prescan', 'security_approval_check',
  'security_approval_approve', 'security_approval_cancel', 'run_program',
  'testcase', 'repair', 'repair_job_start', 'repair_job_status',
  'repair_job_cancel', 'repair_job_delete', 'coordinator_cancel',
  'coordinator_analyze_and_plan', 'repair_post_apply', 'pipeline_latest',
  'pipeline_run', 'validate_patch', 'apply_patch', 'reject_patch',
  'revert_patch', 'dashboard_before_after', 'improvement_advise',
  'improvement_candidate_apply', 'improvement_candidate_rollback',
  'improvement_candidate_reject', 'rules_candidates', 'rules_propose',
  'rules_candidate_validate', 'rules_candidate_approve',
  'rules_candidate_reject', 'rules_active', 'rules_active_disable',
  'rules_active_enable', 'rules_active_rollback', 'rules_history',
  'green_config', 'green_measure', 'green_history', 'benchmark_status',
  'benchmark_dataset', 'benchmark_definitions', 'benchmark_run'
];

function registerIPCHandlers() {
  for (const route of ROUTES) {
    ipcMain.handle(`api:${route}`, async (event, args) => {
      return await sendIPCRequest(route, args || {});
    });
  }

  // Generic handler allowing path-based dispatch
  ipcMain.handle('api:request', async (event, { route, args }) => {
    return await sendIPCRequest(route, args || {});
  });
}

function resolvePreloadPath() {
  const possiblePaths = [
    path.join(__dirname, 'preload.js'),
    path.join(__dirname, '..', 'preload.js'),
    path.join(app.getAppPath(), 'desktop', 'preload.js'),
    path.join(app.getAppPath(), 'preload.js')
  ];
  for (const p of possiblePaths) {
    if (fs.existsSync(p)) return p;
  }
  return path.join(__dirname, 'preload.js');
}

function resolveIndexPath() {
  const possiblePaths = [
    path.join(process.resourcesPath || '', 'gui', 'templates', 'index.html'),
    path.join(__dirname, '..', 'gui', 'templates', 'index.html'),
    path.join(app.getAppPath(), 'gui', 'templates', 'index.html'),
    path.join(app.getAppPath(), '..', 'gui', 'templates', 'index.html')
  ];
  for (const p of possiblePaths) {
    if (fs.existsSync(c = p)) return c;
  }
  return path.join(__dirname, '..', 'gui', 'templates', 'index.html');
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    title: 'SimpleC AI-Assisted Compiler IDE',
    webPreferences: {
      preload: resolvePreloadPath(),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false
    }
  });

  // Load index.html directly from disk via file:// protocol
  const indexPath = resolveIndexPath();
  mainWindow.loadFile(indexPath);

  // Disable DevTools in production
  if (app.isPackaged) {
    mainWindow.webContents.on('devtools-opened', () => {
      mainWindow.webContents.closeDevTools();
    });
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// App lifecycle hooks
app.on('second-instance', () => {
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.focus();
  }
});

app.whenReady().then(() => {
  checkPrerequisites();
  startBackendIPC();
  registerIPCHandlers();
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  isQuitting = true;
  if (pyProcess && pyProcess.pid) {
    killProcessTree(pyProcess.pid);
    pyProcess = null;
  }
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  isQuitting = true;
  if (pyProcess && pyProcess.pid) {
    killProcessTree(pyProcess.pid);
    pyProcess = null;
  }
});
