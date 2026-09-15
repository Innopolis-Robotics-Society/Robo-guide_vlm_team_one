"""T4: скоринг + отчёт -- фикстуры с руками посчитанными значениями.

Прогон собирается настоящим раннером + MockBackend (офлайн, детерминировано);
затем `score_run` судит его. Ожидаемые числа -- посчитаны в тесте вручную
(AC: "unit tests assert exact hand-computed values on fixed fixtures").

Разбивка:
- t4-pointing: перцепция (evidence, candidates, top-2, box IoU) + политика
  (freeform top-1, FP на no-target, abstention credit);
- t4-count: MAE + exact accuracy;
- t4-report: отчёт markdown + score.json, перцепция/политика отдельными
  секциями, заявление «no final score»;
- p6-variant (Taiga #16): engaged-метрики (MAE/exact, exclusion без
  gold/без извлечения), calls-per-case (single/cot_2pass/loop),
  per-variant-группы в отчёте.
"""

import csv
import io
import json
import struct
import zlib
from pathlib import Path

import pytest

from guide_robot_llm.eval.runner import MockBackend, VariantSpec, run_manifest
from guide_robot_llm.eval.schema import Case, MediaRef, PromptSpec, Provenance
from guide_robot_llm.eval.scoring import (
    NO_TARGET_ID,
    STATEMENT,
    box_iou,
    build_report,
    image_size,
    score_run,
    write_outputs,
)

# --- синтетические медиа: PNG 200x100 и JPEG 320x240, байты генерируются ---


