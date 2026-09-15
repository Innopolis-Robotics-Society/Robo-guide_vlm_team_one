"""Синтетика audience engagement (Taiga #16, F1): ENG/SEQ-сцены и манифест.

Проверяем конформность «глазных» маркеров facing_camera (генератор ↔ чекер),
отрицательный случай (перевёрнутый атрибут ловится) и golds манифеста
audience_engagement.jsonl (count/engaged_count + кадры SEQ).
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
from pathlib import Path

from PIL import Image, ImageDraw

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
TOOLS = PACKAGE_ROOT / "pilot" / "tools"


def _load_tool(name: str):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gen = _load_tool("cc_scene_gen")
verify = _load_tool("verify_cc_pixels")
builder = _load_tool("build_eng_manifest")


def _render(scene_id: str) -> tuple[Image.Image, dict]:
    img = Image.new("RGB", (gen.W, gen.H))
    scenes = {**gen.SCENES, **gen.ENG_SCENES}
    gt = scenes[scene_id](ImageDraw.Draw(img))
    return img, gt


def _render_seq_frame(seq_id: str, index: int) -> tuple[Image.Image, dict]:
    img = Image.new("RGB", (gen.W, gen.H))
    gt = gen._seq_render(seq_id, index, ImageDraw.Draw(img))
    return img, gt


def test_eng_scenes_facing_markers_conform() -> None:
    for scene_id in gen.ENG_SCENES:
        img, gt = _render(scene_id)
        errors: list[str] = []
        verify.check_facing(img, gt, errors)
        assert errors == [], f"{scene_id}: {errors}"


def test_seq_frames_facing_markers_conform() -> None:
    for seq_id, frames in gen.SEQUENCES.items():
        for i in range(len(frames)):
            img, gt = _render_seq_frame(seq_id, i)
            errors: list[str] = []
            verify.check_facing(img, gt, errors)
            assert errors == [], f"{seq_id}_f{i}: {errors}"


def test_facing_check_detects_flipped_attribute() -> None:
    _img, gt = _render("ENG-CC-001")
    flipped = copy.deepcopy(gt)
    for p in flipped["people"]:
        p["facing_camera"] = not p["facing_camera"]
    errors: list[str] = []
    verify.check_facing(_img, flipped, errors)
    assert errors, "перевёрнутый facing_camera должен ловиться пиксель-чеком"


def test_facing_check_skips_legacy_people() -> None:
    _img, gt = _render("SCN-CC-002")  # сцена без атрибута facing_camera
    errors: list[str] = []
    verify.check_facing(_img, gt, errors)
    assert errors == []


def test_eng_manifest_golds() -> None:
    cases = builder._static_cases() + builder._sequence_cases()
    assert len(cases) == 7
    expected = {
        "ENG-CC-001": (3, 2), "ENG-CC-002": (1, 1),
        "ENG-CC-003": (0, 0), "ENG-CC-004": (4, 1),
        "SEQ-CC-001": (3, 3), "SEQ-CC-002": (3, 2), "SEQ-CC-003": (3, 1),
    }
    by_id = {c["case_id"]: c for c in cases}
    assert set(by_id) == set(expected)
    for case_id, (n, e) in expected.items():
        assert by_id[case_id]["gold"]["count"] == n, case_id
        assert by_id[case_id]["gold"]["engaged_count"] == e, case_id
        assert by_id[case_id]["source"] == "pilot-cc"
        assert by_id[case_id]["track"] == "audience"


def test_seq_manifest_frames_ordered_and_hashed() -> None:
    seq = next(c for c in builder._sequence_cases() if c["case_id"] == "SEQ-CC-001")
    frames = seq["slices"]["frames"]
    assert [f["path"] for f in frames] == [
        "pilot/media/cc/SEQ-CC-001_f0.png",
        "pilot/media/cc/SEQ-CC-001_f1.png",
        "pilot/media/cc/SEQ-CC-001_f2.png",
    ]
    assert seq["slices"]["min_engaged"] == 2
    for f in frames:
        digest = hashlib.sha256((PACKAGE_ROOT / f["path"]).read_bytes()).hexdigest()
        assert digest == f["sha256"], f["path"]
