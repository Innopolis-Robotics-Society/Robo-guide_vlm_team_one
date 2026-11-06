# Design

## Context

See proposal.md — Why. The code already contains the measurement fix: the decision phase (`final_choice_accuracy`), virtual replay (`replay_pointing`/`resolve_pointing`), and the disjoint `pointing_holdout_15`. The November 2026 campaigns (`2026-11-05-matrix`, `2026-11-06-virtual-replay`) produced the artifacts. The submitted report predates all of it and still presents candidate recall as the pointing outcome ("15/15 (100%)").

## Goals / Non-Goals

**Goals:**
- A pointing results section where every "success" column measures the final decision (or end-to-end replay), with candidate recall explicitly labeled as perception.
- Headline variant claims supported on the disjoint holdout.
- The November campaign artifacts shipped in the archive.

**Non-Goals:**
- Improving the pointing accuracy itself (that is research work, not this change).
- Re-running the September campaign (its artifacts are frozen history; they are re-interpreted, not re-scored — and the current scorer would mark legacy runs `decision_missing`).

## Decisions

1. **Two-block table layout.** Perception block: `target_in_top1`, `in_candidates` (perception metrics). Policy block: `final_choice_accuracy` (decision phase) and replay end-to-end accuracy, each with n and abstention rate. Model × variant rows from the November campaigns. This matches the §1.4 perception/policy distinction the report already makes in prose.
2. **Headline set = `pointing_holdout_15`.** Variant selection happened on the bench_50 pointing track (15 cases); selection claims are reported on the disjoint holdout, per the existing §5.1 selection/evaluation convention.
3. **Count selection bias — gated decision.** Options: (a) a disclosure paragraph (count variants were selected on the same 32 cases they are reported on; no count holdout exists); (b) `make_count_holdout.py` carving a disjoint count set from unused AGHRI frames (local data) plus one campaign run. **Default: (a)** unless a campaign run is scheduled; task 3.1 is the gate. Choosing (b) adds one script + one GPU campaign.
4. **Archive gains the two November campaign directories** (their `score.json`/`results.jsonl`/`replay_tabulation.csv`), so every new table cell is verifiable from the submission.

## Risks / Trade-offs

- [New numbers look much worse (final choice 0–31%, replay 20–50% at n ≤ 5)] → that is the point of the fix; framing separates perception from policy and discloses the small n. A weaker-looking, defensible table beats a strong-looking, refutable one.
- [Replay n ≤ 5 per leg] → disclosed as a limitation; the replay is a validation path, not the primary metric.
- [Legacy 15/15 rows removed may look like hiding results] → the perception metric (candidate recall) stays in the table; only the label changes.

## Migration Plan

Report-only change plus archive contents; no code behavior changes. The September campaign artifacts remain in the archive as frozen history.

## Open Questions

- Count selection bias: option (a) disclose vs (b) AGHRI count holdout + campaign. Does not block tasks 1, 2, 4, 5 — only task 3.1.
