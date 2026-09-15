"""Адаптер EgoPoint-Bench (Taiga #10, T7): авторский протокол, выбор, целостность.

Фикстура: `test/data/ep_stub/pure_real_test.json` (коммичена) — структурный
зеркаль верифицированного файла с синтетическим текстом (контент бенчмарка
в репозиторий не попадает). Изображения генерируются в tmp. Сети и реального
датасета нет.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from guide_robot_llm.eval import schema
from guide_robot_llm.eval.adapters import egopoint

STUB_JSON = (
    Path(__file__).resolve().parents[1] / "test" / "data" / "ep_stub" / "pure_real_test.json"
)

# Ожидаемая выборка в порядке страт:
# (image_id, dimension, deixis_level, буква ответа)
EXPECTED_SELECTION: list[tuple[int, str, str, str]] = [
    (20, "Context & Relation", "L3", "C"),
    (99, "Affordance & Function", "L3", "C"),
    (27, "Basic Perception", "L3", "B"),
    (103, "OCR & Text", "L3", "A"),
    (405, "Adversarial", "L3", "D"),
    (100, "Context & Relation", "L2", "B"),
    (69, "Affordance & Function", "L2", "A"),
    (167, "Basic Perception", "L2", "C"),
    (1270, "Adversarial", "L1", "B"),
    (13, "OCR & Text", "L1", "A"),
]
SELECTED_IDS = [iid for iid, *_ in EXPECTED_SELECTION]
UNSELECTED_IDS = [36, 21, 301, 302]  # дубль страты, null-dataset, TF, OE


def _jpeg_bytes(width: int = 640, height: int = 480) -> bytes:
    """Минимальный JPEG (SOI + SOF0 + EOI)."""
    sof = (
        b"\xff\xc0"
        + (8 + 3).to_bytes(2, "big")
        + bytes([8])
        + height.to_bytes(2, "big")
        + width.to_bytes(2, "big")
        + bytes([1, 1, 0x11, 0])
    )
    return b"\xff\xd8" + sof + b"\xff\xd9"


def _stub_row(image_id: str) -> dict:
    rows = json.loads(STUB_JSON.read_text(encoding="utf-8"))
    return next(e for e in rows if e["image_id"] == image_id)


@pytest.fixture()
def stub_rows() -> list[dict]:
    return json.loads(STUB_JSON.read_text(encoding="utf-8"))


@pytest.fixture()
def ep_root(tmp_path: Path) -> Path:
    """Каталог данных: stub-JSON + изображения выбранных строк."""
    root = tmp_path / "ep"
    bench = root / "realdata_benchmark"
    imgs = bench / "test_img"
    imgs.mkdir(parents=True)
    (bench / "pure_real_test.json").write_bytes(STUB_JSON.read_bytes())
    for iid in SELECTED_IDS:
        (imgs / f"{iid}.jpg").write_bytes(_jpeg_bytes())
    return root


def test_author_prompt_is_verbatim_protocol(stub_rows: list[dict]) -> None:
    """Промпт = дословный MC-протокол eval_real_qwen3vl.py."""
    row = _stub_row("27")
    options_str = "\n".join(row["options"])
    expected = (
        f"{row['question']}\n{options_str}\n"
        "Answer directly using the letters of the options given."
    )
    assert egopoint.author_prompt(row) == expected


def test_built_prompt_matches_authors_protocol(ep_root: Path) -> None:
    cases, _ = egopoint.build_egopoint_cases(ep_root, expected_bench_sha256=None)
    case = next(c for c in cases if c.case_id == "EPO-REAL-0405")
    row = _stub_row("405")
    assert case.prompt.user_text == egopoint.author_prompt(row)
    assert "Answer directly using the letters of the options given." in case.prompt.user_text


def test_candidate_ids_and_answer_map(ep_root: Path) -> None:
    cases, _ = egopoint.build_egopoint_cases(ep_root, expected_bench_sha256=None)
    case = next(c for c in cases if c.case_id == "EPO-REAL-0027")
    assert case.candidates == ("epobj-27-a", "epobj-27-b", "epobj-27-c", "epobj-27-d")
    assert case.gold["type"] == "target_box"
    assert case.gold["target_id"] == "epobj-27-b"  # ответ 'B. Chocolate'
    assert case.gold["box_px"] is None
    assert case.gold["distractors"] == ["epobj-27-a", "epobj-27-c", "epobj-27-d"]
    assert case.slices["answer_map"] == {
        "Strawberry": "epobj-27-a",
        "Chocolate": "epobj-27-b",
        "Matcha": "epobj-27-c",
        "Milk": "epobj-27-d",
    }
    assert case.slices["n_distractors"] == 3


def test_selection_covers_strata_and_min_image_id(stub_rows: list[dict]) -> None:
    selected = egopoint.select_mc_rows(stub_rows)
    ids = [int(e["image_id"]) for e in selected]
    assert ids == SELECTED_IDS
    # Страта (Context & Relation, L3): строка 20 вытесняет строку 36 (min id)
    stratum = [
        int(e["image_id"])
        for e in selected
        if (e["dimension"], e["deixis_level"]) == ("Context & Relation", "L3")
    ]
    assert stratum == [20]
    # TF/OE-строки не в выборке (нет замкнутого набора кандидатов)
    assert not set(ids) & set(UNSELECTED_IDS)


def test_selection_missing_stratum_raises(stub_rows: list[dict]) -> None:
    rows = [e for e in stub_rows if e["image_id"] != "103"]  # OCR & Text L3 пуста
    with pytest.raises(egopoint.EgoPointAdapterError, match="страта"):
        egopoint.select_mc_rows(rows)


def test_selection_non_real_dataset_raises(stub_rows: list[dict]) -> None:
    sim = dict(_stub_row("20"))
    sim.update({"image_id": "500", "dataset": "simdata", "image_path": "test_img/500.jpg"})
    with pytest.raises(egopoint.EgoPointAdapterError, match="не real-world"):
        egopoint.select_mc_rows(stub_rows + [sim])


def test_selection_invalid_mc_row_raises(stub_rows: list[dict]) -> None:
    bad = dict(_stub_row("20"))
    bad.update(
        {"image_id": "501", "options": bad["options"][:3], "image_path": "test_img/501.jpg"}
    )
    with pytest.raises(egopoint.EgoPointAdapterError, match="4 опции"):
        egopoint.select_mc_rows(stub_rows + [bad])


def test_build_cases_full_stub(ep_root: Path) -> None:
    cases, report = egopoint.build_egopoint_cases(ep_root, expected_bench_sha256=None)
    assert len(cases) == 10
    assert [c.case_id for c in cases] == [f"EPO-REAL-{iid:04d}" for iid in sorted(SELECTED_IDS)]
    assert len({c.split_group_id for c in cases}) == len(cases)
    for c in cases:
        assert c.source == "egopoint"
        assert c.track == "pointing"
        assert c.prompt.mode == "freeform"
        assert c.prompt.language == "en"
        image_id = c.case_id.rsplit("-", 1)[-1]
        assert c.split_group_id == f"g-ep-real-{int(image_id)}"
        assert c.media.path == (
            f"eval_data/egopoint/realdata_benchmark/test_img/{int(image_id)}.jpg"
        )
        assert c.media.format == "jpg"
        assert c.media.sha256 == hashlib.sha256(_jpeg_bytes()).hexdigest()
        assert c.provenance is not None
        assert c.provenance.license == egopoint.LICENSE_LINE
        assert "sha256:" in c.provenance.version
        assert egopoint.RIGHTS_NOTE in c.provenance.rights_note
    # Схема round-trip (замороженный манифест проходит валидацию)
    for c in cases:
        assert schema.case_from_dict(schema.case_to_dict(c)) == c
    # Отчёт
    assert report["n_cases"] == 10
    assert report["total_rows"] == 14
    assert report["excluded_non_multiple_choice"] == 2
    assert len(report["selected"]) == 10


def test_build_missing_bench_file(tmp_path: Path) -> None:
    root = tmp_path / "empty"
    root.mkdir()
    with pytest.raises(egopoint.EgoPointAdapterError, match="не найден"):
        egopoint.build_egopoint_cases(root, expected_bench_sha256=None)


def test_build_missing_image_raises(ep_root: Path) -> None:
    (ep_root / "realdata_benchmark" / "test_img" / "13.jpg").unlink()
    with pytest.raises(egopoint.EgoPointAdapterError, match="не найдено изображение"):
        egopoint.build_egopoint_cases(ep_root, expected_bench_sha256=None)


def test_build_changed_bench_file_raises(ep_root: Path) -> None:
    """Пин sha256: файл, отличающийся от верифицированного, сборку останавливает."""
    with pytest.raises(egopoint.EgoPointAdapterError, match="изменился"):
        egopoint.build_egopoint_cases(ep_root)  # дефолт = пин верифицированного файла


def test_no_modification_of_data_dir(ep_root: Path) -> None:
    """Сборка read-only: дерево каталога данных после сборки неизменно."""

    def _snapshot(root: Path) -> dict[str, tuple[int, str]]:
        out: dict[str, tuple[int, str]] = {}
        for p in sorted(root.rglob("*")):
            if p.is_file():
                data = p.read_bytes()
                out[str(p.relative_to(root))] = (
                    p.stat().st_size,
                    hashlib.sha256(data).hexdigest(),
                )
        return out

    before = _snapshot(ep_root)
    egopoint.build_egopoint_cases(ep_root, expected_bench_sha256=None)
    assert _snapshot(ep_root) == before


def test_provenance_text_lists_license_hash_and_steps(ep_root: Path) -> None:
    cases, report = egopoint.build_egopoint_cases(ep_root, expected_bench_sha256=None)
    text = egopoint.provenance_text(cases, report)
    assert egopoint.LICENSE_LINE in text
    assert "GO 2026-09-15" in text
    assert "read-only" in text
    assert report["bench_sha256"] in text
    assert "не скачивает" in text
    assert "huggingface-cli download GUYYYUG/EgoPoint" in text
    assert "simdata_benchmark" in text
    for iid, *_ in EXPECTED_SELECTION:
        assert f"EPO-REAL-{iid:04d}" in text
