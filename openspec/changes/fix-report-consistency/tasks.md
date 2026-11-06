# Tasks

## 1. Table generator

- [ ] 1.1 Create `guide_robot_llm/scripts/render_report_tables.py` that reads `eval_runs/*/score.json` and emits the latency and quality markdown table fragments (ms → s, 2 decimals); verify the emitted qwen3.5-9b P_base full-pass row reads p50 1.38 s / p95 1.77 s
- [ ] 1.2 Add a `--check` mode that compares the report's existing tables against the artifacts and exits non-zero on drift; verify it exits 1 against a deliberately corrupted table and 0 against the corrected one

## 2. Report corrections

- [ ] 2.1 Replace the hand-copied tables in `docs/project_report_benchmarks_en.md` with the generated values and add the rounding convention to the table caption; verify `render_report_tables.py --check` exits 0
- [ ] 2.2 Fix the archive-inventory wording in report §6 to state exactly what the submission contains (includes `eval_runs/2026-09-16-pv16-small/` with 72 scored runs and `llm_server/config/models/`); verify every claim against the staged file list
- [ ] 2.3 Make `README.md` reference the report's inventory section instead of maintaining its own, and remove the stale claims at the lines the review cited; verify no contradictory inventory statement remains in README

## 3. Archive completeness

- [ ] 3.1 Audit every file referenced by the report and README; add missing ones (at minimum `docs/project_report_benchmarks_en.md`) to the archive file list; verify all references resolve in the staged archive
