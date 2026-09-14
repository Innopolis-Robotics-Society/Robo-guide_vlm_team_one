# Eval harness design (Taiga #10, plan `vlm-bench-50`)

Design note for the offline VLM evaluation harness. Scope: replay the existing
pilot episodes plus the 50-case external mini-benchmark (DP 20, EgoPoint-Bench
10, YouRefIt 5, AGHRI 15), record outputs, and produce sliced diagnostics.
**Diagnostic only** — no final project score, no #11 model selection, no
prompt/threshold tuning on the frozen sets.

## Placement (decision)

The harness lives inside the existing pure-Python package, no new colcon
package:

```
guide_robot_llm/
├── guide_robot_llm/
│   ├── eval/                    # NEW module (pure Python, no ROS, no network in tests)
│   │   ├── __init__.py
│   │   ├── schema.py            # unified Case record + validation
│   │   ├── loader.py            # unified JSONL manifest loader + pilot adapter
│   │   ├── runner.py            # CLI: one case or a whole manifest → run dir
│   │   ├── scoring.py           # metrics + report (T4)
│   │   └── adapters/            # one module per external source (T6–T9)
│   │       ├── dp.py
│   │       ├── egopoint.py
│   │       ├── yourifit.py
│   │       └── aghri.py
│   └── llm_client/              # EXISTING — reused, not modified
├── pilot/                       # EXISTING — read-only input (manifest + media)
├── eval_data/                   # NEW, gitignored — external datasets (large)
│   ├── dp/  egopoint/  yourifit/  aghri/
│   └── <source>/PROVENANCE.md   # license, version, archive hashes, download cmds
└── eval_runs/                   # NEW, gitignored — one dir per run
    └── <run_id>/
        ├── run_manifest.json    # one line per case (see below)
        └── cases/<case_id>/     # raw + parsed + meta per case
```

Rationale: `guide_robot_llm` is already pure Python (unit-testable without
ROS/colcon, same rule that keeps `guide_robot_voice/lib` testable), the harness
reuses `llm_client` in-process, and `pilot/` sits in the same package. A
separate colcon package would buy an install step and import indirection for no
isolation we actually need.

## Unified case record

One JSON object per evaluation case (one line in a manifest `.jsonl`):

```json
{
  "case_id": "DP-TAKE-0042",
  "source": "dp | egopoint | yourifit | aghri | pilot-cc | pilot-sr",
  "track": "pointing | audience | scene | tool",
  "split_group_id": "g-dp-2023-01-17-livingroom-take3",
  "media": {
    "path": "eval_data/dp/2023-01-17-livingroom/take3/07/0000001234.jpg",
    "sha256": "<64 hex, computed at manifest build>",
    "format": "jpg"
  },
  "prompt": {
    "mode": "deployed | freeform",
    "user_text": "А что это такое?",
    "language": "ru"
  },
  "candidates": ["exhibit_19", "exhibit_22"],
  "gold": { "type": "target_box | count | action | claims", "...": "track-specific" },
  "provenance": {
    "source": "DP/Deepoint",
    "license": "CC BY-NC 4.0 (verified 2026-09-15, docs/vlm_deixis_audience_datasets.md)",
    "version": "archive md5 6233f6c1…",
    "rights_note": "noncommercial research; no redistribution"
  },
  "slices": { "target_size_px": 412, "n_distractors": 2, "count_bucket": "3" }
}
```

Rules:

- `provenance.license` must cite a dated verification line; a case without
  provenance fails validation (schema rejects).
