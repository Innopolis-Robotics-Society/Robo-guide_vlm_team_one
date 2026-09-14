"""Адаптер DP/Deepoint (Taiga #10, T6): разбор меток, выбор, сборка кейсов.

Фикстур: метки в `test/data/dp_stub/` (коммичены), кадры и venue-info
генерируются в tmp. Сети и реального датасета нет.
"""

from __future__ import annotations

import hashlib
import pickle
import shutil
import struct
import zipfile
from pathlib import Path

import pytest

from guide_robot_llm.eval.adapters import dp

STUB_LABELS = Path(__file__).resolve().parents[1] / "test" / "data" / "dp_stub" / "labels"

# Геометрия, точная в бинариге: смещения 2^-3, глубины 2^2/2^3/2^3,
# фокус 2^9, центр (320, 240) → ожидаемые боксы посчитаны от руки.
# Порядок строк в corners.npy обязан совпадать с valid_ids: [10, 20, 30, 40].
# Маркеры 20/40 -- вне вида всех камер фикстуры (только для списка кандидатов).
_W, _H = 640, 480
_K = ((512.0, 0.0, 320.0), (0.0, 512.0, 240.0), (0.0, 0.0, 1.0))
_R_I = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
_M10 = ((0.125, 0.125, 0.0), (0.125, -0.125, 0.0), (-0.125, 0.125, 0.0), (-0.125, -0.125, 0.0))
_M20 = ((50.125, 50.125, 0.0), (50.125, 49.875, 0.0), (49.875, 50.125, 0.0), (49.875, 49.875, 0.0))
_M30 = ((2.125, 0.125, 0.0), (2.125, -0.125, 0.0), (1.875, 0.125, 0.0), (1.875, -0.125, 0.0))
_M40 = ((55.125, 45.125, 0.0), (55.125, 44.875, 0.0), (54.875, 45.125, 0.0), (54.875, 44.875, 0.0))


def _cam(t: tuple) -> dict:
    return {"R": _R_I, "t": list(t), "K": _K, "dist": [0.0] * 5, "width": _W, "height": _H}


def _jpeg_bytes(width: int = _W, height: int = _H) -> bytes:
    """Минимальный JPEG (SOI + SOF0 + EOI) -- достаточно для `jpeg_size`."""
    sof = (
        b"\xff\xc0"
        + (8 + 3).to_bytes(2, "big")
        + bytes([8])
        + height.to_bytes(2, "big")
        + width.to_bytes(2, "big")
        + bytes([1, 1, 0x11, 0])
    )
    return b"\xff\xd8" + sof + b"\xff\xd9"


def _npy_bytes(flat: list, shape: tuple, descr: str) -> bytes:
    """Формат .npy v1.0 (magic + строка-заголовок + payload)."""
    unit = {"<f8": "d", "<i4": "i"}[descr]
    header = f"{{'descr': '{descr}', 'fortran_order': False, 'shape': {shape!r}}}".encode()
    pad = (64 - (10 + len(header) + 1) % 64) % 64
    header = header + b" " * pad + b"\x00"
    return (
        b"\x93NUMPY\x01\x00"
        + len(header).to_bytes(2, "little")
        + header
        + struct.pack(f"<{len(flat)}{unit}", *flat)
    )


def _write_venue_info(venue_dir: Path) -> None:
    info = venue_dir / "venue-info"
    info.mkdir(parents=True)
    cams = {str(i): _cam((100.0, 0.0, -5.0)) for i in range(15)}
    cams.update(
        {
            "0": _cam((0.0, 0.0, -8.0)),
            "2": _cam((2.0, 0.0, -2.0)),
            "3": _cam((0.0, 0.0, -4.0)),
        }
    )
    with open(info / "params.pickle", "wb") as fh:
        pickle.dump(cams, fh)
    flat = [v for corner in list(_M10) + list(_M20) + list(_M30) + list(_M40) for v in corner]
    with zipfile.ZipFile(info / "marker_corners.npz", "w") as npz:
        npz.writestr("valid_ids.npy", _npy_bytes([10, 20, 30, 40], (4,), "<i4"))
        npz.writestr("corners.npy", _npy_bytes(flat, (4, 4, 3), "<f8"))


