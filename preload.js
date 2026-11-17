const { contextBridge, ipcRenderer } = require('electron');

function makeResponse(res) {
  const status = (res && typeof res.status === 'number') ? res.status : 200;
  const data = (res && res.data !== undefined) ? res.data : (res && res.error ? { error: res.error } : res);
  return {
    ok: status >= 200 && status < 300,
    status: status,
    statusText: status === 200 ? 'OK' : (status === 409 ? 'Conflict' : (status === 202 ? 'Accepted' : 'Error')),
    json: async () => data,
    text: async () => (typeof data === 'string' ? data : JSON.stringify(data)),
    data: data
  };
}

const api = {
  // Generic URL/route dispatcher
  request: async (routeOrUrl, args = {}) => {
    const res = await ipcRenderer.invoke('api:request', { route: routeOrUrl, args });
    return makeResponse(res);
  },

  // Group 1: System & Files
  getLanguages: async () => {
    return makeResponse(await ipcRenderer.invoke('api:languages', {}));
  },
  saveFile: async (payload) => {
    return makeResponse(await ipcRenderer.invoke('api:save_file', payload || {}));
  },
  createFile: async (payload) => {
    return makeResponse(await ipcRenderer.invoke('api:create_file', payload || {}));
  },
  getExamples: async (lang = 'c') => {
    return makeResponse(await ipcRenderer.invoke('api:examples', { language: lang }));
  },
  getExample: async (name, lang) => {
    return makeResponse(await ipcRenderer.invoke('api:load_example', { name, language: lang }));
  },
  modelsStatus: async () => {
    return makeResponse(await ipcRenderer.invoke('api:models_status', {}));
  },
  modelsUnload: async () => {
    return makeResponse(await ipcRenderer.invoke('api:models_unload', {}));
  },

  // Group 2: Security & Analysis
  qualityScore: async (payload) => {
    return makeResponse(await ipcRenderer.invoke('api:quality_score', payload || {}));
  },
  qualityConfig: async () => {
    return makeResponse(await ipcRenderer.invoke('api:quality_config', {}));
  },
  optimizationPotential: async (payload) => {
    return makeResponse(await ipcRenderer.invoke('api:optimization_potential', payload || {}));
  },
  optimizationConfig: async () => {
    return makeResponse(await ipcRenderer.invoke('api:optimization_config', {}));
  },
  securityRisk: async (payload) => {
    return makeResponse(await ipcRenderer.invoke('api:security_risk', payload || {}));
  },
  securityRiskDelta: async (payload) => {
    return makeResponse(await ipcRenderer.invoke('api:security_risk_delta', payload || {}));
  },
  securityRiskConfig: async () => {
    return makeResponse(await ipcRenderer.invoke('api:security_risk_config', {}));
  },
  securityReport: async (payload) => {
    return makeResponse(await ipcRenderer.invoke('api:security_report', payload || {}));
  },
  securityCompare: async (payload) => {
    return makeResponse(await ipcRenderer.invoke('api:security_compare', payload || {}));
  },
  securityBenchmark: async (dirPath) => {
    return makeResponse(await ipcRenderer.invoke('api:security_benchmark', { dir: dirPath }));
  },
  securityRemediation: async (payload) => {
    return makeResponse(await ipcRenderer.invoke('api:security_remediation', payload || {}));
  },
  securityApply: async (payload) => {
    return makeResponse(await ipcRenderer.invoke('api:security_apply', payload || {}));
  },
  securityPrescan: async (payload) => {
    return makeResponse(await ipcRenderer.invoke('api:security_prescan', payload || {}));
  },
  securityApprovalCheck: async (payload) => {
    return makeResponse(await ipcRenderer.invoke('api:security_approval_check', payload || {}));
  },
  securityApprovalApprove: async (payload) => {
    return makeResponse(await ipcRenderer.invoke('api:security_approval_approve', payload || {}));
  },
  securityApprovalCancel: async (payload) => {
    return makeResponse(await ipcRenderer.invoke('api:security_approval_cancel', payload || {}));
  },

  // Group 3: Execution, Repair & Jobs
  programRun: async (payload) => {
    return makeResponse(await ipcRenderer.invoke('api:run_program', payload || {}));
  },
  testcase: async (payload) => {
    return makeResponse(await ipcRenderer.invoke('api:testcase', payload || {}));
  },
  repair: async (payload) => {
    return makeResponse(await ipcRenderer.invoke('api:repair', payload || {}));
  },
  repairJobStart: async (payload) => {
    return makeResponse(await ipcRenderer.invoke('api:repair_job_start', payload || {}));
  },
  repairJobStatus: async (jobId) => {
    return makeResponse(await ipcRenderer.invoke('api:repair_job_status', { job_id: jobId }));
  },
  repairJobCancel: async (jobId) => {
    return makeResponse(await ipcRenderer.invoke('api:repair_job_cancel', { job_id: jobId }));
  },
  repairJobDelete: async (jobId) => {
    return makeResponse(await ipcRenderer.invoke('api:repair_job_delete', { job_id: jobId }));
  },
  coordinatorCancel: async (payload) => {
    return makeResponse(await ipcRenderer.invoke('api:coordinator_cancel', payload || {}));
  },
  coordinatorAnalyzeAndPlan: async (payload) => {
    return makeResponse(await ipcRenderer.invoke('api:coordinator_analyze_and_plan', payload || {}));
  },
  repairPostApply: async (payload) => {
    return makeResponse(await ipcRenderer.invoke('api:repair_post_apply', payload || {}));
  },
  pipelineLatest: async () => {
    return makeResponse(await ipcRenderer.invoke('api:pipeline_latest', {}));
  },
  pipelineRun: async (runId) => {
    return makeResponse(await ipcRenderer.invoke('api:pipeline_run', { run_id: runId }));
  },

  // Group 4: Patch & Diff
  patchValidate: async (payload) => {
    return makeResponse(await ipcRenderer.invoke('api:validate_patch', payload || {}));
  },
  patchApply: async (payload) => {
    return makeResponse(await ipcRenderer.invoke('api:apply_patch', payload || {}));
  },
  patchReject: async (payload) => {
    return makeResponse(await ipcRenderer.invoke('api:reject_patch', payload || {}));
  },
  patchRevert: async (payload) => {
    return makeResponse(await ipcRenderer.invoke('api:revert_patch', payload || {}));
  },
  dashboardBeforeAfter: async (payload) => {
    return makeResponse(await ipcRenderer.invoke('api:dashboard_before_after', payload || {}));
  },

  // Group 5: Improvement & Rules
  improvementAdvise: async (payload) => {
    return makeResponse(await ipcRenderer.invoke('api:improvement_advise', payload || {}));
  },
  improvementApply: async (candidateId, payload) => {
    return makeResponse(await ipcRenderer.invoke('api:improvement_candidate_apply', { candidate_id: candidateId, ...(payload || {}) }));
  },
  improvementRollback: async (candidateId, payload) => {
    return makeResponse(await ipcRenderer.invoke('api:improvement_candidate_rollback', { candidate_id: candidateId, ...(payload || {}) }));
  },
  improvementReject: async (candidateId) => {
    return makeResponse(await ipcRenderer.invoke('api:improvement_candidate_reject', { candidate_id: candidateId }));
  },
  rulesCandidates: async () => {
    return makeResponse(await ipcRenderer.invoke('api:rules_candidates', {}));
  },
  rulesPropose: async (payload) => {
    return makeResponse(await ipcRenderer.invoke('api:rules_propose', payload || {}));
  },
  rulesCandidateValidate: async (ruleId) => {
    return makeResponse(await ipcRenderer.invoke('api:rules_candidate_validate', { rule_id: ruleId }));
  },
  rulesCandidateApprove: async (ruleId, payload) => {
    return makeResponse(await ipcRenderer.invoke('api:rules_candidate_approve', { rule_id: ruleId, ...(payload || {}) }));
  },
  rulesCandidateReject: async (ruleId, payload) => {
    return makeResponse(await ipcRenderer.invoke('api:rules_candidate_reject', { rule_id: ruleId, ...(payload || {}) }));
  },
  rulesActive: async () => {
    return makeResponse(await ipcRenderer.invoke('api:rules_active', {}));
  },
  rulesActiveDisable: async (ruleId, payload) => {
    return makeResponse(await ipcRenderer.invoke('api:rules_active_disable', { rule_id: ruleId, ...(payload || {}) }));
  },
  rulesActiveEnable: async (ruleId) => {
    return makeResponse(await ipcRenderer.invoke('api:rules_active_enable', { rule_id: ruleId }));
  },
  rulesActiveRollback: async (ruleId, payload) => {
    return makeResponse(await ipcRenderer.invoke('api:rules_active_rollback', { rule_id: ruleId, ...(payload || {}) }));
  },
  rulesHistory: async () => {
    return makeResponse(await ipcRenderer.invoke('api:rules_history', {}));
  },

  // Group 6: Benchmark & Green
  greenConfig: async () => {
    return makeResponse(await ipcRenderer.invoke('api:green_config', {}));
  },
  measureGreen: async (payload) => {
    return makeResponse(await ipcRenderer.invoke('api:green_measure', payload || {}));
  },
  greenHistory: async (limit = 30) => {
    return makeResponse(await ipcRenderer.invoke('api:green_history', { limit }));
  },
  benchmarkStatus: async () => {
    return makeResponse(await ipcRenderer.invoke('api:benchmark_status', {}));
  },
  benchmarkDataset: async () => {
    return makeResponse(await ipcRenderer.invoke('api:benchmark_dataset', {}));
  },
  benchmarkDefinitions: async () => {
    return makeResponse(await ipcRenderer.invoke('api:benchmark_definitions', {}));
  },
  benchmarkRun: async (payload) => {
    return makeResponse(await ipcRenderer.invoke('api:benchmark_run', payload || {}));
  }
};

contextBridge.exposeInMainWorld('api', api);
