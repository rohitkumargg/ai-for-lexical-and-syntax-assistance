# Data Retention and Privacy Policy

## 1. Scope and Purpose
This document details the data retention and security policies implemented by the Autonomous Repair Job Engine in accordance with enterprise safety guidelines.

## 2. Retention Periods
- **Repair Job Files**: All job metadata, stage histories, function chunks, and cached intermediate code stored within `data/repair_jobs/*.json` have a strict retention limit of **24 hours (86,400 seconds)**.
- **Automated Expiration Cleanup**: The `RepairJobManager.cleanup_expired_jobs(max_age_s=86400.0)` routine automatically scans the `data/repair_jobs` repository upon server initialization and periodic cycles, deleting all job records older than 24 hours.
- **User-Initiated Deletion**: Users and external orchestrators can immediately purge a job, its cached code, and all associated runtime metadata at any time by issuing an HTTP `DELETE` request to `/api/repair/job/<job_id>`.

## 3. Ephemeral Security Tokens
- **Approval Tokens**: In compliance with the Security Approval Gate policy, one-time security override tokens (`approval_token`) are **NEVER** persisted to disk in job files or state records.
- **Gate Re-evaluation on Resume**: When an interrupted or pending job is resumed upon application startup (`resume_unfinished_jobs()`), the engine enforces a fresh evaluation of the source code through the `SecurityDecisionGate` with `approval_token=None`. No security bypass survives across server restarts or job reloads.

## 4. Path Traversal & Identifier Validation
- **Job Identifiers**: All job identifiers must strictly match the 32-character hexadecimal format `^[a-f0-9]{32}$`. Any identifier containing path separators, parent directory traversals (`..`), or abnormal characters is rejected immediately with HTTP 400 Bad Request.
- **Canonical Filesystem Isolation**: Job operations verify that canonical file targets strictly reside within the designated `data/repair_jobs` root.

