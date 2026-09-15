"""execution=loop (Taiga #16, P5): контракт остановки F3.

AC: остановка по engaged >= N / K / тик-бюджету (каждый путь -- в
terminal_reason), следующий кадр `slices.frames` на вызов (после исчерпания --
последний кадр), терминальное «запроси уточнение» → abstain, `calls_per_case`
= число вызовов. Чистый тест: MockBackend/RecordingBackend, без сети.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from guide_robot_llm.eval.runner import (
    DEFAULT_MIN_ENGAGED,
    LOOP_MAX_CALLS,
    MockBackend,
    _case_min_engaged,
    extract_engaged_freeform,
    load_prompt_variants,
    media_to_data_url,
    run_case,
    run_manifest,
    write_case_run,
)
from guide_robot_llm.eval.schema import case_from_dict
from guide_robot_llm.llm_client.backend import CompletionResult

_SHA = hashlib.sha256(b"fake-media").hexdigest()
_PROVENANCE = {
    "source": "s",
    "license": "self-generated synthetic (PIL, deterministic)",
    "version": "v1",
}

# deployed-наблюдения: не-уверенный финал («запроси уточнение») и уверенный.
OBS_NO_CANDIDATE = (
    '{"people_count": 1, "exhibit_candidates": [], '
    '"pointing_evidence": "uncertain", "pointing_box": null, '
    '"scene_facts": "неоднозначно, уточни"}'
)
OBS_CONFIDENT = (
    '{"people_count": 1, "exhibit_candidates": ["a"], '
    '"pointing_evidence": "yes", "pointing_box": [0.1, 0.2, 0.4, 0.5], '
    '"scene_facts": "один человек у шкафа"}'
)


def _ff(answer: str, abstain: bool = False) -> str:
    """freeform-ответ `{answer, confidence, abstain}`."""
    payload = {"answer": answer, "confidence": 0.8, "abstain": abstain}
    return json.dumps(payload, ensure_ascii=False)


def _case_obj(
    case_id: str,
    *,
    mode: str = "freeform",
    track: str = "audience",
    gold: dict,
    slices: dict | None = None,
    candidates: tuple[str, ...] = (),
    media_path: str = "m.jpg",
):
    return case_from_dict(
        {
            "case_id": case_id,
            "source": "pilot-cc",
            "track": track,
            "split_group_id": f"g-{case_id}",
            "media": {"path": media_path, "sha256": _SHA, "format": "jpg"},
            "prompt": {"mode": mode, "user_text": "сколько людей и кто готов?"},
            "candidates": list(candidates),
            "allowed_tools": [],
            "gold": gold,
            "slices": slices or {},
            "provenance": dict(_PROVENANCE),
        }
    )


def _make_media(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "m.jpg").write_bytes(b"fake-media-bytes")


class RecordingBackend:
    """Бэкенд-записчик: (messages, grammar) каждого вызова, ответы по очереди."""

    def __init__(self, texts: list[str]) -> None:
        self.calls: list[dict] = []
        self._texts = list(texts)
        self._i = 0

    def complete(
        self,
        messages: list[dict],
        *,
        grammar: str | None = None,
        max_tokens: int = 512,
        temperature: float = 0.2,
        telemetry=None,
    ) -> CompletionResult:
        self.calls.append({"messages": copy.deepcopy(messages), "grammar": grammar})
        text = self._texts[self._i] if self._i < len(self._texts) else ""
        self._i += 1
        return CompletionResult(text=text, finish_reason="stop")


def _last_image_url(messages: list[dict]) -> str | None:
    urls: list[str] = []
    for message in messages:
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if isinstance(part, dict) and part.get("type") == "image_url":
                urls.append(part["image_url"]["url"])
    return urls[-1] if urls else None


def _variants() -> dict:
    return load_prompt_variants()


# --- extract_engaged_freeform -------------------------------------------------


def test_extract_engaged_freeform_patterns() -> None:
    assert extract_engaged_freeform("Всего 3 человека, готовы слушать 2.") == 2
    assert extract_engaged_freeform("Всего 2 человека, готовы 0") == 0
    assert extract_engaged_freeform("2 из 3 людей слушают") == 2
    assert extract_engaged_freeform("Всего 4, готовы 1") == 1
    # Фолбэк «всего X, ... Y»: два целых, второе <= первого.
    assert extract_engaged_freeform("3 человека, из них 2 готовы слушать") == 2
    # Без устойчивой привязки числа к «готовым» -- None.
    assert extract_engaged_freeform("Всего 3 человека, готовы слушать") is None
    assert extract_engaged_freeform("кадры не разобрать") is None
    assert extract_engaged_freeform("1, 2, 3 человека") is None


# --- три пути остановки (AC: MockBackend unit tests) ---------------------------


def test_loop_stops_on_engaged_threshold(tmp_path) -> None:
    vs = _variants()
    _make_media(tmp_path)
    case = _case_obj(
        "LP-ENG",
        gold={"type": "count", "count": 3, "engaged_count": 2},
        slices={"min_engaged": 2},
    )
    llm = MockBackend(
        {
            ("LP-ENG", "freeform", "call0"): _ff("Всего 1 человек, готов слушать 0"),
            ("LP-ENG", "freeform", "call1"): _ff("Всего 3 человека, готовы слушать 2"),
        }
    )
    run = run_case(case, llm, variant=vs["A3"], data_root=tmp_path)
    assert run.status == "ok"
    assert run.calls_per_case == 2
    assert run.terminal_reason == "engaged_threshold"
    assert run.freeform is not None
    assert run.freeform.parsed["answer"] == "Всего 3 человека, готовы слушать 2"
    assert run.terminal_abstain is False
    assert [call.engaged for call in run.loop_calls] == [0, 2]


def test_loop_engaged_on_first_call_uses_two_key_fallback(tmp_path) -> None:
    vs = _variants()
    _make_media(tmp_path)
    case = _case_obj(
        "LP-ENG1",
        gold={"type": "count", "count": 2, "engaged_count": 2},
        slices={"min_engaged": 2},
    )
    # 2-ключ (без callN): один заготовленный ответ на все вызовы → стоп сразу.
    llm = MockBackend({("LP-ENG1", "freeform"): _ff("Всего 2 человека, готовы слушать 2")})
    run = run_case(case, llm, variant=vs["A3"], data_root=tmp_path)
    assert run.calls_per_case == 1
    assert run.terminal_reason == "engaged_threshold"


def test_loop_stops_on_k_exhaustion(tmp_path) -> None:
    vs = _variants()
    _make_media(tmp_path)
    case = _case_obj(
        "LP-K",
        gold={"type": "count", "count": 1, "engaged_count": 0},
        slices={"min_engaged": 2},
    )
    llm = MockBackend({("LP-K", "freeform"): _ff("Всего 1 человек, готов 0")})
    run = run_case(case, llm, variant=vs["A3"], data_root=tmp_path)
    assert run.terminal_reason == "k_exhausted"
    assert run.calls_per_case == LOOP_MAX_CALLS == 3
    assert len(run.loop_calls) == 3
    assert all(call.engaged == 0 for call in run.loop_calls)


def test_loop_stops_on_budget_exhaustion(tmp_path) -> None:
    vs = _variants()
    _make_media(tmp_path)
    case = _case_obj(
        "LP-B",
        gold={"type": "count", "count": 1, "engaged_count": 0},
        slices={"min_engaged": 2},
    )
    llm = MockBackend({("LP-B", "freeform"): _ff("Всего 1 человек, готов 0")})
    run = run_case(
        case, llm, variant=vs["A3"], data_root=tmp_path, loop_max_calls=6, loop_budget_ticks=5
    )
    assert run.terminal_reason == "budget_exhausted"
    assert run.calls_per_case == 5


def test_loop_invalid_limits_raise(tmp_path) -> None:
    vs = _variants()
    case = _case_obj("LP-V", gold={"type": "count", "count": 1, "engaged_count": 0})
    with pytest.raises(ValueError):
        run_case(case, MockBackend({}), variant=vs["A3"], data_root=tmp_path, loop_max_calls=0)
    with pytest.raises(ValueError):
        run_case(
            case, MockBackend({}), variant=vs["A3"], data_root=tmp_path, loop_budget_ticks=0
        )


# --- AC: calls_per_case = число вызовов; 2-кадровая последовательность, K=3 ----


def test_loop_calls_per_case_2frame_sequence_k3(tmp_path) -> None:
    vs = _variants()
    root = tmp_path / "data"
    root.mkdir()
    (root / "m.jpg").write_bytes(b"case-media")
    (root / "s0.png").write_bytes(b"frame-0-bytes")
    (root / "s1.png").write_bytes(b"frame-1-bytes")
    case = _case_obj(
        "LP-SEQ",
        gold={"type": "count", "count": 3, "engaged_count": 0},
        slices={
            "min_engaged": 2,
            "n_frames": 2,
            "frames": [
                {"path": "s0.png", "sha256": _SHA, "format": "png"},
                {"path": "s1.png", "sha256": _SHA, "format": "png"},
            ],
        },
    )
    backend = RecordingBackend([_ff("Всего 1 человек, готов 0")] * 3)
    run = run_case(case, backend, variant=vs["A3"], data_root=root)
    assert run.terminal_reason == "k_exhausted"
    # calls_per_case = число вызовов навыка = 3 (K, включая первый).
    assert run.calls_per_case == 3 == len(backend.calls)
    # Следующая кадра на вызов; после конца последовательности -- последний кадр.
    assert [call.frame for call in run.loop_calls] == ["s0.png", "s1.png", "s1.png"]
    url0 = media_to_data_url(root / "s0.png")
    url1 = media_to_data_url(root / "s1.png")
    assert _last_image_url(backend.calls[0]["messages"]) == url0
    assert _last_image_url(backend.calls[1]["messages"]) == url1
    assert _last_image_url(backend.calls[2]["messages"]) == url1


# --- терминальный «запроси уточнение» → abstain ---------------------------------


def test_loop_terminal_abstain_deployed(tmp_path) -> None:
    vs = _variants()
    _make_media(tmp_path)

    # Не-уверенный финал (кандидатов нет) → abstain=True.
    poi_a = _case_obj(
        "LP-PA",
        mode="deployed",
        track="pointing",
        gold={"type": "target_box", "target_id": "a"},
        candidates=("a", "b"),
    )
    run = run_case(
        poi_a, MockBackend({("LP-PA", "observation"): OBS_NO_CANDIDATE}),
        variant=vs["P3"], data_root=tmp_path,
    )
    assert run.status == "ok"
    assert run.terminal_reason == "k_exhausted"
    assert run.terminal_abstain is True
    assert run.observation is not None and run.observation.parsed is not None
    assert run.observation.parsed["exhibit_candidates"] == []

    # Уверенный финал (ровно один кандидат, evidence "yes") → abstain=False.
    poi_b = _case_obj(
        "LP-PB",
        mode="deployed",
        track="pointing",
        gold={"type": "target_box", "target_id": "a"},
        candidates=("a", "b"),
    )
    run = run_case(
        poi_b, MockBackend({("LP-PB", "observation"): OBS_CONFIDENT}),
        variant=vs["P3"], data_root=tmp_path,
    )
    assert run.terminal_abstain is False


def test_loop_terminal_abstain_freeform(tmp_path) -> None:
    vs = _variants()
    # m.jpg не создаём: вызовы без кадра (то же поведение, что у основного медиа).
    case = _case_obj("LP-PC", gold={"type": "count", "count": 1, "engaged_count": 0})
    llm = MockBackend({("LP-PC", "freeform"): _ff("кадры не разобрать", abstain=True)})
    run = run_case(case, llm, variant=vs["A3"], data_root=tmp_path)
    assert run.terminal_reason == "k_exhausted"
    assert run.terminal_abstain is True


# --- min_engaged ----------------------------------------------------------------


def test_case_min_engaged_default() -> None:
    assert _case_min_engaged(_case_obj("LP-M1", gold={"type": "count", "count": 0})) == (
        DEFAULT_MIN_ENGAGED
    )
    assert DEFAULT_MIN_ENGAGED == 2
    case_m2 = _case_obj(
        "LP-M2", slices={"min_engaged": 3}, gold={"type": "count", "count": 0}
    )
    assert _case_min_engaged(case_m2) == 3
    assert _case_min_engaged(
        _case_obj("LP-M3", slices={"min_engaged": "x"}, gold={"type": "count", "count": 0})
    ) == DEFAULT_MIN_ENGAGED


# --- run-директория: meta.json + loop.json --------------------------------------


def test_write_case_run_loop_artifacts(tmp_path) -> None:
    vs = _variants()
    _make_media(tmp_path)
    case = _case_obj(
        "LP-W",
        gold={"type": "count", "count": 1, "engaged_count": 0},
        slices={"min_engaged": 2},
    )
    llm = MockBackend({("LP-W", "freeform"): _ff("Всего 1 человек, готов 0")})
    run = run_case(case, llm, variant=vs["A3"], data_root=tmp_path)
    case_dir = write_case_run(case, run, tmp_path / "run")

    meta = json.loads((case_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["variant_id"] == "A3"
    assert meta["calls_per_case"] == 3
    assert meta["terminal_reason"] == "k_exhausted"
    assert meta["terminal_abstain"] is False
    # Финальный вызов записан как обычная фаза (raw/parsed).
    assert (case_dir / "raw_freeform.txt").is_file()
    assert json.loads((case_dir / "parsed_freeform.json").read_text(encoding="utf-8"))["answer"]

    loop = json.loads((case_dir / "loop.json").read_text(encoding="utf-8"))
    assert [row["tick"] for row in loop] == [0, 1, 2]
    assert all(row["parse_status"] == "ok" for row in loop)
    assert all(row["engaged"] == 0 for row in loop)


# --- run_manifest: строки с loop- полями ----------------------------------------


def test_run_manifest_loop_variant_rows(tmp_path) -> None:
    vs = _variants()
    _make_media(tmp_path)
    aud = _case_obj(
        "LP-M1",
        gold={"type": "count", "count": 1, "engaged_count": 0},
        slices={"min_engaged": 2},
    )
    scene = _case_obj(
        "LP-M2",
        mode="deployed",
        track="scene",
        gold={"type": "claims", "claims": ["один человек"]},
    )
    scene_obs = (
        '{"people_count": 1, "exhibit_candidates": [], '
        '"pointing_evidence": "none", "pointing_box": null, "scene_facts": "один человек"}'
    )
    llm = MockBackend(
        {
            ("LP-M1", "freeform"): _ff("Всего 1 человек, готов 0"),
            ("LP-M2", "observation"): scene_obs,
        }
    )
    lines = run_manifest([aud, scene], llm, tmp_path / "run", variant=vs["A3"], data_root=tmp_path)
    # A3 исполняет только свой трек (audience).
    assert [row["case_id"] for row in lines] == ["LP-M1"]
    assert lines[0]["calls_per_case"] == 3
    assert lines[0]["terminal_reason"] == "k_exhausted"
    assert lines[0]["terminal_abstain"] is False
    manifest = json.loads((tmp_path / "run" / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest[0]["calls_per_case"] == 3
