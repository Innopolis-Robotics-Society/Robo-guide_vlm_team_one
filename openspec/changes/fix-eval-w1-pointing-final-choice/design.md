# Design

## Context

See proposal.md for motivation. Implementation-relevant facts:

- The eval runner (`guide_robot_llm/guide_robot_llm/eval/runner.py`) already
  has a two-phase pattern for tool cases: an **action phase** that fires after
  the observation when `case.gold["type"] == "action"` — it appends an
  instruction + the rendered observation to the messages, runs one
  `_run_phase` with a strict GBNF grammar and a host parser, and stores the
  result in `run.action` (a `PhaseRecord`). Pointing cases
  (`gold.type == "target_box"`) currently stop after the observation.
- Grammar builders live in `guide_robot_llm/llm_client/grammar.py`
  (`build_observation_grammar`, `build_action_grammar`, plus `_JSON_RULES` /
  `_CONFIDENCE_RULE` primitives); host parsers live next to them in
  `runner.py` (`parse_freeform_answer` pattern).
- `write_case_run` and the case `meta.json` iterate a fixed phase tuple
  (`_phase_records`, `("observation", "action", "freeform")`) — a new phase
  is picked up by adding it there.
- Scoring (`eval/scoring.py`) resolves the deployed+target branch on
  `parsed_observation.json` only; run-level metrics are aggregated per family
  (`perception` / `policy`) by `_aggregate`, so new policy metrics slot in
  without schema changes.
- Manifests are frozen by dedicated builder scripts with a sha256 sidecar
  (pattern: `scripts/make_bench50.py`). There is no shared
  `build_manifest.py` in the repo.
- The EgoPoint adapter's `select_mc_rows(rows, n)` deterministically picks the
  minimal `image_id` per stratum from the **rows it is given** — pre-filtering
  rows achieves id exclusion without touching the adapter.
- The re-run driver is `scripts/run_matrix.py` + a matrix JSON
  (`matrix.json`, `matrix_pv16.json`).

## Goals / Non-Goals

**Goals:**
- A pointing case produces and is scored on a **final choice** (one candidate
  id or abstention), in deployed mode, for both target and no-target cases.
- `pass` means final pick; abstention is visible (unjudged + credit); legacy
  artifacts score as unjudged, never pass-by-recall.
- A frozen, disjoint 15-case held-out pointing manifest for confirmation.
- Report §5.2 / Table 7 restated with four columns + honest framing.

**Non-Goals:**
- No changes to the audience or tool tracks.
- No changes to the observation phase, its prompt, loop budget (K=3), or
  freeform mode.
- No production/ROS changes — the harness is offline and diagnostic-only.
- No live-robot episodes (explicitly out of scope).
- No re-tuning of prompts/variants on any frozen set.

## Decisions

### D1. Decision phase as a sibling of the action phase
In the deployed branch of `run_case`, after the observation is parsed, add:
`if case.gold.get("type") == "target_box": run.decision = _run_phase(...)`.
The decision messages are the observation messages + a decision instruction +
the rendered observation (same `render_observation` suffix the action phase
uses). New `CaseRun.decision: PhaseRecord | None` field; "decision" added to
`_phase_records` and the meta phase tuple.

*Why:* identical, already-tested machinery (`_run_phase`, grammar, parse
retries, artifacts, meta). *Alternatives:* extending the observation grammar
with a `final_target` field (rejected — couples perception and choice, breaks
freeform/loop symmetry, and the loop terminal state would be ambiguous);
asking the choice in freeform mode (rejected — freeform has its own contract
and the deployed loop is what production uses).

### D2. Decision contract: pick from one's own observation
Strict grammar: `{"target_id": <one of the observation's candidate ids> |
"none", "confidence": <0..1>}` — built by a new
`build_decision_grammar(candidate_ids)` in `llm_client/grammar.py`; host
parser `_parse_decision(text, candidates)` in `runner.py` (same style as
`parse_freeform_answer`; `target_id` outside the observation's ids → parse
failure, retried within the phase's `max_attempts`).

*Why:* the robot can only act on what it listed; this makes "saw it but didn't
pick it" a visible failure and keeps the grammar closed (small candidate set,
fast constrained decoding). *Alternative:* pick from the manifest's full
candidate list (rejected — leaks candidates the model didn't see; weaker
signal).

### D3. Firing rule
Decision phase runs iff: deployed mode, `gold.type == "target_box"`, and the
observation parsed OK. This includes no-target cases (their observation
usually yields `evidence: "none"` and possibly an empty candidate list —
grammar then offers only `"none"`, so the only legal answer is abstention;
any "invented" id is a parse failure, and the scorer treats a no-target
decision naming a candidate as a false positive). Loop variants: the loop
budget stays on the observation; the decision is **one extra call** after the
loop (`calls_per_case` reflects the total).

