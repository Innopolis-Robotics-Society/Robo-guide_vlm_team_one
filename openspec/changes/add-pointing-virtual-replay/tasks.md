# Tasks

## 1. Geometry inversion and sidecar (pure Python)

- [x] 1.1 Implement the anchor→position inverter (production camera model: 1280×720, HFOV 60/VFOV 34, z=1.0, pitch 10°) with horizon clamping (D_MAX=10 m, per-anchor `clamped` flag) and verify with a round-trip unit test `project(invert(u, v)) ≈ (u, v)` in `guide_robot_llm/test/`
- [x] 1.2 Implement the per-manifest geometry sidecar schema + provenance writer (keyed by `case_id`: anchors, inverted positions, clamped flags, gold region, camera params, image sha256, author/method/date, review status) and verify with a unit test covering all fields and the read-only-on-source guarantee

## 2. Geometry authoring and review page

- [x] 2.1 Author geometry for all 15 egopoint_15 cases (read each image, place 4 option anchors + gold target region per case using the manifest option text) into `eval_manifests/egopoint_15.geometry.json` and verify the sidecar has 15 entries with 4 anchors each and no unflagged horizon violations
- [x] 2.2 Author geometry for all 15 pointing_holdout_15 cases into `eval_manifests/pointing_holdout_15.geometry.json` and verify the same checks as 2.1
- [x] 2.3 Generate a self-contained review page (single HTML, all 30 images with drawn anchors/regions, option labels, clamped flags) and verify it renders with all 30 cases (headless Chrome screenshot)
- [x] 2.4 Human review of the geometry: confirm or flag disputed cases, then set `review_status` in both sidecars (user-executed; verify both sidecars read `confirmed` or carry explicit dispute notes)

## 3. Replay mode in the eval harness

- [x] 3.1 Add the replay mode flag to the runner: observation under the production instruction (P_base) → W1 decision-phase pick → `resolve_pointing()` call, persisting the resolution artifacts (status, resolved id, per-candidate bounded scores) per case; verify with a mock/canned replay run that produces the artifacts for every case
- [x] 3.2 Add replay scoring: case verdict (pass / fail / unjudged+reason / parse-failed) and run metrics (`resolved_accuracy`, mean `box_iou` where boxes exist, `detection_rate`, `agreement_rate`, `clarification_rate` by reason) with W1 final-choice and freeform columns kept as secondary; verify with unit tests covering all four verdict paths and the metric aggregation
- [x] 3.3 Verify standard (non-replay) deployed mode is unchanged: the full existing W1 eval test suite (`test_eval_scoring`, `test_eval_harness`, `test_eval_loop`, `test_eval_variants`) passes unmodified

## 4. Selection campaign

- [x] 4.1 Create `scripts/matrix_virtual_replay.json` with the full grid (4 models × {P_base, P0, P3, P4} × egopoint_15, 16 runs) plus a held-out leg template for top pairs and verify `run_matrix.py --dry-run` lists exactly 16 runs
- [x] 4.2 Verify the launcher GPU guard: running the campaign config without `--dry-run`/`--mock` refuses while port 11434 is listening
- [x] 4.3 User executes the grid campaign and verify 16 runs / 240 cases with all `score.json` present and zero backend errors (assistant verifies, as in W1 T4)

## 5. Results, selection, docs

- [x] 5.1 Tabulate the grid (per pair: resolved_accuracy + decomposition columns), rank pairs, and record the selection recommendation; verify a stable tabulation CSV exists in the campaign directory
- [x] 5.2 User executes the held-out legs for the top pairs and verify their results are present in the campaign directory
- [x] 5.3 Update `guide_robot_llm/docs/eval_harness_design.md` (replay mode, geometry sidecar, new metrics) and `docs/project_report_benchmarks_en.md` §5.2 (selection results under the replay metric; user-requested edit) and verify no stale wording remains and the report cites the tabulation
