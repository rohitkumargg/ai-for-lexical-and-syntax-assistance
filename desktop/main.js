const { app, BrowserWindow, protocol, ipcMain, net } = require('electron');
const path = require('path');
const fs = require('fs');
const url = require('url');
const { spawn } = require('child_process');
const readline = require('readline');

// Register privileged app scheme for custom protocol (zero TCP ports)
protocol.registerSchemesAsPrivileged([
  {
    scheme: 'app',
    privileges: {
      standard: true,
      secure: true,
      supportFetchAPI: true,
      corsEnabled: true
    }
  }
]);

let mainWindow = null;
let pyProcess = null;
let reqSeq = 0;
const pendingRequests = new Map();

function startBackendIPC() {
  const scriptPath = path.join(__dirname, 'backend_ipc.py');
  const pythonCmd = process.env.PYTHON_PATH || 'python';

  pyProcess = spawn(pythonCmd, [scriptPath], {
    cwd: path.join(__dirname, '..'),
    stdio: ['pipe', 'pipe', 'inherit'],
    env: { ...process.env, PYTHONUNBUFFERED: '1' }
  });

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

function setupProtocol() {
  protocol.handle('app', async (request) => {
    const reqUrl = new URL(request.url);
    let pathname = decodeURIComponent(reqUrl.pathname);

    if (pathname === '/' || pathname === '/index.html') {
      const templatePath = path.join(__dirname, '..', 'gui', 'templates', 'index.html');
      let html = fs.readFileSync(templatePath, 'utf-8');
      html = html.replace(/\{\{\s*style_css_hash\s*\}\}/g, '1')
                 .replace(/\{\{\s*app_js_hash\s*\}\}/g, '1');
      return new Response(html, {
        headers: { 'Content-Type': 'text/html; charset=utf-8' }
      });
    }

    if (pathname.startsWith('/static/')) {
      const relPath = pathname.slice('/static/'.length);
      const filePath = path.join(__dirname, '..', 'gui', 'static', relPath);
      if (fs.existsSync(filePath)) {
        return net.fetch(url.pathToFileURL(filePath).toString());
      }
    }

    return new Response('Not found', { status: 404 });
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    webPreferences: {
      preload: path.join(__dirname, '..', 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false
    }
  });

  mainWindow.loadURL('app://simplec/index.html');

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

app.whenReady().then(() => {
  setupProtocol();
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
  if (pyProcess && !pyProcess.killed) {
    pyProcess.kill();
  }
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  if (pyProcess && !pyProcess.killed) {
    pyProcess.kill();
  }
});
