# VLM eval diagnostic report — 2026-11-06-qwen3.5-4b__p15-p0

- Run: `eval_runs/2026-11-06-virtual-replay/2026-11-06-qwen3.5-4b__p15-p0`
- Generated: 2026-11-06T03:53:46+07:00
- Cases: 15 (ok 15, parse_failed 0, backend_error 0)
- Judged: 1 (pass 0, fail 1, unjudged 14)
- Backend: `http://127.0.0.1:11436/v1` · model `qwen3.5-4b-q4_k_m`
- Manifest: `/home/sinorin/jupyter/Robo-guide_vlm_team_one/guide_robot_llm/eval_manifests/egopoint_15.jsonl` (sha256 cbf233b41d3e…)
- Prompt variant: `P0`

> **Diagnostic only — no final project score, no #11 selection.**

## Perception

### Pointing

| metric | value |
|---|---|
| pointing evidence accuracy | 0.7333 (n=15) |
| target in candidates (exact ID) | 1.0 (n=15) |
| top-2 recall | 0.4 (n=15) |
| box IoU not computed | 15 |

### Audience

_нет данных (нет судимых кейсов трека)_

## Policy

### Pointing

| metric | value |
|---|---|
| final-choice accuracy (decision phase, judged only) | 0.1538 (n=13) |
| abstention rate (decision says "none") | 0.1333 (n=15) |

### Tool

_нет данных (нет судимых кейсов трека)_

## Runner

| metric | value |
|---|---|
| latency mean (ms) | 2788.137 (n=15) |
| latency p50 (ms) | 2858.586 |
| latency p95 (ms) | 3321.298 |

## Confidence intervals (session-grouped bootstrap)

Единица ресэмплинга -- сессия записи (`split_group_id`), не кейс: кейсы одной сессии коррелированы. 1000 ресэмплов, seed 0, групп 15, кейсов 15.

| metric | value | 95% CI | n |
|---|---|---|---|
| pass_rate | 0.0000 | [0.0000, 0.0000] | 1 |

## Slices

### By source

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| egopoint | 15 | 0 | 1 | 14 | 0.0 (n=1) | – |

### By split group

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| g-ep-real-3 | 1 | 0 | 0 | 1 | – | – |
| g-ep-real-8 | 1 | 0 | 0 | 1 | – | – |
| g-ep-real-13 | 1 | 0 | 0 | 1 | – | – |
| g-ep-real-27 | 1 | 0 | 1 | 0 | 0.0 (n=1) | – |
| g-ep-real-28 | 1 | 0 | 0 | 1 | – | – |
| g-ep-real-36 | 1 | 0 | 0 | 1 | – | – |
| g-ep-real-69 | 1 | 0 | 0 | 1 | – | – |
| g-ep-real-96 | 1 | 0 | 0 | 1 | – | – |
| g-ep-real-99 | 1 | 0 | 0 | 1 | – | – |
| g-ep-real-100 | 1 | 0 | 0 | 1 | – | – |
| g-ep-real-103 | 1 | 0 | 0 | 1 | – | – |
| g-ep-real-167 | 1 | 0 | 0 | 1 | – | – |
| g-ep-real-405 | 1 | 0 | 0 | 1 | – | – |
| g-ep-real-1204 | 1 | 0 | 0 | 1 | – | – |
| g-ep-real-1270 | 1 | 0 | 0 | 1 | – | – |

### Metadata: dimension

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| Basic Perception | 3 | 0 | 1 | 2 | 0.0 (n=1) | – |
| Affordance & Function | 3 | 0 | 0 | 3 | – | – |
| OCR & Text | 3 | 0 | 0 | 3 | – | – |
| Context & Relation | 3 | 0 | 0 | 3 | – | – |
| Adversarial | 3 | 0 | 0 | 3 | – | – |

