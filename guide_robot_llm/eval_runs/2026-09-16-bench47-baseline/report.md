# VLM eval diagnostic report — 2026-09-16-bench47-baseline

- Run: `eval_runs/2026-09-16-bench47-baseline`
- Generated: 2026-09-16T00:31:26+00:00
- Cases: 47 (ok 47, parse_failed 0, backend_error 0)
- Judged: 47 (pass 34, fail 13, unjudged 0)
> **Diagnostic only — no final project score, no #11 selection.**

## Perception

### Pointing

_нет данных (нет судимых кейсов трека)_

### Audience

| metric | value |
|---|---|
| people count MAE | 0.0 (n=25) |
| exact-count accuracy | 1.0 (n=25) |

## Policy

### Pointing

| metric | value |
|---|---|
| top-1 target (freeform answer) | 0.5333 (n=15) |

### Tool

| metric | value |
|---|---|
| {tool, args} exact match | 0.1667 (n=6) |
| false positive (no-target) | 1.0 (n=1) |
| abstention credit (no-target) | 0.0 (n=1) |

## Confidence intervals (session-grouped bootstrap)

Единица ресэмплинга -- сессия записи (`split_group_id`), не кейс: кейсы одной сессии коррелированы. 1000 ресэмплов, seed 0, групп 26, кейсов 47.

| metric | value | 95% CI | n |
|---|---|---|---|
| counts: mae | 0.0000 | [0.0000, 0.0000] | 25 |
| counts: exact_accuracy | 1.0000 | [1.0000, 1.0000] | 25 |
| policy: pointing_top1_accuracy | 0.5333 | [0.2667, 0.7778] | 15 |
| policy: tool_exact_match_accuracy | 0.1667 | [0.1667, 0.1667] | 6 |
| policy: no_target_false_positive_rate | 1.0000 | [1.0000, 1.0000] | 1 |
| pass_rate | 0.7234 | [0.5283, 0.8913] | 47 |

## Slices

### By source

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| egopoint | 15 | 8 | 7 | 0 | 0.5333 (n=15) | – |
| aghri | 25 | 25 | 0 | 0 | 1.0 (n=25) | 0.0 (n=25) |
| pilot-cc | 7 | 1 | 6 | 0 | 0.1429 (n=7) | – |

### By split group

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| g-ep-real-3 | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |
| g-ep-real-8 | 1 | 0 | 1 | 0 | 0.0 (n=1) | – |
| g-ep-real-13 | 1 | 0 | 1 | 0 | 0.0 (n=1) | – |
| g-ep-real-27 | 1 | 0 | 1 | 0 | 0.0 (n=1) | – |
| g-ep-real-28 | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |
| g-ep-real-36 | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |
| g-ep-real-69 | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |
| g-ep-real-96 | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |
| g-ep-real-99 | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |
| g-ep-real-100 | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |
| g-ep-real-103 | 1 | 0 | 1 | 0 | 0.0 (n=1) | – |
| g-ep-real-167 | 1 | 0 | 1 | 0 | 0.0 (n=1) | – |
| g-ep-real-405 | 1 | 0 | 1 | 0 | 0.0 (n=1) | – |
| g-ep-real-1204 | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |
| g-ep-real-1270 | 1 | 0 | 1 | 0 | 0.0 (n=1) | – |
| g-aghri-seq-0001 | 3 | 3 | 0 | 0 | 1.0 (n=3) | 0.0 (n=3) |
| g-aghri-seq-0004 | 3 | 3 | 0 | 0 | 1.0 (n=3) | 0.0 (n=3) |
| g-aghri-seq-0005 | 3 | 3 | 0 | 0 | 1.0 (n=3) | 0.0 (n=3) |
| g-aghri-seq-0006 | 3 | 3 | 0 | 0 | 1.0 (n=3) | 0.0 (n=3) |
| g-aghri-seq-0007 | 3 | 3 | 0 | 0 | 1.0 (n=3) | 0.0 (n=3) |
| g-aghri-seq-0008 | 3 | 3 | 0 | 0 | 1.0 (n=3) | 0.0 (n=3) |
| g-aghri-seq-0009 | 3 | 3 | 0 | 0 | 1.0 (n=3) | 0.0 (n=3) |
| g-aghri-seq-0010 | 3 | 3 | 0 | 0 | 1.0 (n=3) | 0.0 (n=3) |
| g-aghri-seq-0011 | 1 | 1 | 0 | 0 | 1.0 (n=1) | 0.0 (n=1) |
| g-cc-TOL-NEUTRAL | 6 | 1 | 5 | 0 | 0.1667 (n=6) | – |
| g-cc-TOL-CC-007 | 1 | 0 | 1 | 0 | 0.0 (n=1) | – |

