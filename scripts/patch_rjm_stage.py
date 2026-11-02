# scripts/patch_rjm_stage.py
with open('compiler/repair_job_manager.py', 'r', encoding='utf-8') as f:
    text = f.read()

target = '''            plan_res["stopping_reason"] = "completed" if job.windows_done > 0 else "clean_or_unmodified"
            if not plan_res.get("proposed_code"):
                plan_res["proposed_code"] = final_adopted_code

            job.result = plan_res
            job.current_code = final_adopted_code
            job.state = "COMPLETED"
            job.stage = "Repair job completed successfully."'''

replacement = '''            final_stat = plan_res.get("status") or plan_res.get("terminal_status") or "COMPLETED"
            if job.windows_done > 0:
                plan_res["stopping_reason"] = "completed"
                job.stage = f"Repair job completed: {job.windows_done} window(s) repaired successfully."
            elif final_stat in ("CLEAN", "VALID_NO_FINDINGS"):
                plan_res["stopping_reason"] = "clean_or_unmodified"
                job.stage = "Repair job completed: program is clean with zero syntax errors."
            elif final_stat in ("REPAIR_UNAVAILABLE", "UNRESOLVED", "COMPILATION_FAILED"):
                reason_detail = plan_res.get("stopping_reason") or "No candidate repairs passed compiler validation across attempted tiers."
                plan_res["stopping_reason"] = reason_detail
                job.stage = reason_detail
            else:
                plan_res["stopping_reason"] = plan_res.get("stopping_reason") or "clean_or_unmodified"
                job.stage = plan_res["stopping_reason"]

            if not plan_res.get("proposed_code"):
                plan_res["proposed_code"] = final_adopted_code

            job.result = plan_res
            job.current_code = final_adopted_code
            job.state = "COMPLETED"'''

text_norm = text.replace('\r\n', '\n')
target_norm = target.replace('\r\n', '\n')
replacement_norm = replacement.replace('\r\n', '\n')

if target_norm in text_norm:
    text_norm = text_norm.replace(target_norm, replacement_norm, 1)
    with open('compiler/repair_job_manager.py', 'w', encoding='utf-8', newline='\r\n') as f:
        f.write(text_norm)
    print("Patched stage text in repair_job_manager.py successfully.")
else:
    print("Target not found.")

