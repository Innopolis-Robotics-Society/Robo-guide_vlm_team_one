# Proposal

## Why

The Stage-3 review (weakness W3, Major, −5.0) found repeated inconsistencies between the report/README and the submitted files: the archive inventory claims are wrong (archive *includes* `eval_runs/2026-09-16-pv16-small/` with 72 scored runs and the model profiles, contrary to report §6/§6.4 and README), the latency table reports p95 = 1.5 s for Qwen3.5-9B full pass while `score.json` records 1769.073 ms, and the README points to `project_report_benchmarks_en.md` which was missing from the archive.

## What Changes

- Fix the archive-inventory wording in `docs/project_report_benchmarks_en.md` §6 and `README.md` to state exactly what is and is not in the submission.
- Regenerate the latency/quality tables from `eval_runs/*/score.json` instead of hand-copying (qwen3.5-9b full-pass p95 becomes 1.77 s); add a small generator script so tables cannot drift from artifacts again.
- Ensure `docs/project_report_benchmarks_en.md` is included in the submission archive; audit all README/report file references for inclusion.

## Capabilities

### New Capabilities
- `project-report`: the report and README must match the submitted archive (inventory claims), every numeric table must be derivable from committed run artifacts, and every file referenced by the report must be present in the submission.

### Modified Capabilities
(none — no existing specs)

## Impact

- `docs/project_report_benchmarks_en.md`, `README.md`
- New small table-generation script under `guide_robot_llm/scripts/`
- Submission packaging checklist
- No code behavior change.
