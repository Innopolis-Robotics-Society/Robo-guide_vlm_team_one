# Промпт-варианты для сравнения (Taiga #16)

Замороженные тексты системных промпт-вариантов и манифест
[`prompt_variants.json`](../prompt_variants.json). Итог: **18 вариантов =
3 навыка × 6** (нулевая, техника, production-базлиния):

| id   | навык                | ось            | execution  |
|------|----------------------|----------------|------------|
| D0   | describe_scene       | baseline       | single     |
| D1   | describe_scene       | observational  | single     |
| D2   | describe_scene       | cot            | cot_2pass  |
| D3   | describe_scene       | self_correct   | single     |
| D4   | describe_scene       | few_shot       | single     |
| D_base | describe_scene     | production     | single     |
| P0   | resolve_pointing     | baseline       | single     |
| P1   | resolve_pointing     | evidence       | single     |
| P2   | resolve_pointing     | cot            | cot_2pass  |
| P3   | resolve_pointing     | loop           | loop       |
| P4   | resolve_pointing     | few_shot       | single     |
| P_base | resolve_pointing   | production     | single     |
| A0   | audience_engagement  | baseline       | single     |
| A1   | audience_engagement  | criteria       | single     |
| A2   | audience_engagement  | cot            | cot_2pass  |
| A3   | audience_engagement  | loop           | loop       |
| A4   | audience_engagement  | few_shot       | single     |
| A_base | audience_engagement| production     | single     |

Тексты — чистые промпты (русс. яз.), без заголовков и разметки. Манифест —
единственный источник связи «вариант → файл → execution → примеры».

## `*_base` — production-базлинии (заморожены)

`D_base`/`P_base`/`A_base` — снимки встроенных инструкций
`guide_robot_llm/eval/runner.py` (`_OBSERVATION_INSTRUCTION`,
`_FREEFORM_INSTRUCTION`) от 2026-09-15. В манифесте `text: null`: раннер
использует встроенные инструкции (снимок в файлах — только референс для
человека).

## Few-shot примеры (D4/P4/A4)

Примеры — **синтетические CC-сцены** `EX-CC-*` (1600×900, PIL, детерминированная
спецификация, seed 20260914), сгенерированы `pilot/tools/cc_scene_gen.py`
(`EXAMPLE_SCENES`):

- `EX-CC-D-01` — светлая комната (1 человек, шкаф, картина); `EX-CC-D-02` —
  тёмная пустая комната (эталон: «кадры не разобрать»);
- `EX-CC-P-01` — явное указание на глобус (единственный кандидат);
  `EX-CC-P-02` — жест между двумя похожими вазами (эталон: воздержаться);
  `EX-CC-P-03` — жест в пустую стену (кандидатов нет);
- `EX-CC-A-01` — толпа 4 чел., 3 смотрят; `EX-CC-A-02` — 3 чел., 0 смотрят;
  `EX-CC-A-03` — 2 чел., 1 смотрит.

GT: `pilot/fixtures/cc/EX-CC-*.json`; проверка пикселей —
`pilot/tools/verify_cc_pixels.py` (захватывает все `pilot/fixtures/cc/*.json`).

**Почему синтетика, а не кропы DP/EgoPoint (отклонение от F5):** на хосте
единственные EgoPoint-медиа — 10 изображений `test_img/*.jpg`, и **все 10 уже
входят в eval-набор** `egopoint_10.jsonl` → любое их использование в few-shot
примерах = прямая утечка; данные DP на хосте не загружены (адаптер read-only,
медиа не в репозитории). Синтетика закрывает то же: явные/неоднозначные/пустые
ситуации + честные эталонные ответы, включая два контрпримера «воздержись».

**Лицензия примеров:** self-generated synthetic (PIL, deterministic spec,
seed 20260914); no real persons; no redistribution. Утечка исключена
программно: тест `test/test_prompt_variants.py` проверяет, что ни одно
EX-медиа не входит ни в один eval-манифест.

## Как потребляется

- P4 (раннер): `prompt_examples` — пары (медиа, ответ) вставляются в системный
  промпт до инструкции варианта; `examples[]` из манифеста.
- P7 (сравнение): таблица 18 × N-кейсов по трекам, метрики из скоринга
  runner'а.

## Цитаты техник (поле `source` в манифесте)

- CoT — Kojima et al., 2022, arXiv:2205.11916;
  счёт/перечисление — Hou, Zorzi, Testolin, 2025, arXiv:2512.04727
  (Sequential Enumeration).
- Self-ask self-correction — Dhuliawala et al., 2023, arXiv:2309.11495.
- Few-shot prompting — Brown et al., 2020, arXiv:2005.14165.
- ReAct — Yao et al., 2023, arXiv:2201.11903.
- (Варианты V0/V1/baseline/production — авторские, `source: null`.)
