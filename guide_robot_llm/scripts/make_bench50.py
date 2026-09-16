#!/usr/bin/env python3
"""Сборка замороженного множества матрицы Taiga #11: ``bench_50.jsonl``.

Состав (50 кейсов):
* ``bench_47.jsonl`` (47) — неизменный #10-бенч: EgoPoint 15 + AGHRI 25
  + пилот-CC 7 TOL-CC (единственный источник gold tool-вызовов);
* пилот-CC 3 кейса трека scene (``SCN-CC-*``) через ``load_pilot`` —
  единственный доступный источник scene-кейсов: без них 6 scene-вариантов
  промпта (D0/D1/D2/D3/D4/D_base, Taiga #16) не имеют кейсов, а матрица #11
  покрывает ВСЕ 18 вариантов. Решение 2026-09-16 об исключении CC-синтетики
  касалось диагностического бенча #10; для матрицы #11 scene-трек включён.

Запуск из каталога пакета ``guide_robot_llm/``:

    python3 scripts/make_bench50.py

Итог: ``eval_manifests/bench_50.jsonl`` + sidecar ``bench_50.json``
(состав, sha256 слайсов, дата). Файл заморожен после первой генерации:
повторный запуск пересобирает из тех же входов и должен дать тот же sha256.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

_PKG_ROOT = Path(__file__).resolve().parent.parent
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))

from guide_robot_llm.eval.loader import load_pilot  # noqa: E402
from guide_robot_llm.eval.schema import case_to_dict  # noqa: E402

BENCH47 = _PKG_ROOT / "eval_manifests" / "bench_47.jsonl"
PILOT = _PKG_ROOT / "pilot" / "manifest.jsonl"
OUT = _PKG_ROOT / "eval_manifests" / "bench_50.jsonl"
SIDECAR = _PKG_ROOT / "eval_manifests" / "bench_50.json"
# из пилота берутся только scene-кейсы (остальные 12 — решение 2026-09-16)
SCENE_PREFIX = "SCN-CC-"


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_manifest() -> list[dict[str, object]]:
    """Составить bench_50 = bench_47 + 3 CC-сцены (проекция load_pilot)."""
    rows: list[dict[str, object]] = []
    if BENCH47.exists():
        lines = BENCH47.read_text(encoding="utf-8").splitlines()
        rows.extend(json.loads(line) for line in lines if line.strip())
    scene = [
        case_to_dict(c)
        for c in load_pilot(PILOT, _PKG_ROOT, require_media=False)
        if c.case_id.startswith(SCENE_PREFIX)
    ]
    if len(scene) != 3:
        raise SystemExit(f"ожидалось 3 scene-кейса SCN-CC-*, получено {len(scene)}")
    rows.extend(scene)
    seen: set[str] = set()
    for row in rows:
        if row["case_id"] in seen:
            raise SystemExit(f"дублирующийся case_id: {row['case_id']}")
        seen.add(row["case_id"])
    return rows


def main() -> int:
    """Собрать bench_50.jsonl и sidecar bench_50.json."""
    rows = build_manifest()
    text = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    OUT.write_text(text, encoding="utf-8")
    tracks: dict[str, int] = {}
    for row in rows:
        tracks[str(row["track"])] = tracks.get(str(row["track"]), 0) + 1
    sidecar = {
        "name": OUT.name,
        "n_cases": len(rows),
        "generated": time.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "tracks": tracks,
        "scope_decision": (
            "2026-09 (Taiga #11): bench_47 (47) + 3 SCN-CC scene-кейса пилота "
            "(SCN-CC-001/002/003) — единственный источник scene-трека для "
            "6 scene-промпт-вариантов; решение 2026-09-16 об исключении "
            "CC-синтетики касалось диагностического бенча #10"
        ),
        "slices": [
            {
                "source": "bench_47",
                "file": str(BENCH47.relative_to(_PKG_ROOT)),
                "sha256": _sha256(BENCH47),
                "n_cases": 47,
            },
            {
                "source": "pilot-cc",
                "file": str(PILOT.relative_to(_PKG_ROOT)),
                "sha256": _sha256(PILOT),
                "n_cases": 3,
                "filter": "SCN-CC-* only (scene-трек, Taiga #11)",
            },
        ],
    }
    SIDECAR.write_text(json.dumps(sidecar, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{OUT}: {len(rows)} кейсов; треки: {tracks}")
    print(f"sidecar: {SIDECAR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