### Metadata: dimension

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| Basic Perception | 3 | 1 | 2 | 0 | 0.3333 (n=3) | – |
| Affordance & Function | 3 | 2 | 1 | 0 | 0.6667 (n=3) | – |
| OCR & Text | 3 | 1 | 2 | 0 | 0.3333 (n=3) | – |
| Context & Relation | 3 | 3 | 0 | 0 | 1.0 (n=3) | – |
| Adversarial | 3 | 1 | 2 | 0 | 0.3333 (n=3) | – |

### Metadata: deixis_level

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| L1 | 6 | 3 | 3 | 0 | 0.5 (n=6) | – |
| L3 | 6 | 3 | 3 | 0 | 0.5 (n=6) | – |
| L2 | 3 | 2 | 1 | 0 | 0.6667 (n=3) | – |

### Metadata: n_distractors

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| 3 | 15 | 8 | 7 | 0 | 0.5333 (n=15) | – |

### Metadata: answer_map

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| {'Garlic': 'epobj-3-a', 'Brussels Sprouts': 'epobj-3-b', 'Red Onion': 'epobj-3-c', 'Radish': 'epobj-3-d'} | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |
| {'To store cold beverages for drinking': 'epobj-8-a', 'To clean surfaces like a sponge': 'epobj-8-b', 'To hang clothes for drying': 'epobj-8-c', 'To provide warmth when filled with heated liquid': 'epobj-8-d'} | 1 | 0 | 1 | 0 | 0.0 (n=1) | – |
| {'Ocean Blue': 'epobj-13-a', 'Red Star': 'epobj-13-b', 'Dream Blue': 'epobj-13-c', 'Golden Harvest': 'epobj-13-d'} | 1 | 0 | 1 | 0 | 0.0 (n=1) | – |
| {'Pork chop': 'epobj-27-a', 'Yellow broiler chicken': 'epobj-27-b', 'Silkie chicken': 'epobj-27-c', 'Duck breast': 'epobj-27-d'} | 1 | 0 | 1 | 0 | 0.0 (n=1) | – |
| {'Below': 'epobj-28-a', 'To the right': 'epobj-28-b', 'Above': 'epobj-28-c', 'To the left': 'epobj-28-d'} | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |
| {'Attached to the side wall at eye level': 'epobj-36-a', 'Inside the room on a desk': 'epobj-36-b', 'Above the doorway': 'epobj-36-c', 'On the floor in front of the doorway': 'epobj-36-d'} | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |
| {'Stationery and office organization': 'epobj-69-a', 'Household cleaning and sanitation': 'epobj-69-b', 'Food and beverage consumption': 'epobj-69-c', 'Skincare or cosmetic application': 'epobj-69-d'} | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |
| {'Nike': 'epobj-96-a', 'Uniqlo': 'epobj-96-b', 'H&M': 'epobj-96-c', 'Adidas': 'epobj-96-d'} | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |
| {'An ingredient for a meal.': 'epobj-99-a', 'A single-serving snack bar.': 'epobj-99-b', 'A cleaning product.': 'epobj-99-c', 'A fresh noodle dish.': 'epobj-99-d'} | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |
| {'On the desk surface': 'epobj-100-a', 'On the shelf': 'epobj-100-b', 'Hanging from a cable': 'epobj-100-c', 'Mounted on the wall': 'epobj-100-d'} | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |
| {"Lay's": 'epobj-103-a', 'Orion': 'epobj-103-b', 'Pringles': 'epobj-103-c', 'Oishi': 'epobj-103-d'} | 1 | 0 | 1 | 0 | 0.0 (n=1) | – |
| {'Red bean': 'epobj-167-a', 'Whole wheat': 'epobj-167-b', 'Milk': 'epobj-167-c', 'Chocolate chip': 'epobj-167-d'} | 1 | 0 | 1 | 0 | 0.0 (n=1) | – |
| {'Unknown': 'epobj-405-a', 'Yes': 'epobj-405-b', 'Maybe': 'epobj-405-c', 'No': 'epobj-405-d'} | 1 | 0 | 1 | 0 | 0.0 (n=1) | – |
| {'It prints labels automatically': 'epobj-1204-a', 'It charges mobile devices': 'epobj-1204-b', 'It scans documents digitally': 'epobj-1204-c', 'It has no electronic functions': 'epobj-1204-d'} | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |
| {'No, it is a black metal shelf guard': 'epobj-1270-a', 'Yes, it is a yellow package of tissues': 'epobj-1270-b', 'No, it is a large plastic storage bin': 'epobj-1270-c', 'Yes, it is a blue package of wet wipes': 'epobj-1270-d'} | 1 | 0 | 1 | 0 | 0.0 (n=1) | – |

