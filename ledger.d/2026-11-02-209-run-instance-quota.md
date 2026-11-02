## 2026-11-02 — Semantic — Cloud Run's instance quota out of the caps: it was an increase, and never covered services (#209)

- Done: `free-path.yaml` `caps.cloud_run_regional_quotas` keeps `CpuAllocPerProjectRegion` (4,000 milli vCPU) and `MemAllocPerProjectRegion` (2 GiB) and drops `InstancesPerProject`; `check_free_path.py` no longer accepts an `instances` unit, and a test refuses the instance quota coming back; `infra/tests/monitoring.tftest.hcl` expects the two preferences.
  `guardrails-check.sh` reads a quota whose `details` is `{}` as 0 instead of failing with a `KeyError`.
- Why: the owner's `make gcp-up` failed on `google_cloud_quotas_quota_preference.cloud_run["run.googleapis.com/instances"]` with "Contact email must be set in order to increase quota value".
  The project's `quotaInfos/InstancesPerProject` (read 2026-11-02) lists `details: {}` for us-central1, its proto3 form of 0 (40 other regions show 100), so a preference of 4 was an increase, which the $0.00 rule forbids; its display name is "Instances per region (only for Cloud Run Instances resources, not instances of Cloud Run Services, Jobs, or Worker Pools)", so it never capped the workloads.
  Each service's `max_instance_count` and the vCPU quota at 1 vCPU an instance still bound the instances.
- Evidence: the vCPU and memory preferences were already granted on the project (4000 and 2147483648); from this branch `make gcp-plan` shows "No changes", `make gcp-validate` passes (78 tests, `tofu test`), and `make gcp-guardrails-check` passes against the live project.
- Decisions: semantic/PLAN.md SL-13 (its "regional quota preferences" stay, now vCPU and memory).
- Open: nothing.
