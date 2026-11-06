# VLM eval diagnostic report — 2026-11-05-qwen3.5-9b__p15-p4

- Run: `/home/sinorin/jupyter/Robo-guide_vlm_team_one/guide_robot_llm/eval_runs/2026-11-05-matrix/2026-11-05-qwen3.5-9b__p15-p4`
- Generated: 2026-11-05T20:06:14+07:00
- Cases: 15 (ok 8, parse_failed 7, backend_error 0)
- Judged: 4 (pass 1, fail 3, unjudged 11)
- Backend: `http://127.0.0.1:11436/v1` · model `qwen3.5-9b-q4_k_m`
- Manifest: `/home/sinorin/jupyter/Robo-guide_vlm_team_one/guide_robot_llm/eval_manifests/egopoint_15.jsonl` (sha256 2c0916d9e756…)
- Prompt variant: `P4`

> **Diagnostic only — no final project score, no #11 selection.**

## Perception

### Pointing

| metric | value |
|---|---|
| pointing evidence accuracy | 0.0 (n=8) |
| target in candidates (exact ID) | 1.0 (n=8) |
| top-2 recall | 0.625 (n=8) |
| box IoU not computed | 8 |

### Audience

_нет данных (нет судимых кейсов трека)_

## Policy

### Pointing

| metric | value |
|---|---|
| final-choice accuracy (decision phase, judged only) | 0.25 (n=4) |
| abstention rate (decision says "none") | 0.5 (n=8) |

### Tool

_нет данных (нет судимых кейсов трека)_

## Runner

| metric | value |
|---|---|
| parse failed | 0.4667 (n=15) |
| latency mean (ms) | 8069.135 (n=15) |
| latency p50 (ms) | 8652.468 |
| latency p95 (ms) | 9193.078 |

## Confidence intervals (session-grouped bootstrap)

Единица ресэмплинга -- сессия записи (`split_group_id`), не кейс: кейсы одной сессии коррелированы. 1000 ресэмплов, seed 0, групп 15, кейсов 15.

| metric | value | 95% CI | n |
|---|---|---|---|
| pass_rate | 0.2500 | [0.0000, 1.0000] | 4 |

## Slices

### By source

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| egopoint | 15 | 1 | 3 | 11 | 0.25 (n=4) | – |

### By split group

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| g-ep-real-3 | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |
| g-ep-real-8 | 1 | 0 | 0 | 1 | – | – |
| g-ep-real-13 | 1 | 0 | 1 | 0 | 0.0 (n=1) | – |
| g-ep-real-27 | 1 | 0 | 0 | 1 | – | – |
| g-ep-real-28 | 1 | 0 | 0 | 1 | – | – |
| g-ep-real-36 | 1 | 0 | 0 | 1 | – | – |
| g-ep-real-69 | 1 | 0 | 0 | 1 | – | – |
| g-ep-real-96 | 1 | 0 | 0 | 1 | – | – |
| g-ep-real-99 | 1 | 0 | 0 | 1 | – | – |
| g-ep-real-100 | 1 | 0 | 0 | 1 | – | – |
| g-ep-real-103 | 1 | 0 | 0 | 1 | – | – |
| g-ep-real-167 | 1 | 0 | 1 | 0 | 0.0 (n=1) | – |
| g-ep-real-405 | 1 | 0 | 0 | 1 | – | – |
| g-ep-real-1204 | 1 | 0 | 0 | 1 | – | – |
| g-ep-real-1270 | 1 | 0 | 1 | 0 | 0.0 (n=1) | – |

### Metadata: dimension

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| Basic Perception | 3 | 1 | 1 | 1 | 0.5 (n=2) | – |
| Affordance & Function | 3 | 0 | 0 | 3 | – | – |
| OCR & Text | 3 | 0 | 1 | 2 | 0.0 (n=1) | – |
| Context & Relation | 3 | 0 | 0 | 3 | – | – |
| Adversarial | 3 | 0 | 1 | 2 | 0.0 (n=1) | – |

### Metadata: deixis_level

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| L1 | 6 | 1 | 2 | 3 | 0.3333 (n=3) | – |
| L3 | 6 | 0 | 0 | 6 | – | – |
| L2 | 3 | 0 | 1 | 2 | 0.0 (n=1) | – |

### Metadata: n_distractors

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| 3 | 15 | 1 | 3 | 11 | 0.25 (n=4) | – |

