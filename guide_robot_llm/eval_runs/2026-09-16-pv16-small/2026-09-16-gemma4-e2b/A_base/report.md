# VLM eval diagnostic report — A_base

- Run: `eval_runs/2026-09-16-pv16-small/2026-09-16-gemma4-e2b/A_base`
- Generated: 2026-09-16T18:26:45+07:00
- Cases: 32 (ok 32, parse_failed 0, backend_error 0)
- Judged: 21 (pass 12, fail 9, unjudged 11)
- Backend: `http://127.0.0.1:11436/v1` · model `gemma-4-e2b-it-q4_k_m`
- Manifest: `/home/sinorin/jupyter/Robo-guide_vlm_team_one/guide_robot_llm/eval_manifests/pv_matrix_57.jsonl` (sha256 02530da7e59e…)
- Prompt variant: `A_base`

> **Diagnostic only — no final project score, no #11 selection.**

## Perception

### Pointing

_нет данных (нет судимых кейсов трека)_

### Audience

| metric | value |
|---|---|
| people count MAE | 0.7619 (n=21) |
| exact-count accuracy | 0.5714 (n=21) |
| within-1 count accuracy (|pred-gold| ≤ 1) | 0.8571 (n=21) |

## Policy

### Pointing

_нет данных (нет судимых кейсов трека)_

### Tool

_нет данных (нет судимых кейсов трека)_

## Runner

| metric | value |
|---|---|
| latency mean (ms) | 440.73 (n=32) |
| latency p50 (ms) | 428.196 |
| latency p95 (ms) | 512.646 |

## Confidence calibration

Судимые кейсы с числовым `confidence` freeform-ответа: 21; 5 бакетов шириной 0.2.

| bucket | n | accuracy | mean confidence |
|---|---|---|---|
| 0.8-1.0 | 21 | 0.5714 | 0.9571 |

**ECE**: 0.3857

## Confidence intervals (session-grouped bootstrap)

Единица ресэмплинга -- сессия записи (`split_group_id`), не кейс: кейсы одной сессии коррелированы. 1000 ресэмплов, seed 0, групп 16, кейсов 32.

| metric | value | 95% CI | n |
|---|---|---|---|
| counts: mae | 0.7619 | [0.3043, 1.4118] | 21 |
| counts: exact_accuracy | 0.5714 | [0.3333, 0.7895] | 21 |
| counts: within1_accuracy | 0.8571 | [0.6667, 1.0000] | 21 |
| pass_rate | 0.5714 | [0.3478, 0.7778] | 21 |

## Slices

### By source

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| aghri | 25 | 10 | 4 | 11 | 0.7143 (n=14) | 0.2857 (n=14) |
| pilot-cc | 7 | 2 | 5 | 0 | 0.2857 (n=7) | 1.7143 (n=7) |

### By split group

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| g-aghri-seq-0001 | 3 | 0 | 2 | 1 | 0.0 (n=2) | 1.0 (n=2) |
| g-aghri-seq-0004 | 3 | 1 | 1 | 1 | 0.5 (n=2) | 0.5 (n=2) |
| g-aghri-seq-0005 | 3 | 0 | 0 | 3 | – | – |
| g-aghri-seq-0006 | 3 | 2 | 0 | 1 | 1.0 (n=2) | 0.0 (n=2) |
| g-aghri-seq-0007 | 3 | 2 | 1 | 0 | 0.6667 (n=3) | 0.3333 (n=3) |
| g-aghri-seq-0008 | 3 | 1 | 0 | 2 | 1.0 (n=1) | 0.0 (n=1) |
| g-aghri-seq-0009 | 3 | 2 | 0 | 1 | 1.0 (n=2) | 0.0 (n=2) |
| g-aghri-seq-0010 | 3 | 2 | 0 | 1 | 1.0 (n=2) | 0.0 (n=2) |
| g-aghri-seq-0011 | 1 | 0 | 0 | 1 | – | – |
| g-eng-ENG-CC-001 | 1 | 0 | 1 | 0 | 0.0 (n=1) | 3.0 (n=1) |
| g-eng-ENG-CC-002 | 1 | 0 | 1 | 0 | 0.0 (n=1) | 1.0 (n=1) |
| g-eng-ENG-CC-003 | 1 | 1 | 0 | 0 | 1.0 (n=1) | 0.0 (n=1) |
| g-eng-ENG-CC-004 | 1 | 0 | 1 | 0 | 0.0 (n=1) | 4.0 (n=1) |
| g-eng-SEQ-CC-001 | 1 | 0 | 1 | 0 | 0.0 (n=1) | 1.0 (n=1) |
| g-eng-SEQ-CC-002 | 1 | 0 | 1 | 0 | 0.0 (n=1) | 3.0 (n=1) |
| g-eng-SEQ-CC-003 | 1 | 1 | 0 | 0 | 1.0 (n=1) | 0.0 (n=1) |

