"""Офлайн-харнес оценки (Taiga #10, план vlm-bench-50): схема, загрузчики, раннер.

Только `MockBackend` и синтетика/коммиченный пилот -- без сети.
Дизайн: `docs/eval_harness_design.md`.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from guide_robot_llm.eval.loader import load_manifest, load_pilot
from guide_robot_llm.eval.runner import (
    MockBackend,
    build_freeform_answer_grammar,
    parse_freeform_answer,
    run_case,
    run_manifest,
)
from guide_robot_llm.eval.runner import (
    main as runner_main,
)
from guide_robot_llm.eval.schema import CaseError, case_from_dict, case_to_dict

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PILOT_MANIFEST = PACKAGE_ROOT / "pilot" / "manifest.jsonl"

_SHA = hashlib.sha256(b"fake-media").hexdigest()
_PROVENANCE = {
    "source": "s",
    "license": "CC BY-NC 4.0 (verified 2026-09-15)",
    "version": "v1",
}

OBS_GOOD = (
    '{"people_count": 1, "exhibit_candidates": ["a"], '
    '"pointing_evidence": "yes", "pointing_box": [0.1, 0.2, 0.4, 0.5], '
    '"scene_facts": "один человек у шкафа"}'
)
OBS_BAD = "модель не в JSON"
ACTION_GOOD = '{"tool": "say", "args": {"text": "привет"}, "confidence": 0.9, "abstain": false}'
FREEFORM_GOOD = '{"answer": "epa", "confidence": 0.8, "abstain": false}'


def _case(
    case_id: str,
    *,
    track: str = "pointing",
    gold: dict,
    mode: str = "deployed",
    candidates=("a", "b"),
    tools=("reply", "say"),
    media_sha: str = _SHA,
    provenance: dict | None = _PROVENANCE,
) -> dict:
    data = {
        "case_id": case_id,
        "source": "pilot-cc",
        "track": track,
        "split_group_id": "g-x",
        "media": {"path": "m.jpg", "sha256": media_sha, "format": "jpg"},
        "prompt": {"mode": mode, "user_text": "что это?"},
        "candidates": list(candidates),
        "allowed_tools": list(tools),
        "gold": gold,
        "slices": {},
    }
    if provenance is not None:
        # Копия: мутации в отдельных тестах (pop из provenance) не должны
        # ломать общий модульный словарь дефолта.
        data["provenance"] = dict(provenance)
    return data


def _make_media(root: Path, data: bytes = b"fake-jpeg-bytes") -> str:
    (root / "m.jpg").write_bytes(data)
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# schema (t3-schema)
# ---------------------------------------------------------------------------


def test_valid_case_roundtrips_through_dict() -> None:
    raw = _case(
        "C1",
        track="pointing",
        gold={
            "type": "target_box",
            "target_id": "a",
            "box_px": [1, 2, 3, 4],
            "distractors": ["b"],
        },
    )
    case = case_from_dict(raw)
    assert case.candidates == ("a", "b")
    assert case.gold["target_id"] == "a"
    # `case_to_dict` -- явная форма: включает поля со значениями по умолчанию
    # (`language`, `rights_note`), которых нет в исходной записи, поэтому
    # равенство проверяется семантическим раунд-трипом, а не сырым dict.
    assert case_from_dict(case_to_dict(case)) == case
    dumped = case_to_dict(case)
    assert dumped["case_id"] == "C1"
    assert dumped["media"]["sha256"] == _SHA
    assert dumped["provenance"]["rights_note"] == ""
    assert dumped["prompt"]["language"] == "en"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.pop("provenance"),
        lambda d: d["provenance"].pop("license"),
        lambda d: d["media"].update(sha256="xyz"),
        lambda d: d.update(source="not-a-source"),
        lambda d: d.update(track="not-a-track"),
        lambda d: d["gold"].update(type="not-a-gold-type"),
        lambda d: d["prompt"].update(mode="chatty"),
        lambda d: d["gold"].update(type="count", count=21),
        lambda d: d["gold"].update(type="target_box", target_id=""),
    ],
    ids=[
        "no-provenance",
        "no-license",
        "bad-sha256",
        "unknown-source",
        "unknown-track",
        "unknown-gold",
        "unknown-mode",
        "count-out-of-range",
        "target-box-without-id",
    ],
)
def test_schema_rejects_invalid_records(mutate) -> None:
    raw = _case("C2", gold={"type": "count", "count": 1})
    mutate(raw)
    with pytest.raises(CaseError):
        case_from_dict(raw)


def test_duplicate_case_id_rejected_in_jsonl(tmp_path) -> None:
    raw = _case("C3", gold={"type": "count", "count": 1})
    manifest = tmp_path / "m.jsonl"
    manifest.write_text(json.dumps(raw) + "\n" + json.dumps(raw) + "\n", encoding="utf-8")
    with pytest.raises(CaseError, match="дублирующийся"):
        load_manifest(manifest)


# ---------------------------------------------------------------------------
# loader (t3-loader)
# ---------------------------------------------------------------------------


def test_load_manifest_reads_jsonl_and_skips_blank_lines(tmp_path) -> None:
    a = _case("M1", gold={"type": "count", "count": 1})
    b = _case("M2", gold={"type": "unanswerable"})
    manifest = tmp_path / "m.jsonl"
    manifest.write_text("\n".join([json.dumps(a), "", json.dumps(b)]) + "\n", encoding="utf-8")
    cases = load_manifest(manifest)
    assert [c.case_id for c in cases] == ["M1", "M2"]


def test_load_pilot_maps_committed_manifest(tmp_path) -> None:
    # Коммиченный пилот (2026-09-13, 15 эпизодов) -- вход без сети.
    cases = load_pilot(PILOT_MANIFEST, PACKAGE_ROOT, require_media=True)
    assert len(cases) == 15
    assert {c.source for c in cases} == {"pilot-cc"}
    assert {c.track for c in cases} == {"pointing", "audience", "scene", "tool"}

    by_id = {c.case_id: c for c in cases}
    poi = next(c for c in cases if c.track == "pointing")
    assert poi.gold["type"] == "target_box"
    assert poi.gold["target_id"] in poi.candidates
    assert poi.slices.get("n_distractors", 0) >= 1

    tool_cases = [c for c in cases if c.track == "tool"]
    # Пилотный gold `abstention` проецируется в action с abstention_reason.
    assert all(c.gold["type"] == "action" for c in tool_cases)
    assert all(c.provenance.version == cases[0].provenance.version for c in cases)
    assert by_id[tool_cases[0].case_id].allowed_tools


def test_load_pilot_tampered_sha_rejected(tmp_path) -> None:
    raw_text = PILOT_MANIFEST.read_text(encoding="utf-8")
    episode = json.loads(raw_text.splitlines()[0])
    bad = dict(episode)
    media = dict(episode["media"])
    media["sha256"] = "0" * 64
    bad["media"] = media
    tampered = tmp_path / "m.jsonl"
    tampered.write_text(json.dumps(bad, ensure_ascii=False) + "\n", encoding="utf-8")
    with pytest.raises(CaseError, match="sha256"):
        load_pilot(tampered, PACKAGE_ROOT, require_media=True)
    # Без проверки медиа схема всё равно проходит (быстрая валидация).
    cases = load_pilot(tampered, PACKAGE_ROOT, require_media=False)
    assert cases[0].media.sha256 == "0" * 64


def test_load_pilot_unknown_family_rejected(tmp_path) -> None:
    raw_text = PILOT_MANIFEST.read_text(encoding="utf-8")
    episode = json.loads(raw_text.splitlines()[0])
    bad = dict(episode)
    bad["source_family"] = "mystery"
    tampered = tmp_path / "m.jsonl"
    tampered.write_text(json.dumps(bad, ensure_ascii=False) + "\n", encoding="utf-8")
    with pytest.raises(CaseError, match="source_family"):
        load_pilot(tampered, PACKAGE_ROOT)


# ---------------------------------------------------------------------------
# runner (t3-runner, t3-tests)
# ---------------------------------------------------------------------------


def test_two_synthetic_cases_end_to_end(tmp_path) -> None:
    """Ключевой прогон: deployed (ok) + freeform (ok) -- run-дир на каждый."""
    sha = _make_media(tmp_path)
    poi_raw = _case(
        "E2E-POI",
        gold={
            "type": "target_box",
            "target_id": "a",
            "box_px": [1, 2, 3, 4],
            "distractors": ["b"],
        },
        media_sha=sha,
    )
    epo_raw = _case(
        "E2E-EPO",
        mode="freeform",
        candidates=("epa", "epb"),
        gold={"type": "target_box", "target_id": "epa", "box_px": None, "distractors": ["epb"]},
        media_sha=sha,
    )
    cases = [case_from_dict(poi_raw), case_from_dict(epo_raw)]
    backend = MockBackend(
        {
            ("E2E-POI", "observation"): OBS_GOOD,
            ("E2E-EPO", "freeform"): FREEFORM_GOOD,
        }
    )
    out = tmp_path / "run"
    lines = run_manifest(cases, backend, out, data_root=tmp_path)

    statuses = {line["case_id"]: line["status"] for line in lines}
    assert statuses == {"E2E-POI": "ok", "E2E-EPO": "ok"}
    assert all(line["pass"] is None for line in lines)

    poi_dir = out / "cases" / "E2E-POI"
    assert (poi_dir / "raw_observation.txt").read_text(encoding="utf-8") == OBS_GOOD
    parsed = json.loads((poi_dir / "parsed_observation.json").read_text(encoding="utf-8"))
    assert parsed["people_count"] == 1
    assert parsed["exhibit_candidates"] == ["a"]
    # Фаза действия не запускается: gold не `action`.
    assert not (poi_dir / "raw_action.txt").exists()

    epo_dir = out / "cases" / "E2E-EPO"
    parsed_ff = json.loads((epo_dir / "parsed_freeform.json").read_text(encoding="utf-8"))
    assert parsed_ff == {"answer": "epa", "confidence": 0.8, "abstain": False}

    meta = json.loads((poi_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["tokens"] is None
    assert meta["tokens_note"]
    assert meta["prompt_mode"] == "deployed"
    assert meta["phases"]["observation"]["attempts"] == 1
    assert meta["case"]["case_id"] == "E2E-POI"  # снапшот кейса в meta
    assert meta["case"]["media"]["sha256"] == sha

    manifest_lines = json.loads((out / "run_manifest.json").read_text(encoding="utf-8"))
    assert [line["case_id"] for line in manifest_lines] == ["E2E-POI", "E2E-EPO"]


def test_parse_failure_recorded_not_dropped(tmp_path) -> None:
    sha = _make_media(tmp_path)
    raw = _case(
        "PF",
        gold={"type": "action", "tool": "say", "args": {"text": "привет"}},
        media_sha=sha,
    )
    case = case_from_dict(raw)
    backend = MockBackend(
        {
            ("PF", "observation"): OBS_BAD,  # malformed наблюдение
            ("PF", "action"): ACTION_GOOD,  # действие проходит
        }
    )
    out = tmp_path / "run"
    lines = run_manifest([case], backend, out, data_root=tmp_path)
    assert lines[0]["status"] == "parse_failed"

    case_dir = out / "cases" / "PF"
    # Фаза действия всё равно прошла: production не роняет ход на сломанном
    # наблюдении -- оно просто не попадает в промпт.
    assert json.loads((case_dir / "parsed_observation.json").read_text(encoding="utf-8")) == {
        "parse_status": "failed"
    }
    action = json.loads((case_dir / "parsed_action.json").read_text(encoding="utf-8"))
    assert action["tool"] == "say"
    meta = json.loads((case_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["phases"]["observation"]["parse_status"] == "failed"
    assert meta["phases"]["action"]["parse_status"] == "ok"


def test_backend_error_recorded_and_run_continues(tmp_path) -> None:
    class Down:
        def complete(self, messages, **kwargs):
            raise ConnectionError("нет сервера")

    sha = _make_media(tmp_path)
    cases = [
        case_from_dict(_case("DOWN", gold={"type": "count", "count": 1}, media_sha=sha)),
        case_from_dict(
            _case("GOOD", mode="freeform", gold={"type": "unanswerable"}, media_sha=sha)
        ),
    ]
    out = tmp_path / "run"
    backend = Down()  # type: ignore[assignment]
    lines = run_manifest(cases, backend, out, data_root=tmp_path)
    statuses = {line["case_id"]: line["status"] for line in lines}
    assert statuses == {"DOWN": "backend_error", "GOOD": "backend_error"}
    meta = json.loads((out / "cases" / "DOWN" / "meta.json").read_text(encoding="utf-8"))
    assert "ConnectionError" in meta["error"]


def test_retry_then_success_is_ok(tmp_path) -> None:
    from guide_robot_llm.llm_client.backend import CompletionResult

    class Flaky:
        def __init__(self) -> None:
            self.calls = 0

        def complete(self, messages, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise ConnectionError("сбой первой попытки")
            return CompletionResult(text=OBS_GOOD, finish_reason="stop")

    sha = _make_media(tmp_path)
    case = case_from_dict(_case("FLK", gold={"type": "count", "count": 1}, media_sha=sha))
    run = run_case(case, Flaky(), data_root=tmp_path)  # type: ignore[arg-type]
    assert run.status == "ok"
    assert run.observation is not None and run.observation.attempts == 2


def test_freeform_grammar_and_parser_strictness() -> None:
    grammar = build_freeform_answer_grammar()
    assert '"\\"answer\\""' in grammar
    assert '"\\"confidence\\""' in grammar
    assert '"\\"abstain\\""' in grammar
    assert "value  ::= object | array | string | number" in grammar  # общие JSON-правила
    assert "confidence ::=" in grammar

    assert parse_freeform_answer(FREEFORM_GOOD)["answer"] == "epa"
    # Строгость: лишние ключи, bool-конфиденс, confidence вне [0, 1] -- reject.
    extra_key = '{"answer": "x", "confidence": 0.5, "abstain": false, "extra": 1}'
    assert parse_freeform_answer(extra_key) is None
    assert parse_freeform_answer('{"answer": "x", "confidence": true, "abstain": false}') is None
    assert parse_freeform_answer('{"answer": "x", "confidence": 1.5, "abstain": false}') is None
    assert parse_freeform_answer('{"answer": "x", "confidence": 0.5, "abstain": "no"}') is None
    assert parse_freeform_answer("не json") is None


def test_runner_cli_mock_run(tmp_path) -> None:
    sha = _make_media(tmp_path)
    raw = _case("CLI-1", mode="freeform", gold={"type": "unanswerable"}, media_sha=sha)
    manifest = tmp_path / "m.jsonl"
    manifest.write_text(json.dumps(raw, ensure_ascii=False) + "\n", encoding="utf-8")
    mock = tmp_path / "mock.json"
    mock.write_text(
        json.dumps({"CLI-1": {"freeform": FREEFORM_GOOD}}, ensure_ascii=False),
        encoding="utf-8",
    )
    out = tmp_path / "run"
    exit_code = runner_main(
        [
            "--manifest",
            str(manifest),
            "--out",
            str(out),
            "--mock-responses",
            str(mock),
            "--data-root",
            str(tmp_path),
        ]
    )
    assert exit_code == 0
    assert (out / "run_manifest.json").exists()
    assert (out / "cases" / "CLI-1" / "meta.json").exists()


def test_media_missing_runs_text_only(tmp_path) -> None:
    # Нет файла медиа -- прогон идёт без кадров, а не падает (кейсы фиксируются).
    case = case_from_dict(_case("NOMED", gold={"type": "count", "count": 1}))  # sha без файла
    backend = MockBackend({("NOMED", "observation"): OBS_GOOD})
    run = run_case(case, backend, data_root=tmp_path)
    assert run.status == "ok"
    assert run.observation is not None and run.observation.parse_status == "ok"