def _build_stub_tree(root: Path) -> Path:
    """Метки из фикстура + кадры/venue-info, сгенерированные в tmp."""
    labels = root / "labels"
    labels.mkdir(parents=True)
    for venue_dir in sorted(STUB_LABELS.iterdir()):
        target = labels / venue_dir.name
        target.mkdir()
        for f in venue_dir.iterdir():
            shutil.copyfile(f, target / f.name)
    fr = root / "frames"
    # 01-01: take1/m10 → mid(10..15)=12 → файл 13, камера 3; take2/m30 →
    # mid(5..10)=7 → файл 8, камера 2. 01-02: take1/m50 → mid(10..30)=20
    # → файл 21, камера 0 (venue-info нет → деградация).
    (fr / "2099-01-01-lab" / "take1" / "03").mkdir(parents=True)
    (fr / "2099-01-01-lab" / "take1" / "03" / "0000000013.jpg").write_bytes(_jpeg_bytes())
    (fr / "2099-01-01-lab" / "take2" / "02").mkdir(parents=True)
    (fr / "2099-01-01-lab" / "take2" / "02" / "0000000008.jpg").write_bytes(_jpeg_bytes())
    _write_venue_info(fr / "2099-01-01-lab")
    (fr / "2099-01-02-lab" / "take1" / "00").mkdir(parents=True)
    (fr / "2099-01-02-lab" / "take1" / "00" / "0000000021.jpg").write_bytes(_jpeg_bytes())
    return root


# ---------------------------------------------------------------------------
# Разбор меток
# ---------------------------------------------------------------------------


def test_parse_take_labels_decimation_and_comments() -> None:
    labels = dp.parse_take_labels(STUB_LABELS / "2099-01-01-lab" / "take1.txt")
    assert (labels.valid_start, labels.valid_end) == (5, 50)  # сырое 10..100, filt=2
    assert labels.take == "take1"
    assert labels.events == (
        dp.PointingEvent(10, 10, 15, "r"),
        dp.PointingEvent(20, 25, 30, "l"),
    )


def test_read_filt_missing_file_defaults_to_one() -> None:
    assert dp._read_filt(STUB_LABELS / "nope" / "timeinfo.yaml") == 1
    assert dp._read_filt(STUB_LABELS / "2099-01-01-lab" / "timeinfo.yaml") == 2


def test_parse_take_labels_bad_row_raises(tmp_path: Path) -> None:
    bad = tmp_path / "take1.txt"
    bad.write_text("0, 100\nabc, 2, 4, r\n", encoding="utf-8")
    with pytest.raises(dp.DpAdapterError):
        dp.parse_take_labels(bad)


# ---------------------------------------------------------------------------
# Маркеры → id; проекция
# ---------------------------------------------------------------------------


def test_marker_to_exhibit_stable_rule() -> None:
    assert dp.marker_to_exhibit(19) == "exhibit_19"


def test_project_marker_box_exact_geometry() -> None:
    cam3 = _cam((0.0, 0.0, -4.0))
    box, area = dp.project_marker_box(_M10, cam3, _W, _H)
    assert box == (304, 224, 336, 256)
    assert area == 1089.0
    # Далекая камера -- маркер вне кадра.
    assert dp.project_marker_box(_M10, _cam((100.0, 0.0, -5.0)), _W, _H) == (None, 0.0)
    # Камера «за» маркером -- невидим.
    assert dp.project_marker_box(_M10, _cam((0.0, 0.0, 5.0)), _W, _H) == (None, 0.0)


def test_jpeg_size_minimal_jpeg() -> None:
    assert dp.jpeg_size_from_bytes(_jpeg_bytes()) == (640, 480)
    assert dp.jpeg_size_from_bytes(b"nope") is None


def test_load_venue_info_camera_without_K_degrades(tmp_path: Path) -> None:
    # Реальный params.pickle может не иметь K (код авторов K не использует) --
    # venue деградирует, сборка не падает.
    info = tmp_path / "venue-info"
    info.mkdir()
    with open(info / "params.pickle", "wb") as fh:
        pickle.dump({"0": {"R": _R_I, "t": [0.0, 0.0, -8.0], "filepath": "x"}}, fh)
    with zipfile.ZipFile(info / "marker_corners.npz", "w") as npz:
        npz.writestr("valid_ids.npy", _npy_bytes([10], (1,), "<i4"))
        flat = [v for corner in _M10 for v in corner]
        npz.writestr("corners.npy", _npy_bytes(flat, (1, 4, 3), "<f8"))
    assert dp.load_venue_info(tmp_path) is None


# ---------------------------------------------------------------------------
# Выбор событий
# ---------------------------------------------------------------------------


def _stub_venues() -> dict:
    venues: dict[str, dict[str, dp.TakeLabels]] = {}
    for venue_dir in sorted(STUB_LABELS.iterdir()):
        venues[venue_dir.name] = {
            f.stem: dp.parse_take_labels(f) for f in sorted(venue_dir.glob("take*.txt"))
        }
    return venues


