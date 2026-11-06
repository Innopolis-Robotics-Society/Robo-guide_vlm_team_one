#!/usr/bin/env python3
"""Replay-табуляция (add-pointing-virtual-replay, V5.1): кампания → CSV.

Собирает по каждому run-директории кампании (подкаталоги вида
``<дата>-<model>__<leg>``) replay-метрики из ``score.json`` и пишет
стабильную табуляцию ``replay_tabulation.csv`` в корень кампании.
Столбцы: модель, нога, n кейсов, replay-н, detection_rate,
resolved_accuracy (+ n), agreement_rate, box_iou_mean,
clarification no_candidate/ambiguous, final_choice_accuracy, abstention_rate.

Порядок строк детерминирован (сортировка по model, leg), поэтому CSV
стабилен к повторным прогонам. Запуск (из каталога пакета):

    python3 scripts/tabulate_replay.py --campaign-dir eval_runs/2026-11-06-virtual-replay
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

_PKG_ROOT = Path(__file__).resolve().parent.parent

_COLUMNS = [
    "model",
    "leg",
    "n_cases",
    "replay_n",
    "detection_rate",
    "resolved_accuracy",
    "resolved_n",
    "agreement_rate",
    "box_iou_mean",
    "clarif_no_candidate",
    "clarif_ambiguous",
    "final_choice_accuracy",
    "abstention_rate",
]


def _val(metric: object) -> object:
    """Числовое значение метрики score.json (``{value, n}`` или скаляр)."""
    if isinstance(metric, dict):
        return metric.get("value")
    return metric


def _n(metric: object) -> object:
    """n метрики score.json (``{value, n}``); None для скаляров."""
    if isinstance(metric, dict):
        return metric.get("n")
    return None


def _fmt(x: object) -> str:
    """Однородный формат ячейки: пустая строка для None."""
    if x is None:
        return ""
    if isinstance(x, float):
        return f"{x:.4f}".rstrip("0").rstrip(".")
    return str(x)


def collect_row(run_dir: Path) -> dict[str, object] | None:
    """Одна строка табуляции из run-директории (score.json)."""
    score_path = run_dir / "score.json"
    if not score_path.exists():
        return None
    doc = json.loads(score_path.read_text(encoding="utf-8"))
    manifest_path = run_dir / "run_manifest.json"
    n_cases = 0
    if manifest_path.exists():
        n_cases = len(json.loads(manifest_path.read_text(encoding="utf-8")))
    pointing = doc.get("metrics", {}).get("policy", {}).get("pointing", {})
    replay = pointing.get("replay", {})
    clarif = replay.get("clarification_rate", {})
    name = run_dir.name
    # <YYYY-MM-DD>-<model>__<leg>
    model, _, leg = name.rpartition("__")
    model = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", model)
    return {
        "model": model,
        "leg": leg,
        "n_cases": n_cases,
        "replay_n": replay.get("n"),
        "detection_rate": _val(replay.get("detection_rate")),
        "resolved_accuracy": _val(replay.get("resolved_accuracy")),
        "resolved_n": _n(replay.get("resolved_accuracy")),
        "agreement_rate": _val(replay.get("agreement_rate")),
        "box_iou_mean": _val(replay.get("box_iou_mean")),
        "clarif_no_candidate": clarif.get("no_candidate"),
        "clarif_ambiguous": clarif.get("ambiguous"),
        "final_choice_accuracy": _val(pointing.get("final_choice_accuracy")),
        "abstention_rate": _val(pointing.get("abstention_rate")),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", required=True, help="каталог кампании")
    args = parser.parse_args(argv)
    campaign = Path(args.campaign_dir)
    if not campaign.is_dir():
        raise SystemExit(f"нет каталога кампании: {campaign}")

    rows: list[dict[str, object]] = []
    for sub in sorted(campaign.iterdir()):
        if not sub.is_dir():
            continue
        row = collect_row(sub)
        if row is not None:
            rows.append(row)
    rows.sort(key=lambda r: (str(r["model"]), str(r["leg"])))

    out = campaign / "replay_tabulation.csv"
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: _fmt(row[k]) for k in _COLUMNS})
    print(f"табуляция: {len(rows)} строк → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
