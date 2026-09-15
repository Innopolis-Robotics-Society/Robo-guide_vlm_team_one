"""Адаптер AGHRI (Taiga #10, T9): count-кейсы, выбор последовательностей, gold из 2D-боксов.

Фикстура: ``test/data/aghri_stub/`` (коммичена) — структурный зеркаль
форматов AGHRI (``dataset_summary.csv`` + ``annotations/cam_zed_rgb_ann.json``
+ ``sensor_data/cam_zed_rgb/*.png``, 5 последовательностей × 3 кадра,
count 1..5) с синтетическим контентом. Реальных данных (DOI
10.24385/lincoln.32982638, ~70 GB) в репозитории нет, сеть не требуется.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from guide_robot_llm.eval import schema
from guide_robot_llm.eval.adapters import aghri

STUB_ROOT = Path(__file__).resolve().parents[1] / "test" / "data" / "aghri_stub"
STUB_SUMMARY = STUB_ROOT / aghri.SUMMARY_NAME

# Ожидаемый gold (count не-ignored identity-людей) по каждому кадру
# stub-дерева: ann-позиция → count.
EXPECTED_GOLD = {
    "AGHRI-SEQ-0001-F001": 1,
    "AGHRI-SEQ-0001-F002": 1,
    "AGHRI-SEQ-0001-F003": 0,
    "AGHRI-SEQ-0002-F001": 2,
    "AGHRI-SEQ-0002-F002": 2,
    "AGHRI-SEQ-0002-F003": 1,  # human2 с `Ignore: true` не считается
    "AGHRI-SEQ-0003-F001": 3,
    "AGHRI-SEQ-0003-F002": 3,
    "AGHRI-SEQ-0003-F003": 3,
    "AGHRI-SEQ-0004-F001": 4,
    "AGHRI-SEQ-0004-F002": 4,
    "AGHRI-SEQ-0004-F003": 4,
    "AGHRI-SEQ-0005-F001": 5,
    "AGHRI-SEQ-0005-F002": 5,
    "AGHRI-SEQ-0005-F003": 1,
}
EXPECTED_COVERAGE = {"0": 1, "1": 4, "2": 2, "3": 3, "4": 3, "5": 2}
EXPECTED_ENV_STATE = {
    1: ("footpath1", "st"),
    2: ("in_straw", "st"),
    3: ("in_vine", "mv"),
    4: ("out_straw", "st"),
    5: ("out_vine", "st"),
}
EXPECTED_SPLIT = {1: "train", 2: "train", 3: "val", 4: "test", 5: "test"}


@pytest.fixture()
def aghri_root(tmp_path: Path) -> Path:
    """Корень данных: копирование stub-дерева + готовый ``selection.json``.

    План-стадия (детерминированный выбор) прогоняется на копии stub
    summary; ``selection.json`` кладётся в корень данных, как в
    реальном workflow (``plan`` → загрузка → ``build``).
    """
    root = tmp_path / "aghri"
    shutil.copytree(STUB_ROOT, root)
    selection = tmp_path / "selection.json"
    assert (
        aghri.main(["plan", "--summary", str(root / aghri.SUMMARY_NAME), "--out", str(selection)])
        == 0
    )
    shutil.copy(selection, root / aghri.SELECTION_NAME)
    return root


# ---------------------------------------------------------------------------
# Имя последовательности → число людей
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("footpath1_1walk_st_10_24_2024_1_label", 1),
        ("in_straw_2pick_st_10_30_2024_2_label", 2),
        ("in_vine_3walk_mv_11_02_2024_1_label", 3),
        ("out_straw_4push_st_11_05_2024_1_label", 4),
        # ``walk``/``st_ly`` без цифры — те же 5, счётчик не добавляет
        ("out_vine_5swap_walk_st_ly_11_06_2024_2_label", 5),
        # разные группы людей: 2 push + 1 pick = 3
        ("in_vine_2push_1pick_diff_mv_ly_11_06_2024_3_a", 3),
        # плюс-конъюнкция: те же 2 делают ещё и stand
        ("footpath1_2walk+stand_mv_11_20_2024_1", 2),
        ("out_straw_11push_st_11_05_2024_1_label", 11),
        # даты/instance/env-префикс — не группы людей
        ("2024_10_24_label", None),
        ("in_vine_label", None),
    ],
)
def test_declared_count_from_name(name: str, expected: int | None) -> None:
    assert aghri.declared_count_from_name(name) == expected


# ---------------------------------------------------------------------------
# dataset_summary.csv
# ---------------------------------------------------------------------------


def test_summary_csv_stub(tmp_path: Path) -> None:
    rows = aghri.load_summary_csv(STUB_SUMMARY)
    assert len(rows) == 7
    first = rows[0]
    assert first.seq == "footpath1_1walk_st_10_24_2024_1_label"
    assert first.row_no == 1
    assert first.declared_count == 1
    assert first.count_source == "csv"
    assert first.archive == "dataset_part1.zip"
    assert first.frames == 120
    assert first.split == "train"
    # дубликаты счётчиков — тоже csv
    assert rows[5].declared_count == 2
    assert rows[6].declared_count == 3


def test_summary_csv_header_aliases(tmp_path: Path) -> None:
    p = tmp_path / "s.csv"
    p.write_text(
        "seq,n_people,zip\n" "out_vine_5swap_walk_st_ly_11_06_2024_2_label,,\n",
        encoding="utf-8",
    )
    rows = aghri.load_summary_csv(p)
    assert len(rows) == 1
    # счётчика в CSV нет → fallback на имя последовательности
    assert rows[0].declared_count == 5
    assert rows[0].count_source == "name"


def test_summary_csv_name_fallback(tmp_path: Path) -> None:
    p = tmp_path / "s.csv"
    p.write_text(
        "Sequence Name\n" "in_straw_2pick_st_10_30_2024_2_label\n",
        encoding="utf-8",
    )
    rows = aghri.load_summary_csv(p)
    assert rows[0].declared_count == 2
    assert rows[0].count_source == "name"
    assert rows[0].archive is None
    assert rows[0].frames is None


def test_summary_csv_missing_seq_column_raises(tmp_path: Path) -> None:
    p = tmp_path / "s.csv"
    p.write_text("participants\n1\n", encoding="utf-8")
    with pytest.raises(aghri.AghriAdapterError, match="именем последовательности не найдена"):
        aghri.load_summary_csv(p)


def test_summary_csv_empty_seq_raises(tmp_path: Path) -> None:
    p = tmp_path / "s.csv"
    p.write_text("Sequence Name\n,\n", encoding="utf-8")
    with pytest.raises(aghri.AghriAdapterError, match="пустое имя"):
        aghri.load_summary_csv(p)


def test_summary_csv_no_rows_raises(tmp_path: Path) -> None:
    p = tmp_path / "s.csv"
    p.write_text("Sequence Name\n", encoding="utf-8")
    with pytest.raises(aghri.AghriAdapterError, match="пустой index"):
        aghri.load_summary_csv(p)


def test_summary_csv_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(aghri.AghriAdapterError, match="не найден"):
        aghri.load_summary_csv(tmp_path / "nope.csv")


# ---------------------------------------------------------------------------
# Выбор последовательностей (plan)
# ---------------------------------------------------------------------------


def test_select_sequences_stub() -> None:
    rows = aghri.load_summary_csv(STUB_SUMMARY)
    selected, extra = aghri.select_sequences(rows)
    assert [item.seq_no for item in selected] == [1, 2, 3, 4, 5]
    assert all(item.frames_wanted == 3 for item in selected)
    report = extra["report"]
    assert report["n_selected"] == 5
    assert report["n_frames_selected"] == 15
    assert report["declared_coverage"] == {
        "0": 0,
        "1": 1,
        "2": 1,
        "3": 1,
        "4": 1,
        "5": 1,
    }
    assert report["archives"] == [
        "dataset_part1.zip",
        "dataset_part2.zip",
        "dataset_part3.zip",
    ]
    # 0-счётчика в stub нет → заметка (gold-0 из пустых аннотированных кадров)
    assert any("0 участник" in note for note in report["notes"])
    # дубликаты счётчиков исключены
    excluded_seqs = [item["seq"] for item in extra["excluded"]]
    assert excluded_seqs == [
        "in_straw_2push_diff_st_10_31_2024_1_label",
        "in_vine_3pick_diff_mv_11_03_2024_3_label",
    ]


def test_select_missing_required_count_raises() -> None:
    rows = aghri.load_summary_csv(STUB_SUMMARY)
    # убить последовательность со счётчиком 5
    rows = [row for row in rows if row.declared_count != 5]
    with pytest.raises(aghri.AghriAdapterError, match="покрытие сбоем"):
        aghri.select_sequences(rows)


def test_select_capacity_error() -> None:
    rows = aghri.load_summary_csv(STUB_SUMMARY)
    # 22 кадра при 3/seq требуют 8 последовательностей, доступно 7
    with pytest.raises(aghri.AghriAdapterError, match="недостаточно кадровой ёмкости"):
        aghri.select_sequences(rows, n_frames=22, max_per_seq=3)


def test_select_capacity_uses_reserve_rows() -> None:
    rows = aghri.load_summary_csv(STUB_SUMMARY)
    # 16 кадров: ядро даёт 15, 16-й — из резервного дубликата (строка 6)
    selected, _extra = aghri.select_sequences(rows, n_frames=16, max_per_seq=3)
    assert [item.seq_no for item in selected] == [1, 2, 3, 4, 5, 6]
    assert selected[5].frames_wanted == 1


def test_select_excludes_out_of_range_and_undeclared() -> None:
    rows = aghri.load_summary_csv(STUB_SUMMARY)
    base = rows[:5]  # полное покрытие 1..5
    extra = [
        aghri.SummaryRow(
            seq="out_vine_7push_st_11_07_2024_1_label",
            row_no=90,
            declared_count=7,
            count_source="csv",
            archive=None,
            frames=None,
            split=None,
        ),
        aghri.SummaryRow(
            seq="misc_no_activity_label",
            row_no=91,
            declared_count=None,
            count_source="",
            archive=None,
            frames=None,
            split=None,
        ),
    ]
    _selected, extra_out = aghri.select_sequences(base + extra)
    reasons = {item["seq"]: item["reason"] for item in extra_out["excluded"]}
    assert "declared count 7 > 5" in reasons["out_vine_7push_st_11_07_2024_1_label"]
    assert "count not declared" in reasons["misc_no_activity_label"]


# ---------------------------------------------------------------------------
# Кадровые выборки
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("n_frames", "n_wanted", "expected"),
    [
        (100, 3, [0, 49, 99]),
        (3, 3, [0, 1, 2]),
        (5, 1, [0]),
        (3, 5, [0, 1, 2]),  # n_wanted >= n_frames → все
        (1, 1, [0]),
    ],
)
def test_pick_frame_indices(n_frames: int, n_wanted: int, expected: list[int]) -> None:
    assert aghri.pick_frame_indices(n_frames, n_wanted) == expected


def test_pick_frame_indices_errors() -> None:
    with pytest.raises(aghri.AghriAdapterError, match="нет аннотированных кадров"):
        aghri.pick_frame_indices(0, 1)
    with pytest.raises(aghri.AghriAdapterError, match="frames_wanted < 1"):
        aghri.pick_frame_indices(3, 0)


# ---------------------------------------------------------------------------
# Форматы аннотаций
# ---------------------------------------------------------------------------


def test_load_ann_frames_stub() -> None:
    frames = aghri.load_ann_frames(
        STUB_ROOT
        / "footpath1_1walk_st_10_24_2024_1_label"
        / "annotations"
        / "cam_zed_rgb_ann.json"
    )
    assert [file for file, _labels in frames] == [
        "1729824000000000001.png",
        "1729824000010000001.png",
        "1729824000020000001.png",
    ]
    assert frames[2][1] == []  # третий кадр аннотирован как пустой


def test_load_ann_frames_formats(tmp_path: Path) -> None:
    # dict с ключом `frames`
    p1 = tmp_path / "frames_key.json"
    p1.write_text(
        json.dumps(
            {
                "frames": [
                    {
                        "File": "a.png",
                        "Labels": [{"Class": "human1", "BoundingBoxes": [0, 0, 1, 1]}],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    assert len(aghri.load_ann_frames(p1)) == 1
    # {file: labels}
    p2 = tmp_path / "flat.json"
    p2.write_text(
        json.dumps({"b.png": [{"Class": "human1", "BoundingBoxes": [0, 0, 1, 1]}]}),
        encoding="utf-8",
    )
    assert aghri.load_ann_frames(p2) == [
        ("b.png", [{"Class": "human1", "BoundingBoxes": [0, 0, 1, 1]}])
    ]
    # {file: {"Labels": labels}} + дубликат имени — объединение
    p3 = tmp_path / "wrapped.json"
    p3.write_text(
        json.dumps(
            [
                {"File": "c.png", "Labels": [{"Class": "human1", "BoundingBoxes": [0, 0, 1, 1]}]},
                {"File": "c.png", "Labels": [{"Class": "human2", "BoundingBoxes": [2, 2, 1, 1]}]},
            ]
        ),
        encoding="utf-8",
    )
    frames = aghri.load_ann_frames(p3)
    assert len(frames) == 1
    assert len(frames[0][1]) == 2


def test_load_ann_frames_errors(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(aghri.AghriAdapterError, match="битый JSON"):
        aghri.load_ann_frames(p)
    p2 = tmp_path / "elem.json"
    p2.write_text(json.dumps(["не-объект"]), encoding="utf-8")
    with pytest.raises(aghri.AghriAdapterError, match="не объект"):
        aghri.load_ann_frames(p2)
    with pytest.raises(aghri.AghriAdapterError, match="не найдены аннотации"):
        aghri.load_ann_frames(tmp_path / "missing.json")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ([10, 20, 50, 90], (10.0, 20.0, 50.0, 90.0)),
        ([{"Position": [1, 2, 3, 4]}], (1.0, 2.0, 3.0, 4.0)),
        ([{"position": [1, 2, 3, 4]}], (1.0, 2.0, 3.0, 4.0)),
        ([10, 20, 50, 90, 1280, 720], (10.0, 20.0, 50.0, 90.0)),  # лишние поля
        ([1, 2], None),
        ([{"Position": [1, 2]}], None),
        ([True, 2, 3, 4], None),
        ([], None),
        ("10,20,50,90", None),
    ],
)
def test_parse_box(raw: object, expected: object) -> None:
    assert aghri.parse_box(raw) == expected


# ---------------------------------------------------------------------------
# Gold-счётчик из 2D-боксов
# ---------------------------------------------------------------------------


def _label(cls: str, box: object = [0, 0, 1, 1], **extra: object) -> dict:
    return {"Class": cls, "BoundingBoxes": box, **extra}


@pytest.mark.parametrize(
    ("labels", "expected"),
    [
        # identity-consistent: одна идентичность в N боксах = 1 человек
        ([_label("human1"), _label("human1", [5, 5, 1, 1])], 1),
        ([_label("human1"), _label("human2")], 2),
        # ведущий ноль: 01 и 1 — один человек
        ([_label("01"), _label("1", [5, 5, 1, 1])], 1),
        # legacy без цифры: каждая запись — отдельная личность
        ([_label("person"), _label("human", [5, 5, 1, 1])], 2),
        # ignored-флаги (устойчивые алиасы)
        ([_label("human1", Ignore=True)], 0),
        ([_label("human1", Ignored="true")], 0),
        ([_label("human1", IsIgnored=1)], 0),
        ([_label("human1", IgnoreFlag=1)], 0),
        ([_label("human1", Valid=False)], 0),
        ([_label("human1", Ignore=False)], 1),  # false ≠ true
        # не-человеческие классы
        ([_label("plant")], 0),
        ([_label("human0")], 0),  # 0 не идентичность человека
        # бокс обязателен (не-ignored, но без координат — не кадр-наблюдение)
        ([_label("human1", box=None)], 0),
        ([_label("human1", box=[1, 2])], 0),
        # алиасы ключей
        ([{"class": "human3", "boundingboxes": [0, 0, 1, 1]}], 1),
        # мусорные элементы пропускаются
        ([None, _label("human1")], 1),
        ([], 0),
    ],
    ids=[
        "identity-dedup",
        "two-humans",
        "leading-zero",
        "legacy-unnamed",
        "ignore-true",
        "ignored-string",
        "isignored-int",
        "ignoreflag",
        "valid-false",
        "ignore-false",
        "non-human-class",
        "human-zero",
        "no-box",
        "short-box",
        "alias-keys",
        "skip-non-dict",
        "empty",
    ],
)
def test_frame_person_count(labels: list, expected: int) -> None:
    assert aghri.frame_person_count(labels) == expected


# ---------------------------------------------------------------------------
# Полный pipeline: plan → build (stub)
# ---------------------------------------------------------------------------


def test_plan_selection_payload(tmp_path: Path) -> None:
    out = tmp_path / "selection.json"
    assert aghri.main(["plan", "--summary", str(STUB_SUMMARY), "--out", str(out)]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema"] == aghri.SELECTION_SCHEMA
    assert payload["summary_sha256"] == hashlib.sha256(STUB_SUMMARY.read_bytes()).hexdigest()
    assert payload["n_frames"] == 15
    assert payload["max_frames_per_seq"] == 3
    assert [item["seq_no"] for item in payload["selected"]] == [1, 2, 3, 4, 5]
    assert {item["declared_count"] for item in payload["selected"]} == {1, 2, 3, 4, 5}
    assert [item["seq"] for item in payload["excluded"]] == [
        "in_straw_2push_diff_st_10_31_2024_1_label",
        "in_vine_3pick_diff_mv_11_03_2024_3_label",
    ]
    assert payload["report"]["n_frames_selected"] == 15


def test_build_full_stub(aghri_root: Path) -> None:
    cases, report = aghri.build_aghri_cases(aghri_root)
    # 15 кадров, 5 последовательностей, ≤3 кадра на последовательность
    assert len(cases) == 15
    assert report["n_cases"] == 15
    assert report["n_sequences"] == 5
    assert report["gold_coverage"] == EXPECTED_COVERAGE
    assert all(v <= 3 for v in report["frames_per_sequence"].values())
    assert len(report["frames_per_sequence"]) == 5
    by_id = {case.case_id: case for case in cases}
    assert sorted(by_id) == sorted(EXPECTED_GOLD)
    for case in cases:
        seq_no = int(case.case_id.split("-")[2].removeprefix("SEQ"))
        assert case.source == "aghri"
        assert case.track == "audience"
        assert case.prompt.mode == "deployed"
        assert case.prompt.user_text == aghri.PROMPT_TEXT
        assert case.prompt.language == "ru"
        assert case.candidates == ()
        assert case.allowed_tools == ()
        assert case.gold == {"type": "count", "count": EXPECTED_GOLD[case.case_id]}
        assert case.split_group_id == f"g-aghri-seq-{seq_no:04d}"
        # один RGB-кадр на кейс, fisheye/depth/3D/gaze не в схеме:
        # eval_data/aghri/<seq>/sensor_data/cam_zed_rgb/<frame>.png
        parts = case.media.path.split("/")
        assert len(parts) == 6
        assert parts[:2] == ["eval_data", "aghri"]
        assert parts[3:5] == ["sensor_data", "cam_zed_rgb"]
        seq_dir, frame_name = parts[2], parts[5]
        assert seq_dir.endswith("_label")
        assert case.media.path.startswith(f"{aghri.DEFAULT_MEDIA_PREFIX}/")
        assert case.media.format == "png"
        # sha256 — от байтов кадра (tmp-копия совпадает со stub)
        stub_frame = aghri_root / seq_dir / aghri.FRAMES_REL / frame_name
        assert case.media.sha256 == hashlib.sha256(stub_frame.read_bytes()).hexdigest()
        # срезы
        environment, robot_state = EXPECTED_ENV_STATE[seq_no]
        assert case.slices["count_bucket"] == str(case.gold["count"])
        assert case.slices["declared_count"] == seq_no  # в stub: счётчик == номер строки
        assert case.slices["environment"] == environment
        assert case.slices["robot_state"] == robot_state
        assert case.slices["split"] == EXPECTED_SPLIT[seq_no]
        # provenance
        assert case.provenance is not None
        assert "CC BY 4.0" in case.provenance.license
        assert "no redistribution" in case.provenance.rights_note
        assert case.provenance.version.startswith("dataset_summary.csv sha256:")
        # схема round-trip (замороженный кейс проходит строгую валидацию)
        assert schema.case_from_dict(schema.case_to_dict(case)) == case


def test_load_protocol(aghri_root: Path) -> None:
    cases = aghri.load(aghri_root)
    assert len(cases) == 15
    assert {case.case_id for case in cases} == set(EXPECTED_GOLD)


def test_cli_build_writes_manifest_sidecar_and_provenance(
    aghri_root: Path, tmp_path: Path
) -> None:
    out = tmp_path / "manifest" / "aghri_15.jsonl"
    assert (
        aghri.main(
            [
                "build",
                "--data-root",
                str(aghri_root),
                "--out",
                str(out),
            ]
        )
        == 0
    )
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 15
    for line in lines:
        schema.case_from_dict(json.loads(line))  # каждая строка — валидный кейс
    sidecar = out.with_name(out.name + ".sidecar.json")
    assert sidecar.is_file()
    report = json.loads(sidecar.read_text(encoding="utf-8"))
    assert report["gold_coverage"] == EXPECTED_COVERAGE
    # PROVENANCE.md — в корне данных (контракт дизайна)
    provenance = aghri_root / "PROVENANCE.md"
    assert provenance.is_file()
    text = provenance.read_text(encoding="utf-8")
    assert aghri.DOI_URL in text
    assert aghri.LICENSE_LINE in text
    assert "AGHRI-SEQ-0005-F001" in text
    # part-level архивы (не весь ~70 GB релиза)
    assert "unzip -q dataset_part1.zip" in text
    assert "unzip -q dataset_part2.zip" in text
    assert "unzip -q dataset_part3.zip" in text
    assert "dataset_part4.zip" not in text


def test_build_without_selection_raises(tmp_path: Path) -> None:
    root = tmp_path / "no-sel"
    shutil.copytree(STUB_ROOT, root)
    (root / aghri.SUMMARY_NAME).unlink()  # только данные без плана
    with pytest.raises(aghri.AghriAdapterError, match="сначала `plan`"):
        aghri.build_aghri_cases(root)


def test_build_wrong_selection_schema_raises(aghri_root: Path) -> None:
    selection = aghri_root / aghri.SELECTION_NAME
    payload = json.loads(selection.read_text(encoding="utf-8"))
    payload["schema"] = "other/9"
    selection.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(aghri.AghriAdapterError, match="schema"):
        aghri.build_aghri_cases(aghri_root)


def test_build_missing_frame_raises(aghri_root: Path) -> None:
    frame = aghri_root / "footpath1_1walk_st_10_24_2024_1_label" / aghri.FRAMES_REL
    (frame / "1729824000000000001.png").unlink()
    with pytest.raises(aghri.AghriAdapterError, match="кадр не найден"):
        aghri.build_aghri_cases(aghri_root)


def test_build_empty_ann_raises(aghri_root: Path) -> None:
    ann = aghri_root / "footpath1_1walk_st_10_24_2024_1_label" / aghri.ANNOTATIONS_REL
    ann.write_text("[]", encoding="utf-8")
    with pytest.raises(aghri.AghriAdapterError, match="аннотации пусты"):
        aghri.build_aghri_cases(aghri_root)


def test_build_read_only(aghri_root: Path) -> None:
    """build_aghri_cases не пишет в каталог данных (PROVENANCE — только CLI)."""

    def _snapshot(root: Path) -> dict[str, str]:
        out: dict[str, str] = {}
        for p in sorted(root.rglob("*")):
            if p.is_file():
                out[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
        return out

    before = _snapshot(aghri_root)
    aghri.build_aghri_cases(aghri_root)
    assert _snapshot(aghri_root) == before


# ---------------------------------------------------------------------------
# PROVENANCE и команды загрузки
# ---------------------------------------------------------------------------


def test_download_instructions() -> None:
    text = aghri.download_instructions(["dataset_part3.zip", "dataset_part1.zip"])
    assert aghri.DOI_URL in text
    assert "CC BY 4.0" in text
    assert "не скачивает" in text
    assert "dataset_part1.zip" in text
    assert "unzip -q dataset_part1.zip" in text
    assert "unzip -q dataset_part3.zip" in text


def test_provenance_text(aghri_root: Path) -> None:
    cases, report = aghri.build_aghri_cases(aghri_root)
    text = aghri.provenance_text(cases, report)
    assert aghri.LICENSE_LINE in text
    assert aghri.DOI_URL in text
    assert aghri.TOOLS_REPO_URL in text
    assert report["summary_sha256"] in text
    for case_id, _count in EXPECTED_GOLD.items():
        assert case_id in text
    assert str(cases[0].slices["declared_count"]) in text


# ---------------------------------------------------------------------------
# Формат v2-релиза (страница DOI, 2026-08-21): «Scene Name», «Number of
# Humans», целые номера частей в колонке part, Environment/Robot movements,
# хвостовые пустые строки.
# ---------------------------------------------------------------------------

V2_SUMMARY_CSV = (
    "Scene Name,Environment,Number of Humans,Human activities,Human "
    "movements,Robot movements,Occlusions,Recording Duration (s),Dataset "
    "compressed part it belongs to\n"
    "footpath1_1walk_1stand_st_11_12_2024_1_label,Footpath,2,walking + "
    "standing,moving away from robot,still,none,16.29,1\n"
    "in_straw_2pick_st_11_10_2024_1_label,Inside Strawberry Polytunnel,2,"
    "picking,still,still,partial,20.0,1\n"
    "in_vine_3walk_mv_11_11_2024_1_label,Inside Vineyard,3,walking,moving "
    "towards robot,moving,none,25.5,1\n"
    "footpath1_1walk_st_11_13_2024_1_label,Footpath,1,walking,still,"
    "still,none,10.0,2\n"
    "in_vine_1walk_st_11_14_2024_1_label,Inside Vineyard,1,walking,"
    "moving away from robot,still,none,12.0,3\n"
    "out_vine_4swap_walk_st_ly_11_06_2024_1_label,Outside Vineyard,4,"
    "swapping,still,still,none,30.0,10\n"
    "out_vine_5walk_talk_push_st_ly_11_06_2024_2_label,Outside Vineyard,"
    "5,walking,still,still,none,40.0,10\n"
    "\n"
    "\n"
)


def _write_v2_summary(tmp_path: Path) -> Path:
    """Временный summary в реальном формате v2-релиза."""
    summary = tmp_path / "dataset_summary.csv"
    summary.write_text(V2_SUMMARY_CSV, encoding="utf-8")
    return summary


def test_v2_summary_parsing(tmp_path: Path) -> None:
    """Заголовки v2, целые части, env/robot-колонки, хвостовые пустые строки."""
    rows = aghri.load_summary_csv(_write_v2_summary(tmp_path))
    assert len(rows) == 7  # 9 записей минус 2 пустые хвостовые
    first = rows[0]
    assert first.seq == "footpath1_1walk_1stand_st_11_12_2024_1_label"
    assert first.declared_count == 2
    assert first.count_source == "csv"
    assert first.archive == "dataset_part1.zip"  # целое 1 → имя архива
    assert first.environment == "Footpath"
    assert first.robot_state == "still"
    assert first.frames is None  # колонки Number of Frames в v2 нет
    assert first.split is None
    last = rows[-1]
    assert last.declared_count == 5
    assert last.archive == "dataset_part10.zip"


def test_archive_normalization_helpers() -> None:
    """_archive_to_zip / _zip_to_part: целые ↔ имена архивов."""
    assert aghri._archive_to_zip("3") == "dataset_part3.zip"
    assert aghri._archive_to_zip("10") == "dataset_part10.zip"
    assert aghri._archive_to_zip("dataset_part2.zip") == "dataset_part2.zip"
    assert aghri._archive_to_zip("") is None
    assert aghri._archive_to_zip(None) is None
    assert aghri._zip_to_part("dataset_part10.zip") == 10
    assert aghri._zip_to_part("other.zip") is None
    assert aghri._zip_to_part(None) is None


def test_v2_parts_filter_selects_within_scope(tmp_path: Path) -> None:
    """--parts 1,2,3 + --required 1,2,3: часть 10 исключается, план сходится."""
    rows = aghri.load_summary_csv(_write_v2_summary(tmp_path))
    selected, extra = aghri.select_sequences(
        rows, 5, 3, parts=(1, 2, 3), required_counts=(1, 2, 3)
    )
    report = extra["report"]
    seqs = {item.seq for item in selected}
    assert "out_vine_4swap_walk_st_ly_11_06_2024_1_label" not in seqs
    assert "out_vine_5walk_talk_push_st_ly_11_06_2024_2_label" not in seqs
    assert report["parts"] == [1, 2, 3]
    assert report["required_counts"] == [1, 2, 3]
    excluded_seqnames = {item["seq"] for item in extra["excluded"]}
    assert "out_vine_4swap_walk_st_ly_11_06_2024_1_label" in excluded_seqnames


def test_v2_parts_filter_default_required_raises(tmp_path: Path) -> None:
    """Части 1–3 без override покрытия: 4 и 5 отсутствуют → ошибка."""
    rows = aghri.load_summary_csv(_write_v2_summary(tmp_path))
    with pytest.raises(aghri.AghriAdapterError, match="покрытие сбоем"):
        aghri.select_sequences(rows, 5, 3, parts=(1, 2, 3))


def test_build_slices_prefer_csv_columns(aghri_root: Path) -> None:
    """Срезы: значения из CSV (в selection.json) бьют парсинг имени."""
    import json

    selection_path = aghri_root / aghri.SELECTION_NAME
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    for item in selection["selected"]:
        item["environment"] = "CSV-ENV"
        item["robot_state"] = "csv_state"
    selection_path.write_text(
        json.dumps(selection, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    cases, _ = aghri.build_aghri_cases(aghri_root)
    assert cases, "ожидали кейсы"
    for case in cases:
        assert case.slices["environment"] == "CSV-ENV"
        assert case.slices["robot_state"] == "csv_state"
