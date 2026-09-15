"""EgoPoint-Bench → единая схема кейса (Taiga #10, T7).

Данные: HF-датасет ``GUYYYUG/EgoPoint``, дерево ``realdata_benchmark/``
(``pure_real_test.json`` — 1162 строки, одна строка на изображение;
``test_img/*.jpg``, ~390 МБ).

GO-гейт T1 (2026-09-15, ``docs/vlm_deixis_audience_datasets.md``,
раздел «License verification»): HF-лицензия не заявлена, GO только для
немодифицированного использования в личных исследовательских целях —
NO-GO для адаптации и перераспространения. Отсюда:

* только 10 real-world кейсов — симуляционное подмножество
  (``simdata_benchmark/``) не читается никогда;
* авторский QA-протокол дословно (``eval_code/eval_real_qwen3vl.py`` в
  GitHub-репозитории, Apache-2.0) — промпт не переписывается;
* только строки ``Multiple_Choice``: только у них замкнутый набор
  опций, который становится кандидатной таблицей id; ``True_False`` и
  ``Open_Ended`` не имеют замкнутого набора кандидатов в авторском
  протоколе;
* сборка кейсов read-only относительно данных: никаких производных
  изображений, данные не изменяются; по контракту дизайна CLI
  дополнительно пишет `PROVENANCE.md` в корень данных (как DP-адаптер);
* встроенные в файл baseline-выводы авторов (``model_output``,
  ``is_correct`` и т.п.) не читаются и модели под тест не передаются.

Агент не скачивает датасет — точная команда загрузки приведена в
``provenance_text()`` (пишется в ``eval_data/egopoint/PROVENANCE.md``
рядом с манифестом) и выполняется пользователем.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from guide_robot_llm.eval.schema import Case, case_from_dict, case_to_dict

SOURCE = "egopoint"

# Лицензия: строка из верификации T1 (2026-09-15) — см.
# docs/vlm_deixis_audience_datasets.md, раздел «License verification».
LICENSE_LINE = (
    "HF license undeclared — GO 2026-09-15 (T1): unmodified private "
    "research use only; NO-GO for adaptation/redistribution"
)
RIGHTS_NOTE = (
    "no redistribution, no derivative images; adapter read-only on " "data dir (T1, 2026-09-15)"
)

# Файл бенчмарка, проверенный при верификации T1. HF-копия и копия из
# GitHub-репозитория (Apache-2.0) совпадают по sha256 — проверено
# 2026-09-15. Адаптер требует совпадения: файл, отличающийся от
# верифицированного, сборку останавливает.
BENCH_REL_PATH = "realdata_benchmark/pure_real_test.json"
BENCH_SHA256_EXPECTED = "3cc3b6aa4e68621764624c76a3b1ed5a9e03ab8a8cd166c847c4b6b110db9e3b"

DEFAULT_N_CASES = 10
DEFAULT_MEDIA_PREFIX = "eval_data/egopoint/realdata_benchmark"

# 10 фиксированных страт (dimension, deixis_level): по 2 на каждый из
# пяти основных размеров; L3 — уровень неявного deixis'а, ядро
# бенчмарка — представлен чаще (5 из 10). В страте выбирается строка с
# минимальным image_id (детерминировано).
STRATA: tuple[tuple[str, str], ...] = (
    ("Context & Relation", "L3"),
    ("Affordance & Function", "L3"),
    ("Basic Perception", "L3"),
    ("OCR & Text", "L3"),
    ("Adversarial", "L3"),
    ("Context & Relation", "L2"),
    ("Affordance & Function", "L2"),
    ("Basic Perception", "L2"),
    ("Adversarial", "L1"),
    ("OCR & Text", "L1"),
)

# Строки с таким значением поля `dataset` считаются real-world.
# `None` допустимо: 91 строка верифицированного файла не содержат поле.
_REAL_DATASET_VALUES = (None, "realdata")


class EgoPointAdapterError(RuntimeError):
    """Ошибка адаптера EgoPoint-Bench (формат, гейт, целостность)."""


def author_prompt(entry: dict[str, Any]) -> str:
    """Авторский промпт MC-строки — дословно из eval_code/eval_real_qwen3vl.py."""
    options_str = "\n".join(entry["options"])
    return (
        f"{entry['question']}\n{options_str}\n"
        "Answer directly using the letters of the options given."
    )


def _candidate_id(image_id: str, letter: str) -> str:
    """Id кандидата: ``epobj-<image_id>-<буква опции>`` (lowercase)."""
    return f"epobj-{image_id}-{letter.lower()}"


def _option_label(option: str) -> str:
    """Текст опции без буквеного префикса ('A. Milk' → 'Milk')."""
    return option.split(". ", 1)[1]


def _validate_row(entry: dict[str, Any]) -> None:
    """Строгая проверка MC-строки (формат, верифицированный 2026-09-15)."""
    image_id = str(entry["image_id"])
    if entry.get("dataset") not in _REAL_DATASET_VALUES:
        raise EgoPointAdapterError(
            f"EPO-REAL-{int(image_id):04d}: dataset="
            f"{entry.get('dataset')!r} — не real-world данные; "
            "симуляционный набор не используется (гейт T1)"
        )
    options = entry.get("options")
    if not isinstance(options, list) or len(options) != 4:
        raise EgoPointAdapterError(
            f"EPO-REAL-{int(image_id):04d}: ожидается ровно 4 опции, " f"получено {options!r}"
        )
    for option, letter in zip(options, "ABCD", strict=True):
        if not (isinstance(option, str) and option.startswith(f"{letter}. ")):
            raise EgoPointAdapterError(
                f"EPO-REAL-{int(image_id):04d}: опция {option!r} не "
                f"соответствует шаблону '{letter}. <текст>'"
            )
    answer = str(entry.get("answer", ""))
    if not answer[:2] or answer[1] != ".":
        raise EgoPointAdapterError(
            f"EPO-REAL-{int(image_id):04d}: ответ {answer!r} не в " "формате '<буква>. <текст>'"
        )
    if answer[0] not in "ABCD":
        raise EgoPointAdapterError(
            f"EPO-REAL-{int(image_id):04d}: буква ответа " f"{answer[0]!r} вне диапазона A-D"
        )
    if entry.get("image_path") != f"test_img/{image_id}.jpg":
        raise EgoPointAdapterError(
            f"EPO-REAL-{int(image_id):04d}: image_path="
            f"{entry.get('image_path')!r} не соответствует "
            f"'test_img/{image_id}.jpg'"
        )


def select_mc_rows(
    rows: list[dict[str, Any]], n_cases: int = DEFAULT_N_CASES
) -> list[dict[str, Any]]:
    """Детерминированный выбор: по одной MC-строке на страту.

    Страты — ``STRATA[:n_cases]`` (dimension, deixis_level); в страте —
    строка с минимальным ``image_id``. Строки ``True_False``/
    ``Open_Ended`` отбрасываются (нет замкнутого набора кандидатов в
    авторском протоколе). Нарушение формата или появление не-real строк
    — ошибка, а не тихий skip.
    """
    if not 1 <= n_cases <= len(STRATA):
        raise EgoPointAdapterError(f"n_cases={n_cases} вне диапазона 1..{len(STRATA)}")
    mc_rows = []
    for entry in rows:
        if entry.get("type") != "Multiple_Choice":
            continue  # TF/OE: нет кандидатной таблицы в автор. протоколе
        _validate_row(entry)
        mc_rows.append(entry)
    selected: list[dict[str, Any]] = []
    for dimension, level in STRATA[:n_cases]:
        candidates = [
            e
            for e in mc_rows
            if e.get("dimension") == dimension and e.get("deixis_level") == level
        ]
        if not candidates:
            raise EgoPointAdapterError(
                f"страта ({dimension}, {level}) пуста: файл отличается "
                "от верифицированного или повреждён"
            )
        selected.append(min(candidates, key=lambda e: int(str(e["image_id"]))))
    return selected


def _make_case(
    entry: dict[str, Any],
    image_file: Path,
    media_prefix: str,
    bench_sha256: str,
) -> Case:
    """Строка бенчмарка → кейс единой схемы (через `case_from_dict`)."""
    image_id = str(entry["image_id"])
    options = entry["options"]
    answer_letter = str(entry["answer"])[0]
    letters = "ABCD"
    candidates = [_candidate_id(image_id, L) for L in letters]
    target_id = _candidate_id(image_id, answer_letter)
    distractors = [cid for L, cid in zip(letters, candidates, strict=True) if L != answer_letter]
    answer_map = {
        _option_label(options[i]): _candidate_id(image_id, L) for i, L in enumerate(letters)
    }
    data = {
        "case_id": f"EPO-REAL-{int(image_id):04d}",
        "source": SOURCE,
        "track": "pointing",
        "split_group_id": f"g-ep-real-{image_id}",
        "media": {
            "path": f"{media_prefix}/test_img/{image_id}.jpg",
            "sha256": hashlib.sha256(image_file.read_bytes()).hexdigest(),
            "format": "jpg",
        },
        "prompt": {
            "mode": "freeform",
            "user_text": author_prompt(entry),
            "language": "en",
        },
        "candidates": candidates,
        "allowed_tools": [],
        "gold": {
            "type": "target_box",
            "target_id": target_id,
            "box_px": None,
            "distractors": distractors,
        },
        "provenance": {
            "source": "EgoPoint-Bench",
            "license": LICENSE_LINE,
            "version": f"pure_real_test.json sha256:{bench_sha256[:16]}",
            "rights_note": RIGHTS_NOTE,
        },
        "slices": {
            "dimension": entry.get("dimension"),
            "deixis_level": entry.get("deixis_level"),
            "n_distractors": len(distractors),
            # Таблица «ответ → id кандидата» для freeform-скоринга:
            # _answer_to_id() (eval/scoring.py) сопоставляет ответ модели
            # с ключами после нормализации.
            "answer_map": answer_map,
        },
    }
    return case_from_dict(data)


def build_egopoint_cases(
    data_root: Path,
    *,
    n_cases: int = DEFAULT_N_CASES,
    media_prefix: str = DEFAULT_MEDIA_PREFIX,
    expected_bench_sha256: str | None = BENCH_SHA256_EXPECTED,
) -> tuple[list[Case], dict[str, Any]]:
    """Собирает кейсы EgoPoint-Bench из ``data_root``.

    ``data_root`` — каталог с деревом ``realdata_benchmark/``
    (``pure_real_test.json`` + ``test_img/*.jpg``). Read-only: в
    каталог ничего не записывается.
    """
    data_root = Path(data_root)
    bench_file = data_root / BENCH_REL_PATH
    if not bench_file.is_file():
        raise EgoPointAdapterError(
            f"не найден {bench_file}; см. PROVENANCE.md (команды "
            "загрузки — в разделе 'Загрузка')"
        )
    raw = bench_file.read_bytes()
    bench_sha256 = hashlib.sha256(raw).hexdigest()
    if expected_bench_sha256 is not None and bench_sha256 != expected_bench_sha256:
        raise EgoPointAdapterError(
            f"sha256 {bench_file.name} = {bench_sha256[:16]}… ≠ "
            f"верифицированному {expected_bench_sha256[:16]}… — файл "
            "изменился с момента проверки T1; сборка остановлена"
        )
    try:
        rows = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise EgoPointAdapterError(f"{bench_file}: не JSON: {exc}") from exc
    if not isinstance(rows, list) or not rows:
        raise EgoPointAdapterError(f"{bench_file}: ожидался непустой список")

    selected = select_mc_rows(rows, n_cases=n_cases)
    images_dir = data_root / "realdata_benchmark"
    cases: list[Case] = []
    for entry in selected:
        image_file = images_dir / str(entry["image_path"])
        if not image_file.is_file():
            raise EgoPointAdapterError(
                f"не найдено изображение {image_file} " f"(кейс {entry['image_id']})"
            )
        cases.append(_make_case(entry, image_file, media_prefix, bench_sha256))
    cases.sort(key=lambda c: c.case_id)
    if len({c.case_id for c in cases}) != len(cases):
        raise EgoPointAdapterError("дубликаты case_id в выборке — нарушение формата")

    n_mc = sum(1 for e in rows if e.get("type") == "Multiple_Choice")
    report = {
        "source": SOURCE,
        "n_cases": len(cases),
        "bench_file": BENCH_REL_PATH,
        "bench_sha256": bench_sha256,
        "total_rows": len(rows),
        "excluded_non_multiple_choice": len(rows) - n_mc,
        "selection_rule": (
            f"{len(STRATA)} фиксированных страт (dimension, "
            "deixis_level), по 2 на размер, min image_id в страте; "
            "только Multiple_Choice (единственный тип с замкнутым "
            "набором опций → кандидатная таблица id)"
        ),
        "selected": [
            {
                "case_id": c.case_id,
                "image_id": c.split_group_id.rsplit("-", 1)[-1],
                "dimension": c.slices["dimension"],
                "deixis_level": c.slices["deixis_level"],
                "answer_id": c.gold["target_id"],
            }
            for c in cases
        ],
    }
    return cases, report


def load(data_root: Path) -> list[Case]:
    """Протокол адаптера (дизайн, раздел «Adapter interface»)."""
    cases, _report = build_egopoint_cases(data_root)
    return cases


def provenance_text(cases: list[Case], report: dict[str, Any]) -> str:
    """Текст ``PROVENANCE.md`` (контракт дизайна, раздел "Provenance")."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# EgoPoint-Bench — Provenance (сгенерировано guide_robot_llm.eval.adapters.egopoint)",
        "",
        f"- Время генерации: {now}",
        "- Источник: EgoPoint-Bench — HF-датасет `GUYYYUG/EgoPoint` "
        "(дерево `realdata_benchmark/`); код и авторский QA-протокол — "
        "GitHub `GUYYYUG/EgoPoint` (Apache-2.0)",
        f"- Лицензия: {LICENSE_LINE}",
        "- Использование: read-only, без производных изображений; "
        "адаптер не пишет в каталог данных",
        f"- Файл: `{BENCH_REL_PATH}`, sha256 = `{report['bench_sha256']}` "
        "(совпадает с верифицированным 2026-09-15: HF-копия идентична "
        "копии в GitHub-репозитории)",
        f"- Строк в файле: {report['total_rows']} (из них "
        "Multiple_Choice: "
        f"{report['total_rows'] - report['excluded_non_multiple_choice']}, "
        f"True_False + Open_Ended отброшено: "
        f"{report['excluded_non_multiple_choice']} — нет замкнутого набора "
        "кандидатов в авторском протоколе)",
        f"- Правило выбора: {report['selection_rule']}",
        "- Примечание: файл уже содержит baseline-выводы авторов "
        "(`model_output`, `is_correct`, …) — адаптер их не читает и "
        "модели под тест не передаёт",
        "",
        "## Загрузка (выполняет пользователь — агент не скачивает)",
        "",
        "```bash",
        "cd guide_robot_llm && mkdir -p eval_data/egopoint && cd eval_data/egopoint",
        'pip install -U "huggingface_hub[cli]"        # если не установлено',
        'huggingface-cli download GUYYYUG/EgoPoint --include "realdata_benchmark/*" --local-dir .',
        f"sha256sum realdata_benchmark/pure_real_test.json  # ожидается: {report['bench_sha256']}",
        "```",
        "",
        "Сборка манифеста после загрузки:",
        "",
        "```bash",
        "python -m guide_robot_llm.eval.adapters.egopoint --data-root . "
        "--out ../../eval_manifests/egopoint_10.jsonl",
        "```",
        "",
        "## Выбранные кейсы",
        "",
        "| case_id | image_id | dimension | deixis | answer_id |",
        "|---|---|---|---|---|",
    ]
    for item in report["selected"]:
        lines.append(
            f"| {item['case_id']} | {item['image_id']} | "
            f"{item['dimension']} | {item['deixis_level']} | "
            f"{item['answer_id']} |"
        )
    lines += [
        "",
        f"Кейсов: {len(cases)}. Симуляционное подмножество "
        "(`simdata_benchmark/`) не загружено и не читается (гейт T1).",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """CLI: сборка манифеста EgoPoint-Bench (JSONL) + отчёт + PROVENANCE.md."""
    parser = argparse.ArgumentParser(
        description=(
            "Сборка манифеста EgoPoint-Bench (10 real-кейсов, авторский "
            "QA-протокол) — read-only относительно каталога данных"
        )
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=Path(__file__).resolve().parents[3] / "eval_data" / "egopoint",
        help="Каталог с realdata_benchmark/ (по умолчанию " "guide_robot_llm/eval_data/egopoint)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parents[3] / "eval_manifests" / "egopoint_10.jsonl",
        help="Выходной JSONL-манифест",
    )
    parser.add_argument(
        "--n-cases",
        type=int,
        default=DEFAULT_N_CASES,
        help=f"Число кейсов (по умолчанию {DEFAULT_N_CASES})",
    )
    parser.add_argument(
        "--media-prefix",
        default=DEFAULT_MEDIA_PREFIX,
        help="Префикс пути в media.path (логический, от корня eval_data)",
    )
    args = parser.parse_args(argv)

    cases, report = build_egopoint_cases(
        args.data_root,
        n_cases=args.n_cases,
        media_prefix=args.media_prefix,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        for case in cases:
            fh.write(json.dumps(case_to_dict(case), ensure_ascii=False) + "\n")
    sidecar = args.out.with_name(args.out.name + ".sidecar.json")
    sidecar.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    # PROVENANCE.md в корне данных — по контракту дизайна (аналог
    # DP-адаптера); сами данные адаптер не изменяет.
    (args.data_root / "PROVENANCE.md").write_text(provenance_text(cases, report), encoding="utf-8")
    print(
        f"EgoPoint: кейсов {len(cases)} → {args.out}\n"
        f"  отчёта → {sidecar}\n"
        f"  provenance → {args.data_root / 'PROVENANCE.md'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
