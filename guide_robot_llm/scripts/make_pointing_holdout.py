#!/usr/bin/env python3
"""Сборка held-out pointing-множества ``pointing_holdout_15.jsonl`` (W1-фикс).

Зачем: оригинальный pointing-15 (EgoPoint bench v2) участвовал в
выборе промпт-вариантов (P3 для gemma4, its — для qwen3.5). Честный
политический метрик (фаза решения, W1-фикс) требует подтверждение на
кейсах, которые НИКДА не участвовали в выборе варианта: held-out
подмножество EgoPoint, дизъюнктное со ВСЕМИ замороженными манифестами.

Состав (15 кейсов): только Multiple_Choice-строки ``pure_real_test.json``
(верифицированный файл, гейт T1), с исключением всех EgoPoint
``image_id``, присутствующих в любом ``eval_manifests/*.jsonl``
(bench_40/47/50, pv_matrix_57, egopoint_10/15 и др.).

Правило выбора — то же, что у адаптера
(``guide_robot_llm/eval/adapters/egopoint.py``, bench v2), с двумя
документированными отклонениями:

* страта ``(Adversarial, *)`` исключена: в верифицированном файле
  размер Adversarial содержит ровно 3 MC-строки (405, 1204, 1270), и
  ВСЕ три уже в замороженном бенче — после exclusion-фильтра страты
  пусты, чистый strata-путь невозможен;
* расширение сверх страт — round-robin по размерам (порядок первого
  появления), пока не наберётся 15: 8 страт + 4 + 3.

Запуск из каталога пакета ``guide_robot_llm/``:

    python3 scripts/make_pointing_holdout.py

Если изображения выбранных кейсов ещё не загружены, скрипт печатает
список и точную команду ``huggingface-cli download`` и завершается с
кодом 2 (агент не скачивает — команду выполняет пользователь). После
загрузки повторный запуск собирает
``eval_manifests/pointing_holdout_15.jsonl`` + sidecar
``pointing_holdout_15.json`` (состав, пер-кейс provenance, исключённые
манифесты с sha256, дата). Манифест заморожен после первой генерации:
повторный запуск должен дать тот же sha256 JSONL.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

_PKG_ROOT = Path(__file__).resolve().parent.parent
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))

from guide_robot_llm.eval.adapters.egopoint import (  # noqa: E402
    BENCH_REL_PATH,
    BENCH_SHA256_EXPECTED,
    _make_case,
    _validate_row,
)
from guide_robot_llm.eval.schema import case_to_dict  # noqa: E402

MANIFESTS_DIR = _PKG_ROOT / "eval_manifests"
DATA_ROOT = _PKG_ROOT / "eval_data" / "egopoint"
OUT = MANIFESTS_DIR / "pointing_holdout_15.jsonl"
SIDECAR = MANIFESTS_DIR / "pointing_holdout_15.json"
N_CASES = 15
MEDIA_PREFIX = "eval_data/egopoint/realdata_benchmark"

# STRATA адаптера минус Adversarial (размер исчерпан: 3 MC-строки,
# все в замороженном бенче — см. docstring).
HOLDOUT_STRATA: tuple[tuple[str, str], ...] = (
    ("Context & Relation", "L3"),
    ("Affordance & Function", "L3"),
    ("Basic Perception", "L3"),
    ("OCR & Text", "L3"),
    ("Context & Relation", "L2"),
    ("Affordance & Function", "L2"),
    ("Basic Perception", "L2"),
    ("OCR & Text", "L1"),
)
HOLDOUT_DIMENSIONS: tuple[str, ...] = (
    "Context & Relation",
    "Affordance & Function",
    "Basic Perception",
    "OCR & Text",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def excluded_image_ids(
    manifests_dir: Path = MANIFESTS_DIR,
    skip: Path | None = None,
) -> tuple[list[dict[str, object]], set[int]]:
    """Union EgoPoint ``image_id`` по всем ``<manifests_dir>/*.jsonl``.

    Возвращает (пер-манифест отчёт, множество id). ``source ==
    "egopoint"`` — единственный источник EgoPoint-кейсов; прочие
    адаптеры (AGHRI, DP, пилот-CC) id не имеют. ``skip`` — выходной
    файл самого билдера: не исключает сам себя, иначе повторный запуск
    выбрал бы другие 15 (idemпотентность, task 3.2).
    """
    per_manifest: list[dict[str, object]] = []
    excluded: set[int] = set()
    skip_resolved = Path(skip).resolve() if skip is not None else None
    for mf in sorted(Path(manifests_dir).glob("*.jsonl")):
        if skip_resolved is not None and mf.resolve() == skip_resolved:
            continue
        ids: set[int] = set()
        for line in mf.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("source") == "egopoint":
                ids.add(int(row["split_group_id"].rsplit("-", 1)[-1]))
        per_manifest.append(
            {"file": mf.name, "sha256": _sha256(mf), "n_egopoint_ids": len(ids)}
        )
        excluded |= ids
    return per_manifest, excluded


def select_holdout_rows(
    rows: list[dict[str, object]], excluded: set[int]
) -> list[dict[str, object]]:
    """8 страт (minus Adversarial) + round-robin до 15, min image_id.

    Строки ``True_False``/``Open_Ended`` отбрасываются (нет замкнутого
    набора кандидатов в авторском протоколе); нарушение формата —
    ошибка, а не тихий skip (тот же контракт, что у адаптера).
    """
    mc = []
    for entry in rows:
        if entry.get("type") != "Multiple_Choice":
            continue
        _validate_row(entry)
        if int(str(entry["image_id"])) in excluded:
            continue
        mc.append(entry)

    selected: list[dict[str, object]] = []
    selected_ids: set[int] = set()

    def take(candidates: list[dict[str, object]]) -> None:
        pick = min(candidates, key=lambda e: int(str(e["image_id"])))
        selected.append(pick)
        selected_ids.add(int(str(pick["image_id"])))

    for dimension, level in HOLDOUT_STRATA:
        candidates = [
            e
            for e in mc
            if e.get("dimension") == dimension and e.get("deixis_level") == level
        ]
        if not candidates:
            raise SystemExit(
                f"страта ({dimension}, {level}) пуста после exclusion — "
                "файл отличается от верифицированного?"
            )
        take(candidates)
    while len(selected) < N_CASES:
        for dimension in HOLDOUT_DIMENSIONS:
            if len(selected) >= N_CASES:
                break
            candidates = [
                e
                for e in mc
                if e.get("dimension") == dimension
                and int(str(e["image_id"])) not in selected_ids
            ]
            if not candidates:
                raise SystemExit(
                    f"dimension {dimension!r}: MC-строки исчерпаны — "
                    f"n_cases={N_CASES} не укладывается"
                )
            take(candidates)
    return selected


def download_command(missing: list[int]) -> str:
    includes = " ".join(
        f'--include "realdata_benchmark/test_img/{i}.jpg"' for i in missing
    )
    return (
        "cd guide_robot_llm/eval_data/egopoint && "
        f'huggingface-cli download GUYYYUG/EgoPoint {includes} --local-dir .'
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Сборка held-out pointing-15 (W1-фикс): дизъюнктно со всеми "
            "замороженными манифестами; read-only относительно данных"
        )
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=DATA_ROOT,
        help="Каталог с realdata_benchmark/ (по умолчанию "
        "guide_robot_llm/eval_data/egopoint)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=OUT,
        help="Выходной JSONL-манифест (sidecar — рядом, .json)",
    )
    args = parser.parse_args(argv)
    data_root = args.data_root
    out = args.out

    bench_file = data_root / BENCH_REL_PATH
    if not bench_file.is_file():
        raise SystemExit(f"не найден {bench_file}; см. eval_data/egopoint/PROVENANCE.md")
    raw = bench_file.read_bytes()
    bench_sha256 = hashlib.sha256(raw).hexdigest()
    if bench_sha256 != BENCH_SHA256_EXPECTED:
        raise SystemExit(
            f"sha256 {bench_file.name} = {bench_sha256[:16]}… ≠ "
            f"верифицированному {BENCH_SHA256_EXPECTED[:16]}… — сборка остановлена"
        )
    rows = json.loads(raw)

    per_manifest, excluded = excluded_image_ids(skip=out)
    selected = select_holdout_rows(rows, excluded)
    if len({int(str(e["image_id"])) for e in selected}) != len(selected):
        raise SystemExit("дубликаты image_id в выборке — баг выбора")

    # Медиа: все 15 изображений обязаны существовать (sha256 в манифесте).
    missing = [
        int(str(e["image_id"]))
        for e in selected
        if not (data_root / "realdata_benchmark" / f"test_img/{e['image_id']}.jpg").is_file()
    ]
    if missing:
        print(f"Изображения не загружены ({len(missing)}/{len(selected)}): {missing}")
        print("\nЗагрузите (пользователь — агент не скачивает):")
        print(f"  {download_command(missing)}")
        print(f"\nЗатем повторите: python3 scripts/make_pointing_holdout.py")
        return 2

    images_dir = data_root / "realdata_benchmark"
    cases = [
        _make_case(
            e,
            images_dir / str(e["image_path"]),
            MEDIA_PREFIX,
            bench_sha256,
        )
        for e in selected
    ]
    cases.sort(key=lambda c: c.case_id)

    # Контракт held-out: ноль пересечения со всеми замороженными id.
    assert all(int(c.split_group_id.rsplit("-", 1)[-1]) not in excluded for c in cases), (
        "выбранный кейс присутствует в замороженном манифесте"
    )

    text = "".join(json.dumps(case_to_dict(c), ensure_ascii=False) + "\n" for c in cases)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    sidecar = {
        "name": out.name,
        "n_cases": len(cases),
        "generated": time.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "purpose": (
            "W1-фикс: held-out подтверждение pointing-политики на кейсах, "
            "не участвовавших в выборе промпт-вариантов (оригинальный "
            "pointing-15 был в выборке P3/its)"
        ),
        "source": "EgoPoint-Bench (realdata_benchmark/pure_real_test.json)",
        "bench_sha256": bench_sha256,
        "license": "private-research-use",
        "selection_rule": (
            "8 фиксированных страт (dimension, deixis_level) минус "
            "Adversarial (размер исчерпан: 3 MC-строки 405/1204/1270 "
            "весь в замороженном бенче) + round-robin по размерам до 15; "
            "min image_id в страте; только Multiple_Choice; exclusion всех "
            "EgoPoint image_id из eval_manifests/*.jsonl"
        ),
        "excluded_manifests": per_manifest,
        "excluded_image_ids": sorted(excluded),
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
    sidecar_path = out.with_name(out.stem + ".json")
    sidecar_path.write_text(
        json.dumps(sidecar, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"{out}: {len(cases)} кейсов (held-out, W1-фикс)")
    print(f"sidecar: {sidecar_path}")
    print(f"sha256 jsonl: {_sha256(out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
