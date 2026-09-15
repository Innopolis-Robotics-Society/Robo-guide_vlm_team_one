"""Промпт-варианты (Taiga #16, P3): 18 файлов + манифест prompt_variants.json.

Инварианты замороженного манифеста: id/skill/mode/execution, sources заимствованных
техник (V2/V3/V4), few-shot-примеры (медиа существуют, sha256 совпадает, в eval-наборы
не входят), ответы D4 парсятся как наблюдение-JSON и не выдумывают кандидатов.
Чистый тест: без ROS, без сети.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = PACKAGE_ROOT / "guide_robot_llm" / "eval"
MANIFEST = EVAL_DIR / "prompt_variants.json"
VARIANTS_DIR = EVAL_DIR / "prompt_variants"
EVAL_MANIFESTS = sorted((PACKAGE_ROOT / "eval_manifests").glob("*.jsonl"))
CC_FIXTURES = PACKAGE_ROOT / "pilot" / "fixtures" / "cc"

EXPECTED_IDS = (
    "D0", "D1", "D2", "D3", "D4", "D_base",
    "P0", "P1", "P2", "P3", "P4", "P_base",
    "A0", "A1", "A2", "A3", "A4", "A_base",
)
SKILL_BY_PREFIX = {"D": "describe_scene", "P": "resolve_pointing", "A": "audience_engagement"}
COT_IDS = {"D2", "P2", "A2"}
LOOP_IDS = {"P3", "A3"}
BORROWED_IDS = {"D2", "D3", "D4", "P2", "P3", "P4", "A2", "A3", "A4"}


def _variants() -> dict[str, dict]:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {v["id"]: v for v in data["variants"]}


def test_manifest_loads_and_18_unique_ids() -> None:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert {v["id"] for v in data["variants"]} == set(EXPECTED_IDS)
    assert len(data["variants"]) == 18
    assert set(data["execution_modes"]) == {"single", "cot_2pass", "loop"}


def test_18_files_exist_nonempty_russian() -> None:
    files = sorted(p for p in VARIANTS_DIR.glob("*.txt"))
    assert len(files) == 18
    for vid in EXPECTED_IDS:
        assert (VARIANTS_DIR / f"{vid}.txt").is_file(), vid
    for p in files:
        text = p.read_text(encoding="utf-8")
        assert text.strip(), f"{p.name}: пустой файл"
        assert re.search(r"[а-яА-Я]", text), f"{p.name}: не по-русски"


def test_borrowed_techniques_have_arxiv_source() -> None:
    vs = _variants()
    for vid in sorted(BORROWED_IDS):
        src = vs[vid]["source"]
        assert src, f"{vid}: source пуст"
        assert "arXiv:" in src, f"{vid}: source без arXiv-ссылки"
    for vid in EXPECTED_IDS:
        if vid not in BORROWED_IDS:
            assert vs[vid]["source"] is None, f"{vid}: source должен быть null"


def test_mode_execution_invariants() -> None:
    vs = _variants()
    for vid, v in vs.items():
        assert v["skill"] == SKILL_BY_PREFIX[vid[0]], vid
        assert v["mode"] == ("freeform" if vid[0] == "A" else "deployed"), vid
        if vid in COT_IDS:
            assert v["execution"] == "cot_2pass", vid
        elif vid in LOOP_IDS:
            assert v["execution"] == "loop", vid
        else:
            assert v["execution"] == "single", vid


def test_base_variants_null_text_production_axis() -> None:
    vs = _variants()
    for vid in ("D_base", "P_base", "A_base"):
        v = vs[vid]
        assert v["text"] is None, vid
        assert v["axis"] == "production", vid
        assert v["examples"] == [], vid


def test_variant_text_points_to_file() -> None:
    vs = _variants()
    for vid, v in vs.items():
        if vid.endswith("_base"):
            continue
        assert v["text"] == f"prompt_variants/{vid}.txt", vid
        assert (EVAL_DIR / v["text"]).is_file(), vid


def test_examples_only_for_v4() -> None:
    vs = _variants()
    for vid, v in vs.items():
        if vid in {"D4", "P4", "A4"}:
            assert len(v["examples"]) == (2 if vid == "D4" else 3), vid
        else:
            assert v["examples"] == [], vid


def test_example_media_exist_sha256_matches_no_leakage() -> None:
    vs = _variants()
    eval_media: set[str] = set()
    for mf in EVAL_MANIFESTS:
        for line in mf.read_text(encoding="utf-8").splitlines():
            if line.strip():
                eval_media.add(json.loads(line)["media"]["path"])
    ex_paths: set[str] = set()
    for vid in ("D4", "P4", "A4"):
        for e in vs[vid]["examples"]:
            p = PACKAGE_ROOT / e["media"]["path"]
            assert p.is_file(), e["media"]["path"]
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
            assert digest == e["media"]["sha256"], e["id"]
            assert e["media"]["format"] == "png"
            assert e["answer"].strip(), e["id"]
            ex_paths.add(e["media"]["path"])
    assert ex_paths and not (ex_paths & eval_media), "few-shot-примеры утекают в eval-наборы"


def test_examples_match_cc_fixtures() -> None:
    vs = _variants()
    for vid in ("D4", "P4"):
        for e in vs[vid]["examples"]:
            gt = json.loads((CC_FIXTURES / f"{e['id']}.json").read_text(encoding="utf-8"))
            assert set(gt["objects"]) == set(e["context"]["candidates"]), e["id"]
    p01 = next(e for e in vs["P4"]["examples"] if e["id"] == "EX-CC-P-01")
    gt = json.loads((CC_FIXTURES / "EX-CC-P-01.json").read_text(encoding="utf-8"))
    assert gt["pointing"]["target_id"] in p01["context"]["candidates"]


def test_d4_answers_parse_as_observation_json() -> None:
    vs = _variants()
    for e in vs["D4"]["examples"]:
        data = json.loads(e["answer"])
        assert set(data) == {
            "people_count", "exhibit_candidates", "pointing_evidence",
            "pointing_box", "scene_facts",
        }
        assert isinstance(data["people_count"], int)
        allowed = set(e["context"]["candidates"])
        assert set(data["exhibit_candidates"]) <= allowed, e["id"]
        assert data["pointing_evidence"] in {"none", "yes", "uncertain"}
        assert len(data["scene_facts"]) <= 400
