# Tasks

## 1. Restructured pointing section

- [ ] 1.1 Draft the two-block pointing results table (perception: `target_in_top1`/`in_candidates`; policy: `final_choice_accuracy` + replay end-to-end, each with n and abstention rate) from the `2026-11-05-matrix` and `2026-11-06-virtual-replay` artifacts; verify every cell is traceable to a `score.json` or `replay_tabulation.csv` value
- [ ] 1.2 Insert the table into `docs/project_report_benchmarks_en.md`, retire the "15/15 (100%)" pointing-success rows, and update §1.4/§5 wording so candidate recall is labeled perception-only; verify no unlabeled pointing "100%" claim remains in the report
- [ ] 1.3 Report pointing variant-selection claims on the disjoint `pointing_holdout_15` per the §5.1 convention; verify the selection set and the headline set are disjoint (media-path check)

## 2. Limitations

- [ ] 2.1 Add the disclosed limitations: zero no-target cases (safe-abstention path unmeasured), replay n ≤ 5 per leg; verify both statements match the manifests and `replay_tabulation.csv`

## 3. Count selection bias (gated)

- [ ] 3.1 Decide option (a) disclose vs (b) AGHRI count holdout + campaign (see design.md Open Questions); if (a): add the disclosure paragraph to the count section and verify it states selection and evaluation used the same 32 cases; if (b): proceed to 3.2
- [ ] 3.2 (only if 3.1 chose b) Create `guide_robot_llm/scripts/make_count_holdout.py` carving a disjoint count set from unused AGHRI frames in `guide_robot_llm/eval_data/aghri/`; verify zero media-path overlap with the selection set and ≥15 cases
- [ ] 3.3 (only if 3.1 chose b) Run the count campaign on the holdout and add the holdout numbers to the report; verify the new cells are traceable to the new run artifacts

## 4. Archive and export

- [ ] 4.1 Add `2026-11-05-matrix/` and `2026-11-06-virtual-replay/` to the archive file list; verify both directories (with score/replay artifacts) are present in the staged archive
- [ ] 4.2 Regenerate the report PDF from the updated markdown; verify Table 7/8 equivalents match the markdown and the retired 15/15 rows are gone
