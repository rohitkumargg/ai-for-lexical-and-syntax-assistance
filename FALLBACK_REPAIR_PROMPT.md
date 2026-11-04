# FALLBACK PROMPT — Repair pipeline if the full prompt stalls

Use this only if the full prompt cannot be completed as written. The objective remains: one click of **Run** should produce one complete, applicable repair for each repairable example, with truthful status, pipeline logs, and metrics. Do not add product features.

## Guardrails
- Work in the existing project at `Implementation/`; begin by checking `git status` and recent commits. Preserve the user's current changes. Do not overwrite backups or commit unless explicitly asked.
- Do not edit tests to make them pass. Do not add filename/sample-specific branches, weaken success criteria, or change program meaning. A repair is successful only when the applied editor text passes gcc and the project parser, and Apply succeeds.
- Keep raw command output and model responses in the report. Say `unknown` when evidence is unavailable; never infer success from an API status alone.
- Do not implement new features. Fix only behavior required for correct repair, status, logs, metrics, and reporting.

## Step 1 — Establish the actual state
1. Record `git status --short`, `git log --oneline -5`, and the project’s existing test/run instructions.
2. Inspect the current runner, server routes, repair/job pipeline, parser/compiler integration, metrics, and existing reports before changing code.
3. Run the smallest existing reproduction that demonstrates the reported failure. Capture the UI/API output, logs, gcc result, parser result, and relevant code locations.
4. Write a short baseline table: reproduction, observed status, failing check, likely cause, evidence. Do not begin broad fixes until there is a reproducible cause.

## Step 2 — Build a small, resumable validation runner
Create or repair `scripts/run_all_examples_ui.py` only if the project has a usable real UI/server flow. It must use the real application, resume safely, save raw per-file results, and independently validate the editor text after Apply with gcc and the project parser. Start with a representative set: one clean file, one simple syntax error, one warning case, one security case, and one large file. Confirm the runner works end-to-end before expanding it to every `.c` and `.py` under `examples/` and `held_out/` (if present).

For every file record: path, expected class, displayed status, stages/tiers actually run, attempts/windows and durations when available, Apply result, gcc errors before/after, parser errors after, all displayed metrics, raw output, and exact failure reason. A file is successful only under the original prompt's success rules. Never call “already compiled” a repair success. If a requested measurement cannot be collected, mark it unknown and explain why.

## Step 3 — Diagnose by shared cause, then fix the engine
After the representative run, group failures by demonstrated cause and include exact locations and raw evidence. Fix the largest shared engine cause first. Keep one source of truth for repair behavior and final status across small and job-based paths. Do not special-case sample filenames or examples.

Required behavior when relevant to the reproduced defect:
- Deterministic edits are accepted only when parser/compiler errors do not increase.
- Learned repair tiers are accepted only when they reduce errors; escalate to the next tier while errors remain, within bounded per-window attempts and a job-wide ceiling.
- Validate the assembled whole file with gcc and the project parser before offering Apply. Apply must apply the complete candidate and return success.
- Derive final status from final validation. Never report clean/warnings while syntax errors remain, or compilation failure when the program compiles.
- Pipeline stages, counters, window summaries, and job JSON must describe work that actually ran and agree with one another.
- Metrics must be present and deterministic for the current editor text. If syntax errors prevent exact metrics, label best-effort values as estimated; recompute after repair.
- If the parser rejects gcc-valid syntax, report it as a parser grammar limitation rather than a gcc error.

## Step 4 — Expand coverage and verify each fix
After the representative set passes, run all examples. Report every remaining failure with file, function/line, rejecting gate, tiers attempted/skipped and why, raw model output, remaining gcc/parser errors, and blank/inconsistent metrics. Fix failures by shared cause and rerun the affected files plus the representative set after each change. Do not stop at the first group.

Do not add or run tests unless asked; use existing tests and the requested real-run validation only. Report commands and raw outputs used.

## Step 5 — Architecture documentation and final report
Update `docs/ARCHITECTURE.md` only after tracing the real implementation. Document modules and callers, request flow, status rules, and where pipeline stages are emitted. Avoid describing intended behavior as implemented behavior.

At the end provide:
- Baseline and final counts by status, success class, and failure cause.
- The path to the CSV/JSON results and the exact success rule used.
- Every unresolved file and its evidence-based cause.
- `git status --short`, `git log --oneline`, and `git diff --stat` for the work performed.
- A clear list of changed files and the validation actually completed.

Do not claim completion for files absent from the results or that fail independent gcc/parser validation. If time or a hard blocker prevents full coverage, report the completed subset and continue with the highest-impact reproducible cause rather than fabricating results.
