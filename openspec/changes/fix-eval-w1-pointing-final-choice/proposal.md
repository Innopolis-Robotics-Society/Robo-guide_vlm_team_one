# Proposal

## Why

The accepted review weakness **W1** (project report §5.2, Table 7): for deployed
pointing cases the harness's `pass` metric measures **candidate recall** —
"was the gold exhibit on the model's shortlist" — not the **final pointing
choice**. The shortlist contains all visible exhibits, so `pass` is true even
when the model abstains (e.g. `EPO-REAL-0003`, P3: `pointing_evidence: "none"`,
`terminal_abstain: true` → still `pass: true`). The report headline "15/15
(100%)" therefore does not mean what readers take it to mean, and the
design doc's promised metric (T4: policy top-1 target accuracy) was never
implemented in the deployed branch.

## What Changes

- **Decision phase (new)** in the eval runner for pointing cases
  (deployed mode, `gold.type == "target_box"`): after the observation phase the
  model must pick **exactly one** candidate id from its own observation, or
  abstain (`null`). Same strict-grammar + host-parser pattern as the existing
  action phase. The phase also fires on **no-target** pointing cases, giving a
  clean false-positive / abstention-credit signal (today the weakest-evaluated
  part of the track).
- **Scoring change** in the deployed+target branch: `policy.top1_correct`
  derived from the decision; **`pass` = final choice** (was: candidate
  recall). Abstention → **unjudged + credit** (was: pass via recall). Runs
  without a decision artifact → unjudged with `decision_missing` — **BREAKING
  for old artifacts**: previously passing pointing runs score as unjudged
  until re-run with the decision phase.
- Candidate recall, evidence accuracy, and IoU remain as **perception
  columns**; they no longer gate `pass`. Audience and tool tracks are
  untouched.
- **Held-out set (new)**: frozen manifest `pointing_holdout_15.jsonl` — 15
  fresh EgoPoint images selected by the existing deterministic rule while
  **excluding every image id already used in any frozen manifest**
  (bench_40/47/50, pv_matrix_57), so variant comparison gets a genuine
  confirmation set. Manifest build script gains an exclusion option.
- **Re-run scope**: 4 (model, best-variant) pairs from the report + the plain
  production baseline, each on original 15 + held-out 15 cases.
- **Report** (§5.2 / Table 7): four columns — right one on shortlist, robot
  saw a point at all, **robot picked the right one**, says "nobody's pointing"
  when true — plus a held-out confirmation note and an explicit sentence that
  the drop from 100% is the truth surfacing, not a regression.

## Capabilities

### New Capabilities
- `pointing-eval`: the eval-harness contract for pointing (deixis) cases —
  phases (observation + decision), final-choice scoring, abstention and
  no-target semantics, and held-out manifest discipline.

### Modified Capabilities
<!-- None: this project has no existing specs. -->

## Impact

- `guide_robot_llm/guide_robot_llm/eval/runner.py` — decision phase,
  artifacts (`raw_decision.txt`, `parsed_decision.json`), meta fields.
- `guide_robot_llm/guide_robot_llm/eval/scoring.py` — deployed+target branch
  (top-1, abstention credit, `decision_missing`).
- `guide_robot_llm/guide_robot_llm/eval/host.py` (or adjacent) — decision
  grammar + host parser.
- `guide_robot_llm/scripts/build_manifest.py` — image-id exclusion for
  held-out sets.
- `guide_robot_llm/eval_manifests/pointing_holdout_15.jsonl` — new frozen
  manifest (images gitignored under `eval_data/`, research-use-only license).
- `guide_robot_llm/test/` — runner + scoring tests, MockBackend decision
  fixtures.
- `docs/project_report_benchmarks_en.md` §5.2 — user-requested edit
  (file is AGENT_EDIT_POLICY: USER_REQUEST_ONLY).
- New `eval_runs/` for the re-run; existing run directories remain on disk,
  their pointing cases now score unjudged.
- No ROS/production impact: the harness is offline, pure Python, and
  diagnostic-only.
