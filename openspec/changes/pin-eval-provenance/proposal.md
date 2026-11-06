# Proposal

## Why

The Stage-3 review (weakness W2, Minor, −3.75) confirmed that exact model/projector revisions, the llama-server build, and the sampling seed are not pinned, so the historical inference campaign cannot be recreated. All inputs exist locally today (weights in `/home/sinorin/models/pilot`, llama.cpp at commit `1511ce3`); nothing is missing — only the pinning is.

## What Changes

- Add `llm_server/config/models/PROVENANCE.md`: for each GGUF + mmproj file (4 models × weight, 4 mmproj) record source URL, quantization, SHA-256 (computed from the current local files), and retrieval date.
- Record the llama.cpp build (commit `1511ce3bc3f087376c8526b4ad07100bfabb277f`, 2026-08-18) in the provenance doc, and note that the full server command line is frozen per-run in `run_config.json`.
- Add a fixed `--seed` to `server_cmd()` in `guide_robot_llm/scripts/run_matrix.py`; carry the seed value through the model profile so it lands in `run_config.json` (the runner already preserves extra backend keys such as `seed` declaratively).
- Report §6.3 (reproducibility) updated to point at the provenance doc.

## Capabilities

### New Capabilities
- `eval-reproducibility`: an evaluation campaign must pin and record weight provenance (source + SHA-256), backend/server build (commit), and sampling parameters (temperature + seed) so a third party can recreate the inference environment from the submission alone.

### Modified Capabilities
(none — no existing specs)

## Impact

- `llm_server/config/models/` (new provenance doc, profile files gain `seed`)
- `guide_robot_llm/scripts/run_matrix.py` (`server_cmd()`)
- `docs/project_report_benchmarks_en.md` §6
- No functional behavior change; re-runs become deterministic.
