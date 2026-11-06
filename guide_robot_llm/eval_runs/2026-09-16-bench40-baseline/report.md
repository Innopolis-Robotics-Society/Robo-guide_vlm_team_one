# VLM eval diagnostic report — 2026-09-16-bench40-baseline

- Run: `eval_runs/2026-09-16-bench40-baseline`
- Generated: 2026-09-16T02:50:02+07:00
- Cases: 40 (ok 40, parse_failed 0, backend_error 0)
- Judged: 37 (pass 24, fail 13, unjudged 3)

> **Diagnostic only — no final project score, no #11 selection.**

## Run notes

- Состав прогона: 40 кейсов = EgoPoint-Bench (10, freeform, авторский MC-протокол) + AGHRI (15, Footpath) + pilot-CC (15: 3 POI, 3 SCN, 2 AUD, 7 TOL).
- DP/Deepoint slice: not acquired — 180 GB distribution exceeds local capacity (scope-решение 2026-09-15, пометка T10).
- YouRefIt slice: not acquired — registration pending (scope-решение 2026-09-15); 5 кейсов добавляются инкрементальным прогоном без перепрогона остальных.
- AGHRI: скачаны части 1–3 (declared counts 1–3); gold -- по-кадрово из 2D-боксов аннотаций (детерминированно), в слайсе полученное распределение counts 0–2; детали в `eval_data/aghri/PROVENANCE.md`.
- Бэкенд: локальный llama.cpp (Qwen3.8-27B-UD-IQ4_XS + mmproj, порт 11434), строгие GBNF-грамматики, temperature 0.2, ≤2 попытки. Сервер работает с `--reasoning on`: ответ приходит в `reasoning_content` при пустом `content` — бэкенд `llm_client` делает фолбэк на этот поток (под грамматикой он по определению валиден; regression-тест в `test_llm_client_backend.py`).
- Скоринг (2026-09-16): добавлен мост «буква опции → фраза» для freeform (вопросы EgoPoint требуют ответ буквой A–D; без моста 0/10 было структурным артефактом). Изменён только интерпретатор ответа; манифест и прогоны не менялись.

### Error slices → next steps (T11, 13 fail из 37 судимых)

1. **pilot-CC / TOL: «reply вместо tool» — 4 кейса** (TOL-CC-002 hold_position, -004 ask_visitor, -005 finish_answer, -006 search_content). Утверждение пользователя -- прямая команда, gold-tool в `allowed_tools`, модель отвечает прозой. → Не прогон данных: **#11 tool-surface** (усилить контракт «выбрать один из инструментов, reply -- последний резерв»; фью-шоты; перепрогон 6 TOL-кейсов -- ~2 мин).
2. **pilot-CC / TOL-CC-001: tool верный, args пустые** (start_tour без `tour_id`). Контекст прогона не несёт каталога туров. → **#11/брокер**: injecting списка доступных `tour_id` в deployed-промпт; данных не нужно.
3. **EgoPoint / MC: неверный вариант — 6/10** (OCR & Text 2, Basic Perception 2, Adversarial 2; deixis L2/L3; distractors=3 во всех). Настоящий capability-gap на эгоцентрическом распознавании объектов. → Ни один watchlist (Gaze4HRI/EGO-CH-Gaze/CrowdHuman) не покрывает эго-объектный MC: либо **расширить срез EgoPoint-Bench** (тот же бенч, тот же режим прав), либо отложить; док-слайс не покупать.
4. **pilot-CC / POI-CC-001: жест виден, `exhibit_candidates` пустой** (1/3). Кандидаты (cabinet-01/frame-02/poster-03) были в контексте; модель нашла бокс «синего объекта слева», но не связала жест с каталогом. → **Точечный local re-shoot**: указательные кейсы с кандидатным контекстом и визуально близкими distractor'ами в музейном масштабе (n=1, внешний док пока не нужен).
5. **pilot-CC / AUD-CC-002: count 3 при gold 2** (пересчёт фоновых фигур; bucket ≥2; AUD MAE 0.0588). → Watchlist: **EGO-CH-Gaze** (эгоцентрические кадры людей — близкий домен) как ближайший; **CrowdHuman** — только как стресс-тест плотных толп (outdoor-домен, fit слабый); **Gaze4HRI** не покрывает (лабория, один участник, геометрия взгляда, без audience-count).

