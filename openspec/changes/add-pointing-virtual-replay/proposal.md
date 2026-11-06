# Proposal

## Why

The W1 fix made the pointing eval honest about *final choice* — but the 2026-11-05
matrix deep-dive (16 runs, 240 cases) showed that metric measures a step the robot
does not decide by. Production pointing (`guide_robot_llm/pointing.py`, Taiga #7)
resolves an exhibit with a **deterministic** resolver: 70% weight on the model's
`pointing_box` geometry + 30% language, gated on visibility, with the model's pick
only as a cross-check against the geometry leader. In the matrix, variant prompts
(P0/P3/P4) replaced the production observation instruction and never asked for a
box (7/120 observations emitted one, two of them full-frame), the box is never
scored (EgoPoint has no gold boxes), and the real resolver has never been executed
in the eval. With current models the production pipeline therefore ends in a
clarification question almost every time — a fact the eval cannot currently see.

Goal: **pick the best model/variant for pointing** on a metric that mirrors what
production actually does, offline, without live-robot episodes.

## What Changes

- **Virtual-robot replay mode in the eval harness**: for each pointing case, run
  the exact production pipeline — (1) observation call with the production
  instruction (`P_base`, which requests `pointing_box`), (2) pick call (the W1
  decision phase, closed grammar over candidates + `none`), (3) the real
  deterministic `resolve_pointing()` — and score the end-to-end outcome.
- **Per-case virtual geometry** for the 30 pointing cases (egopoint_15 +
  pointing_holdout_15): 4 option-anchor pixels per image, inverted through the
  camera model into 4 virtual candidate 3D positions, plus 1 gold target region
  for box scoring. Frozen as a geometry sidecar with provenance; authoring is
  read-only on EgoPoint data (T1 license: no derivative images — the geometry is
  our own data, images untouched).
- **New metrics**: `resolved_accuracy` (primary selection metric — the end-to-end
  production outcome), `box_iou` (the 0.7-weight signal, finally scored),
  `detection_rate` (`pointing_evidence == yes`), `agreement_rate` (model pick ==
  geometry leader), and `clarification_rate` broken down by reason
  (`no_candidate` / `ambiguous` / `unusable_frames`).
- **Selection re-run**: full grid 4 models × {P_base, P0, P3, P4} on the
  selection set (egopoint_15); held-out set (pointing_holdout_15) only for the
  top pairs, per the W1 selection/confirmation convention. Bounded GPU campaign,
  user-executed, same launcher guards as the W1 matrix.
- W1 metrics (final-choice accuracy, abstention) and freeform top-1 stay as
  secondary diagnostic columns in the report.
- Production code is consumed, not changed: `pointing.py` runs unmodified.
  No live-robot episodes; no no-target cases (still out of scope, as in W1).

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `pointing-eval`: adds the virtual-replay execution mode and its end-to-end
  metrics; the primary model/variant selection metric for pointing becomes
  production-pipeline `resolved_accuracy` instead of final-choice accuracy.

Note: the base `pointing-eval` spec is defined by the completed change
`fix-eval-w1-pointing-final-choice` (18/18 tasks, unarchived). Archive that
change before archiving this one so the deltas stack cleanly.

## Impact

- `guide_robot_llm/eval/` — runner (replay mode), scoring (replay metrics),
  case schema (per-case virtual geometry fields).
- New: geometry-authoring tooling + frozen geometry sidecar for the 30 cases.
- `guide_robot_llm/pointing.py` — imported read-only, unmodified.
- `guide_robot_llm/scripts/run_matrix.py` + a new matrix config for the grid
  campaign (user-executed GPU job; `:11434` guard retained).
- Docs: `guide_robot_llm/docs/eval_harness_design.md`;
  `docs/project_report_benchmarks_en.md` §5.2 updated with selection results
  (user-requested edit, per W1 precedent).
- Tests: pure-Python tests for geometry inversion and replay scoring (no ROS),
  following the existing `test/test_eval_*` pattern.
