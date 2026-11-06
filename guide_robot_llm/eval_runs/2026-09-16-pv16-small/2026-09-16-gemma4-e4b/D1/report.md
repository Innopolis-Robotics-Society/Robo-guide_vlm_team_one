# VLM eval diagnostic report — D1

- Run: `eval_runs/2026-09-16-pv16-small/2026-09-16-gemma4-e4b/D1`
- Generated: 2026-09-16T18:26:47+07:00
- Cases: 3 (ok 3, parse_failed 0, backend_error 0)
- Judged: 0 (pass 0, fail 0, unjudged 3)
- Backend: `http://127.0.0.1:11436/v1` · model `gemma-4-e4b-it-q4_k_m`
- Manifest: `/home/sinorin/jupyter/Robo-guide_vlm_team_one/guide_robot_llm/eval_manifests/pv_matrix_57.jsonl` (sha256 02530da7e59e…)
- Prompt variant: `D1`

> **Diagnostic only — no final project score, no #11 selection.**

## Perception

### Pointing

_нет данных (нет судимых кейсов трека)_

### Audience

_нет данных (нет судимых кейсов трека)_

## Policy

### Pointing

_нет данных (нет судимых кейсов трека)_

### Tool

_нет данных (нет судимых кейсов трека)_

## Runner

| metric | value |
|---|---|
| latency mean (ms) | 1601.459 (n=3) |
| latency p50 (ms) | 1772.932 |
| latency p95 (ms) | 1784.903 |

## Slices

### By source

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| pilot-cc | 3 | 0 | 0 | 3 | – | – |

### By split group

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| g-cc-SCN-CC-001 | 1 | 0 | 0 | 1 | – | – |
| g-cc-SCN-CC-002 | 1 | 0 | 0 | 1 | – | – |
| g-cc-SCN-CC-003 | 1 | 0 | 0 | 1 | – | – |

### Metadata: venue

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| synthetic (PIL, deterministic spec, seed 20260914) | 3 | 0 | 0 | 3 | – | – |

## Variants

### D1

| metric | value |
|---|---|
| cases | 3 (pass 0, fail 0, unjudged 3) |
| scene cases (recorded, not judged) | 3 |
| count MAE | – |
| exact count | – |
| within-1 count | – |
| engaged MAE | – |
| exact engaged | – |
| pointing top-2 | – |
| pointing top-1 (freeform) | – |
| calls per case | 1.0 (n=3) |
| parse failed | 0 (rate 0.0 (n=3)) |
| latency mean (ms) | 1601.459 (n=3) |
| latency p50 (ms) | 1772.932 |
| latency p95 (ms) | 1784.903 |

## Per-case

| case | source | track | mode | status | perception | policy | pass |
|---|---|---|---|---|---|---|---|
| SCN-CC-001 | pilot-cc | scene | deployed | ok | – | – | – |
| SCN-CC-002 | pilot-cc | scene | deployed | ok | – | – | – |
| SCN-CC-003 | pilot-cc | scene | deployed | ok | – | – | – |
