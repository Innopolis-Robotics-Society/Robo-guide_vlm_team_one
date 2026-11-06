# VLM eval diagnostic report — 2026-11-05-qwen3.5-9b__h15-base

- Run: `/home/sinorin/jupyter/Robo-guide_vlm_team_one/guide_robot_llm/eval_runs/2026-11-05-matrix/2026-11-05-qwen3.5-9b__h15-base`
- Generated: 2026-11-05T20:06:15+07:00
- Cases: 15 (ok 15, parse_failed 0, backend_error 0)
- Judged: 15 (pass 12, fail 3, unjudged 0)
- Backend: `http://127.0.0.1:11436/v1` · model `qwen3.5-9b-q4_k_m`
- Manifest: `/home/sinorin/jupyter/Robo-guide_vlm_team_one/guide_robot_llm/eval_manifests/pointing_holdout_15.jsonl` (sha256 0e9269b39d8b…)

> **Diagnostic only — no final project score, no #11 selection.**

## Perception

### Pointing

_нет данных (нет судимых кейсов трека)_

### Audience

_нет данных (нет судимых кейсов трека)_

## Policy

### Pointing

| metric | value |
|---|---|
| top-1 target (freeform answer) | 0.8 (n=15) |

### Tool

_нет данных (нет судимых кейсов трека)_

## Runner

| metric | value |
|---|---|
| latency mean (ms) | 1428.531 (n=15) |
| latency p50 (ms) | 1461.187 |
| latency p95 (ms) | 1504.224 |

## Confidence calibration

Судимые кейсы с числовым `confidence` freeform-ответа: 15; 5 бакетов шириной 0.2.

| bucket | n | accuracy | mean confidence |
|---|---|---|---|
| 0.8-1.0 | 15 | 0.8 | 0.9233 |

**ECE**: 0.1233

## Confidence intervals (session-grouped bootstrap)

Единица ресэмплинга -- сессия записи (`split_group_id`), не кейс: кейсы одной сессии коррелированы. 1000 ресэмплов, seed 0, групп 15, кейсов 15.

| metric | value | 95% CI | n |
|---|---|---|---|
| policy: pointing_top1_accuracy | 0.8000 | [0.6000, 1.0000] | 15 |
| pass_rate | 0.8000 | [0.6000, 1.0000] | 15 |

## Slices

### By source

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| egopoint | 15 | 12 | 3 | 0 | 0.8 (n=15) | – |

### By split group

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| g-ep-real-4 | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |
| g-ep-real-18 | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |
| g-ep-real-21 | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |
| g-ep-real-23 | 1 | 0 | 1 | 0 | 0.0 (n=1) | – |
| g-ep-real-55 | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |
| g-ep-real-61 | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |
| g-ep-real-92 | 1 | 0 | 1 | 0 | 0.0 (n=1) | – |
| g-ep-real-141 | 1 | 0 | 1 | 0 | 0.0 (n=1) | – |
| g-ep-real-162 | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |
| g-ep-real-168 | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |
| g-ep-real-187 | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |
| g-ep-real-234 | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |
| g-ep-real-235 | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |
| g-ep-real-242 | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |
| g-ep-real-385 | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |

### Metadata: dimension

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| Basic Perception | 4 | 3 | 1 | 0 | 0.75 (n=4) | – |
| Affordance & Function | 4 | 4 | 0 | 0 | 1.0 (n=4) | – |
| Context & Relation | 4 | 2 | 2 | 0 | 0.5 (n=4) | – |
| OCR & Text | 3 | 3 | 0 | 0 | 1.0 (n=3) | – |

### Metadata: deixis_level

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| L1 | 6 | 5 | 1 | 0 | 0.8333 (n=6) | – |
| L3 | 6 | 4 | 2 | 0 | 0.6667 (n=6) | – |
| L2 | 3 | 3 | 0 | 0 | 1.0 (n=3) | – |

### Metadata: n_distractors

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| 3 | 15 | 12 | 3 | 0 | 0.8 (n=15) | – |