*Why:* one call is enough — the decision is a closed-form choice over a short
list; a second decision loop would add latency for no expected signal.

### D4. Scoring semantics (deployed + target branch)
- `parsed_decision.json` present:
  - target case: `policy.top1_correct = (target_id == gold)`;
    `pass = top1_correct`; `target_id == "none"` → `pass = null` (unjudged),
    `policy.abstained = true` + run-level abstention credit.
  - no-target case: `target_id == "none"` → correct + credit;
    else `pass = false`, `policy.false_positive = true`.
- `parsed_decision.json` absent (legacy runs): `policy.decision_missing =
  true`, `pass = null` (unjudged). **No recall-based pass path remains.**
- Perception fields (`evidence_correct`, `target_in_candidates`, `top2_hit`,
  `box_iou`) are computed as before and reported, but never set `pass`.
- Freeform and audience/tool branches: unchanged.

*Why:* matches the spec; the `decision_missing` marker makes legacy
artifacts visibly stale instead of silently flattering.

### D5. Held-out manifest: dedicated builder, row pre-filter
New `scripts/make_pointing_holdout.py` (pattern of `make_bench50.py`): load
the verified EgoPoint data, compute the exclusion set = union of EgoPoint
`image_id`s in **all existing frozen manifests** (bench_40/47/50,
pv_matrix_57), pre-filter rows, then `select_mc_rows(rows, 15)` — deterministic
minimal-id-per-stratum on the remainder. Output:
`eval_manifests/pointing_holdout_15.jsonl` + sha256 sidecar
`pointing_holdout_15.json` (composition, per-case provenance: source, license
`private-research-use`, selection rule, exclusion manifest list, date).
Images under `eval_data/egopoint/` (gitignored, as today).

*Why:* zero adapter changes; exclusion is auditable from the sidecar;
re-running the builder with the same inputs must reproduce the same sha256.
*Alternative:* an `--exclude-manifests` flag on a hypothetical shared builder
(rejected — no shared builder exists in this repo).

### D6. Re-run scope and naming
New matrix JSON `scripts/matrix_w1_fix.json`: models × variants =
{gemma4-e2b×P3, gemma4-e4b×P3, qwen3.5-4b×P0, qwen3.5-9b×<its report
best>}, plus a baseline (no variant) per model; each on
`pointing_15` (the original EgoPoint-15 subset of bench_47) **and**
`pointing_holdout_15`. Run driver: `scripts/run_matrix.py` as today. New run
dirs under `eval_runs/2026-MM-DD-w1-fix-*/`.

*Why:* exactly the pairs the report quotes, plus the production baseline —
no wasted GPU; the original-15 re-run is what replaces the stale 15/15.

### D7. Report restatement
§5.2 / Table 7 → per model: (1) right one on shortlist (recall), (2) saw a
point at all (evidence), (3) **picked the right one (top-1, headline)**,
(4) "nobody's pointing" when true (no-target abstention/credit). Add: the
held-out confirmation row set; one explicit sentence that the drop from 100%
is the metric now measuring what it claims; a note that variant selection was
done on the original set and the held-out set was used only for confirmation.
`docs/project_report_benchmarks_en.md` is USER_REQUEST_ONLY — the user
requested this edit.

## Risks / Trade-offs

- [Expected score drop reads as regression] → D7 sentence + the four-column
  layout shows recall is unchanged; the drop is disclosed as honesty, with the
  old number retained as a labeled perception column.
- [Decision adds ~1 call/case → higher latency in the pointing table] →
  expected and honest; the latency column already reports per-case totals.
- [Small models may produce unparseable decisions] → the phase's existing
  retry (`max_attempts`) applies; persistent failure marks the case
  parse-failed, visible in status counts — never a silent pass.
- [Exclusion set depends on frozen manifests staying frozen] → the sidecar
  records exactly which manifests were excluded and their sha256; a later
  bench change requires a new sidecar, not a silent rebuild.
- [GPU shared with the local inference backend (the agent)] → the re-run is
  one bounded job (~150 cases, tens of minutes), scheduled explicitly, not in
  the background of other work.
- [Legacy `score.json` files flip to unjudged] → intended; they are kept on
  disk, and any regenerated summary for the report comes from the new runs.

## Migration Plan

No deployment: offline diagnostic harness. Order: code (D1–D4) with tests →
held-out builder (D5) → re-run (D6) → report (D7). Rollback = drop the
branch; old run directories are untouched on disk, so nothing is destroyed.

## Open Questions

None material — all scope-relevant decisions were settled with the user
before this design (re-run scope, held-out size/disjointness, report framing).