### Metadata: deixis_level

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| L1 | 6 | 0 | 0 | 6 | – | – |
| L3 | 6 | 0 | 1 | 5 | 0.0 (n=1) | – |
| L2 | 3 | 0 | 0 | 3 | – | – |

### Metadata: n_distractors

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| 3 | 15 | 0 | 1 | 14 | 0.0 (n=1) | – |

### Metadata: answer_map

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| {'Garlic': 'epobj-3-a', 'Brussels Sprouts': 'epobj-3-b', 'Red Onion': 'epobj-3-c', 'Radish': 'epobj-3-d'} | 1 | 0 | 0 | 1 | – | – |
| {'To store cold beverages for drinking': 'epobj-8-a', 'To clean surfaces like a sponge': 'epobj-8-b', 'To hang clothes for drying': 'epobj-8-c', 'To provide warmth when filled with heated liquid': 'epobj-8-d'} | 1 | 0 | 0 | 1 | – | – |
| {'Ocean Blue': 'epobj-13-a', 'Red Star': 'epobj-13-b', 'Dream Blue': 'epobj-13-c', 'Golden Harvest': 'epobj-13-d'} | 1 | 0 | 0 | 1 | – | – |
| {'Pork chop': 'epobj-27-a', 'Yellow broiler chicken': 'epobj-27-b', 'Silkie chicken': 'epobj-27-c', 'Duck breast': 'epobj-27-d'} | 1 | 0 | 1 | 0 | 0.0 (n=1) | – |
| {'Below': 'epobj-28-a', 'To the right': 'epobj-28-b', 'Above': 'epobj-28-c', 'To the left': 'epobj-28-d'} | 1 | 0 | 0 | 1 | – | – |
| {'Attached to the side wall at eye level': 'epobj-36-a', 'Inside the room on a desk': 'epobj-36-b', 'Above the doorway': 'epobj-36-c', 'On the floor in front of the doorway': 'epobj-36-d'} | 1 | 0 | 0 | 1 | – | – |
| {'Stationery and office organization': 'epobj-69-a', 'Household cleaning and sanitation': 'epobj-69-b', 'Food and beverage consumption': 'epobj-69-c', 'Skincare or cosmetic application': 'epobj-69-d'} | 1 | 0 | 0 | 1 | – | – |
| {'Nike': 'epobj-96-a', 'Uniqlo': 'epobj-96-b', 'H&M': 'epobj-96-c', 'Adidas': 'epobj-96-d'} | 1 | 0 | 0 | 1 | – | – |
| {'An ingredient for a meal.': 'epobj-99-a', 'A single-serving snack bar.': 'epobj-99-b', 'A cleaning product.': 'epobj-99-c', 'A fresh noodle dish.': 'epobj-99-d'} | 1 | 0 | 0 | 1 | – | – |
| {'On the desk surface': 'epobj-100-a', 'On the shelf': 'epobj-100-b', 'Hanging from a cable': 'epobj-100-c', 'Mounted on the wall': 'epobj-100-d'} | 1 | 0 | 0 | 1 | – | – |
| {"Lay's": 'epobj-103-a', 'Orion': 'epobj-103-b', 'Pringles': 'epobj-103-c', 'Oishi': 'epobj-103-d'} | 1 | 0 | 0 | 1 | – | – |
| {'Red bean': 'epobj-167-a', 'Whole wheat': 'epobj-167-b', 'Milk': 'epobj-167-c', 'Chocolate chip': 'epobj-167-d'} | 1 | 0 | 0 | 1 | – | – |
| {'Unknown': 'epobj-405-a', 'Yes': 'epobj-405-b', 'Maybe': 'epobj-405-c', 'No': 'epobj-405-d'} | 1 | 0 | 0 | 1 | – | – |
| {'It prints labels automatically': 'epobj-1204-a', 'It charges mobile devices': 'epobj-1204-b', 'It scans documents digitally': 'epobj-1204-c', 'It has no electronic functions': 'epobj-1204-d'} | 1 | 0 | 0 | 1 | – | – |
| {'No, it is a black metal shelf guard': 'epobj-1270-a', 'Yes, it is a yellow package of tissues': 'epobj-1270-b', 'No, it is a large plastic storage bin': 'epobj-1270-c', 'Yes, it is a blue package of wet wipes': 'epobj-1270-d'} | 1 | 0 | 0 | 1 | – | – |

