# Model & backend provenance

Static snapshot of the exact weights and inference backend used for all recorded
evaluation campaigns (`guide_robot_llm/eval_runs/`, September 2026 and November 2026).
This file is shipped in the submission so a third party can recreate the inference
environment from the archive alone.

## Weight files (GGUF + vision projector)

All eight files are published GGUF quants from Hugging Face (unsloth), downloaded
2026-09-13 / 2026-09-16 (dates from file mtimes). SHA-256 was computed on this
machine with `sha256sum` and re-verified (stable across runs). To re-download a
file, use the `resolve/main/` URL below; to verify an existing copy, re-run
`sha256sum` and compare against the table.

| Profile | Local file (under `MODELS_DIR`) | Source (Hugging Face) | Retrieved | SHA-256 |
|---|---|---|---|---|
| `gemma4-e2b` | `gemma4-e2b/gemma-4-E2B-it-Q4_K_M.gguf` | [unsloth/gemma-4-E2B-it-GGUF/resolve/main/gemma-4-E2B-it-Q4_K_M.gguf](https://huggingface.co/unsloth/gemma-4-E2B-it-GGUF/resolve/main/gemma-4-E2B-it-Q4_K_M.gguf) | 2026-09-13 | `740185b21d22ceb83a11c3aa62ad5842ef32c70f6096d756bbee85a1e4ec34b8` |
| `gemma4-e2b` | `gemma4-e2b/mmproj-F16.gguf` | [unsloth/gemma-4-E2B-it-GGUF/resolve/main/mmproj-F16.gguf](https://huggingface.co/unsloth/gemma-4-E2B-it-GGUF/resolve/main/mmproj-F16.gguf) | 2026-09-13 | `140be8d7849741f88c50757d529b84373ee8e27052cc2236855b537f4a8215fa` |
| `gemma4-e4b` | `gemma4-e4b/gemma-4-E4B-it-Q4_K_M.gguf` | [unsloth/gemma-4-E4B-it-GGUF/resolve/main/gemma-4-E4B-it-Q4_K_M.gguf](https://huggingface.co/unsloth/gemma-4-E4B-it-GGUF/resolve/main/gemma-4-E4B-it-Q4_K_M.gguf) | 2026-09-16 | `85a896a047553e842f25297ee5b031d64ff30147d9c4af17b1e4b394cd1fab87` |
| `gemma4-e4b` | `gemma4-e4b/mmproj-F16.gguf` | [unsloth/gemma-4-E4B-it-GGUF/resolve/main/mmproj-F16.gguf](https://huggingface.co/unsloth/gemma-4-E4B-it-GGUF/resolve/main/mmproj-F16.gguf) | 2026-09-16 | `ddf46c21d7078e95338cfc22306b19b276a29a5ad089023449dd54d4b6170a51` |
| `qwen3.5-4b` | `qwen3.5-4b/Qwen3.5-4B-Q4_K_M.gguf` | [unsloth/Qwen3.5-4B-GGUF/resolve/main/Qwen3.5-4B-Q4_K_M.gguf](https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/resolve/main/Qwen3.5-4B-Q4_K_M.gguf) | 2026-09-13 | `00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4` |
| `qwen3.5-4b` | `qwen3.5-4b/mmproj-F16.gguf` | [unsloth/Qwen3.5-4B-GGUF/resolve/main/mmproj-F16.gguf](https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/resolve/main/mmproj-F16.gguf) | 2026-09-13 | `cd88edcf8d031894960bb0c9c5b9b7e1fea6ebee02b9f7ce925a00d12891f864` |
| `qwen3.5-9b` | `qwen3.5-9b/Qwen3.5-9B-Q4_K_M.gguf` | [unsloth/Qwen3.5-9B-GGUF/resolve/main/Qwen3.5-9B-Q4_K_M.gguf](https://huggingface.co/unsloth/Qwen3.5-9B-GGUF/resolve/main/Qwen3.5-9B-Q4_K_M.gguf) | 2026-09-16 | `1d72077e2779568d4df1f5ab5595282abffff88e084b35eb893e144516acbfa8` |
| `qwen3.5-9b` | `qwen3.5-9b/mmproj-F16.gguf` | [unsloth/Qwen3.5-9B-GGUF/resolve/main/mmproj-F16.gguf](https://huggingface.co/unsloth/Qwen3.5-9B-GGUF/resolve/main/mmproj-F16.gguf) | 2026-09-16 | `f70dc3509053962b0d0d3ee8a7eacebf5d60aa560cad78254ae8698516ae029f` |

Quantization: all weight files are `Q4_K_M`; all projectors are `F16` (lossless
float16).

## Development model (not part of the campaigns)

`Qwen3.5-2B` was used for development and pilot iteration (fast local runs,
prompt/tooling debugging). It has no vision projector and no campaign profile,
so it appears in no recorded campaign; it is documented here for completeness.

| Role | Local file (under `MODELS_DIR`) | Source (Hugging Face) | Retrieved | SHA-256 |
|---|---|---|---|---|
| development | `qwen3.5-2b/Qwen3.5-2B-Q4_K_M.gguf` | [unsloth/Qwen3.5-2B-GGUF/resolve/main/Qwen3.5-2B-Q4_K_M.gguf](https://huggingface.co/unsloth/Qwen3.5-2B-GGUF/resolve/main/Qwen3.5-2B-Q4_K_M.gguf) | 2026-09-16 | `aaf42c8b7c3cab2bf3d69c355048d4a0ee9973d48f16c731c0520ee914699223` |

## Inference backend (llama.cpp)

- Repository: `ggml-org/llama.cpp` (public)
- Build commit: `1511ce3bc3f087376c8526b4ad07100bfabb277f` (2026-08-18)
- Binary used: `llama-server` from a local CUDA build of that commit.

The exact per-run server flags are not re-derived by hand: the command line is
built deterministically by `guide_robot_llm/scripts/run_matrix.py::server_cmd()`
from the committed model profile (`llm_server/config/models/*.env`). The
profiles carry a relative `MODELS_DIR` (`models/pilot`); on a machine where the
weights live elsewhere, set the `MODELS_DIR` environment variable — the
runner's `models_dir()` resolves env var first and fails clearly if the
directory is missing. Same profile + same weights ⇒ same command.

## Per-run freeze

Every evaluation run writes `run_config.json` into its output directory, freezing:

- the backend endpoint config (`base_url`, `model_name` alias, multimodal settings);
- the prompt variant id and **temperature (0.2)**;
- the manifest path + SHA-256 and case count;
- runner params (`max_attempts`, loop budget).

Since this change, the server sampling **seed (42)** is pinned in each model
profile (`SEED=42`), passed to `llama-server` as `--seed 42`, and recorded in
`run_config.json.backend.seed` via the runner's declarative backend freeze.

Reproducibility claim: same pinned environment (weights above, backend commit
above, seed + temperature above) reproduces the recorded runs; bit-exactness
across different hardware/driver stacks is not claimed.
