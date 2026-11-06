# VLM eval diagnostic report — A0

- Run: `/home/sinorin/jupyter/Robo-guide_vlm_team_one/guide_robot_llm/eval_runs/2026-09-16-matrix-mock/2026-09-16-gemma4-e4b/A0`
- Generated: 2026-09-16T09:07:58+07:00
- Cases: 25 (ok 25, parse_failed 0, backend_error 0)
- Judged: 0 (pass 0, fail 0, unjudged 25)
- Backend: mock (canned 42691246e036…)
- Manifest: `/home/sinorin/jupyter/Robo-guide_vlm_team_one/guide_robot_llm/eval_manifests/bench_50.jsonl` (sha256 9b3e494ebe73…)
- Prompt variant: `A0`

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

## Slices

### By source

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| aghri | 25 | 0 | 0 | 25 | – | – |

### By split group

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| g-aghri-seq-0001 | 3 | 0 | 0 | 3 | – | – |
| g-aghri-seq-0004 | 3 | 0 | 0 | 3 | – | – |
| g-aghri-seq-0005 | 3 | 0 | 0 | 3 | – | – |
| g-aghri-seq-0006 | 3 | 0 | 0 | 3 | – | – |
| g-aghri-seq-0007 | 3 | 0 | 0 | 3 | – | – |
| g-aghri-seq-0008 | 3 | 0 | 0 | 3 | – | – |
| g-aghri-seq-0009 | 3 | 0 | 0 | 3 | – | – |
| g-aghri-seq-0010 | 3 | 0 | 0 | 3 | – | – |
| g-aghri-seq-0011 | 1 | 0 | 0 | 1 | – | – |

### Metadata: count_bucket

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| 2 | 3 | 0 | 0 | 3 | – | – |
| 1 | 13 | 0 | 0 | 13 | – | – |
| 0 | 9 | 0 | 0 | 9 | – | – |

### Metadata: declared_count

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| 2 | 3 | 0 | 0 | 3 | – | – |
| 3 | 3 | 0 | 0 | 3 | – | – |
| 1 | 19 | 0 | 0 | 19 | – | – |

### Metadata: environment

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| Footpath | 25 | 0 | 0 | 25 | – | – |

### Metadata: robot_state

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| still | 12 | 0 | 0 | 12 | – | – |
| move | 13 | 0 | 0 | 13 | – | – |

### Metadata: split

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| unknown | 25 | 0 | 0 | 25 | – | – |

## Variants

### A0

| metric | value |
|---|---|
| cases | 25 (pass 0, fail 0, unjudged 25) |
| scene cases (recorded, not judged) | 0 |
| count MAE | – |
| exact count | – |
| engaged MAE | – |
| exact engaged | – |
| pointing top-2 | – |
| pointing top-1 (freeform) | – |
| calls per case | 1.0 (n=25) |
| latency (ms) | 0.0031 (n=25) |

## Per-case

| case | source | track | mode | status | perception | policy | pass |
|---|---|---|---|---|---|---|---|
| AGHRI-SEQ-0001-F001 | aghri | audience | freeform | ok | – | – | – |
| AGHRI-SEQ-0001-F040 | aghri | audience | freeform | ok | – | – | – |
| AGHRI-SEQ-0001-F079 | aghri | audience | freeform | ok | – | – | – |
| AGHRI-SEQ-0004-F001 | aghri | audience | freeform | ok | – | – | – |
| AGHRI-SEQ-0004-F130 | aghri | audience | freeform | ok | – | – | – |
| AGHRI-SEQ-0004-F260 | aghri | audience | freeform | ok | – | – | – |
| AGHRI-SEQ-0005-F001 | aghri | audience | freeform | ok | – | – | – |
| AGHRI-SEQ-0005-F125 | aghri | audience | freeform | ok | – | – | – |
| AGHRI-SEQ-0005-F249 | aghri | audience | freeform | ok | – | – | – |
| AGHRI-SEQ-0006-F001 | aghri | audience | freeform | ok | – | – | – |
| AGHRI-SEQ-0006-F158 | aghri | audience | freeform | ok | – | – | – |
| AGHRI-SEQ-0006-F316 | aghri | audience | freeform | ok | – | – | – |
| AGHRI-SEQ-0007-F001 | aghri | audience | freeform | ok | – | – | – |
| AGHRI-SEQ-0007-F131 | aghri | audience | freeform | ok | – | – | – |
| AGHRI-SEQ-0007-F262 | aghri | audience | freeform | ok | – | – | – |
| AGHRI-SEQ-0008-F001 | aghri | audience | freeform | ok | – | – | – |
| AGHRI-SEQ-0008-F122 | aghri | audience | freeform | ok | – | – | – |
| AGHRI-SEQ-0008-F243 | aghri | audience | freeform | ok | – | – | – |
| AGHRI-SEQ-0009-F001 | aghri | audience | freeform | ok | – | – | – |
| AGHRI-SEQ-0009-F124 | aghri | audience | freeform | ok | – | – | – |
| AGHRI-SEQ-0009-F248 | aghri | audience | freeform | ok | – | – | – |
| AGHRI-SEQ-0010-F001 | aghri | audience | freeform | ok | – | – | – |
| AGHRI-SEQ-0010-F061 | aghri | audience | freeform | ok | – | – | – |
| AGHRI-SEQ-0010-F121 | aghri | audience | freeform | ok | – | – | – |
| AGHRI-SEQ-0011-F001 | aghri | audience | freeform | ok | – | – | – |
