"""Тесты сборщика held-out pointing-15 (W1-фикс, T3).

Проверяют: exclusion-фильтр по замороженным манифестам, детерминированную
стратную выборку (min image_id), round-robin расширение до 15, guard на
пустую страту и union id по манифестам.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_PKG_ROOT = Path(__file__).resolve().parent.parent
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))

# Скрипт сборки — не модуль пакета: подгружаем по пути.
_SPEC = importlib.util.spec_from_file_location(
    "make_pointing_holdout",
    _PKG_ROOT / "scripts" / "make_pointing_holdout.py",
)
assert _SPEC and _SPEC.loader
_mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_mod)

excluded_image_ids = _mod.excluded_image_ids
select_holdout_rows = _mod.select_holdout_rows


def _row(image_id: int, dimension: str, level: str, mtype: str = "Multiple_Choice") -> dict:
    """Валидная MC-строка (формат верифицированного файла)."""
    return {
        "image_id": image_id,
        "type": mtype,
        "dataset": "realdata",
        "dimension": dimension,
        "deixis_level": level,
        "question": "What is the target?",
        "options": ["A. first", "B. second", "C. third", "D. fourth"],
        "answer": "A. first",
        "image_path": f"test_img/{image_id}.jpg",
    }


def _rows_for_all_strata() -> list[dict]:
    """Дискретные id-диапазоны: страта i → ids i*100+1..i*100+3."""
    rows: list[dict] = []
    for i, (dim, lvl) in enumerate(_mod.HOLDOUT_STRATA, start=1):
        for k in range(1, 4):
            rows.append(_row(i * 100 + k, dim, lvl))
    # Adversarial: ровно 3 строки, как в верифицированном файле (гейт T1)
    rows.append(_row(405, "Adversarial", "L3"))
    rows.append(_row(1204, "Adversarial", "L3"))
    rows.append(_row(1270, "Adversarial", "L1"))
    return rows


def test_selection_excludes_frozen_ids_and_picks_next_min() -> None:
    """Замороженный min id пропущен: в страте выбран следующий min."""
    rows = _rows_for_all_strata()
    # Замораживаем первые два id первой страты (101, 102) + Adversarial.
    frozen = {101, 102, 405, 1204, 1270}
    selected = select_holdout_rows(rows, frozen)
    ids = [int(r["image_id"]) for r in selected]
    assert len(ids) == 15
    assert not set(ids) & frozen
    # Страта (Context & Relation, L3): 101/102 заморожены → pick = 103.
    first_pick = next(
        int(r["image_id"])
        for r in selected
        if r["dimension"] == "Context & Relation" and r["deixis_level"] == "L3"
        and int(r["image_id"]) < 200
    )
    assert first_pick == 103
    # Остальные страты -- свои min: 201, 301, 401, 501, 601, 701, 801.
    for i in range(2, 9):
        assert i * 100 + 1 in ids


def test_selection_deterministic_and_round_robin_to_15() -> None:
    """15 = 8 страт + 4 + 3 (round-robin); детерминизм; без Adversarial."""
    rows = _rows_for_all_strata()
    a = select_holdout_rows(rows, set())
    b = select_holdout_rows(rows, set())
    assert [r["image_id"] for r in a] == [r["image_id"] for r in b]
    assert len(a) == 15
    assert all(r["dimension"] != "Adversarial" for r in a)
    ids = [int(r["image_id"]) for r in a]
    # Стратные picks: 101..801 (по одному min на страту).
    for i in range(1, 9):
        assert i * 100 + 1 in ids
    # Расширение round-robin: 2-я волна 102,202,302,402; 3-я — 103,203,303.
    assert 102 in ids and 202 in ids and 302 in ids and 402 in ids
    assert 103 in ids and 203 in ids and 303 in ids


def test_selection_empty_stratum_raises() -> None:
    """Пустая страта после exclusion — ошибка, а не тихий skip."""
    rows = _rows_for_all_strata()
    frozen = {101, 102, 103, 405, 1204, 1270}  # вся первая страта
    with pytest.raises(SystemExit, match="пуста после exclusion"):
        select_holdout_rows(rows, frozen)


def test_selection_non_mc_rows_dropped() -> None:
    """True_False/Open_Ended отбрасываются (нет кандидатной таблицы)."""
    rows = _rows_for_all_strata()
    rows.append(_row(999, "Context & Relation", "L3", mtype="True_False"))
    selected = select_holdout_rows(rows, set())
    assert 999 not in [int(r["image_id"]) for r in selected]


def test_excluded_image_ids_unions_manifests(tmp_path) -> None:
    """Union по всем *.jsonl; дубликаты и не-EgoPoint не считаются."""
    (tmp_path / "a.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"source": "egopoint", "split_group_id": "g-ep-real-7"}),
                json.dumps({"source": "egopoint", "split_group_id": "g-ep-real-9"}),
                json.dumps({"source": "aghri", "split_group_id": "g-aghri-7"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "b.jsonl").write_text(
        json.dumps({"source": "egopoint", "split_group_id": "g-ep-real-7"}) + "\n",
        encoding="utf-8",
    )
    per_manifest, excluded = excluded_image_ids(tmp_path)
    assert excluded == {7, 9}
    files = {m["file"]: m["n_egopoint_ids"] for m in per_manifest}
    assert files == {"a.jsonl": 2, "b.jsonl": 1}
    assert all("sha256" in m for m in per_manifest)


def test_excluded_image_ids_skips_own_output(tmp_path: Path) -> None:
    """Idempotency (task 3.2): the builder's own output manifest in the
    directory must not enter the exclusion set, else a re-run would pick
    a different 15."""
    out = tmp_path / "pointing_holdout_15.jsonl"
    out.write_text(
        json.dumps({"source": "egopoint", "split_group_id": "g-ep-real-42"}) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "a.jsonl").write_text(
        json.dumps({"source": "egopoint", "split_group_id": "g-ep-real-7"}) + "\n",
        encoding="utf-8",
    )
    per_manifest, excluded = excluded_image_ids(tmp_path, skip=out)
    assert excluded == {7}
    assert [m["file"] for m in per_manifest] == ["a.jsonl"]
