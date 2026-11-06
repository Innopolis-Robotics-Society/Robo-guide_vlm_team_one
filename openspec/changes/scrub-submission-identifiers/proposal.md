# Proposal

## Why

The tree contains identifying information that violates submission anonymity: `guide_robot_llm/setup.py` carries `author="Mook"`, `author_email="mook@innopolis.university"` (name + institution), `guide_robot_llm/scripts/matrix_pv16.json` hardcodes `/home/sinorin/llama.cpp/build-cuda/bin/llama-server`, and `llm_server/config/models/*.env` reference `/home/sinorin/models/pilot`. Git author metadata (`S1norin`, `mishacat_2015@mail.ru`) is present in the repo history. The current review did not flag this, but it is a rule violation a next reviewer can catch in seconds.

## What Changes

- Neutralize author/maintainer fields in `guide_robot_llm/setup.py` (and any other package metadata with personal names/emails).
- Replace machine-specific paths with env-var-overridable defaults: `LLAMA_SERVER_BIN` and `MODELS_DIR` environment variables (documented in `.env` files and report §6), with sane relative fallbacks so no committed file names a user home directory.
- Submission hygiene checklist: archive must not contain `.git`; sweep the packaged file list for personal names, emails, and home-directory paths before zipping.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
(none — submission-process hygiene, no spec-level behavior changes; this change opts out of specs)

## Impact

- `guide_robot_llm/setup.py`, `guide_robot_llm/scripts/matrix_pv16.json`, `llm_server/config/models/*.env`, `guide_robot_llm/scripts/run_matrix.py` (env-var handling)
- Packaging checklist doc
- No functional behavior change when env vars are set as they are on the build machine.
