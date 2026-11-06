# Design

## Context

See proposal.md — Why. Current state: weights live in `/home/sinorin/models/pilot/` (5 model dirs; 4 GGUF + 4 mmproj files used by the four campaign profiles), the llama.cpp build is at commit `1511ce3bc3f087376c8526b4ad07100bfabb277f` (2026-08-18), `server_cmd()` in `guide_robot_llm/scripts/run_matrix.py` builds the server command without `--seed`, temperature is frozen at 0.2 by the runner (`_PHASE_TEMPERATURE`), and the runner's backend-freeze already copies extra backend keys (like `seed`) into `run_config.json` declaratively.

## Goals / Non-Goals

**Goals:**
- A provenance record that pins all 8 weight/projector files + the server build, committed to the repo and shipped in the archive.
- Deterministic re-runs: fixed seed in the server command, recorded per run.

**Non-Goals:**
- Vendoring the GGUF files or the server binary into the repo.
- Bit-exact reproducibility across different hardware/driver stacks (we claim same-environment reproducibility).
- Changes to the eval runner's scoring or case flow.

## Decisions

1. **`model_provenance.md` (human-readable), not JSON.** It is a one-time static snapshot of the files used for the recorded runs; nothing consumes it programmatically. Alternative considered: `models_provenance.json` — rejected as unneeded machinery. Hashes are computed once with `sha256sum` and committed; a future re-download that changes a hash is detected by re-running `sha256sum -c`-style verification, and a new campaign records its own provenance. **Location:** `guide_robot_llm/docs/model_provenance.md`, not `llm_server/config/models/` as originally planned — `llm_server/.gitignore` ignores `models/`, so a doc there would never be committed/shipped. The doc also covers the development model (`qwen3.5-2b`, no projector, no campaign profile) per user request.
2. **Seed travels through the model profile.** Add `seed: 42` to each profile under `llm_server/config/models/`; `server_cmd()` appends `--seed {seed}` when the key is present. The runner already carries unknown backend keys into `run_config.json`, so the seed lands in the per-run freeze with zero runner changes. Alternative considered: a global CLI flag on `run_matrix.py` — rejected because per-profile keeps the pin next to the weights it applies to.
3. **Server build pinned by git commit, not binary hash.** The llama.cpp repo is public; commit + date is sufficient to rebuild. `run_config.json` freezes the backend endpoint config (`base_url`, `model_name` alias, multimodal settings), the prompt variant + temperature, and the manifest identity — verified against an actual run artifact. The server command line itself is not stored in `run_config.json`; it is built deterministically by `server_cmd()` from the committed profile, which pins the flags. PROVENANCE.md states both facts precisely.

## Risks / Trade-offs

- [Weights re-downloaded later, hash drifts] → provenance documents the snapshot used for the recorded runs; new campaigns record new provenance.
- [`--seed` determinism is per-environment] → report claims "same pinned environment", not cross-hardware bit-exactness.
- [Seed value 42 is arbitrary] → it only needs to be fixed and recorded; any value works.

## Migration Plan

Additive only: new doc, one key per profile, one flag in the server command. Old runs are unaffected (their `run_config.json` freezes stand as recorded).

## Open Questions

None.
