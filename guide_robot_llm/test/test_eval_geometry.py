"""Тесты виртуальной геометрии replay-режима (OpenSpec add-pointing-virtual-replay).

Чистый Python, без ROS: инверсия якоря → позиция кандидата (инверсия
`pointing._project` при единичной позе робота), clamping выше горизонта,
сайдкар с provenance, золотая область.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from guide_robot_llm.eval.geometry import (
    D_MAX_M,
    GOLD_REGION_FRACTION,
    PRODUCTION_CAMERA,
    SCHEMA,
    build_case_geometry,
    compute_sha256,
    default_gold_region,
    invert_anchor,
    set_review_status,
    write_geometry_sidecar,
)
from guide_robot_llm.pointing import (
    Candidate,
    CameraGeometry,
    RobotPose,
    _project,
)

_CAM = CameraGeometry(**PRODUCTION_CAMERA)
_POSE = RobotPose(x=0.0, y=0.0, yaw=0.0)


def _project_norm(u: float, v: float) -> tuple[bool, float, float]:
    inv = invert_anchor(u, v)
    cand = Candidate(id="c", name="c", x=inv.x, y=inv.y)
    in_img, _depth, u_px, v_px = _project(cand, _POSE, _CAM)
    return in_img, u_px / PRODUCTION_CAMERA["width_px"], v_px / PRODUCTION_CAMERA["height_px"]


def test_invert_roundtrip_below_horizon():
    """project(invert(u, v)) == (u, v) для якорей ниже линии горизонта."""
    for u in (0.1, 0.25, 0.5, 0.75, 0.9):
        for v in (0.3, 0.45, 0.5, 0.6, 0.75, 0.9):
            inv = invert_anchor(u, v)
            assert not inv.clamped
            in_img, u_rt, v_rt = _project_norm(u, v)
            assert in_img
            assert abs(u_rt - u) < 1e-9
            assert abs(v_rt - v) < 1e-9


def test_invert_center_anchor():
    """Якорь в центре кадра: точка на оптической оси, ~впереди робота."""
    inv = invert_anchor(0.5, 0.5)
    assert not inv.clamped
    assert abs(inv.x) > 0.9  # tan(10°) → d_h = 1/tan(10°) ≈ 5.67 м
    assert abs(inv.y) < 1e-9


def test_invert_above_horizon_clamps():
    """Якорь выше горизонта (v < ~0.21) → clamped, d_h == D_MAX."""
    inv = invert_anchor(0.5, 0.10)
    assert inv.clamped
    assert math.hypot(inv.x, inv.y) == D_MAX_M


def test_invert_rejects_out_of_range():
    for bad in ((-0.1, 0.5), (1.1, 0.5), (0.5, -0.2), (0.5, 1.2)):
        try:
            invert_anchor(*bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"no ValueError for {bad}")


def test_default_gold_region_center():
    x0, y0, x1, y1 = default_gold_region((0.5, 0.5))
    half = GOLD_REGION_FRACTION / 2.0
    assert (x0, y0, x1, y1) == (0.5 - half, 0.5 - half, 0.5 + half, 0.5 + half)


def test_default_gold_region_clamps_to_frame():
    x0, _y0, x1, _y1 = default_gold_region((0.02, 0.98))
    assert x0 == 0.0
    x0, _y0, x1, _y1 = default_gold_region((0.98, 0.02))
    assert x1 == 1.0


def test_build_case_geometry_fields(tmp_path: Path):
    img = tmp_path / "img.jpg"
    img.write_bytes(b"fake-image-bytes")
    case = build_case_geometry(
        case_id="egopoint_4",
        image_path=img,
        anchors={"opt_a": (0.3, 0.6), "opt_b": (0.7, 0.6),
                 "opt_c": (0.5, 0.75), "opt_d": (0.5, 0.10)},
        target_anchor=(0.3, 0.6),
    )
    assert case["case_id"] == "egopoint_4"
    assert case["image_sha256"] == hashlib.sha256(b"fake-image-bytes").hexdigest()
    assert set(case["anchors"]) == {"opt_a", "opt_b", "opt_c", "opt_d"}
    assert case["positions"]["opt_a"]["clamped"] is False
    assert case["positions"]["opt_d"]["clamped"] is True
    assert case["positions"]["opt_d"]["x"] == D_MAX_M
    assert abs(case["positions"]["opt_d"]["y"]) < 1e-9
    assert isinstance(case["gold_region"], list) and len(case["gold_region"]) == 4


def test_write_sidecar_schema_and_read_only(tmp_path: Path):
    """Сайдкар содержит весь provenance; в каталог источника ничего не
    пишется (там остаётся только исходная картинка)."""
    img = tmp_path / "src" / "img.jpg"
    img.parent.mkdir()
    img.write_bytes(b"fake")
    case = build_case_geometry(
        case_id="c1", image_path=img,
        anchors={"a": (0.5, 0.6)}, target_anchor=(0.5, 0.6),
    )
    out = tmp_path / "sidecar.json"
    write_geometry_sidecar(
        Path("egopoint_15.jsonl"), [case], out,
        author="agent", method="manual-anchors", date="2026-11-05",
    )
    doc = json.loads(out.read_text())
    assert doc["schema"] == SCHEMA
    assert doc["manifest"] == "egopoint_15.jsonl"
    assert doc["camera"] == PRODUCTION_CAMERA
    assert doc["d_max_m"] == D_MAX_M
    assert doc["gold_region_fraction"] == GOLD_REGION_FRACTION
    prov = doc["provenance"]
    assert prov == {
        "author": "agent", "method": "manual-anchors",
        "date": "2026-11-05", "review_status": "pending",
    }
    assert "c1" in doc["cases"]
    assert doc["cases"]["c1"]["image_sha256"] == compute_sha256(img)
    # источник не тронут: в каталоге источника только img.jpg
    assert [p.name for p in (tmp_path / "src").iterdir()] == ["img.jpg"]


def test_set_review_status(tmp_path: Path):
    out = tmp_path / "sidecar.json"
    write_geometry_sidecar(
        Path("m.jsonl"), [], out,
        author="a", method="m", date="d",
    )
    set_review_status(out, "confirmed", note="all 30 anchors verified")
    doc = json.loads(out.read_text())
    assert doc["provenance"]["review_status"] == "confirmed"
    assert doc["provenance"]["review_note"] == "all 30 anchors verified"