AGHRI: 15/15 pass (count MAE 0.0) — срез простой (counts 0–2); 4–5-person кейсы не покрыты (части 7/10 не скачаны) — см. пометку состава.

## Perception

### Pointing

| metric | value |
|---|---|
| pointing evidence accuracy | 1.0 (n=3) |
| target in candidates (exact ID) | 0.6667 (n=3) |
| top-2 recall | 0.6667 (n=3) |
| pointing box IoU (mean) | 0.0138 (n=3) |

### Audience

| metric | value |
|---|---|
| people count MAE | 0.0588 (n=17) |
| exact-count accuracy | 0.9412 (n=17) |

## Policy

### Pointing

| metric | value |
|---|---|
| top-1 target (freeform answer) | 0.4 (n=10) |

### Tool

| metric | value |
|---|---|
| {tool, args} exact match | 0.1667 (n=6) |
| false positive (no-target) | 0.0 (n=1) |
| abstention credit (no-target) | 1.0 (n=1) |

## Slices

### By source

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| egopoint | 10 | 4 | 6 | 0 | 0.4 (n=10) | – |
| aghri | 15 | 15 | 0 | 0 | 1.0 (n=15) | 0.0 (n=15) |
| pilot-cc | 15 | 5 | 7 | 3 | 0.4167 (n=12) | 0.5 (n=2) |

### By split group

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| g-ep-real-13 | 1 | 0 | 1 | 0 | 0.0 (n=1) | – |
| g-ep-real-27 | 1 | 0 | 1 | 0 | 0.0 (n=1) | – |
| g-ep-real-36 | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |
| g-ep-real-69 | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |
| g-ep-real-99 | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |
| g-ep-real-100 | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |
| g-ep-real-103 | 1 | 0 | 1 | 0 | 0.0 (n=1) | – |
| g-ep-real-167 | 1 | 0 | 1 | 0 | 0.0 (n=1) | – |
| g-ep-real-405 | 1 | 0 | 1 | 0 | 0.0 (n=1) | – |
| g-ep-real-1270 | 1 | 0 | 1 | 0 | 0.0 (n=1) | – |
| g-aghri-seq-0001 | 3 | 3 | 0 | 0 | 1.0 (n=3) | 0.0 (n=3) |
| g-aghri-seq-0004 | 3 | 3 | 0 | 0 | 1.0 (n=3) | 0.0 (n=3) |
| g-aghri-seq-0005 | 3 | 3 | 0 | 0 | 1.0 (n=3) | 0.0 (n=3) |
| g-aghri-seq-0006 | 3 | 3 | 0 | 0 | 1.0 (n=3) | 0.0 (n=3) |
| g-aghri-seq-0007 | 3 | 3 | 0 | 0 | 1.0 (n=3) | 0.0 (n=3) |
| g-cc-POI-CC-001 | 1 | 0 | 1 | 0 | 0.0 (n=1) | – |
| g-cc-POI-CC-002 | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |
| g-cc-POI-CC-003 | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |
| g-cc-SCN-CC-001 | 1 | 0 | 0 | 1 | – | – |
| g-cc-SCN-CC-002 | 1 | 0 | 0 | 1 | – | – |
| g-cc-SCN-CC-003 | 1 | 0 | 0 | 1 | – | – |
| g-cc-AUD-CC-001 | 1 | 1 | 0 | 0 | 1.0 (n=1) | 0.0 (n=1) |
| g-cc-AUD-CC-002 | 1 | 0 | 1 | 0 | 0.0 (n=1) | 1.0 (n=1) |
| g-cc-TOL-NEUTRAL | 6 | 1 | 5 | 0 | 0.1667 (n=6) | – |
| g-cc-TOL-CC-007 | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |

### Metadata: dimension

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| OCR & Text | 2 | 0 | 2 | 0 | 0.0 (n=2) | – |
| Basic Perception | 2 | 0 | 2 | 0 | 0.0 (n=2) | – |
| Context & Relation | 2 | 2 | 0 | 0 | 1.0 (n=2) | – |
| Affordance & Function | 2 | 2 | 0 | 0 | 1.0 (n=2) | – |
| Adversarial | 2 | 0 | 2 | 0 | 0.0 (n=2) | – |