def test_select_events_no_shared_takes_and_min_interval() -> None:
    chosen = dp.select_events(_stub_venues(), n_cases=20)
    takes = [(v, t) for v, t, _ in chosen]
    assert len(takes) == 3  # валидных событий в фикстуре ровно три
    assert len(set(takes)) == 3  # take не переиспользуется (утечки)
    # take3 (интервал 1 кадр < 5) не попал; из take1 -- m10, a m20 -- нет.
    assert ("2099-01-01-lab", "take3") not in takes
    assert sorted(e.marker_id for *_, e in chosen) == [10, 30, 50]


# ---------------------------------------------------------------------------
# Сборка кейсов
# ---------------------------------------------------------------------------


def test_build_dp_cases_full_stub(tmp_path: Path) -> None:
    root = _build_stub_tree(tmp_path / "dp")
    cases, report = dp.build_dp_cases(root, n_cases=20)

    assert [c.case_id for c in cases] == [
        "DP-2099-01-01-lab-take1-10",
        "DP-2099-01-01-lab-take2-30",
        "DP-2099-01-02-lab-take1-50",
    ]
    c10, c30, c50 = cases
    # Маркер 10: лучшая камера 3 (площадь 1089 > 289 у камеры 0).
    assert (c10.slices["camera_id"], c10.slices["camera_rule"]) == (3, "auto-max-area")
    assert c10.gold["box_px"] == [304, 224, 336, 256]
    assert c10.slices["marker_area_px"] == 1089
    # Маркер 30: лучшая камера 2 (4225).
    assert (c30.slices["camera_id"], c30.slices["camera_rule"]) == (2, "auto-max-area")
    assert c30.gold["box_px"] == [288, 208, 352, 272]
    # Venue без venue-info: честная деградация в камеру 00, box_px null.
    assert (c50.slices["camera_id"], c50.slices["camera_rule"]) == (0, "fallback-fixed-00")
    assert c50.gold["box_px"] is None
    assert any(d["take"] == "take1" and d["venue"] == "2099-01-02-lab" for d in report["degraded"])

    # Кандидаты: все маркеры вена (venue-info) / из меток (без venue-info).
    assert c10.candidates == ("exhibit_10", "exhibit_20", "exhibit_30", "exhibit_40")
    assert c10.gold["target_id"] == "exhibit_10"
    assert c10.gold["distractors"] == ["exhibit_20", "exhibit_30", "exhibit_40"]
    assert c50.candidates == ("exhibit_50",)

    # Мультимодальность: один кадр, sha256 настоящего файла, путь-контракт.
    assert c10.media.format == "jpg"
    assert c10.media.path == "eval_data/dp/frames/2099-01-01-lab/take1/03/0000000013.jpg"
    frame = root / "frames" / "2099-01-01-lab" / "take1" / "03" / "0000000013.jpg"
    assert c10.media.sha256 == hashlib.sha256(frame.read_bytes()).hexdigest()

    # In-схема: кейс проходит валидацию при реру (round-trip).
    for c in cases:
        data = dp.case_to_dict(c)
        assert "depth" not in data["media"]["path"] and "keypoints" not in data["media"]["path"]
        assert dp.case_from_dict(data).case_id == c.case_id
    assert report["cameras"] == {"auto-max-area": 2, "fallback-fixed-00": 1}
    assert report["exhibit_map"] == {"10": "exhibit_10", "30": "exhibit_30", "50": "exhibit_50"}


def test_build_dp_cases_missing_labels_raises(tmp_path: Path) -> None:
    with pytest.raises(dp.DpAdapterError):
        dp.build_dp_cases(tmp_path)


def test_build_dp_cases_missing_frame_raises(tmp_path: Path) -> None:
    root = _build_stub_tree(tmp_path / "dp")
    (root / "frames" / "2099-01-01-lab" / "take1" / "03" / "0000000013.jpg").unlink()
    with pytest.raises(dp.DpAdapterError, match="кадр не найден"):
        dp.build_dp_cases(root, n_cases=20)


# ---------------------------------------------------------------------------
# PROVENANCE.md
# ---------------------------------------------------------------------------


def test_provenance_text_lists_licenses_hashes_and_steps(tmp_path: Path) -> None:
    root = _build_stub_tree(tmp_path / "dp")
    cases, report = dp.build_dp_cases(root, n_cases=20)
    text = dp.provenance_text(cases, report)
    assert dp.LICENSE_LINE in text
    assert "2099-01-01" in text and "2099-01-02" in text
    assert "e1e0f881ac95a0b38f12c006ab7517a7" in text  # labels.zip
    assert "d1e46d1c7e7d5a0bd19b44de145e7655" in text  # keypoints.zip (вне кейсов)
    assert "не скачивает" in text  # правила: агент не скачивает данные
    assert '"10": "exhibit_10"' in text  # таблица marker→exhibit набора