### Metadata: answer_map

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| {'Garlic': 'epobj-3-a', 'Brussels Sprouts': 'epobj-3-b', 'Red Onion': 'epobj-3-c', 'Radish': 'epobj-3-d'} | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |
| {'To store cold beverages for drinking': 'epobj-8-a', 'To clean surfaces like a sponge': 'epobj-8-b', 'To hang clothes for drying': 'epobj-8-c', 'To provide warmth when filled with heated liquid': 'epobj-8-d'} | 1 | 0 | 0 | 1 | – | – |
| {'Ocean Blue': 'epobj-13-a', 'Red Star': 'epobj-13-b', 'Dream Blue': 'epobj-13-c', 'Golden Harvest': 'epobj-13-d'} | 1 | 0 | 1 | 0 | 0.0 (n=1) | – |
| {'Pork chop': 'epobj-27-a', 'Yellow broiler chicken': 'epobj-27-b', 'Silkie chicken': 'epobj-27-c', 'Duck breast': 'epobj-27-d'} | 1 | 0 | 0 | 1 | – | – |
| {'Below': 'epobj-28-a', 'To the right': 'epobj-28-b', 'Above': 'epobj-28-c', 'To the left': 'epobj-28-d'} | 1 | 0 | 0 | 1 | – | – |
| {'Attached to the side wall at eye level': 'epobj-36-a', 'Inside the room on a desk': 'epobj-36-b', 'Above the doorway': 'epobj-36-c', 'On the floor in front of the doorway': 'epobj-36-d'} | 1 | 0 | 0 | 1 | – | – |
| {'Stationery and office organization': 'epobj-69-a', 'Household cleaning and sanitation': 'epobj-69-b', 'Food and beverage consumption': 'epobj-69-c', 'Skincare or cosmetic application': 'epobj-69-d'} | 1 | 0 | 0 | 1 | – | – |
| {'Nike': 'epobj-96-a', 'Uniqlo': 'epobj-96-b', 'H&M': 'epobj-96-c', 'Adidas': 'epobj-96-d'} | 1 | 0 | 0 | 1 | – | – |
| {'An ingredient for a meal.': 'epobj-99-a', 'A single-serving snack bar.': 'epobj-99-b', 'A cleaning product.': 'epobj-99-c', 'A fresh noodle dish.': 'epobj-99-d'} | 1 | 0 | 0 | 1 | – | – |
| {'On the desk surface': 'epobj-100-a', 'On the shelf': 'epobj-100-b', 'Hanging from a cable': 'epobj-100-c', 'Mounted on the wall': 'epobj-100-d'} | 1 | 0 | 0 | 1 | – | – |
| {"Lay's": 'epobj-103-a', 'Orion': 'epobj-103-b', 'Pringles': 'epobj-103-c', 'Oishi': 'epobj-103-d'} | 1 | 0 | 0 | 1 | – | – |
| {'Red bean': 'epobj-167-a', 'Whole wheat': 'epobj-167-b', 'Milk': 'epobj-167-c', 'Chocolate chip': 'epobj-167-d'} | 1 | 0 | 1 | 0 | 0.0 (n=1) | – |
| {'Unknown': 'epobj-405-a', 'Yes': 'epobj-405-b', 'Maybe': 'epobj-405-c', 'No': 'epobj-405-d'} | 1 | 0 | 0 | 1 | – | – |
| {'It prints labels automatically': 'epobj-1204-a', 'It charges mobile devices': 'epobj-1204-b', 'It scans documents digitally': 'epobj-1204-c', 'It has no electronic functions': 'epobj-1204-d'} | 1 | 0 | 0 | 1 | – | – |
| {'No, it is a black metal shelf guard': 'epobj-1270-a', 'Yes, it is a yellow package of tissues': 'epobj-1270-b', 'No, it is a large plastic storage bin': 'epobj-1270-c', 'Yes, it is a blue package of wet wipes': 'epobj-1270-d'} | 1 | 0 | 1 | 0 | 0.0 (n=1) | – |

## Variants

### P4

| metric | value |
|---|---|
| cases | 15 (pass 1, fail 3, unjudged 11) |
| pass rate | 0.25 (n=4) |
| scene cases (recorded, not judged) | 0 |
| count MAE | – |
| exact count | – |
| within-1 count | – |
| engaged MAE | – |
| exact engaged | – |
| pointing top-2 | 0.625 (n=8) |
| pointing top-1 (freeform) | 0.25 (n=4) |
| calls per case | 1.5333 (n=15) |
| parse failed | 7 (rate 0.4667 (n=15)) |
| latency mean (ms) | 8069.135 (n=15) |
| latency p50 (ms) | 8652.468 |
| latency p95 (ms) | 9193.078 |

## Per-case

| case | source | track | mode | status | perception | policy | pass |
|---|---|---|---|---|---|---|---|
| EPO-REAL-0003 | egopoint | pointing | deployed | ok | evidence ✗, target ✓, top2 ✗, iou – (gold_box_null) | top1 ✓ | ✓ |
| EPO-REAL-0008 | egopoint | pointing | deployed | parse_failed | – | – | – |
| EPO-REAL-0013 | egopoint | pointing | deployed | ok | evidence ✗, target ✓, top2 ✓, iou – (gold_box_null) | top1 ✗ | ✗ |
| EPO-REAL-0027 | egopoint | pointing | deployed | parse_failed | – | – | – |
| EPO-REAL-0028 | egopoint | pointing | deployed | ok | evidence ✗, target ✓, top2 ✗, iou – (gold_box_null) | credit ✓, abstained | – |
| EPO-REAL-0036 | egopoint | pointing | deployed | parse_failed | – | – | – |
| EPO-REAL-0069 | egopoint | pointing | deployed | ok | evidence ✗, target ✓, top2 ✗, iou – (gold_box_null) | credit ✓, abstained | – |
| EPO-REAL-0096 | egopoint | pointing | deployed | ok | evidence ✗, target ✓, top2 ✓, iou – (gold_box_null) | credit ✓, abstained | – |
| EPO-REAL-0099 | egopoint | pointing | deployed | ok | evidence ✗, target ✓, top2 ✓, iou – (gold_box_null) | credit ✓, abstained | – |
| EPO-REAL-0100 | egopoint | pointing | deployed | parse_failed | – | – | – |
| EPO-REAL-0103 | egopoint | pointing | deployed | parse_failed | – | – | – |
| EPO-REAL-0167 | egopoint | pointing | deployed | ok | evidence ✗, target ✓, top2 ✓, iou – (gold_box_null) | top1 ✗ | ✗ |
| EPO-REAL-0405 | egopoint | pointing | deployed | parse_failed | – | – | – |
| EPO-REAL-1204 | egopoint | pointing | deployed | parse_failed | – | – | – |
| EPO-REAL-1270 | egopoint | pointing | deployed | ok | evidence ✗, target ✓, top2 ✓, iou – (gold_box_null) | top1 ✗ | ✗ |