### Metadata: count_bucket

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| 2 | 3 | 0 | 3 | 0 | 0.0 (n=3) | 1.0 (n=3) |
| 1 | 14 | 7 | 2 | 5 | 0.7778 (n=9) | 0.2222 (n=9) |
| 0 | 10 | 4 | 0 | 6 | 1.0 (n=4) | 0.0 (n=4) |
| 3 | 4 | 1 | 3 | 0 | 0.25 (n=4) | 1.75 (n=4) |
| 4 | 1 | 0 | 1 | 0 | 0.0 (n=1) | 4.0 (n=1) |

### Metadata: declared_count

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| 2 | 3 | 0 | 2 | 1 | 0.0 (n=2) | 1.0 (n=2) |
| 3 | 3 | 1 | 1 | 1 | 0.5 (n=2) | 0.5 (n=2) |
| 1 | 19 | 9 | 1 | 9 | 0.9 (n=10) | 0.1 (n=10) |

### Metadata: environment

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| Footpath | 25 | 10 | 4 | 11 | 0.7143 (n=14) | 0.2857 (n=14) |

### Metadata: robot_state

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| still | 12 | 4 | 3 | 5 | 0.5714 (n=7) | 0.4286 (n=7) |
| move | 13 | 6 | 1 | 6 | 0.8571 (n=7) | 0.1429 (n=7) |

### Metadata: split

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| unknown | 25 | 10 | 4 | 11 | 0.7143 (n=14) | 0.2857 (n=14) |

### Metadata: venue

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| synthetic (PIL, deterministic spec) | 7 | 2 | 5 | 0 | 0.2857 (n=7) | 1.7143 (n=7) |

### Metadata: min_engaged

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| 2 | 7 | 2 | 5 | 0 | 0.2857 (n=7) | 1.7143 (n=7) |

### Metadata: sequence

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| SEQ-CC-001 | 1 | 0 | 1 | 0 | 0.0 (n=1) | 1.0 (n=1) |
| SEQ-CC-002 | 1 | 0 | 1 | 0 | 0.0 (n=1) | 3.0 (n=1) |
| SEQ-CC-003 | 1 | 1 | 0 | 0 | 1.0 (n=1) | 0.0 (n=1) |

### Metadata: n_frames

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| 3 | 3 | 1 | 2 | 0 | 0.3333 (n=3) | 1.3333 (n=3) |

### Metadata: frames

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| [{'path': 'pilot/media/cc/SEQ-CC-001_f0.png', 'sha256': 'cf9b613c4bf67fb8a22638a9a5a7d9f70f56b3d3450e6de2e84b1597b9c81408', 'format': 'png'}, {'path': 'pilot/media/cc/SEQ-CC-001_f1.png', 'sha256': '270268d97cc0041499ffe6c29b5a7cf4ad7095947897c8a083aaaf01504d7015', 'format': 'png'}, {'path': 'pilot/media/cc/SEQ-CC-001_f2.png', 'sha256': 'eda6206fc0954cd603bfb1c14fc4831e83d0be0ebb34ac6640a3604814bb234c', 'format': 'png'}] | 1 | 0 | 1 | 0 | 0.0 (n=1) | 1.0 (n=1) |
| [{'path': 'pilot/media/cc/SEQ-CC-002_f0.png', 'sha256': '99473468e72a08b75d788d8af8462762bfcefb457868b7862131dc995c1c5f54', 'format': 'png'}, {'path': 'pilot/media/cc/SEQ-CC-002_f1.png', 'sha256': 'cf9b613c4bf67fb8a22638a9a5a7d9f70f56b3d3450e6de2e84b1597b9c81408', 'format': 'png'}, {'path': 'pilot/media/cc/SEQ-CC-002_f2.png', 'sha256': 'ae668c624f1afd23f977acc90383e7611dc3415711bd834cd710793b3640395d', 'format': 'png'}] | 1 | 0 | 1 | 0 | 0.0 (n=1) | 3.0 (n=1) |
| [{'path': 'pilot/media/cc/SEQ-CC-003_f0.png', 'sha256': '9607c59d4b77d20cf217720dd81c9ddd2e815ba01ad6e6dc7d53db65b4147441', 'format': 'png'}, {'path': 'pilot/media/cc/SEQ-CC-003_f1.png', 'sha256': '9607c59d4b77d20cf217720dd81c9ddd2e815ba01ad6e6dc7d53db65b4147441', 'format': 'png'}, {'path': 'pilot/media/cc/SEQ-CC-003_f2.png', 'sha256': '430547334fcb58b29789e6eb1b66f9045daa143f2d892325b33a764a8ae333c1', 'format': 'png'}] | 1 | 1 | 0 | 0 | 1.0 (n=1) | 0.0 (n=1) |

