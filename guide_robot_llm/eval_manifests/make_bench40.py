#!/usr/bin/env python3
"""Сборка манифеста bench-40 (Taiga #10, T10) + mock-ответы для dry-рана.

Состав (scope-решение 2026-09-15, пометка на T10):
* EgoPoint-Bench 10 кейсов — ``eval_manifests/egopoint_10.jsonl`` (T7);
* AGHRI 15 кейсов — ``eval_manifests/aghri_15.jsonl`` (T9);
* пилот 15 кейсов — ``pilot/manifest.jsonl`` через ``load_pilot`` (T5).

DP/Deepoint исключён (дистрибуция 180 GB, не скачивается локально),
YouRefIt — регистрация pending (досборка позже инкрементальным прогонсом).

Запуск из каталога пакета ``guide_robot_llm/``:

    uv run --with requests python eval_manifests/make_bench40.py manifest
    uv run --with requests python eval_manifests/make_bench40.py mock \
        --out .scratch/bench40_dry/mock_responses.json

Путь медиа во всех слайсах -- относительно корня пакета, поэтому
``--data-root`` раннера -- корень пакета.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

_PKG_ROOT = Path(__file__).resolve().parent.parent
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))

from guide_robot_llm.eval.loader import load_pilot  # noqa: E402
from guide_robot_llm.eval.schema import case_to_dict  # noqa: E402

EGOPPOINT = _PKG_ROOT / "eval_manifests" / "egopoint_10.jsonl"
AGHRI = _PKG_ROOT / "eval_manifests" / "aghri_15.jsonl"
PILOT = _PKG_ROOT / "pilot" / "manifest.jsonl"
OUT = _PKG_ROOT / "eval_manifests" / "bench_40.jsonl"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_manifest() -> list[dict[str, Any]]:
    """Три слайса → единый список унифицированных кейсов (порядок: EPO, AGHRI, pilot)."""
    rows: list[dict[str, Any]] = []
    for path in (EGOPPOINT, AGHRI):
        rows.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    pilot = [case_to_dict(c) for c in load_pilot(PILOT, _PKG_ROOT, require_media=False)]
    rows.extend(pilot)
    seen: set[str] = set()
    for row in rows:
        if row["case_id"] in seen:
            raise SystemExit(f"дублирующийся case_id: {row['case_id']}")
        seen.add(row["case_id"])
    return rows


def cmd_manifest(_args: argparse.Namespace) -> None:
    rows = build_manifest()
    OUT.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
    )
    sidecar = {
        "name": OUT.name,
        "n_cases": len(rows),
        "generated": time.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "scope_decision": "2026-09-15 (T10): DP excluded (180 GB), YouRefIt registration pending",
        "slices": [
            {"source": "egopoint", "file": str(EGOPPOINT.relative_to(_PKG_ROOT)), "sha256": _sha256(EGOPPOINT), "n_cases": 10},
            {"source": "aghri", "file": str(AGHRI.relative_to(_PKG_ROOT)), "sha256": _sha256(AGHRI), "n_cases": 15},
            {"source": "pilot-cc", "file": str(PILOT.relative_to(_PKG_ROOT)), "sha256": _sha256(PILOT), "n_cases": 15},
        ],
        "media_root": "корень пакета guide_robot_llm/ (раннер: --data-root . из каталога пакета)",
    }
    OUT.with_suffix(".jsonl.sidecar.json").write_text(
        json.dumps(sidecar, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"{OUT.name}: {len(rows)} кейсов; sidecar: {OUT.name}.sidecar.json")


def _mock_observation(gold: dict[str, Any]) -> dict[str, Any]:
    """Gold-верная observation (мок-смоук: «идеальная модель»)."""
    obs = {
        "people_count": 1,
        "exhibit_candidates": [],
        "pointing_evidence": "none",
        "pointing_box": None,
        "scene_facts": "mock dry run (gold-faithful)",
    }
    gtype = gold.get("type")
    if gtype == "count":
        obs["people_count"] = int(gold["count"])
    elif gtype == "target_box":
        obs["exhibit_candidates"] = [gold["target_id"]]
    elif gtype == "unanswerable":
        obs["people_count"] = 0
    return obs


def cmd_mock(args: argparse.Namespace) -> None:
    """Canned-ответы (строго грамматики) на каждый кейс bench-40."""
    if not OUT.exists():
        raise SystemExit(f"нет {OUT.name} — сначала подкоманда `manifest`")
    canned: dict[str, dict[str, str]] = {}
    for line in OUT.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        case = json.loads(line)
        gold = case["gold"]
        mode = case["prompt"]["mode"]
        phases: dict[str, str] = {}
        if mode == "freeform":
            answer = gold.get("target_id") or gold.get("count") or "mock"
            phases["freeform"] = json.dumps(
                {"answer": str(answer), "confidence": 1, "abstain": False}, ensure_ascii=False
            )
        else:
            phases["observation"] = json.dumps(_mock_observation(gold), ensure_ascii=False)
            if gold.get("type") == "action":
                if "abstention_reason" in gold:
                    action = {
                        "tool": "reply",
                        "args": {"text": "mock abstention"},
                        "confidence": 0.9,
                        "abstain": True,
                    }
                else:
                    action = {
                        "tool": gold["tool"],
                        "args": gold["args"],
                        "confidence": 1,
                        "abstain": False,
                    }
                phases["action"] = json.dumps(action, ensure_ascii=False)
        canned[case["case_id"]] = phases
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(canned, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{out}: {len(canned)} кейсов, {sum(len(v) for v in canned.values())} фаз")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("manifest", help="собрать bench_40.jsonl + sidecar")
    mock_p = sub.add_parser("mock", help="gold-верные canned-ответы для dry-рана")
    mock_p.add_argument("--out", required=True, type=Path, help="путь mock_responses.json")
    args = parser.parse_args(argv)
    if args.command == "manifest":
        cmd_manifest(args)
    else:
        cmd_mock(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