## Variants

### P0

| metric | value |
|---|---|
| cases | 15 (pass 0, fail 1, unjudged 14) |
| pass rate | 0.0 (n=1) |
| scene cases (recorded, not judged) | 0 |
| count MAE | – |
| exact count | – |
| within-1 count | – |
| engaged MAE | – |
| exact engaged | – |
| pointing top-2 | 0.4 (n=15) |
| pointing top-1 (freeform) | 0.1538 (n=13) |
| calls per case | 2.0 (n=15) |
| parse failed | 0 (rate 0.0 (n=15)) |
| latency mean (ms) | 2788.137 (n=15) |
| latency p50 (ms) | 2858.586 |
| latency p95 (ms) | 3321.298 |

## Per-case

| case | source | track | mode | status | perception | policy | pass |
|---|---|---|---|---|---|---|---|
| EPO-REAL-0003 | egopoint | pointing | deployed | ok | evidence ✓, target ✓, top2 ✗, iou – (gold_box_null) | top1 ✗ | – |
| EPO-REAL-0008 | egopoint | pointing | deployed | ok | evidence ✓, target ✓, top2 ✗, iou – (gold_box_null) | top1 ✗ | – |
| EPO-REAL-0013 | egopoint | pointing | deployed | ok | evidence ✓, target ✓, top2 ✓, iou – (gold_box_null) | top1 ✗ | – |
| EPO-REAL-0027 | egopoint | pointing | deployed | ok | evidence ✓, target ✓, top2 ✗, iou – (gold_box_null) | top1 ✗ | ✗ |
| EPO-REAL-0028 | egopoint | pointing | deployed | ok | evidence ✓, target ✓, top2 ✗, iou – (gold_box_null) | top1 ✗ | – |
| EPO-REAL-0036 | egopoint | pointing | deployed | ok | evidence ✓, target ✓, top2 ✗, iou – (gold_box_null) | top1 ✗ | – |
| EPO-REAL-0069 | egopoint | pointing | deployed | ok | evidence ✗, target ✓, top2 ✗, iou – (gold_box_null) | credit ✓, abstained | – |
| EPO-REAL-0096 | egopoint | pointing | deployed | ok | evidence ✓, target ✓, top2 ✓, iou – (gold_box_null) | top1 ✓ | – |
| EPO-REAL-0099 | egopoint | pointing | deployed | ok | evidence ✓, target ✓, top2 ✓, iou – (gold_box_null) | top1 ✗ | – |
| EPO-REAL-0100 | egopoint | pointing | deployed | ok | evidence ✗, target ✓, top2 ✓, iou – (gold_box_null) | credit ✓, abstained | – |
| EPO-REAL-0103 | egopoint | pointing | deployed | ok | evidence ✓, target ✓, top2 ✓, iou – (gold_box_null) | top1 ✗ | – |
| EPO-REAL-0167 | egopoint | pointing | deployed | ok | evidence ✓, target ✓, top2 ✓, iou – (gold_box_null) | top1 ✗ | – |
| EPO-REAL-0405 | egopoint | pointing | deployed | ok | evidence ✗, target ✓, top2 ✗, iou – (gold_box_null) | top1 ✗ | – |
| EPO-REAL-1204 | egopoint | pointing | deployed | ok | evidence ✓, target ✓, top2 ✗, iou – (gold_box_null) | top1 ✗ | – |
| EPO-REAL-1270 | egopoint | pointing | deployed | ok | evidence ✗, target ✓, top2 ✗, iou – (gold_box_null) | top1 ✓ | – |