### Metadata: count_bucket

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| 2 | 3 | 3 | 0 | 0 | 1.0 (n=3) | 0.0 (n=3) |
| 1 | 13 | 13 | 0 | 0 | 1.0 (n=13) | 0.0 (n=13) |
| 0 | 9 | 9 | 0 | 0 | 1.0 (n=9) | 0.0 (n=9) |

### Metadata: declared_count

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| 2 | 3 | 3 | 0 | 0 | 1.0 (n=3) | 0.0 (n=3) |
| 3 | 3 | 3 | 0 | 0 | 1.0 (n=3) | 0.0 (n=3) |
| 1 | 19 | 19 | 0 | 0 | 1.0 (n=19) | 0.0 (n=19) |

### Metadata: environment

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| Footpath | 25 | 25 | 0 | 0 | 1.0 (n=25) | 0.0 (n=25) |

### Metadata: robot_state

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| still | 12 | 12 | 0 | 0 | 1.0 (n=12) | 0.0 (n=12) |
| move | 13 | 13 | 0 | 0 | 1.0 (n=13) | 0.0 (n=13) |

### Metadata: split

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| unknown | 25 | 25 | 0 | 0 | 1.0 (n=25) | 0.0 (n=25) |

### Metadata: venue

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| synthetic (PIL, deterministic spec, seed 20260914) | 7 | 1 | 6 | 0 | 0.1429 (n=7) | – |

## Variants

### (no variant)

| metric | value |
|---|---|
| cases | 47 (pass 34, fail 13, unjudged 0) |
| pass rate | 0.7234 (n=47) |
| scene cases (recorded, not judged) | 0 |
| count MAE | 0.0 (n=25) |
| exact count | 1.0 (n=25) |
| engaged MAE | – |
| exact engaged | – |
| pointing top-2 | – |
| pointing top-1 (freeform) | 0.5333 (n=15) |
| calls per case | 1.1489 (n=47) |
| latency (ms) | 11170.5531 (n=47) |

## Per-case

