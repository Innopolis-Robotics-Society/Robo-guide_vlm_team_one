"""Виртуальная геометрия для replay-режима оценки pointing.

OpenSpec: `add-pointing-virtual-replay` (дизайн D2/D3). Якоря (u, v) --
нормализованные пиксели объектов-кандидатов на картинке кейса --
инвертируются через production-модель камеры (`pointing._project`,
конфиг `vision.camera.*` в `guide_robot_llm/config/llm.yaml`) в позиции
(x, y) на плоскости пола. Робот-поза -- единичная (камера в начале
координат, yaw 0): без свободы глубины, каждому (u, v) соответствует
уникальная (x, y).

Сайдкар -- данные проекта: картинки бенчмарка только для чтения, вся
производная геометрия живёт в `eval_manifests/<manifest>.geometry.json`.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Production-модель камеры (llm.yaml, `vision.camera.*`; Taiga #7).
PRODUCTION_CAMERA: dict[str, float] = {
    "width_px": 1280,
    "height_px": 720,
    "hfov_deg": 60.0,
    "vfov_deg": 34.0,
    "mount_x": 0.0,
    "mount_y": 0.0,
    "mount_z": 1.0,
    "yaw_deg": 0.0,
    "pitch_deg": 10.0,
}

# Якоря выше горизонта дают d_h -> инф: клампим и флаг.
D_MAX_M = 10.0
_HORIZON_EPS_RAD = 1e-3

# Золотая область под box_iou: доля меньшей стороны кадра.
GOLD_REGION_FRACTION = 0.15

SCHEMA = "pointing_virtual_geometry.v1"


@dataclass(frozen=True)
class InvertedAnchor:
    """Позиция кандидата (x, y), инвертированная из якоря (u, v)."""

    x: float
    y: float
    clamped: bool = False


def invert_anchor(
    u: float, v: float, cam: dict[str, float] | None = None
) -> InvertedAnchor:
    """Якорь (u, v) ∈ [0, 1]² → позиция кандидата (x, y) на плоскости пола.

    Инверсия `pointing._project` при единичной позе робота:
    `u = W/2 + fx·tan(Δθ)`, `v = H/2 + fy·tan(vert)`,
    `vert + pitch = atan2(z, d_h)`. Если `vert + pitch ≤ eps` (якорь выше
    линии горизонта), глубина расходитится: клампим в `D_MAX_M` и
    помечаем `clamped=True`.
    """
    if not (0.0 <= u <= 1.0 and 0.0 <= v <= 1.0):
        raise ValueError(f"anchor out of [0,1]: u={u}, v={v}")
    c = cam or PRODUCTION_CAMERA
    fx = (c["width_px"] / 2.0) / math.tan(math.radians(c["hfov_deg"]) / 2.0)
    fy = (c["height_px"] / 2.0) / math.tan(math.radians(c["vfov_deg"]) / 2.0)
    delta_theta = math.atan((u - 0.5) * c["width_px"] / fx)
    pitch = math.radians(c["pitch_deg"])
    vert_angle = math.atan((v - 0.5) * c["height_px"] / fy)
    denom = math.tan(vert_angle + pitch)
    if denom <= _HORIZON_EPS_RAD:
        d_h, clamped = D_MAX_M, True
    else:
        d_h, clamped = c["mount_z"] / denom, False
    bearing = math.radians(c["yaw_deg"]) + delta_theta
    return InvertedAnchor(
        d_h * math.cos(bearing), d_h * math.sin(bearing), clamped
    )


def default_gold_region(
    target_anchor: tuple[float, float], cam: dict[str, float] | None = None
) -> tuple[float, float, float, float]:
    """Золотая область box-указания: `GOLD_REGION_FRACTION` меньшей
    стороны кадра, по центру якоря-цели, обрезаемая в [0, 1]."""
    c = cam or PRODUCTION_CAMERA
    size = GOLD_REGION_FRACTION * min(c["width_px"], c["height_px"])
    half = size / 2.0 / min(c["width_px"], c["height_px"])
    u, v = target_anchor
    x0, x1 = u - half, u + half
    y0, y1 = v - half, v + half
    return (
        max(0.0, min(1.0, x0)),
        max(0.0, min(1.0, y0)),
        max(0.0, min(1.0, x1)),
        max(0.0, min(1.0, y1)),
    )


def box_iou(
    box_a: tuple[float, float, float, float],
    box_b: tuple[float, float, float, float],
) -> float | None:
    """IoU двух нормализованных боксов [x0, y0, x1, y1]; `None`, если
    объединение пусто (вырожденный бокс)."""
    x0 = max(box_a[0], box_b[0])
    y0 = max(box_a[1], box_b[1])
    x1 = min(box_a[2], box_b[2])
    y1 = min(box_a[3], box_b[3])
    inter = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    area_a = (box_a[2] - box_a[0]) * (box_a[3] - box_a[1])
    area_b = (box_b[2] - box_b[0]) * (box_b[3] - box_b[1])
    union = area_a + area_b - inter
    return inter / union if union > 0.0 else None


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_case_geometry(
    *,
    case_id: str,
    image_path: Path,
    anchors: dict[str, tuple[float, float]],
    target_anchor: tuple[float, float],
    cam: dict[str, float] | None = None,
    gold_region: tuple[float, float, float, float] | None = None,
) -> dict[str, Any]:
    """Запись сайдcara на один кейс: якоря → позиции + clamped-флаги,
    sha256 картинки, золотая область (по умолчанию из `target_anchor`).

    `image_path` только читается (sha256); в каталог источника ничего не
    пишется.
    """
    c = cam or PRODUCTION_CAMERA
    positions = {}
    for cand_id, (u, v) in anchors.items():
        inv = invert_anchor(u, v, c)
        positions[cand_id] = {"x": inv.x, "y": inv.y, "clamped": inv.clamped}
    return {
        "case_id": case_id,
        "image_sha256": compute_sha256(image_path),
        "anchors": {cid: {"u": u, "v": v} for cid, (u, v) in anchors.items()},
        "positions": positions,
        "target_anchor": {"u": target_anchor[0], "v": target_anchor[1]},
        "gold_region": (
            list(gold_region) if gold_region is not None
            else list(default_gold_region(target_anchor, c))
        ),
    }


def write_geometry_sidecar(
    manifest_path: Path,
    cases: list[dict[str, Any]],
    out_path: Path,
    *,
    author: str,
    method: str,
    date: str,
    review_status: str = "pending",
) -> Path:
    """Замораживает геометрию в сайдкар рядом с манифестом.

    Схема: `schema`, `manifest`, `camera`, `d_max_m`,
    `gold_region_fraction`, `provenance` (author/method/date/
    review_status), `cases` (ключ -- case_id). `out_path` задаётся явно;
    в каталог исходных данных бенчмарка не пишем.
    """
    doc = {
        "schema": SCHEMA,
        "manifest": manifest_path.name,
        "camera": dict(PRODUCTION_CAMERA),
        "d_max_m": D_MAX_M,
        "gold_region_fraction": GOLD_REGION_FRACTION,
        "provenance": {
            "author": author,
            "method": method,
            "date": date,
            "review_status": review_status,
        },
        "cases": {c["case_id"]: c for c in cases},
    }
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return out_path


def set_review_status(
    sidecar_path: Path, status: str, note: str | None = None
) -> None:
    """Переписать `provenance.review_status` (и необязательный `note`)."""
    with open(sidecar_path, encoding="utf-8") as f:
        doc = json.load(f)
    doc["provenance"]["review_status"] = status
    if note is not None:
        doc["provenance"]["review_note"] = note
    with open(sidecar_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write("\n")
