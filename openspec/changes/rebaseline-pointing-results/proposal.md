# Proposal

## Why

The Stage-3 review (weakness W1, Major, −12.5) confirmed that the pointing "pass" in the submitted Table 7 was candidate recall (`target ∈ candidates`), not the final choice — so "15/15 (100%)" does not measure end-to-end pointing success. The measurement fix **already exists in code** (decision phase with `final_choice_accuracy`, virtual replay with `resolve_pointing`/`replay_pointing`, and a disjoint `pointing_holdout_15`), from the November 2026 campaigns — but the submitted report predates it and still presents the old metric.

## What Changes

- Restructure the pointing section of `docs/project_report_benchmarks_en.md`: report candidate recall explicitly as a *perception* metric; report `final_choice_accuracy` (decision phase, 2026-11-05-matrix) and virtual-replay end-to-end accuracy (2026-11-06-virtual-replay) as the *policy* metrics; retire the "15/15 (100%)" rows.
- Report pointing results on the disjoint `pointing_holdout_15` for variant selection claims (selection set vs. holdout set, per the existing §5.1 convention).
- Include the `2026-11-05-matrix` and `2026-11-06-virtual-replay` campaign artifacts in the submission archive.
- **Open scope decision — count selection bias:** count prompt variants were selected on the same 32 cases they are reported on (unlike pointing, which has a holdout). Options: (a) disclose as a limitation, (b) build a count holdout from unused AGHRI frames (data is local in `guide_robot_llm/eval_data/aghri/`) and run one campaign. Default recommendation: (b) if a campaign run is feasible, else (a). Decision gates the corresponding task.

## Capabilities

### New Capabilities
- `pointing-evaluation`: any metric reported as pointing *success* must measure the final pointing decision (or a validated end-to-end replay of it), not merely target inclusion in the candidate set; candidate recall may be reported only as a perception metric; variant selection and headline evaluation must use disjoint sets.

### Modified Capabilities
(none — no existing specs)

## Impact

- `docs/project_report_benchmarks_en.md` (results + interpretation sections)
- Submission archive contents (two November campaigns)
- Optionally: new `guide_robot_llm/scripts/make_count_holdout.py` + one eval campaign (GPU)
- No change to eval code behavior — the metrics already exist.
