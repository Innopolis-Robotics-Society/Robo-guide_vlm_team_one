"""Адаптер DP/Deepoint (Taiga #10, T6): 20 pointing-кейсов в единой схеме.

Исходник: DP Dataset (Kyoto Univ., Deepoint) — CC BY-NC 4.0, 5 дней
записей, 15 камер на take, марки (маркеры-«экспонаты») с 3D-координатами.
Выбор цели по жесту-указанию сводится к выбору маркера — это и есть
замена «экспоната» стабильным синтетическим id по правилу
`marker_<id> → exhibit_<id>` (таблица фиксируется в `exhibit_map.json`
при сборке манифеста).

Правила (дизайн `docs/eval_harness_design.md` + PROVENANCE.md):
* один кейс = один take (утечки: take/sequence никогда не делятся);
* один кадр из одной камеры (midpoint pointing-интервала, номер файла
  = кадр+1, ffmpeg 1-indexed, как в коде авторов);
* камера `auto`: проекция 3D-углов маркера во все 15 камер по
  `venue-info` (params.pickle + marker_corners.npz); берётся камера,
  в которой маркер целиком в кадре и с наибольшей площадью; без
  venue-info — фиксированная камера `00` с `box_px: null` (честная
  деградация: точность по id, без IoU);
* в модель — ТОЛЬКО RGB-кадр: depth/3D/keypoints в кейс не попадают
  (проверка в тестах и в инварианте сборки).

Сборка манифеста (агент НИКОГДА не скачивает; данные готовит пользователь):

    # Google Drive-папка (7 zip, md5sums в data/README.md; keypoints.zip
    # не нужен -- ключепоинты/3D в кейс не попадают по дизайну):
    #   https://drive.google.com/drive/folders/1W_49HId_2FLFH0X9Ry8QiTTyaVt2Y0ks
    # 1) скачать 5 frame-zip'ов + labels.zip и сверить md5sum;
    # 2) распаковать: frame-архивы → eval_data/dp/frames_squashed/ (10
    #    squashfs-файлов по венам), labels.zip → eval_data/dp/labels/;
    # 3) `unsquashfs -d frames/<venue> frames_squashed/<venue>` (squashfs-tools);
    # 4) сборка:
    python -m guide_robot_llm.eval.adapters.dp \
        --data-root guide_robot_llm/eval_data/dp \
        --out guide_robot_llm/eval_manifests/dp_20.jsonl

После сборки в корне данных пишется `PROVENANCE.md` (лицензия, хэши,
правила выбора, команды) -- см. `provenance_text`.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import pickle
import re
import struct
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from guide_robot_llm.eval.schema import Case, case_from_dict, case_to_dict

# Лицензионная строка -- датированная верификация T1 (план vlm-bench-50).
LICENSE_LINE = "CC BY-NC 4.0 (verified 2026-09-15, docs/vlm_deixis_audience_datasets.md)"
RIGHTS_NOTE = "noncommercial research; no redistribution (CC BY-NC 4.0)"

# md5sums семнадцати архивов -- из data/README.md репозитория kyotovision-public/deepoint
# (проверено 2026-09-15, T1). День → md5 zip-а с кадрами.
FRAME_ZIP_MD5: dict[str, str] = {
    "2023-01-17": "6233f6c1f82c961bf9a8a14bf2a2c166",
    "2023-01-18": "0821b5fb7551a05e0a304131c135a208",
    "2023-01-19": "f7326341e0a2fd55063fa5cadb0bacb7",
    "2023-01-24": "7e00a62efb57e04b3d19ffe40f4a80a9",
    "2023-01-25": "77a71a36d688fa93cb543c6012e3bf9d",
}
LABELS_ZIP_MD5 = "e1e0f881ac95a0b38f12c006ab7517a7"
KEYPOINTS_ZIP_MD5 = "d1e46d1c7e7d5a0bd19b44de145e7655"  # не нужен для кейсов
FRAME_ZIP_URL = "https://drive.google.com/drive/folders/1W_49HId_2FLFH0X9Ry8QiTTyaVt2Y0ks"

DEFAULT_N_CASES = 20
N_CAMERAS = 15
# Минимальная длительность pointing-интервала (кадров после децимации).
MIN_INTERVAL_FRAMES = 5
# Камера деградации, если venue-info отсутствует/нечитаема.
FALLBACK_CAMERA = 0
# Путь к медиавыдачи в кейсе -- относительно корня пакета `guide_robot_llm/`.
DEFAULT_MEDIA_PREFIX = "eval_data/dp"
# Вопрос посетителя (deployed-контракт, как у пилота).
USER_TEXT = "А что это такое?"

# Инвентарь (venue, take) → person_id: таблица VENUESESSION2PERSONID из
# utils.py репозитория авторов (MIT, kyotovision-public/deepoint).
# Распределение по людям -- только для разнообразия набора; человек в
# кадре не идентифицируется.
VENUE_TAKE_PERSON: dict[tuple[str, str], int] = {
    ("2023-01-17-livingroom", "take1"): 1,
    ("2023-01-17-livingroom", "take2"): 2,
    ("2023-01-17-livingroom", "take3"): 3,
    ("2023-01-17-livingroom", "take4"): 4,
    ("2023-01-17-livingroom", "take5"): 5,
    ("2023-01-17-livingroom", "take6"): 6,
    ("2023-01-17-openoffice", "take1"): 3,
    ("2023-01-17-openoffice", "take2"): 1,
    ("2023-01-17-openoffice", "take4"): 6,
    ("2023-01-17-openoffice", "take5"): 5,
    ("2023-01-17-openoffice", "take6"): 4,
    ("2023-01-18-livingroom", "take1"): 7,
    ("2023-01-18-livingroom", "take2"): 8,
    ("2023-01-18-livingroom", "take3"): 9,
    ("2023-01-18-livingroom", "take4"): 10,
    ("2023-01-18-livingroom", "take5"): 11,
    ("2023-01-18-livingroom", "take6"): 12,
    ("2023-01-18-openoffice", "take4"): 12,
    ("2023-01-18-openoffice", "take5"): 10,
    ("2023-01-18-openoffice", "take6"): 11,
    ("2023-01-19-livingroom", "take1"): 13,
    ("2023-01-19-livingroom", "take2"): 14,
    ("2023-01-19-livingroom", "take3"): 15,
    ("2023-01-19-livingroom", "take4"): 16,
    ("2023-01-19-livingroom", "take5"): 17,
    ("2023-01-19-livingroom", "take6"): 18,
    ("2023-01-19-openoffice", "take4"): 17,
    ("2023-01-24-livingroom", "take1"): 20,
    ("2023-01-24-livingroom", "take2"): 21,
    ("2023-01-24-livingroom", "take4"): 23,
    ("2023-01-24-openoffice", "take1"): 19,
    ("2023-01-24-openoffice", "take2"): 20,
    ("2023-01-24-openoffice", "take3"): 21,
    ("2023-01-24-openoffice", "take4"): 22,
    ("2023-01-24-openoffice", "take5"): 23,
    ("2023-01-24-openoffice", "take6"): 24,
    ("2023-01-25-livingroom", "take1"): 25,
    ("2023-01-25-livingroom", "take2"): 26,
    ("2023-01-25-livingroom", "take3"): 27,
    ("2023-01-25-livingroom", "take4"): 28,
    ("2023-01-25-livingroom", "take6"): 33,
    ("2023-01-25-livingroom", "take9"): 29,
    ("2023-01-25-livingroom", "take10"): 30,
    ("2023-01-25-openoffice", "take1"): 27,
    ("2023-01-25-openoffice", "take6"): 29,
    ("2023-01-25-openoffice", "take7"): 31,
    ("2023-01-25-openoffice", "take8"): 32,
}


class DpAdapterError(ValueError):
    """Сборка DP-манифеста невозможна: структура данных не совпала с ожидаемой."""


# ---------------------------------------------------------------------------
# Маркеры → стабильные синтетические id экспонатов
# ---------------------------------------------------------------------------


def marker_to_exhibit(marker_id: int) -> str:
    """Правило переименования маркера в id «экспоната».

    Чистая детерминированная функция -- вся «таблица» есть это правило;
    коммиченный артефакт `exhibit_map.json` (сборка манифеста) фиксирует
    именно те пары, что использованы в замороженном наборе.
    """
    return f"exhibit_{marker_id}"


# ---------------------------------------------------------------------------
# Разбор файлов меток (labels/<venue>/takeN.txt)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PointingEvent:
    """Одно указание: маркер + интервал кадров (после децимации) + рука."""

    marker_id: int
    start: int
    end: int
    arm: str


@dataclass(frozen=True)
class TakeLabels:
    """Метки одного take: валидный диапазон кадров + события-указания."""

    take: str
    valid_start: int
    valid_end: int
    events: tuple[PointingEvent, ...]


def _read_filt(timeinfo_path: Path) -> int:
    """`filt:` (децимация кадров) из timeinfo.yaml; 1, если нет.

    YAML-зависимости не вводим: файл авторов простой (`filt: N` первой
    строкой ключа), читаем ровно этот ключ.
    """
    if not timeinfo_path.is_file():
        return 1
    for line in timeinfo_path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^filt:\s*(\d+)", line)
        if match:
            return int(match.group(1))
    return 1


def parse_take_labels(path: Path) -> TakeLabels:
    """Файл `takeN.txt` → валидный диапазон + события (формат авторов).

    Формат (data/README.md):
    * строка 1: `<start>, <end>` -- диапазон валидных кадров (сырые);
    * далее: `marker_id, start, end, arm(l|r)`; строки `#...` -- комментарии.
    Координаты кадров делятся на `filt` из timeinfo.yaml (как в коде
    авторов, `dataset.usable_frames_in_venue`).
    """
    filt = _read_filt(path.parent / "timeinfo.yaml")
    if filt <= 0:
        raise DpAdapterError(f"{path}: filt={filt} не может быть <= 0")
    rows = list(csv.reader(path.open(encoding="utf-8")))
    if not rows:
        raise DpAdapterError(f"{path}: пустой файл меток")
    try:
        valid_start = int(rows[0][0]) // filt
        valid_end = int(rows[0][1]) // filt
    except (IndexError, ValueError) as error:
        raise DpAdapterError(f"{path}: битая первая строка диапазона") from error
    events: list[PointingEvent] = []
    for row in rows[1:]:
        if not row or row[0].startswith("#"):
            continue
        try:
            marker_id = int(row[0])
            start = int(row[1]) // filt
            end = int(row[2]) // filt
            arm = row[3].strip().lower()
        except (IndexError, ValueError) as error:
            raise DpAdapterError(f"{path}: битая строка {row!r}") from error
        if arm not in ("l", "r"):
            arm = "r" if "r" in arm else "l"
        events.append(PointingEvent(marker_id, start, end, arm))
    return TakeLabels(
        take=path.stem,
        valid_start=valid_start,
        valid_end=valid_end,
        events=tuple(events),
    )


# ---------------------------------------------------------------------------
# venue-info: проекция маркеров (чистый Python, без numpy/cv2)
# ---------------------------------------------------------------------------


def _to_vec(value: Any) -> tuple[float, ...]:
    """Массив (list/tuple, в т.ч. numpy -- через tolist) → tuple[float]."""
    if hasattr(value, "tolist"):  # numpy-массив, без импорта numpy
        value = value.tolist()
    return tuple(float(v) for v in value)


def _to_mat3(value: Any) -> tuple[tuple[float, ...], ...]:
    """Матрица 3x3 (list/tuple/numpy) → кортеж кортежей."""
    if hasattr(value, "tolist"):
        value = value.tolist()
    rows = tuple(tuple(float(v) for v in row) for row in value)
    if len(rows) != 3 or any(len(row) != 3 for row in rows):
        raise DpAdapterError("матрица должна быть 3x3")
    return rows


def _undistort(
    x: float,
    y: float,
    dist: tuple[float, ...],
) -> tuple[float, float]:
    """Обратная дисторсия (модель OpenCV) тремя фиксированными итерациями.

    Точности хватает для эвристики выбора камеры; при `dist == 0`
    коррекция нулевая. Коэффициенты: k1, k2, p1, p2 [, k5 ...].
    """
    if not dist:
        return x, y
    k1 = dist[0]
    k2 = dist[1] if len(dist) > 1 else 0.0
    p1 = dist[2] if len(dist) > 2 else 0.0
    p2 = dist[3] if len(dist) > 3 else 0.0
    k5 = dist[4] if len(dist) > 4 else 0.0
    for _ in range(3):
        r2 = x * x + y * y
        radial = 1.0 + k1 * r2 + k2 * r2 * r2 + k5 * r2 * r2 * r2
        dx = 2.0 * p1 * x * y + p2 * (r2 + 2.0 * x * x)
        dy = p1 * (r2 + 2.0 * y * y) + 2.0 * p2 * x * y
        x -= dx / radial
        y -= dy / radial
    return x, y


def project_marker_box(
    corners: tuple[tuple[float, ...], ...],
    cam_params: dict[str, Any],
    width: int,
    height: int,
) -> tuple[tuple[int, int, int, int] | None, float]:
    """Проецировать 3D-углы маркера в камеру → (box|None, площадь).

    `corners` -- 4 угла маркера (3D, мировой системе; формат
    marker_corners.npz). `cam_params` -- словарь камеры (params.pickle):
    `R` (3x3, колонки = оси камеры в мировом), `t` (3,), `K` (3x3),
    опционально `dist`. `box` -- [x0, y0, x1, y1] (int, в кадре) или
    `None`, если центр маркера вне кадра. Площадь -- по bounding box.
    """
    r_mat = _to_mat3(cam_params["R"])
    t_vec = _to_vec(cam_params["t"])
    k_mat = _to_mat3(cam_params["K"])
    dist = _to_vec(cam_params.get("dist", ())) if cam_params.get("dist") is not None else ()

    pts: list[tuple[float, float]] = []
    for corner in corners:
        p = _to_vec(corner)
        # мир → камера: R^T * (P - t)
        pc0 = p[0] - t_vec[0]
        pc1 = p[1] - t_vec[1]
        pc2 = p[2] - t_vec[2]
        cx = sum(r_mat[i][0] * v for i, v in enumerate((pc0, pc1, pc2)))
        cy = sum(r_mat[i][1] * v for i, v in enumerate((pc0, pc1, pc2)))
        cz = sum(r_mat[i][2] * v for i, v in enumerate((pc0, pc1, pc2)))
        if cz <= 1e-6:
            return None, 0.0  # за камерой/на оптической оси -- невидим
        x = cx / cz
        y = cy / cz
        x, y = _undistort(x, y, dist)
        px = k_mat[0][0] * x + k_mat[0][1] * y + k_mat[0][2]
        py = k_mat[1][0] * x + k_mat[1][1] * y + k_mat[1][2]
        pts.append((px, py))

    center = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
    if not (0.0 <= center[0] < float(width) and 0.0 <= center[1] < float(height)):
        return None, 0.0
    x0 = max(0, min(int(p[0]) for p in pts))
    y0 = max(0, min(int(p[1]) for p in pts))
    x1 = min(width - 1, max(int(p[0]) for p in pts))
    y1 = min(height - 1, max(int(p[1]) for p in pts))
    box = (x0, y0, x1, y1)
    area = float((x1 - x0 + 1) * (y1 - y0 + 1))
    return box, area


def _camera_usable(cam: Any) -> bool:
    """Камера пригодна для проекции: есть `R` (3x3), `t` (3,), `K` (3x3).

    Код авторов не использует `K` (сеть учит направления end-to-end),
    поэтому наличие внутренних параметров в реальном `params.pickle`
    не гарантировано; без `K` проекция в пиксели невозможна и такая
    камера исключается из выбора (а весь venue без камер -- деградация).
    """
    if not isinstance(cam, dict):
        return False
    try:
        _to_mat3(cam["R"])
        _to_mat3(cam["K"])
        return len(_to_vec(cam["t"])) == 3
    except (KeyError, TypeError, DpAdapterError):
        return False


def load_venue_info(venue_frames_dir: Path) -> tuple[dict[int, Any], dict[int, tuple]] | None:
    """`venue-info` → (cam_params по камерам, corners маркеров по id) | None.

    Любой сбой чтения/формата → `None` (вызов деградирует в фиксированную
    камеру с `box_px: null`; ошибка не прерывает сборку). Камеры без
    `R`/`t`/`K` (см. `_camera_usable`) из выборки исключаются.
    """
    try:
        params_raw = pickle.load(open(venue_frames_dir / "venue-info" / "params.pickle", "rb"))
        npz = zipfile.ZipFile(venue_frames_dir / "venue-info" / "marker_corners.npz")
        valid_ids = tuple(int(v) for v in _npy_array(npz, "valid_ids"))
        corners_by_id: dict[int, tuple] = {}
        corners_raw = _npy_array(npz, "corners")  # (N, 4, 3)
        for i, mid in enumerate(valid_ids):
            corners_by_id[mid] = tuple(tuple(float(v) for v in row) for row in corners_raw[i])
        cameras: dict[int, Any] = {}
        for cam_key, cam in params_raw.items():
            if not _camera_usable(cam):
                continue
            cameras[int(str(cam_key))] = cam
        if not cameras:
            return None
        return cameras, corners_by_id
    except Exception:  # noqa: BLE001 -- любой сбой = деградация, не сбой сборки
        return None


_NPY_STRUCT_FMT = {
    "f": {8: "d", 4: "f", 2: "e"},
    "i": {8: "q", 4: "i", 2: "h", 1: "b"},
    "u": {1: "B"},
}


def _npy_array(npz: zipfile.ZipFile, name: str) -> list:
    """Массив из .npz (формат .npy v1/v2) → вложенные списки (без numpy).

    Поддерживает float64/32/16, int64/32/16/8, uint8 -- достаточно для
    `valid_ids` (int) и `corners` (float64) в marker_corners.npz.
    """
    with npz.open(f"{name}.npy") as fh:
        magic = fh.read(6)
        if magic != b"\x93NUMPY":
            raise DpAdapterError(f"{name}: не .npy-заголовок")
        fh.read(2)  # версия
        header_len = int.from_bytes(fh.read(2), "little")
        header = fh.read(header_len).decode("utf-8")
        payload = fh.read()
    descr_match = re.search(r"'descr':\s*'([^']+)'", header)
    if not descr_match:
        raise DpAdapterError(f"{name}: нечитаемый .npy-заголовок")
    descr = descr_match.group(1)
    # вида "<f8", "<i4", "|u1"
    kind_match = re.search(r"([fui])(\d)", descr)
    if not kind_match:
        raise DpAdapterError(f"{name}: неподдерживаемый .npy-тип {descr!r}")
    kind, size = kind_match.group(1), int(kind_match.group(2))
    if kind not in _NPY_STRUCT_FMT or size not in _NPY_STRUCT_FMT[kind]:
        raise DpAdapterError(f"{name}: неподдерживаемый .npy-тип {descr!r}")
    shape_match = re.search(r"'shape':\s*\(([^)]*)\)", header)
    if not shape_match:
        raise DpAdapterError(f"{name}: нечитаемый shape в .npy-заголовке")
    shape_text = shape_match.group(1).strip()
    # В одномерных shape numpy пишет хвостовую запятую: `(4,)`.
    parts = [p.strip() for p in shape_text.split(",") if p.strip()]
    shape: tuple[int, ...] = tuple(int(p) for p in parts)
    n_values = math.prod(shape) if shape else 1
    unit = _NPY_STRUCT_FMT[kind][size]
    expected = n_values * size
    if len(payload) < expected:
        raise DpAdapterError(f"{name}: payload короче ожидаемого ({len(payload)} < {expected})")
    flat = list(struct.unpack(f"<{n_values}{unit}", payload[:expected]))

    def nest(values: list, dims: tuple[int, ...]) -> Any:
        if len(dims) <= 1:
            return values  # 1-D (и скаляр) -- плоский список
        stride = math.prod(dims[1:])
        return [nest(values[i * stride : (i + 1) * stride], dims[1:]) for i in range(dims[0])]

    return nest(flat, shape)


# ---------------------------------------------------------------------------
# Размеры JPEG (SOF) без Pillow
# ---------------------------------------------------------------------------


def jpeg_size_from_bytes(data: bytes) -> tuple[int, int] | None:
    """(width, height) из первого SOF-маркера JPEG; None, если не JPEG."""
    if data[:2] != b"\xff\xd8":
        return None
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            return None
        marker = data[i + 1]
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            height = int.from_bytes(data[i + 5 : i + 7], "big")
            width = int.from_bytes(data[i + 7 : i + 9], "big")
            return width, height
        length = int.from_bytes(data[i + 2 : i + 4], "big")
        i += 2 + length
    return None


# ---------------------------------------------------------------------------
# Выбор событий (20 кейсов, без общих take/sequence)
# ---------------------------------------------------------------------------


def _take_number(take: str) -> int:
    match = re.search(r"(\d+)$", take)
    return int(match.group(1)) if match else 0


def select_events(
    venues: dict[str, dict[str, TakeLabels]], n_cases: int
) -> list[tuple[str, str, PointingEvent]]:
    """Определённый round-robin по венам: по одному take за проход.

    Правила: валидный интервал ≥ MIN_INTERVAL_FRAMES; take не
    переиспользуется (утечки); люди (там, где известны) не
    переиспользуются, пока есть варианты; среди вариантов -- наиболее
    длинный интервал (самое устойчивое указание). Трэй-брейк: take,
    затем start, затем marker_id.
    """
    used_takes: set[tuple[str, str]] = set()
    used_people: set[int] = set()
    chosen: list[tuple[str, str, PointingEvent]] = []
    # кандидаты: venue → take → лучшие события
    while len(chosen) < n_cases:
        progressed = False
        for venue in sorted(venues):
            if len(chosen) >= n_cases:
                break
            best: tuple | None = None
            for take in sorted(venues[venue], key=_take_number):
                if (venue, take) in used_takes:
                    continue
                for event in sorted(
                    venues[venue][take].events, key=lambda e: (e.start, e.marker_id)
                ):
                    if event.end - event.start < MIN_INTERVAL_FRAMES:
                        continue
                    person = VENUE_TAKE_PERSON.get((venue, take))
                    # (0: новый человек, 1: повтор) → (0: длина интервала)
                    key = (
                        0 if (person is None or person not in used_people) else 1,
                        -(event.end - event.start),
                        _take_number(take),
                        event.start,
                        event.marker_id,
                    )
                    candidate = (key, take, event)
                    if best is None or candidate[0] < best[0]:
                        best = (key, take, event)  # type: ignore[assignment]
            if best is None:
                continue
            _, take, event = best
            used_takes.add((venue, take))
            person = VENUE_TAKE_PERSON.get((venue, take))
            if person is not None:
                used_people.add(person)
            chosen.append((venue, take, event))
            progressed = True
        if not progressed:
            break
    return chosen


# ---------------------------------------------------------------------------
# Сборка кейсов
# ---------------------------------------------------------------------------


def _frame_path(data_root: Path, venue: str, take: str, camera: int, frame: int) -> Path:
    # ffmpeg 1-indexed: файл = кадр + 1 (как в src/dataset.py авторов).
    return data_root / "frames" / venue / take / f"{camera:02d}" / f"{frame + 1:010d}.jpg"


def _case_day(venue: str) -> str:
    return venue.split("-")[0] + "-" + venue.split("-")[1] + "-" + venue.split("-")[2]


def _sha256_of_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _choose_camera(
    camera: int | str,
    venue_info: tuple[dict[int, Any], dict[int, tuple]] | None,
    frame_size: tuple[int, int] | None,
    marker_id: int,
) -> tuple[int, tuple[int, int, int, int] | None, str, float]:
    """→ (camera_id, box_px, rule, area).

    `camera` -- "auto" или фикс. id; `frame_size` -- фактический размер
    кадра вена (без него проекция в пиксели невозможна -- деградация).
    """
    if isinstance(camera, int):
        return camera, None, f"fixed-{camera:02d}", 0.0
    if venue_info is None or marker_id not in venue_info[1] or frame_size is None:
        return FALLBACK_CAMERA, None, "fallback-fixed-00", 0.0
    cameras, corners_by_id = venue_info
    best: tuple[float, int, tuple[int, int, int, int]] | None = None
    for cam_id in range(N_CAMERAS):
        params = cameras.get(cam_id)
        if params is None:
            continue
        box, area = project_marker_box(corners_by_id[marker_id], params, *frame_size)
        if box is None or area <= 0:
            continue
        if best is None or area > best[0]:
            best = (area, cam_id, box)
    if best is None:
        return FALLBACK_CAMERA, None, "fallback-fixed-00", 0.0
    return best[1], best[2], "auto-max-area", best[0]


def _venue_frame_size(root: Path, venue: str) -> tuple[int, int] | None:
    """Фактический размер кадра вена: из первого найденного JPEG (SOF).

    Все 15 камер вена сняты одним ригом -- размер общий. Если ни одного
    readable-кадра нет -- None (вызов деградирует в фиксированную камеру).
    """
    frames_dir = root / "frames" / venue
    for pattern in ("take*/00/*.jpg", "take*/*/*.jpg"):
        for frame_file in sorted(frames_dir.glob(pattern)):
            size = jpeg_size_from_bytes(frame_file.read_bytes())
            if size is not None:
                return size
    return None


def build_dp_cases(
    data_root: str | Path,
    *,
    n_cases: int = DEFAULT_N_CASES,
    camera: int | str = "auto",
    media_prefix: str = DEFAULT_MEDIA_PREFIX,
) -> tuple[list[Case], dict[str, Any]]:
    """Собрать DP-кейсы из каталога данных → (кейсы, отчёт сборки).

    `data_root` -- каталог `eval_data/dp` с подкаталогами `frames/`
    (смонтированные squashfs) и `labels/` (разархивированные).
    Кейсы сортированы по case_id; отчёт -- выбор событий, камеры,
    деградации (для PROVENANCE.md и Taiga-заметки).
    """
    root = Path(data_root)
    labels_root = root / "labels"
    if not labels_root.is_dir():
        raise DpAdapterError(f"{labels_root}: нет каталога labels (разархивируйте labels.zip)")
    venues: dict[str, dict[str, TakeLabels]] = {}
    for venue_dir in sorted(labels_root.iterdir()):
        if not venue_dir.is_dir():
            continue
        take_labels: dict[str, TakeLabels] = {}
        for take_file in sorted(venue_dir.glob("take*.txt")):
            take_labels[take_file.stem] = parse_take_labels(take_file)
        if take_labels:
            venues[venue_dir.name] = take_labels
    if not venues:
        raise DpAdapterError(f"{labels_root}: нет ни одного take-файла меток")

    chosen = select_events(venues, n_cases)
    takes = [(v, t) for v, t, _ in chosen]
    if len(set(takes)) != len(takes):
        raise DpAdapterError("нарушена инвариант: два кейса из одного take")

    report: dict[str, Any] = {
        "n_cases": len(chosen),
        "cameras": {},
        "degraded": [],
        "excluded": [],
        "exhibit_map": {},
    }
    frame_sizes: dict[str, tuple[int, int] | None] = {}
    cases: list[Case] = []
    for venue, take, event in chosen:
        frame = (event.start + event.end) // 2
        take_labels = venues[venue][take]
        frame = max(take_labels.valid_start, min(frame, take_labels.valid_end - 1))

        venue_frames = root / "frames" / venue
        venue_info = load_venue_info(venue_frames)
        if venue not in frame_sizes:
            frame_sizes[venue] = _venue_frame_size(root, venue)
        cam_id, box, rule, area = _choose_camera(
            camera, venue_info, frame_sizes[venue], event.marker_id
        )
        report["cameras"].setdefault(rule, 0)
        report["cameras"][rule] += 1
        if box is None:
            report["degraded"].append(
                {"venue": venue, "take": take, "reason": "no venue-info or marker invisible"}
            )

        # Кандидаты: все маркеры вена (venue-info) или, без него, все
        # маркеры меток вена (из labels).
        if venue_info is not None:
            marker_ids = sorted(venue_info[1])
        else:
            marker_ids = sorted({e.marker_id for tl in venues[venue].values() for e in tl.events})
        candidates = [marker_to_exhibit(m) for m in marker_ids]
        target_id = marker_to_exhibit(event.marker_id)
        report["exhibit_map"][str(event.marker_id)] = target_id

        frame_path = _frame_path(root, venue, take, cam_id, frame)
        if not frame_path.is_file():
            raise DpAdapterError(
                f"{frame_path}: кадр не найден (take {take}, камера {cam_id:02d}, "
                f"кадр {frame + 1}) -- смонтируйте frames_squashed (mount_frames.sh)"
            )
        if jpeg_size_from_bytes(frame_path.read_bytes()) is None:
            raise DpAdapterError(f"{frame_path}: не JPEG")

        day = _case_day(venue)
        version = f"{day}.zip:{FRAME_ZIP_MD5.get(day, 'md5-unknown')}+labels.zip:{LABELS_ZIP_MD5}"
        data = {
            "case_id": f"DP-{venue}-{take}-{event.marker_id:02d}",
            "source": "dp",
            "track": "pointing",
            "split_group_id": f"g-dp-{venue}-{take}",
            "media": {
                "path": f"{media_prefix}/frames/{venue}/{take}/{cam_id:02d}/{frame + 1:010d}.jpg",
                "sha256": _sha256_of_file(frame_path),
                "format": "jpg",
            },
            "prompt": {"mode": "deployed", "user_text": USER_TEXT, "language": "ru"},
            "candidates": candidates,
            "allowed_tools": ["reply", "say"],
            "gold": {
                "type": "target_box",
                "target_id": target_id,
                "box_px": list(box) if box is not None else None,
                "distractors": [c for c in candidates if c != target_id],
            },
            "provenance": {
                "source": "DP/Deepoint",
                "license": LICENSE_LINE,
                "version": version,
                "rights_note": RIGHTS_NOTE,
            },
            "slices": {
                "venue": venue,
                "day": day,
                "take": take,
                "arm": event.arm,
                "camera_id": cam_id,
                "camera_rule": rule,
                "marker_area_px": round(area) if box is not None else None,
                "n_distractors": len(candidates) - 1,
            },
        }
        cases.append(case_from_dict(data))
    cases.sort(key=lambda c: c.case_id)
    return cases, report


def provenance_text(cases: list[Case], report: dict[str, Any]) -> str:
    """Текст `PROVENANCE.md` для корня данных (дизайн: контракт адаптера).

    Чистая функция: лицензия, хэши архивов, правило marker→exhibit,
    состав набора и команды для пользователя (агент не скачивает).
    """
    days = sorted({c.slices["day"] for c in cases})
    lines: list[str] = [
        "# DP/Deepoint — provenance (генерируется `adapters.dp`, не править)",
        "",
        f"- Кейсов: {len(cases)}; правила камер: {report['cameras']}; "
        f"деградаций без box_px: {len(report['degraded'])}",
        f"- Дни в наборе: {', '.join(days)}",
        f"- Лицензия: {LICENSE_LINE}",
        f"- Права: {RIGHTS_NOTE}",
        f"- Источник: kyotovision-public/deepoint, данные: {FRAME_ZIP_URL}",
        "- Правило marker → exhibit: `marker_<id> → exhibit_<id>`",
        "  (`marker_to_exhibit`); таблица набора: "
        f"{json.dumps(report['exhibit_map'], ensure_ascii=False)}",
        "",
        "## Архивы (md5sums из data/README.md, проверены 2026-09-15, T1)",
        "",
        "| Архив | md5 | Статус |",
        "|---|---|---|",
    ]
    for day, md5 in sorted(FRAME_ZIP_MD5.items()):
        status = "нужен (день в наборе)" if day in days else "не нужен (день вне набора)"
        lines.append(f"| {day}.zip | `{md5}` | {status} |")
    lines.append(f"| labels.zip | `{LABELS_ZIP_MD5}` | нужен |")
    lines.append(f"| keypoints.zip | `{KEYPOINTS_ZIP_MD5}` | не нужен (3D/keypoints вне кейсов) |")
    lines += [
        "",
        "## Шаги пользователя (агент не скачивает)",
        "",
        "```bash",
        "cd guide_robot_llm && mkdir -p eval_data/dp && cd eval_data/dp",
        f"# скачать архивы из папки: {FRAME_ZIP_URL}",
        "md5sum 2023-01-17.zip 2023-01-18.zip 2023-01-19.zip 2023-01-24.zip \\",
        "        2023-01-25.zip labels.zip   # сверить с таблицей выше",
        "mkdir frames_squashed",
        "unzip -q 2023-01-*.zip -d frames_squashed   # 10 squashfs-файлов",
        "unzip -q labels.zip                       # labels/<venue>/",
        "mkdir -p frames",
        'for f in frames_squashed/*; do unsquashfs -d "frames/$(basename "$f")" "$f"; done',
        "python -m guide_robot_llm.eval.adapters.dp \\",
        "    --data-root . --out ../../eval_manifests/dp_20.jsonl",
        "```",
        "",
        "`unsquashfs` -- из `squashfs-tools`. Итоговая раскладка: "
        "`frames/<venue>/venue-info/` + `frames/<venue>/take*/00..14/*.jpg`, "
        "`labels/<venue>/take*.txt` + `timeinfo.yaml`.",
    ]
    lines.append(f"Собрано: {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC.")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    """CLI: собрать манифест DP-кейсов (JSONL) + отчёт + PROVENANCE.md."""
    parser = argparse.ArgumentParser(description="Сборка DP/Deepoint-кейсов (Taiga #10, T6)")
    parser.add_argument("--data-root", required=True, help="каталог eval_data/dp")
    parser.add_argument("--out", required=True, help="выходной JSONL-манифест")
    parser.add_argument("--n-cases", type=int, default=DEFAULT_N_CASES)
    parser.add_argument("--camera", default="auto", help='"auto" или фикс. номер камеры')
    parser.add_argument("--media-prefix", default=DEFAULT_MEDIA_PREFIX)
    args = parser.parse_args(argv)

    camera: int | str = "auto"
    if args.camera.isdigit():
        camera = int(args.camera)
    cases, report = build_dp_cases(
        args.data_root,
        n_cases=args.n_cases,
        camera=camera,
        media_prefix=args.media_prefix,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        for case in cases:
            fh.write(json.dumps(case_to_dict(case), ensure_ascii=False) + "\n")
    side = out.with_name(out.name + ".sidecar.json")
    with open(side, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    prov = Path(args.data_root) / "PROVENANCE.md"
    prov.write_text(provenance_text(cases, report), encoding="utf-8")
    print(f"DP-кейсов: {len(cases)}; манифест: {out}; отчёт: {side}")
    print(f"provenance: {prov}")
    if report["degraded"]:
        print(
            f"внимание: кейсов без box_px (деградация камеры): {len(report['degraded'])} "
            "-- см. отчёт"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