- `candidates` is the closed ID set the model may answer with — the semantic
  map is the only ID source (invariant carried over from #4). For DP the
  markers are mapped to stable synthetic exhibit IDs by a committed mapping
  table (fixture), never invented by the VLM.
- `split_group_id` groups all cases sharing one take/sequence/image; a group
  is never split across any half (leakage rule).
- `gold` types:
  - `target_box`: `{target_id, box_px, distractors}` (pointing; DP/EgoPoint/
    YouRefIt/pilot POI);
  - `count`: `{count}` (audience; AGHRI/pilot AUD, 0–5);
  - `action`: `{tool, args}` or `{abstention_reason}` (pilot TOL);
  - `claims` / `unanswerable` (pilot SCN — recorded, not the focus of this plan).
- Pilot episodes are not rewritten: `loader.py` maps `episode_template.json`
  fields (`media.uri`/`sha256`, `mission_snapshot.visible_candidate_ids`,
  `gold`, `split_group_id`, `utterance`) onto this record; `source` is
  `pilot-cc` or `pilot-sr` by `source_family`, `version` is the manifest date.
  Future #9 robot-view episodes land as `pilot-sr` rows with no code change.

## Adapter interface

```python
class Adapter(Protocol):
    source: str
    def load(self, data_root: Path) -> list[Case]: ...
```

- Deterministic: same data dir → same cases (stable `case_id`s, sorted output).
- `media.sha256` computed at load time from the actual file (never hand-edited).
- No network, no dataset modification (YouRefIt/EgoPoint adapters are
  read-only on `eval_data/`; no derivative images are produced).
- Each adapter module has a `PROVENANCE.md` contract: exact download commands
  (executed by the user — the agent never downloads), archive hashes, license
  line, and the selection rules used to curate the case set.

## Runner

Reuses the existing `llm_client` — the harness does not invent a second
transport:

- `Backend` + `BackendConfig` — endpoint comes from config (base_url,
  `multimodal_enabled`, `max_images`, `model_name`); **no hardcoded URLs**.
- `build_content(text, frames)` — image_url parts for frames.
- `ClientTelemetry` — per-attempt stage timings (serialization/upload/TTFT/
  full/parse-ready) recorded into case meta.
- Token usage: the current `Backend.complete()` returns text only (no
  `usage` capture) — `meta.json` records `tokens: null` with
  `tokens_note: "server usage not captured by llm_client (known gap)"`.
  Extending `llm_client` is out of scope for #10.

Contract modes (per case `prompt.mode`):

1. `deployed` — the exact two-phase production contract, so diagnostics
   measure what #11 will actually run:
   - phase 1: `grammar.build_observation_grammar(candidates)` →
     `{"people_count", "exhibit_candidates", "pointing_evidence",
     "pointing_box", "scene_facts"}`; final validation by the existing host
     parser `visual_context.parse_observation`;
   - phase 2 (tracks with an action gold): `grammar.build_action_grammar(
     allowed_tools)` → `{"tool","args","confidence","abstain"}`; final
     validation by `tools.validate.parse_action`.
2. `freeform` — strict JSON grammar reusing grammar.py's JSON + confidence
   rules: `{"answer": string, "confidence": 0..1, "abstain": bool}` — for
   EgoPoint-Bench's authors' QA protocol, where the answer is an object name
   and the candidate table maps it to an exhibit ID on the scoring side.

Per-case run dir contents:

```
cases/<case_id>/
├── raw_observation.txt      # verbatim model text, phase 1
├── raw_action.txt           # verbatim model text, phase 2 (if run)
├── parsed_observation.json  # host-parsed or {"parse_status": "failed", ...}
├── parsed_action.json
└── meta.json                # attempts, per-stage latency_ms, tokens (null),
                             # finish_reason, prompt mode, case snapshot
```

`run_manifest.json` — one line per case: `case_id, source, track, status
(ok|parse_failed|backend_error), pass, latency_ms, attempts`.

Attempts: up to 2 (one retry on network/generation failure). Parse failures
are logged, never dropped. CLI:

```
python -m guide_robot_llm.eval.runner \
    --manifest eval_manifests/external_50.jsonl \
    --backend-config eval_data/backend_config.json \
    --out eval_runs/2026-09-XX-prompt-baseline
```

Mock backend: `MockBackend` implementing the same `complete()` signature,
returning canned per-case responses from a fixture file. All unit tests use
the mock — no network in tests, ever.

## Scoring and report (T4)

- **Pointing** (perception + policy split):
  - perception: `pointing_evidence` accuracy vs gold presence,
    `pointing_box` IoU vs gold box (where gold has a box),
    gold-target membership in `exhibit_candidates` (top-2 recall slice);
  - policy/action: top-1 target accuracy (action-args ID or freeform answer
    mapped via candidate table), false-positive rate on no-target/ambiguous
    cases (gold `unknown` + model answered), abstention credit (gold
    `unknown` + model abstained).
- **Audience**: `people_count` MAE + exact-count accuracy over 0–5.
- **Tool** (pilot TOL): exact `{tool, args}` match or justified abstention,
  per the existing gold semantics.
- **Scene** (pilot SCN): claim support / unanswerable — recorded as-is
  (covered by the other #10 adapters, not tuned here).
- Slices: `source`, `split_group_id`, and every `slices` metadata key present
  (target size, distractor count, count bucket, …).
- Report (markdown + JSON): perception metrics and policy metrics in
  **separate sections** (a correct count with a wrong policy action is a
  policy problem — the report must let a reviewer tell them apart), plus an
  explicit statement: *diagnostic only — no final project score, no #11
  selection*.

## Freeze rules

- The 50-case external set is frozen at manifest build (sha256 per media item
  recorded in the manifest); the pilot input is the committed
  `pilot/manifest.jsonl` (2026-09-13).
- No prompt, threshold, or candidate-set tuning on the frozen sets — that
  belongs to #11 iterations after the diagnostic report exists.

## Out of scope

- Final project scores, model selection (that is #11).
- Modifying any external dataset (YouRefIt: no-modification clause;
  EgoPoint-Bench: no declared HF license → unmodified use only).
- New pilot data collection (that is #9; this harness replays it).
- Changes to `llm_client` itself; ROS integration; C++ (Stage-3 concerns).

## Appendix A — one schema, five source shapes

The same record shape below (abridged to the fields that differ per
source) expresses every source without runner branches:

```json
// 1. DP/Deepoint — pointing, synthetic exhibit IDs from the marker table
{"case_id":"DP-TAKE-0042","source":"dp","track":"pointing","split_group_id":"g-dp-2023-01-17-livingroom-take3",
 "media":{"path":"eval_data/dp/2023-01-17-livingroom/take3/07/0000001234.jpg","sha256":"…","format":"jpg"},
 "prompt":{"mode":"deployed","user_text":"А что это такое?","language":"ru"},
 "candidates":["exhibit_19","exhibit_22"],
 "gold":{"type":"target_box","target_id":"exhibit_19","box_px":[120,80,300,400],"distractors":["exhibit_22"]},
 "provenance":{"source":"DP/Deepoint","license":"CC BY-NC 4.0 (verified 2026-09-15)","version":"md5 6233f6c1…","rights_note":"noncommercial"},
 "slices":{"target_size_px":412,"n_distractors":2}}

// 2. EgoPoint-Bench — pointing, freeform QA, candidate table maps name→ID
{"case_id":"EPO-REAL-0007","source":"egopoint","track":"pointing","split_group_id":"g-ep-real-0007",
 "media":{"path":"eval_data/egopoint/realdata_benchmark/test_img/…jpg","sha256":"…","format":"jpg"},
 "prompt":{"mode":"freeform","user_text":"What is the person pointing at?","language":"en"},
 "candidates":["epobj-07-a","epobj-07-b","epobj-07-c"],
 "gold":{"type":"target_box","target_id":"epobj-07-a","box_px":null,"distractors":["epobj-07-b","epobj-07-c"]},
 "provenance":{"source":"EgoPoint-Bench","license":"HF license undeclared — unmodified private research use (GO 2026-09-15)","version":"hf-rev-…","rights_note":"no redistribution, no derivatives"},
 "slices":{"n_distractors":3,"deixis_level":"implicit_pronoun"}}

// 3. YouRefIt — pointing, authors' protocol, unmodified
{"case_id":"YRI-SCN-0114-03","source":"yourifit","track":"pointing","split_group_id":"g-yri-scene-0114",
 "media":{"path":"eval_data/yourifit/scenes/0114/frame_…jpg","sha256":"…","format":"jpg"},
 "prompt":{"mode":"freeform","user_text":"Can you show me the <object class> the person is referring to?","language":"en"},
 "candidates":["yri-0114-t1","yri-0114-t2"],
 "gold":{"type":"target_box","target_id":"yri-0114-t1","box_px":[…],"distractors":["yri-0114-t2"]},
 "provenance":{"source":"YouRefIt","license":"no-modification clause (verified 2026-09-15), reg-ref …","version":"release-1","rights_note":"unmodified, one archive copy"},
 "slices":{"n_distractors":1}}

// 4. AGHRI — audience count, 2D-box-derived gold
{"case_id":"AGHRI-SEQ-0041-F003","source":"aghri","track":"audience","split_group_id":"g-aghri-seq-0041",
 "media":{"path":"eval_data/aghri/seq_0041/rgb/frame_…png","sha256":"…","format":"png"},
 "prompt":{"mode":"deployed","user_text":"Сколько людей сейчас рядом с роботом?","language":"ru"},
 "candidates":[],
 "gold":{"type":"count","count":3},
 "provenance":{"source":"AGHRI","license":"CC BY 4.0 (verified 2026-09-15)","version":"part-hash-…","rights_note":"attribution; selected sequences only"},
 "slices":{"count_bucket":"3","n_sequences_sampled":1}}

// 5. Pilot (CC, 2026-09-13 manifest) — pointing/audience/tool/scene, unchanged fields
{"case_id":"POI-CC-001","source":"pilot-cc","track":"pointing","split_group_id":"g-cc-poi-001",
 "media":{"path":"pilot/media/cc/…jpg","sha256":"…","format":"jpg"},
 "prompt":{"mode":"deployed","user_text":"Это что за прибор?","language":"ru"},
 "candidates":["cand-voltmeter-01","cand-gauge-02"],
 "gold":{"type":"target_box","target_id":"cand-voltmeter-01","box_px":[…],"distractors":["cand-gauge-02"]},
 "provenance":{"source":"pilot-manifest","license":"self-captured/pre-approved","version":"2026-09-13","rights_note":"rights_ledger.csv"},
 "slices":{"venue":"staged-office","n_distractors":1}}
```

## Approval

Approved by: sinorin (user, date: 2026-09-15)
