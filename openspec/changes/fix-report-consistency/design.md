# Design

## Context

See proposal.md — Why. Tables in `docs/project_report_benchmarks_en.md` were hand-copied from `score.json` files (the qwen3.5-9b full-pass p95 drifted to 1.5 s vs the artifact's 1769.073 ms), the §6/README inventory wording was written when `eval_runs/` was not shipped and is now false, and the README references `project_report_benchmarks_en.md` which the archive omitted.

## Goals / Non-Goals

**Goals:**
- Tables that cannot drift: generated from `eval_runs/*/score.json`, with a check mode.
- Inventory text that states exactly what the archive contains and is easy to keep true.
- All referenced files present in the archive.

**Non-Goals:**
- Automating PDF generation (the report is exported manually; the script operates on the markdown).
- Changing any reported metric's definition.

## Decisions

1. **Generator + check mode, not in-place rewrite.** `guide_robot_llm/scripts/render_report_tables.py` reads the run artifacts and (a) emits markdown table fragments, (b) in `--check` mode, compares the report's existing tables against the artifacts and exits non-zero on drift. The report keeps the tables as static markdown (pasted from the generator); `--check` is run before packaging. Alternative considered: the script rewrites the report file in place — rejected to avoid merge-conflict pain and silent churn in a human-maintained document.
2. **Rounding convention documented once.** Milliseconds → seconds, rounded to 2 decimals, stated in the table caption. This is the convention the reviewer used implicitly; making it explicit closes the "1.4 vs 1.375" ambiguity class.
3. **Single source for the inventory.** The "what is in the submission" list lives in report §6; the README points to it instead of maintaining a second copy.

## Risks / Trade-offs

- [Generated fragments go stale between runs and packaging] → `--check` in the packaging checklist; cheap to run.
- [Two places (report, README) can still drift] → README references the report section rather than duplicating.

## Migration Plan

One-shot: run the generator, paste, fix wording, re-verify. No runtime impact.

## Open Questions

None.
