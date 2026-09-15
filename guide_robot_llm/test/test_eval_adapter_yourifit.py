"""Адаптер YouRefIt (Taiga #10, T8): авторский протокол, unmodified, целостность.

Фикстура: ``test/data/yri_stub/`` (коммичена) — структурный зеркаль
верифицированного ``yourefit_test.pth`` (yixchen/YouRefIt_ERU, main,
проверено 2026-09-15) с синтетическим текстом (контент датасета в
репозиторий не попадает). Сети и реального датасета нет.
"""

from __future__ import annotations

import hashlib
import pickle
import zipfile
from pathlib import Path

import pytest

from guide_robot_llm.eval import schema
from guide_robot_llm.eval.adapters import yourifit

STUB_ROOT = Path(__file__).resolve().parents[1] / "test" / "data" / "yri_stub"
STUB_SPLIT = STUB_ROOT / "splits" / "yourefit_test.pth"

# Ожидаемая выборка (первый инстанс каждой группы (env, session)):
# (case_id, session, phrase, target_id, box_px)
EXPECTED_SELECTION: list[tuple[str, str, str, str, list[int]]] = [
    ("YRI-cs-101-500", "cs-101", "the pillow", "yri-cs-101-t1", [75, 668, 448, 1518]),
    (
        "YRI-cs-102-300",
        "cs-102",
        "this is a white scarf on the bed",
        "yri-cs-102-t1",
        [0, 0, 500, 300],
    ),
    (
        "YRI-cs-104-700",
        "cs-104",
        "the garbage can next to me",
        "yri-cs-104-t1",
        [5, 802, 152, 1878],
    ),
    ("YRI-lab-103-200", "lab-103", "book", "yri-lab-103-t1", [100, 100, 300, 300]),
    ("YRI-lab-105-100", "lab-105", 'a letter "m"', "yri-lab-105-t1", [600, 500, 900, 750]),
]
UNSELECTED_FILE = "cs_p_101_2_0_900.jpg"  # дубль группы (cs, 101)


def _entries() -> list[tuple]:
    with zipfile.ZipFile(STUB_SPLIT) as zf:
        return pickle.loads(zf.read("archive/data.pkl"))


@pytest.fixture()
def stub_entries() -> list[tuple]:
    return _entries()


@pytest.fixture()
def yri_root(tmp_path: Path) -> Path:
    """Каталог данных: stub-сплит + все изображения (read-only дерево)."""
    root = tmp_path / "yri"
    (root / "splits").mkdir(parents=True)
    (root / "images").mkdir()
    (root / "splits" / "yourefit_test.pth").write_bytes(STUB_SPLIT.read_bytes())
    for img in (STUB_ROOT / "images").glob("*.jpg"):
        (root / "images" / img.name).write_bytes(img.read_bytes())
    return root


def test_author_prompt_is_unmodified_phrase() -> None:
    """Фраза в вопросе дословно (unmodified), вопрос — harness-надстройка."""
    prompt = yourifit.author_prompt("the grey shelf")
    assert "the grey shelf" in prompt
    assert prompt == (
        "The person in the image says: 'the grey shelf'. "
        "Can you show me the object the person is referring to?"
    )
    # Кавычки внутри фразы не ломают шаблон (реальная фраза 'a letter "m"')
    assert yourifit.author_prompt('a letter "m"') == (
        "The person in the image says: 'a letter \"m\"'. "
        "Can you show me the object the person is referring to?"
    )


def test_built_prompt_contains_verbatim_phrase(yri_root: Path) -> None:
    cases, _ = yourifit.build_yourifit_cases(yri_root, expected_split_sha256=None)
    case = next(c for c in cases if c.case_id == "YRI-lab-105-100")
    assert case.prompt.user_text == yourifit.author_prompt('a letter "m"')
    assert 'a letter "m"' in case.prompt.user_text


def test_candidate_ids_and_gold(yri_root: Path) -> None:
    cases, _ = yourifit.build_yourifit_cases(yri_root, expected_split_sha256=None)
    by_id = {c.case_id: c for c in cases}
    for case_id, _session, phrase, target_id, box_px in EXPECTED_SELECTION:
        case = by_id[case_id]
        assert case.candidates == (target_id,)  # один референт в аннотации
        assert case.gold["type"] == "target_box"
        assert case.gold["target_id"] == target_id
        assert case.gold["box_px"] == box_px  # [x1,y1,w,h] → [x0,y0,x1,y1]
        assert case.gold["distractors"] == []
        assert case.slices["answer_map"] == {phrase: target_id}
        assert case.slices["n_distractors"] == 0


EXPECTED_FILES = (
    "cs_p_101_1_0_500.jpg",
    "cs_p_102_3_0_300.jpg",
    "lab_p_103_4_0_200.jpg",
    "cs_p_104_5_0_700.jpg",
    "lab_p_105_6_0_100.jpg",
)


def test_selection_first_instance_per_group(stub_entries: list[tuple]) -> None:
    selected = yourifit.select_yourifit_entries(stub_entries)
    assert [e[0] for e in selected] == list(EXPECTED_FILES)
    assert UNSELECTED_FILE not in (e[0] for e in selected)  # дубль группы не выбирается