### Metadata: answer_map

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| {'Green': 'epobj-4-a', 'Black': 'epobj-4-b', 'Blue': 'epobj-4-c', 'Red': 'epobj-4-d'} | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |
| {'To designate a safe crossing path for pedestrians': 'epobj-18-a', 'To separate opposing lanes of traffic': 'epobj-18-b', 'To provide a parking space for electric scooters': 'epobj-18-c', 'To mark a stopping line for vehicles at a traffic light': 'epobj-18-d'} | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |
| {"To turn on the bicycle's headlight": 'epobj-21-a', 'To alert pedestrians or other vehicles': 'epobj-21-b', 'To measure the speed of the bicycle': 'epobj-21-c', 'To shift gears on the bicycle': 'epobj-21-d'} | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |
| {'Dried Bean Curd Sticks': 'epobj-23-a', 'Dried Daylilies': 'epobj-23-b', 'Dried Lily Bulbs': 'epobj-23-c', 'White Fungus (Tremella)': 'epobj-23-d'} | 1 | 0 | 1 | 0 | 0.0 (n=1) | – |
| {'Mesh strainer': 'epobj-55-a', 'Soup ladle': 'epobj-55-b', 'Frying pan': 'epobj-55-c', 'Silicone spatula': 'epobj-55-d'} | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |
| {'Yes, it stands on its own feet': 'epobj-61-a', 'No, it is mounted on a pedestal': 'epobj-61-b', 'No, it is hanging from the ceiling': 'epobj-61-c', 'Yes, it is a floor mat': 'epobj-61-d'} | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |
| {'Navigation': 'epobj-92-a', 'Advertising': 'epobj-92-b', 'Safety': 'epobj-92-c', 'Decoration': 'epobj-92-d'} | 1 | 0 | 1 | 0 | 0.0 (n=1) | – |
| {'Only in vehicles': 'epobj-141-a', 'Indoors': 'epobj-141-b', 'Only underwater': 'epobj-141-c', 'Outdoors': 'epobj-141-d'} | 1 | 0 | 1 | 0 | 0.0 (n=1) | – |
| {'Ice cubes': 'epobj-162-a', 'Cold beverages': 'epobj-162-b', 'Coffee': 'epobj-162-c', 'Boiling water': 'epobj-162-d'} | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |
| {'A park or green space': 'epobj-168-a', 'A busy urban street': 'epobj-168-b', 'A construction site': 'epobj-168-c', 'An industrial complex': 'epobj-168-d'} | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |
| {'Chair': 'epobj-187-a', 'Whiteboard': 'epobj-187-b', 'Desk': 'epobj-187-c', 'Table': 'epobj-187-d'} | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |
| {'Yes, it is fully open.': 'epobj-234-a', 'It is designed only for pedestrians.': 'epobj-234-b', 'It is partially open.': 'epobj-234-c', 'No, it is blocking the path.': 'epobj-234-d'} | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |
| {'University Physics': 'epobj-235-a', 'Analog Electronics Technique': 'epobj-235-b', 'C Programming Design': 'epobj-235-c', 'Engineering Drawing': 'epobj-235-d'} | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |
| {'JISS': 'epobj-242-a', 'J154': 'epobj-242-b', 'J155': 'epobj-242-c', 'T155': 'epobj-242-d'} | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |
| {'Corn starch': 'epobj-385-a', 'Wheat flour': 'epobj-385-b', 'Glutinous rice flour': 'epobj-385-c', 'Potato starch': 'epobj-385-d'} | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |

## Variants

### (no variant)

| metric | value |
|---|---|
| cases | 15 (pass 12, fail 3, unjudged 0) |
| pass rate | 0.8 (n=15) |
| scene cases (recorded, not judged) | 0 |
| count MAE | – |
| exact count | – |
| within-1 count | – |
| engaged MAE | – |
| exact engaged | – |
| pointing top-2 | – |
| pointing top-1 (freeform) | 0.8 (n=15) |
| calls per case | 1.0 (n=15) |
| parse failed | 0 (rate 0.0 (n=15)) |
| latency mean (ms) | 1428.531 (n=15) |
| latency p50 (ms) | 1461.187 |
| latency p95 (ms) | 1504.224 |

## Per-case

| case | source | track | mode | status | perception | policy | pass |
|---|---|---|---|---|---|---|---|
| EPO-REAL-0004 | egopoint | pointing | freeform | ok | – | top1 ✓, mapped epobj-4-d | ✓ |
| EPO-REAL-0018 | egopoint | pointing | freeform | ok | – | top1 ✓, mapped epobj-18-a | ✓ |
| EPO-REAL-0021 | egopoint | pointing | freeform | ok | – | top1 ✓, mapped epobj-21-b | ✓ |
| EPO-REAL-0023 | egopoint | pointing | freeform | ok | – | top1 ✗, mapped epobj-23-a | ✗ |
| EPO-REAL-0055 | egopoint | pointing | freeform | ok | – | top1 ✓, mapped epobj-55-a | ✓ |
| EPO-REAL-0061 | egopoint | pointing | freeform | ok | – | top1 ✓, mapped epobj-61-b | ✓ |
| EPO-REAL-0092 | egopoint | pointing | freeform | ok | – | top1 ✗, mapped epobj-92-a | ✗ |
| EPO-REAL-0141 | egopoint | pointing | freeform | ok | – | top1 ✗, mapped epobj-141-b | ✗ |
| EPO-REAL-0162 | egopoint | pointing | freeform | ok | – | top1 ✓, mapped epobj-162-d | ✓ |
| EPO-REAL-0168 | egopoint | pointing | freeform | ok | – | top1 ✓, mapped epobj-168-a | ✓ |
| EPO-REAL-0187 | egopoint | pointing | freeform | ok | – | top1 ✓, mapped epobj-187-c | ✓ |
| EPO-REAL-0234 | egopoint | pointing | freeform | ok | – | top1 ✓, mapped epobj-234-d | ✓ |
| EPO-REAL-0235 | egopoint | pointing | freeform | ok | – | top1 ✓, mapped epobj-235-c | ✓ |
| EPO-REAL-0242 | egopoint | pointing | freeform | ok | – | top1 ✓, mapped epobj-242-c | ✓ |
| EPO-REAL-0385 | egopoint | pointing | freeform | ok | – | top1 ✓, mapped epobj-385-c | ✓ |
