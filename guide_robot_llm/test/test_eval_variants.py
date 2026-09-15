"""Промпт-варианты в раннере (Taiga #16, P4): ось варианта, few-shot, CoT 2-pass.

Только `MockBackend`/записывающий бэкенд + коммиченные EX-CC медиа -- без сети.
AC: прогон манифеста по id варианта (только кейсы трека варианта), cot_2pass
(2 вызова, pass-1 grammar=None, pass-2 грамматика + текст pass-1 в контексте),
few-shot (пары кадр+ответ до кейсовых кадров).
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from guide_robot_llm.eval.runner import (
    _FREEFORM_INSTRUCTION,
    LoopVariantNotImplemented,
    MockBackend,
    _observation_instruction,
    _variant_deployed_instruction,
    _variant_freeform_instruction,
    load_prompt_variants,
    run_case,
    run_manifest,
    write_case_run,
)
from guide_robot_llm.llm_client.backend import CompletionResult

PACKAGE_ROOT = Path(__file__).resolve().parents[1]

_SHA = hashlib.sha256(b"fake-media").hexdigest()
_PROVENANCE = {
    "source": "s",
    "license": "self-generated synthetic (PIL, deterministic)",
    "version": "v1",
}
OBS_GOOD = (
    '{"people_count": 1, "exhibit_candidates": ["a"], '
    '"pointing_evidence": "yes", "pointing_box": [0.1, 0.2, 0.4, 0.5], '
    '"scene_facts": "один человек у шкафа"}'
)
FREEFORM_GOOD = '{"answer": "2 человека, готов 1", "confidence": 0.8, "abstain": false}'


def _case(case_id: str, track: str, gold: dict, mode: str = "deployed") -> dict:
    return {
        "case_id": case_id,
        "source": "pilot-cc",
        "track": track,
        "split_group_id": f"g-{case_id}",
        "media": {"path": "m.jpg", "sha256": _SHA, "format": "jpg"},
        "prompt": {"mode": mode, "user_text": "что это?"},
        "candidates": ["a", "b"],
        "allowed_tools": ["reply", "say"],
        "gold": gold,
        "slices": {},
        "provenance": dict(_PROVENANCE),
    }


def _fixture_manifest(tmp_path: Path) -> tuple[Path, Path]:
    """4 кейса (scene/pointing/audience/tool) + медиа → (манифест, data_root)."""
    root = tmp_path / "data"
    root.mkdir()
    (root / "m.jpg").write_bytes(b"fake-jpeg-bytes")
    rows = [
        _case("VAR-SCN-01", "scene", {"type": "claims", "claims": ["один человек"]}),
        _case("VAR-POI-01", "pointing", {"type": "target_box", "target_id": "a"}),
        _case(
            "VAR-AUD-01",
            "audience",
            {"type": "count", "count": 2, "engaged_count": 1},
            mode="freeform",
        ),
        _case("VAR-TOL-01", "tool", {"type": "action", "tool": "reply", "args": {}}),
    ]
    manifest = tmp_path / "cases.jsonl"
    manifest.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )
    return manifest, root


def _load_cases(tmp_path: Path):
    from guide_robot_llm.eval.loader import load_manifest

    manifest, _ = _fixture_manifest(tmp_path)
    return load_manifest(manifest)


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


def _image_urls(messages: list[dict]) -> list[str]:
    urls: list[str] = []
    for message in messages:
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if isinstance(part, dict) and part.get("type") == "image_url":
                urls.append(part["image_url"]["url"])
    return urls


def _variants() -> dict:
    return load_prompt_variants()  # коммиченные EX-CC медиа, sha256 сверяются


def test_load_prompt_variants_18_and_tracks() -> None:
    vs = _variants()
    assert len(vs) == 18
    for vid, spec in vs.items():
        assert (spec.text is None) == vid.endswith("_base"), vid
    assert vs["D0"].text.startswith("Опиши")
    assert vs["A4"].examples and len(vs["A4"].examples) == 3
    # треки: D* → scene, P* → pointing, A* → audience
    assert vs["D2"].track == "scene" and vs["P2"].track == "pointing"
    assert vs["A2"].track == "audience"
    # execution по дизайну #16
    assert {v.id for v in vs.values() if v.execution == "cot_2pass"} == {"D2", "P2", "A2"}
    assert {v.id for v in vs.values() if v.execution == "loop"} == {"P3", "A3"}


def test_run_manifest_by_variant_id_only_runs_its_track(tmp_path) -> None:
    cases = _load_cases(tmp_path)
    vs = _variants()
    data_root = tmp_path / "data"

    # P1: deployed single → только pointing-кейс
    llm = MockBackend({("VAR-POI-01", "observation"): OBS_GOOD})
    lines = run_manifest(cases, llm, tmp_path / "run-p1", variant=vs["P1"], data_root=data_root)
    assert [row["case_id"] for row in lines] == ["VAR-POI-01"]
    assert all(row["variant"] == "P1" and row["status"] == "ok" for row in lines)
    manifest = json.loads((tmp_path / "run-p1" / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest[0]["variant"] == "P1"

    # A1: freeform single → только audience-кейс
    llm = MockBackend({("VAR-AUD-01", "freeform"): FREEFORM_GOOD})
    lines = run_manifest(cases, llm, tmp_path / "run-a1", variant=vs["A1"], data_root=data_root)
    assert [row["case_id"] for row in lines] == ["VAR-AUD-01"]
    assert lines[0]["status"] == "ok"

    # D1: deployed single → только scene-кейс (tool-кейс вне всех навыков)
    llm = MockBackend({("VAR-SCN-01", "observation"): OBS_GOOD})
    lines = run_manifest(cases, llm, tmp_path / "run-d1", variant=vs["D1"], data_root=data_root)
    assert [row["case_id"] for row in lines] == ["VAR-SCN-01"]


def test_cot_2pass_two_calls_grammar_and_bridge(tmp_path) -> None:
    cases = {c.case_id: c for c in _load_cases(tmp_path)}
    vs = _variants()
    data_root = tmp_path / "data"

    # deployed: D2 (cot_2pass)
    backend = RecordingBackend(["рассуждение: человек, шкаф", OBS_GOOD])
    run = run_case(
        cases["VAR-POI-01"],
        backend,
        variant=vs["D2"],
        data_root=data_root,
    )
    assert run.status == "ok" and run.variant_id == "D2"
    assert run.observation is not None
    assert run.observation.parsed is not None  # strict-ответ pass-2 распарсился
    assert run.observation.calls == 2
    assert run.observation.cot_reason == "рассуждение: человек, шкаф"
    assert len(backend.calls) == 2
    assert backend.calls[0]["grammar"] is None  # pass 1 -- без грамматики
    assert backend.calls[1]["grammar"] is not None  # pass 2 -- строгая
    # Текст pass-1 в контексте pass-2 (мост-сообщение, последнее в списке).
    bridge = backend.calls[1]["messages"][-1]
    assert bridge["role"] == "user"
    assert "рассуждение: человек, шкаф" in bridge["content"]
    # Pass-2 контекст = pass-1 сообщения + мост.
    assert backend.calls[1]["messages"][: len(backend.calls[0]["messages"])] == (
        backend.calls[0]["messages"]
    )

    # freeform: A2 (cot_2pass)
    backend = RecordingBackend(["этап 1: два человека", FREEFORM_GOOD])
    run = run_case(cases["VAR-AUD-01"], backend, variant=vs["A2"], data_root=data_root)
    assert run.status == "ok"
    assert run.freeform is not None and run.freeform.parsed is not None
    assert run.freeform.calls == 2
    assert backend.calls[0]["grammar"] is None
    assert backend.calls[1]["grammar"] is not None
    assert "этап 1: два человека" in backend.calls[1]["messages"][-1]["content"]


def test_few_shot_examples_before_case_frame(tmp_path) -> None:
    cases = {c.case_id: c for c in _load_cases(tmp_path)}
    vs = _variants()
    data_root = tmp_path / "data"
    case_url_prefix = "data:image/jpeg;base64,"  # кейсовое медиа m.jpg

    # D4: 2 примера (deployed, кандидаты в вопросе примера)
    backend = RecordingBackend([OBS_GOOD])
    run_case(cases["VAR-SCN-01"], backend, variant=vs["D4"], data_root=data_root)
    messages = backend.calls[0]["messages"]
    urls = _image_urls(messages)
    assert len(urls) == 3  # 2 кадра примеров + кадр кейса
    assert urls[0] != urls[-1] and urls[1] != urls[-1]
    assert urls[0].startswith("data:image/png;base64,")
    assert urls[-1].startswith(case_url_prefix)
    # Пары (кадр, ответ): assistant-сообщения -- эталонные ответы примеров.
    answers = [m["content"] for m in messages if m["role"] == "assistant"]
    assert len(answers) == 2
    assert all(json.loads(a)["people_count"] in (0, 1) for a in answers)
    # Вопрос примера 1 несёт inline-кандидаты примера.
    first_q = messages[0]["content"][0]["text"]
    assert "cabinet-01" in first_q and "frame-02" in first_q
    # Кейсовое сообщение с кадром -- после примеров.
    assert messages[4]["role"] == "user"
    assert "что это?" in (
        messages[4]["content"] if isinstance(messages[4]["content"], str)
        else messages[4]["content"][0]["text"]
    )

    # A4: 3 примера (freeform, без кандидатов)
    backend = RecordingBackend([FREEFORM_GOOD])
    run_case(cases["VAR-AUD-01"], backend, variant=vs["A4"], data_root=data_root)
    messages = backend.calls[0]["messages"]
    urls = _image_urls(messages)
    assert len(urls) == 4  # 3 примера + кадр кейса
    answers = [m["content"] for m in messages if m["role"] == "assistant"]
    assert answers == [
        "Всего 4 человека, готовы слушать 3.",
        "Всего 3 человека, готовы слушать 0.",
        "Всего 2 человека, готов слушать 1.",
    ]
    assert urls[-1].startswith(case_url_prefix)


def test_base_variants_match_production_instruction() -> None:
    vs = _variants()
    assert _variant_deployed_instruction(vs["D_base"], ("a", "b")) == _observation_instruction(
        ("a", "b")
    )
    assert _variant_deployed_instruction(vs["P_base"], ()) == _observation_instruction(())
    assert _variant_freeform_instruction(vs["A_base"]) == _FREEFORM_INSTRUCTION
    # Без варианта -- та же production-инструкция (regression).
    assert _variant_deployed_instruction(None, ("a",)) == _observation_instruction(("a",))
    assert _variant_freeform_instruction(None) == _FREEFORM_INSTRUCTION


def test_loop_variant_not_implemented_in_p4(tmp_path) -> None:
    cases = {c.case_id: c for c in _load_cases(tmp_path)}
    vs = _variants()
    with pytest.raises(LoopVariantNotImplemented):
        run_case(cases["VAR-POI-01"], MockBackend({}), variant=vs["P3"], data_root=tmp_path / "d")
    with pytest.raises(LoopVariantNotImplemented):
        run_case(
            cases["VAR-AUD-01"], MockBackend({}), variant=vs["A3"], data_root=tmp_path / "d"
        )


def test_mock_backend_pass_label_and_fallback() -> None:
    llm = MockBackend(
        {
            ("C1", "observation", "pass1"): "pass-1 text",
            ("C1", "observation"): "pass-2 text",
            ("C2", "observation"): "only-phase",
        }
    )
    llm.set_context("C1", "observation", "pass1")
    assert llm.complete([]).text == "pass-1 text"
    llm.set_context("C1", "observation", "pass2")  # 3-ключа нет → фолбэк на 2-ключ
    assert llm.complete([]).text == "pass-2 text"
    llm.set_context("C2", "observation")  # legacy 2-ключ без pass
    assert llm.complete([]).text == "only-phase"
    llm.set_context("C3", "observation", "pass1")  # ни 3-ключа, ни 2-ключа → пусто
    assert llm.complete([]).text == ""


def test_write_case_run_variant_meta(tmp_path) -> None:
    cases = {c.case_id: c for c in _load_cases(tmp_path)}
    vs = _variants()
    data_root = tmp_path / "data"
    backend = RecordingBackend(["рассуждение", OBS_GOOD])
    run = run_case(cases["VAR-POI-01"], backend, variant=vs["D2"], data_root=data_root)
    case_dir = write_case_run(cases["VAR-POI-01"], run, tmp_path / "run")
    meta = json.loads((case_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["variant_id"] == "D2"
    obs = meta["phases"]["observation"]
    assert obs["calls"] == 2
    assert obs["cot_reason"] == "рассуждение"
    assert obs["parse_status"] == "ok"
    # Single: calls=1, без cot_reason.
    run = run_case(
        cases["VAR-POI-01"],
        MockBackend({("VAR-POI-01", "observation"): OBS_GOOD}),
        variant=vs["P1"],
        data_root=data_root,
    )
    case_dir = write_case_run(cases["VAR-POI-01"], run, tmp_path / "run-p1")
    meta = json.loads((case_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["variant_id"] == "P1"
    assert meta["phases"]["observation"]["calls"] == 1
    assert "cot_reason" not in meta["phases"]["observation"]