### Metadata: deixis_level

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| L1 | 2 | 0 | 2 | 0 | 0.0 (n=2) | – |
| L3 | 5 | 2 | 3 | 0 | 0.4 (n=5) | – |
| L2 | 3 | 2 | 1 | 0 | 0.6667 (n=3) | – |

### Metadata: n_distractors

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| 3 | 11 | 5 | 6 | 0 | 0.4545 (n=11) | – |
| 2 | 2 | 1 | 1 | 0 | 0.5 (n=2) | – |

### Metadata: answer_map

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| {'Ocean Blue': 'epobj-13-a', 'Red Star': 'epobj-13-b', 'Dream Blue': 'epobj-13-c', 'Golden Harvest': 'epobj-13-d'} | 1 | 0 | 1 | 0 | 0.0 (n=1) | – |
| {'Pork chop': 'epobj-27-a', 'Yellow broiler chicken': 'epobj-27-b', 'Silkie chicken': 'epobj-27-c', 'Duck breast': 'epobj-27-d'} | 1 | 0 | 1 | 0 | 0.0 (n=1) | – |
| {'Attached to the side wall at eye level': 'epobj-36-a', 'Inside the room on a desk': 'epobj-36-b', 'Above the doorway': 'epobj-36-c', 'On the floor in front of the doorway': 'epobj-36-d'} | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |
| {'Stationery and office organization': 'epobj-69-a', 'Household cleaning and sanitation': 'epobj-69-b', 'Food and beverage consumption': 'epobj-69-c', 'Skincare or cosmetic application': 'epobj-69-d'} | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |
| {'An ingredient for a meal.': 'epobj-99-a', 'A single-serving snack bar.': 'epobj-99-b', 'A cleaning product.': 'epobj-99-c', 'A fresh noodle dish.': 'epobj-99-d'} | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |
| {'On the desk surface': 'epobj-100-a', 'On the shelf': 'epobj-100-b', 'Hanging from a cable': 'epobj-100-c', 'Mounted on the wall': 'epobj-100-d'} | 1 | 1 | 0 | 0 | 1.0 (n=1) | – |
| {"Lay's": 'epobj-103-a', 'Orion': 'epobj-103-b', 'Pringles': 'epobj-103-c', 'Oishi': 'epobj-103-d'} | 1 | 0 | 1 | 0 | 0.0 (n=1) | – |
| {'Red bean': 'epobj-167-a', 'Whole wheat': 'epobj-167-b', 'Milk': 'epobj-167-c', 'Chocolate chip': 'epobj-167-d'} | 1 | 0 | 1 | 0 | 0.0 (n=1) | – |
| {'Unknown': 'epobj-405-a', 'Yes': 'epobj-405-b', 'Maybe': 'epobj-405-c', 'No': 'epobj-405-d'} | 1 | 0 | 1 | 0 | 0.0 (n=1) | – |
| {'No, it is a black metal shelf guard': 'epobj-1270-a', 'Yes, it is a yellow package of tissues': 'epobj-1270-b', 'No, it is a large plastic storage bin': 'epobj-1270-c', 'Yes, it is a blue package of wet wipes': 'epobj-1270-d'} | 1 | 0 | 1 | 0 | 0.0 (n=1) | – |

### Metadata: count_bucket

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| 2 | 5 | 4 | 1 | 0 | 0.8 (n=5) | 0.2 (n=5) |
| 1 | 9 | 9 | 0 | 0 | 1.0 (n=9) | 0.0 (n=9) |
| 0 | 3 | 3 | 0 | 0 | 1.0 (n=3) | 0.0 (n=3) |

### Metadata: declared_count

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| 2 | 3 | 3 | 0 | 0 | 1.0 (n=3) | 0.0 (n=3) |
| 3 | 3 | 3 | 0 | 0 | 1.0 (n=3) | 0.0 (n=3) |
| 1 | 9 | 9 | 0 | 0 | 1.0 (n=9) | 0.0 (n=9) |

### Metadata: environment

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| Footpath | 15 | 15 | 0 | 0 | 1.0 (n=15) | 0.0 (n=15) |

