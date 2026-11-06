# Tasks

## 1. Provenance record

- [x] 1.1 Compute SHA-256 for the 8 files in `/home/sinorin/models/pilot/` (4 GGUF + 4 mmproj) and verify with `sha256sum` that hashes are stable across two runs
- [x] 1.2 Create `guide_robot_llm/docs/model_provenance.md` (moved from `llm_server/config/models/PROVENANCE.md` — that path is gitignored by `llm_server/.gitignore: models/`, so the doc could not be committed there) with, per file: source URL, quantization, SHA-256, retrieval date, plus the llama.cpp build commit `1511ce3bc3f087376c8526b4ad07100bfabb277f` (2026-08-18); verify the file lists all 8 campaign files, the development model (`qwen3.5-2b`), and the build commit
- [x] 1.3 Note in PROVENANCE.md that the full server command line is frozen per run in `run_config.json`; verify the statement against an existing `run_config.json`

## 2. Seed pinning

- [x] 2.1 Add `seed: 42` to the four profiles in `llm_server/config/models/` and verify each profile still parses
- [x] 2.2 Extend `server_cmd()` in `guide_robot_llm/scripts/run_matrix.py` to append `--seed {seed}` when the profile carries the key; verify the built command contains the flag (dry-run/config-load check)
- [x] 2.3 Verify a generated `run_config.json` records the seed value (runner backend-freeze pass-through)

## 3. Report

- [x] 3.1 Update `docs/project_report_benchmarks_en.md` §6 (reproducibility) to point at PROVENANCE.md and state the seed/temperature pin; verify the section names the provenance file and the seed value