def _png(width: int, height: int) -> bytes:
    """Минимальный PNG с IHDR `width x height` (скорер читает только IHDR)."""
    sig = b"\x89PNG\r\n\x1a\n"

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return (
            struct.pack(">I", len(data))
            + body
            + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IEND", b"")


def _jpeg(width: int, height: int) -> bytes:
    """Минимальный JPEG с SOF0 `height x width` (после APP-сегмента)."""
    sof = (
        b"\xff\xc0"
        + struct.pack(">H", 8)  # длина сегмента
        + b"\x08"  # precision
        + struct.pack(">HH", height, width)
        + b"\x01\x01\x01"  # planes, quant, sampling
    )
    return b"\xff\xd8" + sof + b"\xff\xd9"


PNG_200_100 = "p1.png"
JPG_320_240 = "m.jpg"
FAKE_MEDIA = "fake.bin"


def _case(
    case_id: str,
    *,
    track: str = "pointing",
    source: str = "pilot-cc",
    mode: str = "deployed",
    gold: dict,
    candidates: tuple[str, ...] = ("a", "b"),
    tools: tuple[str, ...] = ("reply",),
    slices: dict | None = None,
    media: str = FAKE_MEDIA,
    media_sha: str = "0" * 64,
) -> Case:
    return Case(
        case_id=case_id,
        source=source,
        track=track,
        split_group_id=f"g-{case_id.lower()}",
        media=MediaRef(
            path=media,
            sha256=media_sha,
            format="png" if media.endswith(".png") else "jpg",
        ),
        prompt=PromptSpec(mode=mode, user_text="x"),
        candidates=candidates,
        allowed_tools=tools,
        gold=gold,
        provenance=Provenance(
            source=source,
            license="test",
            version="v1",
            rights_note="fixture",
        ),
        slices=slices or {},
    )


def _target_gold(
    target: str, candidates: tuple[str, ...], *, box: list[int] | None = None
) -> dict:
    return {
        "type": "target_box",
        "target_id": target,
        "box_px": box,
        "distractors": [c for c in candidates if c != target],
    }


OBS_P1 = (
    '{"people_count": 1, "exhibit_candidates": ["a", "b"],'
    ' "pointing_evidence": "yes", "pointing_box": [0.0, 0.0, 0.3, 0.6],'
    ' "scene_facts": "человек у шкафа"}'
)
OBS_P2 = (
    '{"people_count": 0, "exhibit_candidates": ["b"], "pointing_evidence": "none",'
    ' "pointing_box": null, "scene_facts": "пусто"}'
)
def _obs_count(n: int) -> str:  # фикстура-генератор
    return (
        f'{{"people_count": {n}, "exhibit_candidates": [],'
        ' "pointing_evidence": "none", "pointing_box": null,'
        f' "scene_facts": "зрительный зал"}}'
    )
OBS_TOOL = (
    '{"people_count": 1, "exhibit_candidates": [], "pointing_evidence": "none",'
    ' "pointing_box": null, "scene_facts": "x"}'
)
ACT_T1 = (
    '{"tool": "start_tour", "args": {"tour_id": "tour-lab-01"},'
    ' "confidence": 0.9, "abstain": false}'
)
ACT_T2 = '{"tool": "reply", "args": {}, "confidence": 0.6, "abstain": true}'
ACT_T3 = '{"tool": "reply", "args": {}, "confidence": 0.6, "abstain": true}'
ACT_T4 = '{"tool": "pause", "args": {}, "confidence": 0.8, "abstain": false}'
FF_P3 = '{"answer": "the Red Car", "confidence": 0.8, "abstain": false}'
FF_P4 = '{"answer": "", "confidence": 0.2, "abstain": true}'
FF_P5 = '{"answer": "chair", "confidence": 0.7, "abstain": false}'


def _build_run(tmp_path: Path) -> Path:
    """14 кейсов + canned-ответы → run-директория настоящим раннером."""
    ab = ("a", "b")
    ep = ("epa", "epb")
    cases = [
        # перцепция pointing (deployed): P1 -- всё верно, P2 -- всё неверно
        _case("SC-P1", source="dp", gold=_target_gold("a", ab, box=[0, 0, 100, 100]),
              slices={"n_distractors": 1}, media=PNG_200_100),
        _case("SC-P2", source="dp", gold=_target_gold("a", ab, box=[0, 0, 100, 100]),
              slices={"n_distractors": 2}, media=PNG_200_100),
        # политика pointing (freeform, авторский QA-протокол)
        _case("SC-P3", source="egopoint", mode="freeform",
              gold=_target_gold("epa", ep), candidates=ep,
              slices={"answer_map": {"red car": "epa", "blue vase": "epb"}, "n_distractors": 1}),
        _case("SC-P4", source="egopoint", mode="freeform", gold={"type": "unanswerable"}),
        _case("SC-P5", source="egopoint", mode="freeform", gold={"type": "unanswerable"}),
        # аудитория: MAE 0.5, exact 0.5 (вручную: ошибки 1 и 0)
        _case("SC-C1", source="aghri", track="audience", gold={"type": "count", "count": 2},
              candidates=(), slices={"count_bucket": "2"}),
        _case("SC-C2", source="aghri", track="audience", gold={"type": "count", "count": 3},
              candidates=(), slices={"count_bucket": "3"}),
        # политика tool: T1 -- точное совпадение, T2 -- отказ,
        # T3 -- обоснованный отказ (credit), T4 -- FP (инструмент при gold-отказе)
        _case("SC-T1", source="pilot-cc", track="tool",
              gold={"type": "action", "tool": "start_tour", "args": {"tour_id": "tour-lab-01"}},
              candidates=(), tools=("reply", "start_tour")),
        _case("SC-T2", source="pilot-cc", track="tool",
              gold={"type": "action", "tool": "start_tour", "args": {"tour_id": "tour-lab-01"}},
              candidates=(), tools=("reply", "start_tour")),
        _case("SC-T3", source="pilot-cc", track="tool",
              gold={"type": "action", "abstention_reason": "injection"},
              candidates=(), tools=("reply", "pause")),
        _case("SC-T4", source="pilot-cc", track="tool",
              gold={"type": "action", "abstention_reason": "injection"},
              candidates=(), tools=("reply", "pause")),
        # сцена: claims и unanswerable -- записываем, без вердикта
        _case("SC-S1", source="pilot-cc", track="scene",
              gold={"type": "claims", "claims": ["красный короб", "синий шкаф"]}, candidates=()),
        _case("SC-S2", source="pilot-cc", track="scene", gold={"type": "unanswerable"}),
        # parse_failed: не судим, не дроп
        _case("SC-PF", source="dp", gold=_target_gold("a", ab, box=[0, 0, 100, 100]),
              media=JPG_320_240),
    ]
    responses: dict[tuple[str, str], str] = {
        ("SC-P1", "observation"): OBS_P1,
        ("SC-P2", "observation"): OBS_P2,
        ("SC-P3", "freeform"): FF_P3,
        ("SC-P4", "freeform"): FF_P4,
        ("SC-P5", "freeform"): FF_P5,
        ("SC-C1", "observation"): _obs_count(1),
        ("SC-C2", "observation"): _obs_count(3),
        ("SC-T1", "observation"): OBS_TOOL,
        ("SC-T1", "action"): ACT_T1,
        ("SC-T2", "observation"): OBS_TOOL,
        ("SC-T2", "action"): ACT_T2,
        ("SC-T3", "observation"): OBS_TOOL,
        ("SC-T3", "action"): ACT_T3,
        ("SC-T4", "observation"): OBS_TOOL,
        ("SC-T4", "action"): ACT_T4,
        ("SC-S1", "observation"): OBS_TOOL,
        ("SC-S2", "observation"): OBS_TOOL,
        ("SC-PF", "observation"): "not json at all",
    }
    (tmp_path / PNG_200_100).write_bytes(_png(200, 100))
    (tmp_path / JPG_320_240).write_bytes(_jpeg(320, 240))
    (tmp_path / FAKE_MEDIA).write_bytes(b"not an image")
    backend = MockBackend(responses)
    out = tmp_path / "run"
    run_manifest(cases, backend, out, data_root=tmp_path)
    return out


# --- примитивы: box IoU и размер картинки ------------------------------------


def test_box_iu_exact_hand_computed_values() -> None:
    # пересечение [0,0,0.3,0.6]∩[0,0,0.5,1.0] = 0.18; объединение = 0.5
    assert box_iou((0.0, 0.0, 0.5, 1.0), (0.0, 0.0, 0.3, 0.6)) == pytest.approx(0.36)
    assert box_iou((0.0, 0.0, 1.0, 1.0), (0.0, 0.0, 1.0, 1.0)) == 1.0
    assert box_iou((0.0, 0.0, 1.0, 1.0), (2.0, 2.0, 3.0, 3.0)) == 0.0
    assert box_iou((0.0, 0.0, 0.0, 0.0), (0.0, 0.0, 1.0, 1.0)) == 0.0  # вырожденный


def test_image_size_png_jpeg_and_unknown(tmp_path: Path) -> None:
    png = tmp_path / "p.png"
    png.write_bytes(_png(200, 100))
    jpg = tmp_path / "j.jpg"
    jpg.write_bytes(_jpeg(320, 240))
    other = tmp_path / "x.bin"
    other.write_bytes(b"hello world")
    assert image_size(png) == (200, 100)
    assert image_size(jpg) == (320, 240)
    assert image_size(other) is None
    assert image_size(tmp_path / "absent.png") is None


# --- t4-pointing: перцепция + политика pointing ------------------------------


def test_pointing_perception_hand_computed(tmp_path: Path) -> None:
    run_dir = _build_run(tmp_path)
    score = score_run(run_dir, data_root=tmp_path)
    p1 = score["per_case"]["SC-P1"]["perception"]
    # gold px [0,0,100,100] на 200x100 → [0, 0, 0.5, 1.0]; obs [0,0,0.3,0.6] → IoU 0.36
    assert p1["evidence_correct"] is True
    assert p1["target_in_candidates"] is True
    assert p1["top2_hit"] is True
    assert p1["box_iou"] == 0.36
    p2 = score["per_case"]["SC-P2"]["perception"]
    assert p2["evidence_correct"] is False
    assert p2["target_in_candidates"] is False
    assert p2["top2_hit"] is False
    assert p2["box_iou"] is None
    assert p2["box_iou_skipped"] == "no_observation_box"
    m = score["metrics"]["perception"]["pointing"]
    assert m["evidence_accuracy"] == {"value": 0.5, "n": 2}
    assert m["target_in_candidates"] == {"value": 0.5, "n": 2}
    assert m["top2_recall"] == {"value": 0.5, "n": 2}
    assert m["box_iou_mean"] == {"value": 0.36, "n": 1}
    assert m["box_iou_not_computed"] == 1
    assert score["per_case"]["SC-P1"]["pass"] is True
    assert score["per_case"]["SC-P2"]["pass"] is False


def test_pointing_policy_freeform_and_no_target(tmp_path: Path) -> None:
    run_dir = _build_run(tmp_path)
    score = score_run(run_dir, data_root=tmp_path)
    p3 = score["per_case"]["SC-P3"]["policy"]
    assert p3["mapped_target_id"] == "epa"  # "the Red Car" → "red car" → epa
    assert p3["top1_correct"] is True
    assert score["per_case"]["SC-P3"]["pass"] is True
    # no-target (gold unanswerable): P4 -- credit, P5 -- false positive
    p4 = score["per_case"]["SC-P4"]["policy"]
    p5 = score["per_case"]["SC-P5"]["policy"]
    assert p4["abstention_credit"] is True
    assert p4["false_positive"] is False
    assert p5["abstention_credit"] is False
    assert p5["false_positive"] is True
    assert score["per_case"]["SC-P4"]["pass"] is True
    assert score["per_case"]["SC-P5"]["pass"] is False
    m = score["metrics"]["policy"]["pointing"]
    assert m["top1_target_accuracy"] == {"value": 1.0, "n": 1}
    assert m["no_target"]["n"] == 2
    assert m["no_target"]["false_positive_rate"] == {"value": 0.5, "n": 2}
    assert m["no_target"]["abstention_credit"] == {"value": 0.5, "n": 2}


def test_freeform_letter_answer_maps_via_options() -> None:
    """MC-протокол (EgoPoint-Bench): вопрос требует ответ буквой ("Answer
    directly using the letters"), а `answer_map` держит фразы опций --
    мост буква → фраза опции из текста вопроса → id (regression: bench-40
    live, все 10 EgoPoint-кейсов отвечали буквой и структурно
    засчитывались бы промахами)."""
    from guide_robot_llm.eval.scoring import _answer_to_id

    prompt_text = (
        "What is the brand on the object I am pointing to?\n"
        "A. Ocean Blue\nB. Red Star\nC. Dream Blue\nD. Golden Harvest\n"
        "Answer directly using the letters of the options given."
    )
    amap = {"Ocean Blue": "epa", "Red Star": "epb", "Dream Blue": "epc", "Golden Harvest": "epd"}
    case = Case(
        case_id="MC-1",
        source="egopoint",
        track="pointing",
        split_group_id="g-mc",
        media=MediaRef(path=FAKE_MEDIA, sha256="0" * 64, format="png"),
        prompt=PromptSpec(mode="freeform", user_text=prompt_text),
        candidates=("epa", "epb", "epc", "epd"),
        allowed_tools=("reply",),
        gold={"type": "target_box", "target_id": "epa", "box_px": None, "distractors": ["epb"]},
        provenance=Provenance(
            source="egopoint", license="test", version="v1", rights_note="fixture"
        ),
        slices={"answer_map": amap},
    )
    assert _answer_to_id("C", case) == "epc"
    assert _answer_to_id("c", case) == "epc"  # регистр буквы не важен
    assert _answer_to_id("A", case) == "epa"
    assert _answer_to_id("D", case) == "epd"  # последняя опция + инструкция в хвосте
    assert _answer_to_id("Ocean Blue", case) == "epa"  # фраза продолжает работать
    assert _answer_to_id("E", case) is None  # буквы вне A-D
    assert _answer_to_id("1", case) is None
    assert _answer_to_id("something else", case) is None


def test_deployed_no_target_case_abstention_credit(tmp_path: Path) -> None:
    """Deployed no-target (gold `unknown`): отказ верен, ответ -- FP."""
    abstain = (
        '{"people_count": 0, "exhibit_candidates": [], "pointing_evidence": "none",'
        ' "pointing_box": null, "scene_facts": "x"}'
    )
    answered = (
        '{"people_count": 1, "exhibit_candidates": ["a"], "pointing_evidence": "yes",'
        ' "pointing_box": [0.1, 0.1, 0.2, 0.2], "scene_facts": "x"}'
    )
    gold = {"type": "target_box", "target_id": NO_TARGET_ID, "box_px": None, "distractors": ["a"]}
    cases = [
        _case("NT-1", gold=gold),
        _case("NT-2", gold=gold),
    ]
    backend = MockBackend({("NT-1", "observation"): abstain, ("NT-2", "observation"): answered})
    (tmp_path / FAKE_MEDIA).write_bytes(b"x")
    out = tmp_path / "run"
    run_manifest(cases, backend, out, data_root=tmp_path)
    score = score_run(out, data_root=tmp_path)
    assert score["per_case"]["NT-1"]["kind"] == "pointing-no-target"
    assert score["per_case"]["NT-1"]["pass"] is True
    assert score["per_case"]["NT-2"]["policy"]["false_positive"] is True
    assert score["per_case"]["NT-2"]["pass"] is False
    m = score["metrics"]["policy"]["pointing"]["no_target"]
    assert m["false_positive_rate"] == {"value": 0.5, "n": 2}
    assert m["abstention_credit"] == {"value": 0.5, "n": 2}


# --- t4-count: MAE + exact accuracy ------------------------------------------


def test_count_mae_and_exact_hand_computed(tmp_path: Path) -> None:
    run_dir = _build_run(tmp_path)
    score = score_run(run_dir, data_root=tmp_path)
    c1 = score["per_case"]["SC-C1"]["perception"]
    c2 = score["per_case"]["SC-C2"]["perception"]
    assert c1 == {"count_pred": 1, "count_gold": 2, "count_exact": False, "abs_error": 1}
    assert c2 == {"count_pred": 3, "count_gold": 3, "count_exact": True, "abs_error": 0}
    assert score["per_case"]["SC-C1"]["pass"] is False
    assert score["per_case"]["SC-C2"]["pass"] is True
    m = score["metrics"]["perception"]["audience"]
    assert m["mae"] == {"value": 0.5, "n": 2}  # (1 + 0) / 2
    assert m["exact_accuracy"] == {"value": 0.5, "n": 2}


# --- tool-политика ------------------------------------------------------------


def test_tool_exact_match_and_abstention_credit(tmp_path: Path) -> None:
    run_dir = _build_run(tmp_path)
    score = score_run(run_dir, data_root=tmp_path)
    assert score["per_case"]["SC-T1"]["policy"]["exact_match"] is True
    assert score["per_case"]["SC-T1"]["pass"] is True
    assert score["per_case"]["SC-T2"]["policy"]["abstained"] is True
    assert score["per_case"]["SC-T2"]["pass"] is False
    assert score["per_case"]["SC-T3"]["policy"]["abstention_credit"] is True
    assert score["per_case"]["SC-T3"]["pass"] is True
    assert score["per_case"]["SC-T4"]["policy"]["false_positive"] is True
    assert score["per_case"]["SC-T4"]["pass"] is False
    m = score["metrics"]["policy"]["tool"]
    assert m["exact_match_accuracy"] == {"value": 0.5, "n": 2}  # T1 ✓, T2 отказ
    assert m["no_target"]["n"] == 2
    assert m["no_target"]["false_positive_rate"] == {"value": 0.5, "n": 2}
    assert m["no_target"]["abstention_credit"] == {"value": 0.5, "n": 2}


# --- сцена и parse_failed: не судим, не дроп ---------------------------------


def test_scene_recorded_and_parse_failed_unjudged(tmp_path: Path) -> None:
    run_dir = _build_run(tmp_path)
    score = score_run(run_dir, data_root=tmp_path)
    s1 = score["per_case"]["SC-S1"]
    assert s1["kind"] == "scene-recorded"
    assert s1["pass"] is None
    assert s1["recorded"]["claims"] == ["красный короб", "синий шкаф"]
    assert s1["recorded"]["scene_facts"] == "x"
    assert score["per_case"]["SC-S2"]["pass"] is None
    pf = score["per_case"]["SC-PF"]
    assert pf["status"] == "parse_failed"
    assert pf["pass"] is None
    assert score["status_counts"] == {"ok": 13, "parse_failed": 1, "backend_error": 0}
    # судимые: 11 (14 минус сцена-2 минус parse_failed), pass 6 / fail 5
    assert score["pass_counts"] == {"pass": 6, "fail": 5, "unjudged": 3}
    assert score["errors"] == []


# --- срезy --------------------------------------------------------------------


def test_slices_by_source_and_metadata(tmp_path: Path) -> None:
    run_dir = _build_run(tmp_path)
    score = score_run(run_dir, data_root=tmp_path)
    by_source = score["slices"]["by_source"]
    assert by_source["dp"] == {
        "n": 3, "pass": 1, "fail": 1, "unjudged": 1, "pass_rate": {"value": 0.5, "n": 2}
    }
    assert by_source["aghri"] == {
        "n": 2, "pass": 1, "fail": 1, "unjudged": 0, "pass_rate": {"value": 0.5, "n": 2},
        "count_mae": {"value": 0.5, "n": 2},
    }
    assert by_source["egopoint"] == {
        "n": 3, "pass": 2, "fail": 1, "unjudged": 0, "pass_rate": {"value": 0.6667, "n": 3}
    }
    assert by_source["pilot-cc"]["n"] == 6
    assert by_source["pilot-cc"]["pass"] == 2
    assert by_source["pilot-cc"]["fail"] == 2
    assert by_source["pilot-cc"]["unjudged"] == 2
    meta = score["slices"]["by_metadata"]
    assert meta["n_distractors"]["1"] == {
        "n": 2, "pass": 2, "fail": 0, "unjudged": 0, "pass_rate": {"value": 1.0, "n": 2}
    }
    assert meta["n_distractors"]["2"] == {
        "n": 1, "pass": 0, "fail": 1, "unjudged": 0, "pass_rate": {"value": 0.0, "n": 1}
    }
    assert meta["count_bucket"]["2"]["fail"] == 1
    assert meta["count_bucket"]["3"]["pass"] == 1
    # split-группы: у синтетических кейсов каждая своя
    assert len(score["slices"]["by_split_group"]) == 14


# --- t4-report: markdown + score.json ----------------------------------------


def test_report_structure_and_statement(tmp_path: Path) -> None:
    run_dir = _build_run(tmp_path)
    score = score_run(run_dir, data_root=tmp_path)
    report = build_report(score)
    # обязательное заявление (режим диагностики)
    assert STATEMENT in report
    assert "no final project score" in report
    # перцепция и политика -- РАЗДЕЛЬНЫЕ секции
    perception_pos = report.index("## Perception")
    policy_pos = report.index("## Policy")
    slices_pos = report.index("## Slices")
    assert perception_pos < policy_pos < slices_pos
    assert "### Audience" in report
    # ключевые числа из ручного расчёта
    assert "0.36 (n=1)" in report
    assert "0.5 (n=2)" in report
    # per-case приложен
    assert "SC-P1" in report
    assert "| SC-S1 |" in report
    assert score["statement"] == STATEMENT
    # пометки прогона (T10: состав/исключения срезов) -- после заявления, до метрик
    noted = build_report(score, notes="DP slice: not acquired")
    notes_pos = noted.index("## Run notes")
    assert noted.index(STATEMENT) < notes_pos < noted.index("## Perception")
    assert "DP slice: not acquired" in noted


def test_write_outputs_and_manifest_pass_backfill(tmp_path: Path) -> None:
    run_dir = _build_run(tmp_path)
    score = score_run(run_dir, data_root=tmp_path)
    write_outputs(run_dir, score)
    assert (run_dir / "score.json").is_file()
    assert (run_dir / "report.md").is_file()
    on_disk = json.loads((run_dir / "score.json").read_text(encoding="utf-8"))
    assert on_disk["statement"] == STATEMENT
    assert on_disk["metrics"]["perception"]["audience"]["mae"] == {"value": 0.5, "n": 2}
    # `pass` в run_manifest.json заполнен из score
    lines = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    passes = {line["case_id"]: line["pass"] for line in lines}
    assert passes["SC-P1"] is True
    assert passes["SC-P2"] is False
    assert passes["SC-C2"] is True
    assert passes["SC-C1"] is False
    assert passes["SC-S1"] is None  # сцена -- не судим
    assert passes["SC-PF"] is None  # parse_failed -- не судим
    assert passes["SC-T3"] is True
    assert passes["SC-T4"] is False


def test_results_jsonl_and_summary_csv(tmp_path: Path) -> None:
    """AC #10 «Export JSONL and CSV summary».

    `results.jsonl` -- построчно per-episode (порядок манифеста, `pass`
    заполнен); `summary.csv` -- плоская сводка: scope, group, metric, value, n.
    """
    run_dir = _build_run(tmp_path)
    score = score_run(run_dir, data_root=tmp_path)
    write_outputs(run_dir, score)

    # --- results.jsonl ---
    jsonl_lines = (run_dir / "results.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(jsonl_lines) == score["n_cases"]
    rows = {json.loads(line)["case_id"]: json.loads(line) for line in jsonl_lines}
    assert rows["SC-P1"]["pass"] is True
    assert rows["SC-PF"]["pass"] is None  # parse_failed -- не судим
    assert rows["SC-S1"]["pass"] is None  # сцена -- не судим
    assert rows["SC-C1"]["perception"]["abs_error"] == 1
    manifest_ids = [
        line["case_id"]
        for line in json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    ]
    assert [json.loads(line)["case_id"] for line in jsonl_lines] == manifest_ids

    # --- summary.csv ---
    csv_text = (run_dir / "summary.csv").read_text(encoding="utf-8")
    parsed = list(csv.DictReader(io.StringIO(csv_text)))
    assert list(parsed[0].keys()) == ["scope", "group", "metric", "value", "n"]
    by_key = {(r["scope"], r["group"], r["metric"]): r for r in parsed}
    assert by_key[("counts", "", "n_cases")]["value"] == str(score["n_cases"])
    assert by_key[("counts", "", "status_parse_failed")]["value"] == "1"
    # ручные значения: MAE 0.5 (n=2), top-2 0.5 (n=2)
    mae = by_key[("perception", "audience", "mae")]
    assert (mae["value"], mae["n"]) == ("0.5", "2")
    top2 = by_key[("perception", "pointing", "top2_recall")]
    assert (top2["value"], top2["n"]) == ("0.5", "2")
    # no-target-блок разворачивается в точечные метрики
    assert by_key[("policy", "pointing", "no_target.false_positive_rate")]["value"] == "0.5"
    # срезы: по source и split_group
    assert any(r["group"] == "source:dp" for r in parsed if r["scope"] == "slice")
    assert any(r["group"] == "split_group:g-sc-p1" for r in parsed if r["scope"] == "slice")
    # прогон без варианта группируется в (no variant)
    assert by_key[("variant", "(no variant)", "n")]["value"] == str(score["n_cases"])


def test_run_config_in_score_and_report_header(tmp_path: Path) -> None:
    """AC #10 «freeze metadata»: run_config.json → score.json + шапка отчёта."""
    run_dir = _build_run(tmp_path)
    (run_dir / "run_config.json").write_text(
        json.dumps(
            {
                "generated": "2026-09-16T00:00:00+00:00",
                "manifest": {"path": "m.jsonl", "sha256": "ab" * 32, "n_cases": 14},
                "backend": {
                    "kind": "http",
                    "base_url": "http://127.0.0.1:8080/v1",
                    "model_name": "qwen3.8-27b",
                    "seed": 42,
                    "api_key_set": True,
                },
                "prompt": {"variant_id": None, "examples_root": None, "temperature": 0.2},
                "params": {},
            }
        ),
        encoding="utf-8",
    )
    score = score_run(run_dir, data_root=tmp_path)
    assert score["run_config"] is not None
    assert score["run_config"]["backend"]["seed"] == 42
    report = build_report(score)
    assert (
        "- Backend: `http://127.0.0.1:8080/v1` · model `qwen3.8-27b` · seed `42`"
        in report
    )
    assert "(sha256 abababababab…)" in report
    write_outputs(run_dir, score)
    on_disk = json.loads((run_dir / "score.json").read_text(encoding="utf-8"))
    assert on_disk["run_config"]["backend"]["model_name"] == "qwen3.8-27b"


def test_no_run_config_is_tolerated(tmp_path: Path) -> None:
    """Старые run-директории (без run_config.json) не роняют скоринг и экспорт."""
    run_dir = _build_run(tmp_path)
    score = score_run(run_dir, data_root=tmp_path)
    assert score["run_config"] is None
    report = build_report(score)
    assert "- Backend:" not in report
    write_outputs(run_dir, score)
    assert (run_dir / "results.jsonl").is_file()
    assert (run_dir / "summary.csv").is_file()


def test_scoring_tolerates_missing_meta(tmp_path: Path) -> None:
    """Кейс без meta.json не роняет скоринг: ошибка записана, кейс не судим."""
    run_dir = _build_run(tmp_path)
    (run_dir / "cases" / "SC-P1" / "meta.json").unlink()
    score = score_run(run_dir, data_root=tmp_path)
    assert score["per_case"]["SC-P1"]["pass"] is None
    assert score["per_case"]["SC-P1"]["status"] == "ok"
    assert any("SC-P1" in e for e in score["errors"])
    # остальные кейсы судятся как обычно
    assert score["per_case"]["SC-C2"]["pass"] is True
    assert score["pass_counts"]["pass"] == 5  # 6 минус SC-P1


# --- P6 (Taiga #16): engaged-метрики, calls, per-variant-группы --------------


def _variant(execution: str) -> VariantSpec:
    """Тестовый A-вариант: freeform, audience, инструкция-заглушка."""
    return VariantSpec(
        id={"single": "A1", "cot_2pass": "A2", "loop": "A3"}[execution],
        skill="audience",
        track="audience",
        axis="direct",
        technique="test",
        source=None,
        mode="freeform",
        execution=execution,
        text="Считай людей в кадре.",
    )


def _ff(answer: str, conf: float = 0.8) -> str:
    """Freeform-ответ JSON-строкой (корень {answer, confidence, abstain})."""
    return f'{{"answer": "{answer}", "confidence": {conf}, "abstain": false}}'


FF_ENG_2 = _ff("Всего 3, готовы слушать 2")
FF_ENG_1 = _ff("Всего 4, из них готовы слушать 1")
FF_NO_ENG = _ff("Люди в зале, число трудно сказать", 0.4)
FF_TOTAL_ONLY = _ff("Всего 2", 0.9)


def test_engagement_metrics_hand_computed_and_exclusion(tmp_path: Path) -> None:
    """Engaged MAE/exact по gold.engaged_count; без gold/без сигнала -- исключение."""
    cases = [
        _case("EV-1", source="pilot-cc", track="audience", mode="freeform",
              gold={"type": "count", "count": 3, "engaged_count": 2}, candidates=()),
        _case("EV-2", source="pilot-cc", track="audience", mode="freeform",
              gold={"type": "count", "count": 4, "engaged_count": 2}, candidates=()),
        # есть gold, но сигнал не извлекается → из метрик исключается, не 0
        _case("EV-3", source="pilot-cc", track="audience", mode="freeform",
              gold={"type": "count", "count": 2, "engaged_count": 1}, candidates=()),
        # без gold.engaged_count → engaged-поля вообще не записываются
        _case("EV-N", source="pilot-cc", track="audience", mode="freeform",
              gold={"type": "count", "count": 2}, candidates=()),
        # deployed: в замороженной грамматике наблюдения поля engaged нет
        _case("EV-D", source="pilot-cc", track="audience",
              gold={"type": "count", "count": 2, "engaged_count": 1},
              candidates=()),
    ]
    responses = {
        ("EV-1", "freeform"): FF_ENG_2,   # 2/2 → exact, err 0
        ("EV-2", "freeform"): FF_ENG_1,   # 1/2 → err 1
        ("EV-3", "freeform"): FF_NO_ENG,  # не извлекается
        ("EV-N", "freeform"): FF_TOTAL_ONLY,
        ("EV-D", "observation"): _obs_count(2),
    }
    (tmp_path / FAKE_MEDIA).write_bytes(b"x")
    out = tmp_path / "run"
    run_manifest(cases, MockBackend(responses), out, data_root=tmp_path)
    score = score_run(out, data_root=tmp_path)
    e1 = score["per_case"]["EV-1"]["perception"]
    e2 = score["per_case"]["EV-2"]["perception"]
    e3 = score["per_case"]["EV-3"]["perception"]
    en = score["per_case"]["EV-N"]["perception"]
    ed = score["per_case"]["EV-D"]["perception"]
    assert e1["engaged_pred"] == 2 and e1["engaged_gold"] == 2
    assert e1["engaged_exact"] is True and e1["engaged_abs_error"] == 0
    assert e2["engaged_pred"] == 1
    assert e2["engaged_exact"] is False and e2["engaged_abs_error"] == 1
    assert e3["engaged_pred"] is None
    assert "engaged_exact" not in e3 and "engaged_abs_error" not in e3
    # без gold -- engaged-ключей нет вовсе (не заполняем нулями)
    assert not any(key.startswith("engaged") for key in en)
    # deployed: gold записан, предсказания нет → исключается
    assert ed["engaged_gold"] == 1 and ed["engaged_pred"] is None
    assert "engaged_exact" not in ed
    m = score["metrics"]["perception"]["audience"]
    # MAE (0 + 1) / 2 = 0.5, n=2 (не 5): EV-3/EV-N/EV-D исключены
    assert m["engaged_mae"] == {"value": 0.5, "n": 2}
    assert m["engaged_exact_accuracy"] == {"value": 0.5, "n": 2}
    # count-метрики не затронуты (freeform-кейсы без obs их не дают)
    assert m["mae"] == {"value": 0.0, "n": 1}


def test_variant_groups_calls_latency_and_report(tmp_path: Path) -> None:
    """Per-variant-группы: single-выполнение, calls=1, engaged в отчёте."""
    cases = [
        _case("VG-1", source="pilot-cc", track="audience", mode="freeform",
              gold={"type": "count", "count": 3, "engaged_count": 2}, candidates=()),
        _case("VG-2", source="pilot-cc", track="audience", mode="freeform",
              gold={"type": "count", "count": 4, "engaged_count": 2}, candidates=()),
    ]
    responses = {
        ("VG-1", "freeform"): FF_ENG_2,
        ("VG-2", "freeform"): FF_ENG_1,
    }
    (tmp_path / FAKE_MEDIA).write_bytes(b"x")
    out = tmp_path / "run_a1"
    run_manifest(cases, MockBackend(responses), out, variant=_variant("single"),
                 data_root=tmp_path)
    score = score_run(out, data_root=tmp_path)
    assert score["per_case"]["VG-1"]["variant_id"] == "A1"
    assert score["per_case"]["VG-1"]["calls"] == 1
    assert score["per_case"]["VG-1"]["latency_ms"] is not None
    g = score["variants"]["A1"]
    assert g["n"] == 2 and g["unjudged"] == 2
    assert "count_mae" not in g  # freeform: observation-фазы нет → count-метрик нет
    assert g["engaged_mae"] == {"value": 0.5, "n": 2}
    assert g["engaged_exact_accuracy"] == {"value": 0.5, "n": 2}
    assert g["calls_per_case"] == {"value": 1.0, "n": 2}
    assert g["latency_ms"]["n"] == 2
    report = build_report(score)
    assert STATEMENT in report
    assert "## Variants" in report
    assert "### A1" in report
    assert "engaged MAE" in report
    # engaged-строка и в общей Audience-таблице
    assert "0.5 (n=2)" in report


def test_cot_2pass_and_loop_calls_per_case(tmp_path: Path) -> None:
    """calls: cot_2pass = 2 (сумма по фазам), loop = meta calls_per_case (K=3)."""
    cases = [
        _case("VG-2P", source="pilot-cc", track="audience", mode="freeform",
              gold={"type": "count", "count": 3, "engaged_count": 2}, candidates=()),
        _case("VG-L", source="pilot-cc", track="audience", mode="freeform",
              gold={"type": "count", "count": 3, "engaged_count": 1}, candidates=()),
    ]
    responses = {
        ("VG-2P", "freeform", "pass1"): "Считаю: один, два, три.",
        ("VG-2P", "freeform", "pass2"): FF_ENG_2,
        ("VG-L", "freeform"): FF_NO_ENG,  # без engaged-сигнала → стоп по K
    }
    (tmp_path / FAKE_MEDIA).write_bytes(b"x")
    out_cot = tmp_path / "run_a2"
    run_manifest(cases[:1], MockBackend(responses), out_cot,
                 variant=_variant("cot_2pass"), data_root=tmp_path)
    score_cot = score_run(out_cot, data_root=tmp_path)
    assert score_cot["per_case"]["VG-2P"]["calls"] == 2
    g = score_cot["variants"]["A2"]
    assert g["calls_per_case"] == {"value": 2.0, "n": 1}
    assert g["engaged_exact_accuracy"] == {"value": 1.0, "n": 1}
    out_loop = tmp_path / "run_a3"
    run_manifest(cases[1:], MockBackend(responses), out_loop,
                 variant=_variant("loop"), data_root=tmp_path)
    score_loop = score_run(out_loop, data_root=tmp_path)
    assert score_loop["per_case"]["VG-L"]["calls"] == 3  # K=3, k_exhausted
    g3 = score_loop["variants"]["A3"]
    assert g3["calls_per_case"] == {"value": 3.0, "n": 1}
    # engaged не извлекается → в группе нет engaged-метрик, а не 0
    assert "engaged_mae" not in g3


def test_no_variant_grouped_as_base(tmp_path: Path) -> None:
    """Прогон без варианта: группа `(no variant)`, заяvek на месте."""
    cases = [_case("VG-B", source="pilot-cc", track="audience", mode="freeform",
                   gold={"type": "count", "count": 3, "engaged_count": 2}, candidates=())]
    responses = {("VG-B", "freeform"): FF_ENG_2}
    (tmp_path / FAKE_MEDIA).write_bytes(b"x")
    out = tmp_path / "run_base"
    run_manifest(cases, MockBackend(responses), out, data_root=tmp_path)
    score = score_run(out, data_root=tmp_path)
    assert set(score["variants"]) == {"(no variant)"}
    assert score["variants"]["(no variant)"]["engaged_mae"] == {"value": 0.0, "n": 1}
    report = build_report(score)
    assert "### (no variant)" in report
    assert STATEMENT in report


def test_score_run_empty_metric_groups_do_not_crash(tmp_path: Path) -> None:
    """Только tool-кейсы: перцепционных групп нет → метрики пустые, не краш (AC #10)."""
    cases = [
        _case("ONLY-T", source="pilot-cc", track="tool",
              gold={"type": "action", "tool": "start_tour", "args": {"tour_id": "tour-lab-01"}},
              candidates=(), tools=("reply", "start_tour")),
    ]
    backend = MockBackend({("ONLY-T", "observation"): OBS_TOOL, ("ONLY-T", "action"): ACT_T1})
    (tmp_path / FAKE_MEDIA).write_bytes(b"x")
    out = tmp_path / "run"
    run_manifest(cases, backend, out, data_root=tmp_path)
    score = score_run(out, data_root=tmp_path)
    assert score["metrics"]["perception"]["pointing"] == {}
    assert score["metrics"]["perception"]["audience"] == {}
    assert score["metrics"]["policy"]["tool"]["exact_match_accuracy"] == {"value": 1.0, "n": 1}
    report = build_report(score)
    assert STATEMENT in report
    assert "нет данных" in report


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
