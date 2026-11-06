# Design

## Context

See proposal.md for motivation. The parts that shape the approach:

- Production pointing (`guide_robot_llm/pointing.py`, Taiga #7) is pure
  deterministic code: `resolve_pointing(ctx, model_content_id)` scores
  `0.7·Gaussian(projection, pointing_box) + 0.3·language`, gates on
  in-frame + visible, and resolves only a unique leader that the model's pick
  agrees with. `compute_pointing_metrics` already exists. No ROS inside.
- The production observation instruction (`P_base`, frozen snapshot in
  `eval/prompt_variants/P_base.txt`) is the only variant that asks for
  `pointing_box`. The W1 matrix ran P0/P3/P4, which replace it and never ask
  for a box — 7/120 observations emitted one.
- The W1 decision phase (closed grammar over observation candidates + `none`)
  is implemented, tested, and persisted per case.
- The production camera model is pinned in `guide_robot_llm/config/llm.yaml`
  (Taiga #7 block): 1280×720, HFOV 60°, VFOV 34°, mount (0, 0, 1.0 m),
  yaw 0°, pitch 10°.
- EgoPoint rows carry no boxes and no geometry; the adapter is read-only on
  the data (T1 license: unmodified private research use, no derivative
  images).

## Goals / Non-Goals

**Goals:**

- An eval mode that runs the production pointing pipeline end-to-end on
  EgoPoint cases, offline, and reports the outcome that predicts the robot.
- A production-faithful primary metric for model/variant selection, with the
  failure decomposed into detection / box / agreement / clarification factors.
- Frozen, provenance-carrying, human-reviewable per-case virtual geometry for
  the 30 pointing cases (egopoint_15 + pointing_holdout_15).

**Non-Goals:**

- No changes to production code (`pointing.py` is imported, not modified).
- No live-robot episodes, no new datasets, no no-target cases (as in W1).
- No model/prompt fixes (truncation, box-elicitation, A-bias) — those are
  separate tickets; this change only measures.
- Not a certification: n=15 per set, selection purpose only.

## Decisions

### D1 — Replay = the production pipeline, verbatim

Replay mode runs three steps per case:

1. **Observation** with the production instruction (`P_base`). This is the
   only variant that requests `pointing_box`, so box emission is finally
   measured under the instruction production actually uses.
2. **Pick** — reuse the W1 decision phase as-is (closed grammar over the
   observation's candidate ids + `none`). Production's pick happens in the
   action phase (a tool call); a focused pick call is a close enough
   approximation for model selection and reuses tested code. Alternative
   considered: mimic the full action grammar — rejected as overkill; the
   resolver's cross-check semantics (pick must equal the geometry leader) are
   preserved either way.
3. **Resolve** — call the real `resolve_pointing()` with a `PointingContext`
   built from the case's virtual geometry, the model's observation
   (`PointingEvidence` from `pointing_evidence`/`pointing_box`,
   `visible_ids` from `exhibit_candidates`), the author question as
   `utterance`, and `frame_quality = ok`.

The case verdict in replay mode is the end-to-end outcome: `pass` iff
`resolved` and the resolved id equals the gold; `fail` if resolved to a wrong
id; unjudged with a reason (`no_candidate` / `ambiguous` / `unusable_frames`)
on clarification. Standard (non-replay) deployed mode is unchanged — W1's
final-choice semantics keep governing it, so the two modes are comparable
columns, not a replacement.

### D2 — Virtual geometry: invert the production projection

Per case, four candidate anchors (u, v) — normalized pixels where options
A–D sit in the photo — are inverted through the production camera model into
candidate 3D positions. With the camera at the origin, yaw 0, pitch p:

```
delta_theta = atan((u - 0.5) · W / f_x)          f_x = (W/2) / tan(HFOV/2)
bearing     = delta_theta                        (heading = 0)
vert_angle  = (v - 0.5) · VFOV                   (radians)
d_h         = z_mount / tan(vert_angle + p)
(x, y)      = (d_h · cos(bearing), d_h · sin(bearing))
```

There is **no free depth parameter**: each (u, v) maps to a unique (x, y).
Edge case: anchors above the horizon line (`vert_angle + pitch ≤ ε`, roughly
the top 20% of the frame for these parameters) diverge — the inverter clamps
`d_h` to `D_MAX = 10 m` and records a `clamped: true` flag per anchor in the
sidecar. A round-trip unit test (`project(invert(u, v)) ≈ (u, v)`) pins the
math.

- **Candidate names** are the option labels from the manifest (via the
  adapter's option text), so the resolver's 0.3 language signal behaves as in
  real use (the visitor's utterance — the author question — contains the
  option words).
- **Robot pose** is the identity (0, 0, 0); the camera sits at the origin
  looking along +x. This is WLOG: the resolver only uses relative geometry.
- **Gold target region** (for `box_iou` only, not used by the resolver): a
  box of 15% of the frame's shorter side, centered on the target anchor,
  overridable per case in the sidecar when the target object is clearly
  larger/smaller in the photo.

### D3 — Geometry authoring: agent-authored, human-reviewed

I (the agent) read each of the 30 images, identify the four option objects
using the option text, place the anchors and the gold region, and write the
sidecar. A self-contained **review page** (single HTML, images with drawn
anchors/regions and option labels) is generated for a later human pass.

- **Sidecar layout**: one file per manifest, next to it
  (`egopoint_15.geometry.json`, `pointing_holdout_15.geometry.json`), keyed by
  `case_id`, carrying per case: the 4 anchors, the inverted positions, the
  clamped flags, the gold region, the camera parameters used, and provenance
  (author, date, method, image sha256 from the manifest, review status).
- **Review gate (process, not code)**: selection results are reported as
  *pending geometry review* until the user confirms the review page. Disputed
  cases are excluded from selection with a provenance note, not silently.
- Source images are never modified (T1); the sidecar is our own data.

### D4 — Metrics

Per replay case: resolver status, resolved id, per-candidate scores (bounded
metadata, already the resolver's output), model `pointing_box`, box IoU vs
the gold region.

Run-level:

| Metric | Definition | Role |
|---|---|---|
| `resolved_accuracy` | resolved-and-correct / all cases | **primary selection metric** |
| `box_iou` (mean, where box present) | IoU(model box, gold region) | the 0.7-weight signal |
| `detection_rate` | `pointing_evidence == yes` / all cases | first production gate |
| `agreement_rate` | model pick == geometry leader / cases with both | cross-check factor |
| `clarification_rate` by reason | per `no_candidate`/`ambiguous`/`unusable_frames` | where the pipeline gives up |

W1 final-choice accuracy, abstention, and freeform top-1 remain secondary
columns in the report.

### D5 — Campaign

Full grid: 4 models × {P_base, P0, P3, P4} on egopoint_15 → 16 runs / 240
cases. The top pairs by `resolved_accuracy` on the selection set are
confirmed on pointing_holdout_15 (W1 selection/confirmation convention).
User-executed bounded GPU job via `run_matrix.py` + a new config
(`matrix_virtual_replay.json`), same `:11434` launcher guard as the W1
matrix. Replay is a per-leg config flag; the decision phase runs in both
replay and standard deployed legs (W1 behavior), so no runner branching
beyond the mode flag and the resolve step.

## Risks / Trade-offs

- [My anchor placement is imprecise (~5–10% of frame) or I misidentify an
  option object] → within the resolver's 10%-of-frame Gaussian sigma; the
  review page is the safety net; disputed cases are excluded with a provenance
  note, not silently.
- [EgoPoint frames are egocentric (visitor's viewpoint, hand often in frame);
  production frames are robot-camera (third person)] → replay measures the
  pipeline mechanics and model behavior under the production contract, not
  the exact visual domain; the freeform/MCQ columns already carry the raw
  visual-ability signal. Accepted — no robot-frame dataset exists (live
  episodes are out of scope).
- [The 0.3 language signal can dominate easy cases, since option words appear
  in the question] → capped by design (weight 0.3); per-candidate language
  scores are persisted, so a language-driven resolution is diagnosable per
  case.
- [n=15 per set → wide CIs] → selection purpose only; the held-out
  confirmation step guards against selection-set overfit.
- [Observation truncation (known W1 deep-dive issue) still applies to replay
  observation calls] → out of scope here; truncated observations yield
  parse-failed cases, visible in the metrics, not silently dropped.
- [Box IoU against an authored 15% region is lenient] → it is a decomposition
  signal, not a verdict gate; `resolved_accuracy` remains the primary metric.

## Migration Plan

Purely additive eval capability: new mode flag, new sidecars, new metrics.
No production code, config, or existing run artifacts change. Rollback = stop
using the flag; standard-mode runs and W1 metrics are untouched. The W1 change
(`fix-eval-w1-pointing-final-choice`) must be archived before this one so the
`pointing-eval` deltas stack cleanly.

## Open Questions

None — the four candidate open questions (authoring method, grid size, pick
call, depth) were resolved with the user on 2026-11-05: agent-authored
geometry with later human review; full 4×4 grid + held-out top pairs; W1
decision call reused; depth fixed by the production camera model (D2).