### Metadata: robot_state

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| still | 9 | 9 | 0 | 0 | 1.0 (n=9) | 0.0 (n=9) |
| move | 6 | 6 | 0 | 0 | 1.0 (n=6) | 0.0 (n=6) |

### Metadata: split

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| unknown | 15 | 15 | 0 | 0 | 1.0 (n=15) | 0.0 (n=15) |

### Metadata: venue

| group | n | pass | fail | unjudged | pass rate | count MAE |
|---|---|---|---|---|---|---|
| synthetic (PIL, deterministic spec, seed 20260914) | 15 | 5 | 7 | 3 | 0.4167 (n=12) | 0.5 (n=2) |

## Variants

### (no variant)

| metric | value |
|---|---|
| cases | 40 (pass 24, fail 13, unjudged 3) |
| pass rate | 0.6486 (n=37) |
| scene cases (recorded, not judged) | 3 |
| count MAE | 0.0588 (n=17) |
| exact count | 0.9412 (n=17) |
| engaged MAE | – |
| exact engaged | – |
| pointing top-2 | 0.6667 (n=3) |
| pointing top-1 (freeform) | 0.4 (n=10) |
| calls per case | 1.175 (n=40) |
| latency (ms) | 13519.073 (n=40) |

## Per-case

| case | source | track | mode | status | perception | policy | pass |
|---|---|---|---|---|---|---|---|
| EPO-REAL-0013 | egopoint | pointing | freeform | ok | – | top1 ✗, mapped epobj-13-c | ✗ |
| EPO-REAL-0027 | egopoint | pointing | freeform | ok | – | top1 ✗, mapped epobj-27-b | ✗ |
| EPO-REAL-0036 | egopoint | pointing | freeform | ok | – | top1 ✓, mapped epobj-36-c | ✓ |
| EPO-REAL-0069 | egopoint | pointing | freeform | ok | – | top1 ✓, mapped epobj-69-d | ✓ |
| EPO-REAL-0099 | egopoint | pointing | freeform | ok | – | top1 ✓, mapped epobj-99-a | ✓ |
| EPO-REAL-0100 | egopoint | pointing | freeform | ok | – | top1 ✓, mapped epobj-100-a | ✓ |
| EPO-REAL-0103 | egopoint | pointing | freeform | ok | – | top1 ✗, mapped epobj-103-a | ✗ |
| EPO-REAL-0167 | egopoint | pointing | freeform | ok | – | top1 ✗, mapped epobj-167-b | ✗ |
| EPO-REAL-0405 | egopoint | pointing | freeform | ok | – | top1 ✗, mapped epobj-405-b | ✗ |
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
| POI-CC-001 | pilot-cc | pointing | deployed | ok | evidence ✓, target ✗, top2 ✗, iou 0.0 | – | ✗ |
| POI-CC-002 | pilot-cc | pointing | deployed | ok | evidence ✓, target ✓, top2 ✓, iou 0.0017 | – | ✓ |
| POI-CC-003 | pilot-cc | pointing | deployed | ok | evidence ✓, target ✓, top2 ✓, iou 0.0397 | – | ✓ |
| SCN-CC-001 | pilot-cc | scene | deployed | ok | – | – | – |
| SCN-CC-002 | pilot-cc | scene | deployed | ok | – | – | – |
| SCN-CC-003 | pilot-cc | scene | deployed | ok | – | – | – |
| AUD-CC-001 | pilot-cc | audience | deployed | ok | count 2/2 | – | ✓ |
| AUD-CC-002 | pilot-cc | audience | deployed | ok | count 3/2 | – | ✗ |
| TOL-CC-001 | pilot-cc | tool | deployed | ok | – | start_tour ✗ | ✗ |
| TOL-CC-002 | pilot-cc | tool | deployed | ok | – | reply ✗ | ✗ |
| TOL-CC-003 | pilot-cc | tool | deployed | ok | – | pause ✓ | ✓ |
| TOL-CC-004 | pilot-cc | tool | deployed | ok | – | reply ✗ | ✗ |
| TOL-CC-005 | pilot-cc | tool | deployed | ok | – | reply ✗ | ✗ |
| TOL-CC-006 | pilot-cc | tool | deployed | ok | – | reply ✗ | ✗ |
| TOL-CC-007 | pilot-cc | tool | deployed | ok | – | fp ✗, credit ✓ | ✓ |
