# Tasks

## 1. Metadata and paths

- [ ] 1.1 Neutralize `author`/`author_email` in `guide_robot_llm/setup.py` (team-neutral value, no personal email); verify no personal name or email remains in any package `setup.py`
- [ ] 1.2 Make `llama_server_bin` in `guide_robot_llm/scripts/matrix_pv16.json` resolve from `LLAMA_SERVER_BIN` env var with an explicit error fallback (no silent default); verify the matrix config loads with the var set and fails with a clear message when unset
- [x] 1.3 Make `MODELS_DIR` in `llm_server/config/models/*.env` env-var-overridable with a relative fallback and no home-directory path committed; verify the profiles resolve on a machine with the var set and error clearly without it

## 2. Packaging checklist

- [ ] 2.1 Add a packaging checklist section (exclude `.git`; sweep command `grep -rniE 'sinorin|mook|mishacat|innopolis' <staged-dir>` must return nothing) to the submission docs; verify the checklist exists and names the sweep command
- [ ] 2.2 Stage a dry-run archive from the file list and run the sweep; verify zero identifier hits and no `.git` directory in the staged tree