| case | source | track | mode | status | perception | policy | pass |
|---|---|---|---|---|---|---|---|
| EPO-REAL-0003 | egopoint | pointing | freeform | ok | – | top1 ✓, mapped epobj-3-c | ✓ |
| EPO-REAL-0008 | egopoint | pointing | freeform | ok | – | top1 ✗, mapped epobj-8-c | ✗ |
| EPO-REAL-0013 | egopoint | pointing | freeform | ok | – | top1 ✗, mapped epobj-13-c | ✗ |
| EPO-REAL-0027 | egopoint | pointing | freeform | ok | – | top1 ✗, mapped epobj-27-b | ✗ |
| EPO-REAL-0028 | egopoint | pointing | freeform | ok | – | top1 ✓, mapped epobj-28-c | ✓ |
| EPO-REAL-0036 | egopoint | pointing | freeform | ok | – | top1 ✓, mapped epobj-36-c | ✓ |
| EPO-REAL-0069 | egopoint | pointing | freeform | ok | – | top1 ✓, mapped epobj-69-d | ✓ |
| EPO-REAL-0096 | egopoint | pointing | freeform | ok | – | top1 ✓, mapped epobj-96-b | ✓ |
| EPO-REAL-0099 | egopoint | pointing | freeform | ok | – | top1 ✓, mapped epobj-99-a | ✓ |
| EPO-REAL-0100 | egopoint | pointing | freeform | ok | – | top1 ✓, mapped epobj-100-a | ✓ |
| EPO-REAL-0103 | egopoint | pointing | freeform | ok | – | top1 ✗, mapped epobj-103-a | ✗ |
| EPO-REAL-0167 | egopoint | pointing | freeform | ok | – | top1 ✗, mapped epobj-167-b | ✗ |
| EPO-REAL-0405 | egopoint | pointing | freeform | ok | – | top1 ✗, mapped epobj-405-b | ✗ |
| EPO-REAL-1204 | egopoint | pointing | freeform | ok | – | top1 ✓, mapped epobj-1204-d | ✓ |
| EPO-REAL-1270 | egopoint | pointing | freeform | ok | – | top1 ✗, mapped epobj-1270-d | ✗ |
| AGHRI-SEQ-0001-F001 | aghri | audience | deployed | ok | count 2/2 | – | ✓ |
| AGHRI-SEQ-0001-F040 | aghri | audience | deployed | ok | count 2/2 | – | ✓ |
| AGHRI-SEQ-0001-F079 | aghri | audience | deployed | ok | count 1/1 | – | ✓ |
| AGHRI-SEQ-0004-F001 | aghri | audience | deployed | ok | count 0/0 | – | ✓ |
| AGHRI-SEQ-0004-F130 | aghri | audience | deployed | ok | count 2/2 | – | ✓ |
| AGHRI-SEQ-0004-F260 | aghri | audience | deployed | ok | count 1/1 | – | ✓ |
| AGHRI-SEQ-0005-F001 | aghri | audience | deployed | ok | count 0/0 | – | ✓ |
| AGHRI-SEQ-0005-F125 | aghri | audience | deployed | ok | count 1/1 | – | ✓ |
| AGHRI-SEQ-0005-F249 | aghri | audience | deployed | ok | count 0/0 | – | ✓ |
| AGHRI-SEQ-0006-F001 | aghri | audience | deployed | ok | count 1/1 | – | ✓ |
| AGHRI-SEQ-0006-F158 | aghri | audience | deployed | ok | count 1/1 | – | ✓ |
| AGHRI-SEQ-0006-F316 | aghri | audience | deployed | ok | count 1/1 | – | ✓ |
| AGHRI-SEQ-0007-F001 | aghri | audience | deployed | ok | count 1/1 | – | ✓ |
| AGHRI-SEQ-0007-F131 | aghri | audience | deployed | ok | count 1/1 | – | ✓ |
| AGHRI-SEQ-0007-F262 | aghri | audience | deployed | ok | count 1/1 | – | ✓ |
| AGHRI-SEQ-0008-F001 | aghri | audience | deployed | ok | count 0/0 | – | ✓ |
| AGHRI-SEQ-0008-F122 | aghri | audience | deployed | ok | count 1/1 | – | ✓ |
| AGHRI-SEQ-0008-F243 | aghri | audience | deployed | ok | count 0/0 | – | ✓ |
| AGHRI-SEQ-0009-F001 | aghri | audience | deployed | ok | count 0/0 | – | ✓ |
| AGHRI-SEQ-0009-F124 | aghri | audience | deployed | ok | count 0/0 | – | ✓ |
| AGHRI-SEQ-0009-F248 | aghri | audience | deployed | ok | count 1/1 | – | ✓ |
| AGHRI-SEQ-0010-F001 | aghri | audience | deployed | ok | count 1/1 | – | ✓ |
| AGHRI-SEQ-0010-F061 | aghri | audience | deployed | ok | count 1/1 | – | ✓ |
| AGHRI-SEQ-0010-F121 | aghri | audience | deployed | ok | count 0/0 | – | ✓ |
| AGHRI-SEQ-0011-F001 | aghri | audience | deployed | ok | count 0/0 | – | ✓ |
| TOL-CC-001 | pilot-cc | tool | deployed | ok | – | start_tour ✗ | ✗ |
| TOL-CC-002 | pilot-cc | tool | deployed | ok | – | reply ✗ | ✗ |
| TOL-CC-003 | pilot-cc | tool | deployed | ok | – | pause ✓ | ✓ |
| TOL-CC-004 | pilot-cc | tool | deployed | ok | – | reply ✗ | ✗ |
| TOL-CC-005 | pilot-cc | tool | deployed | ok | – | reply ✗ | ✗ |
| TOL-CC-006 | pilot-cc | tool | deployed | ok | – | reply ✗ | ✗ |
| TOL-CC-007 | pilot-cc | tool | deployed | ok | – | fp ✓, credit ✗ | ✗ |