## Variants

### A_base

| metric | value |
|---|---|
| cases | 32 (pass 12, fail 9, unjudged 11) |
| pass rate | 0.5714 (n=21) |
| scene cases (recorded, not judged) | 0 |
| count MAE | 0.7619 (n=21) |
| exact count | 0.5714 (n=21) |
| within-1 count | 0.8571 (n=21) |
| engaged MAE | – |
| exact engaged | – |
| pointing top-2 | – |
| pointing top-1 (freeform) | – |
| calls per case | 1.0 (n=32) |
| parse failed | 0 (rate 0.0 (n=32)) |
| latency mean (ms) | 440.73 (n=32) |
| latency p50 (ms) | 428.196 |
| latency p95 (ms) | 512.646 |

## Per-case

| case | source | track | mode | status | perception | policy | pass |
|---|---|---|---|---|---|---|---|
| AGHRI-SEQ-0001-F001 | aghri | audience | freeform | ok | count 1/2 | – | ✗ |
| AGHRI-SEQ-0001-F040 | aghri | audience | freeform | ok | count 1/2 | – | ✗ |
| AGHRI-SEQ-0001-F079 | aghri | audience | freeform | ok | count None/1 | – | – |
| AGHRI-SEQ-0004-F001 | aghri | audience | freeform | ok | count None/0 | – | – |
| AGHRI-SEQ-0004-F130 | aghri | audience | freeform | ok | count 1/2 | – | ✗ |
| AGHRI-SEQ-0004-F260 | aghri | audience | freeform | ok | count 1/1 | – | ✓ |
| AGHRI-SEQ-0005-F001 | aghri | audience | freeform | ok | count None/0 | – | – |
| AGHRI-SEQ-0005-F125 | aghri | audience | freeform | ok | count None/1 | – | – |
| AGHRI-SEQ-0005-F249 | aghri | audience | freeform | ok | count None/0 | – | – |
| AGHRI-SEQ-0006-F001 | aghri | audience | freeform | ok | count None/1 | – | – |
| AGHRI-SEQ-0006-F158 | aghri | audience | freeform | ok | count 1/1 | – | ✓ |
| AGHRI-SEQ-0006-F316 | aghri | audience | freeform | ok | count 1/1 | – | ✓ |
| AGHRI-SEQ-0007-F001 | aghri | audience | freeform | ok | count 0/1 | – | ✗ |
| AGHRI-SEQ-0007-F131 | aghri | audience | freeform | ok | count 1/1 | – | ✓ |
| AGHRI-SEQ-0007-F262 | aghri | audience | freeform | ok | count 1/1 | – | ✓ |
| AGHRI-SEQ-0008-F001 | aghri | audience | freeform | ok | count 0/0 | – | ✓ |
| AGHRI-SEQ-0008-F122 | aghri | audience | freeform | ok | count None/1 | – | – |
| AGHRI-SEQ-0008-F243 | aghri | audience | freeform | ok | count None/0 | – | – |
| AGHRI-SEQ-0009-F001 | aghri | audience | freeform | ok | count None/0 | – | – |
| AGHRI-SEQ-0009-F124 | aghri | audience | freeform | ok | count 0/0 | – | ✓ |
| AGHRI-SEQ-0009-F248 | aghri | audience | freeform | ok | count 1/1 | – | ✓ |
| AGHRI-SEQ-0010-F001 | aghri | audience | freeform | ok | count None/1 | – | – |
| AGHRI-SEQ-0010-F061 | aghri | audience | freeform | ok | count 1/1 | – | ✓ |
| AGHRI-SEQ-0010-F121 | aghri | audience | freeform | ok | count 0/0 | – | ✓ |
| AGHRI-SEQ-0011-F001 | aghri | audience | freeform | ok | count None/0 | – | – |
| ENG-CC-001 | pilot-cc | audience | freeform | ok | count 6/3, engaged None/2 | – | ✗ |
| ENG-CC-002 | pilot-cc | audience | freeform | ok | count 2/1, engaged None/1 | – | ✗ |
| ENG-CC-003 | pilot-cc | audience | freeform | ok | count 0/0, engaged None/0 | – | ✓ |
| ENG-CC-004 | pilot-cc | audience | freeform | ok | count 8/4, engaged None/1 | – | ✗ |
| SEQ-CC-001 | pilot-cc | audience | freeform | ok | count 2/3, engaged None/3 | – | ✗ |
| SEQ-CC-002 | pilot-cc | audience | freeform | ok | count 0/3, engaged None/2 | – | ✗ |
| SEQ-CC-003 | pilot-cc | audience | freeform | ok | count 3/3, engaged None/1 | – | ✓ |