def test_selection_not_enough_groups_raises(stub_entries: list[tuple]) -> None:
    with pytest.raises(yourifit.YourifitAdapterError, match="недостаточно"):
        yourifit.select_yourifit_entries(stub_entries, n_cases=6)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda e: (*e[:2], [75, 668, 0, 850], *e[3:]),  # w = 0
        lambda e: (*e[:2], [75, 668, 373, -850], *e[3:]),  # h < 0
        lambda e: ("bad_name.jpg", *e[1:]),  # имя вне формата
        lambda e: (*e[:3], "", *e[4:]),  # пустая фраза
        lambda e: (*e[:4], "not-a-list"),  # attri не список
    ],
    ids=["zero-w", "neg-h", "bad-name", "empty-phrase", "bad-attri"],
)
def test_selection_invalid_entry_raises(stub_entries: list[tuple], mutate) -> None:
    bad = mutate(stub_entries[0])
    with pytest.raises(yourifit.YourifitAdapterError):
        yourifit.select_yourifit_entries(stub_entries[:1] + [bad] + stub_entries[1:5])


def test_load_split_bad_archive_raises(tmp_path: Path) -> None:
    p = tmp_path / "bad.pth"
    p.write_bytes(b"not a zip")
    with pytest.raises(yourifit.YourifitAdapterError, match="не zip"):
        yourifit.load_split(p)
    z = tmp_path / "noinner.pth"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("other.bin", b"")
    with pytest.raises(yourifit.YourifitAdapterError, match="archive/data.pkl"):
        yourifit.load_split(z)


def test_build_cases_full_stub(yri_root: Path) -> None:
    cases, report = yourifit.build_yourifit_cases(yri_root, expected_split_sha256=None)
    assert len(cases) == 5
    assert [c.case_id for c in cases] == [item[0] for item in sorted(EXPECTED_SELECTION)]
    for c in cases:
        assert c.source == "yourifit"
        assert c.track == "pointing"
        assert c.prompt.mode == "freeform"
        assert c.prompt.language == "en"
        assert not c.allowed_tools
        img = c.media.path.rsplit("/", 1)[-1]
        assert c.media.path == f"eval_data/yourifit/images/{img}"
        assert c.media.format == "jpg"
        expected_hash = hashlib.sha256((STUB_ROOT / "images" / img).read_bytes()).hexdigest()
        assert c.media.sha256 == expected_hash
        # Provenance: no-modification-clause + ссылка на регистрацию (T8)
        assert c.provenance is not None
        assert "non-commercial" in c.provenance.license
        assert "no redistribution" in c.provenance.rights_note
        assert "registration:" in c.provenance.rights_note
        assert "yourefit_test.pth sha256:" in c.provenance.version
        assert c.split_group_id == f"g-yri-{c.case_id.split('-')[1]}-{c.case_id.split('-')[2]}"
    # Схема round-trip (замороженный манифест проходит валидацию)
    for c in cases:
        assert schema.case_from_dict(schema.case_to_dict(c)) == c
    # Отчёт
    assert report["n_cases"] == 5
    assert report["total_instances"] == 6
    assert report["n_capture_groups"] == 5
    assert report["split_sha256"] == hashlib.sha256(STUB_SPLIT.read_bytes()).hexdigest()
    assert len(report["selected"]) == 5


def test_build_with_registration_ref(yri_root: Path) -> None:
    cases, _ = yourifit.build_yourifit_cases(
        yri_root, expected_split_sha256=None, registration_ref="2026-09-15 email #123"
    )
    assert all("2026-09-15 email #123" in c.provenance.rights_note for c in cases)


def test_build_missing_split_raises(tmp_path: Path) -> None:
    root = tmp_path / "empty"
    root.mkdir()
    with pytest.raises(yourifit.YourifitAdapterError, match="не найден"):
        yourifit.build_yourifit_cases(root, expected_split_sha256=None)


def test_build_missing_image_raises(yri_root: Path) -> None:
    (yri_root / "images" / "cs_p_101_1_0_500.jpg").unlink()
    with pytest.raises(yourifit.YourifitAdapterError, match="не найдено изображение"):
        yourifit.build_yourifit_cases(yri_root, expected_split_sha256=None)


def test_build_changed_split_raises(yri_root: Path) -> None:
    """Пин sha256: файл, отличающийся от верифицированного, сборку останавливает."""
    with pytest.raises(yourifit.YourifitAdapterError, match="изменена"):
        yourifit.build_yourifit_cases(yri_root)  # дефолт = пин верифицированного файла


def test_no_modification_of_data_dir(yri_root: Path) -> None:
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

    before = _snapshot(yri_root)
    yourifit.build_yourifit_cases(yri_root, expected_split_sha256=None)
    assert _snapshot(yri_root) == before


def test_provenance_text_lists_license_hash_and_steps(yri_root: Path) -> None:
    cases, report = yourifit.build_yourifit_cases(yri_root, expected_split_sha256=None)
    text = yourifit.provenance_text(cases, report)
    assert yourifit.LICENSE_LINE in text
    assert yourifit.REGISTRATION_FORM_URL in text
    assert yourifit.LICENSE_URL in text
    assert "не скачивает" in text
    assert report["split_sha256"] in text
    assert f"sha256sum eval_data/yourifit/{yourifit.SPLIT_REL_PATH}" in text
    assert "yri-cs-101-t1" in text
    for case_id, *_ in EXPECTED_SELECTION:
        assert case_id in text
