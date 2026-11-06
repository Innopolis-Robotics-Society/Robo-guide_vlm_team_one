# Design

## Context

See proposal.md — Why. Identifying material currently in the tree: `guide_robot_llm/setup.py` (`author="Mook"`, `author_email="mook@innopolis.university"`), `guide_robot_llm/scripts/matrix_pv16.json` (`llama_server_bin: /home/sinorin/llama.cpp/build-cuda/bin/llama-server`), `llm_server/config/models/*.env` (`MODELS_DIR=/home/sinorin/models/pilot`), and git author metadata (`S1norin`, `mishacat_2015@mail.ru`) in the repo history.

## Goals / Non-Goals

**Goals:**
- No personal names, emails, or user-home paths in any file that can ship in the archive.
- A packaging checklist that catches regressions before zipping.

**Non-Goals:**
- Rewriting git history (unnecessary: the archive ships without `.git`; history scrubbing is destructive and out of scope).
- Anonymizing the live working machine's environment (env vars keep the local setup working as-is).

## Decisions

1. **Env-var indirection for machine paths.** `run_matrix.py`/matrix config reads `LLAMA_SERVER_BIN` (fallback: `llama-server` on `PATH`) and the model profiles read `MODELS_DIR` (fallback: a relative `models/` dir). On the build machine the vars are set as today; in the archive no file names a home directory. Alternative considered: relative paths only — rejected because the llama-server binary is not installed on `PATH` on the build machine and a silent fallback would break runs there.
2. **Neutral package metadata.** `author`/`author_email` in `setup.py` become a team-neutral value (e.g. "Guide Robot Team" / no email). No other package metadata carries personal data (verified during the sweep).
3. **Packaging checklist with a sweep command.** A short doc section: exclude `.git`, then `grep -rniE 'sinorin|mook|mishacat|innopolis' <staged-dir>` must return nothing. The sweep list is extended if new identifiers appear.

## Risks / Trade-offs

- [Env vars unset on a fresh machine break the matrix runner] → documented in the checklist and report §6; fallbacks are explicit errors, not silent defaults.
- [Sweep list goes stale] → it is a starting point; the checklist says to add any new identifier found.

## Migration Plan

Edit metadata and configs, add env-var handling, then stage a dry-run archive and run the sweep. Rollback is a normal revert; nothing runtime-critical changes when the vars are set.

## Open Questions

None.
