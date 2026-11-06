"""Тесты `scripts/run_matrix.py`: canned-генератор (W1: фаза решения).

Драйвер безприсмотрный, GPU-зависимую часть не тестируем; покрываем
чистую логику `generate_canned` — в particular, что на pointing-кейсы
заготавливается gold-верный ответ decision-фазы (W1-fix).
"""

import json
import sys
from pathlib import Path

_PKG_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PKG_ROOT / "scripts"))

from run_matrix import generate_canned  # noqa: E402


def _write_manifest(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "m.jsonl"
    text = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n"
    p.write_text(text, encoding="utf-8")
    return p


def _decision_of(canned: dict, case_id: str) -> dict:
    return json.loads(canned[case_id]["decision"])


def test_canned_decision_for_target_case(tmp_path: Path) -> None:
    """Target-кейс: decision выбирает gold-цель."""
    row = {
        "case_id": "EPO-REAL-0003",
        "gold": {"type": "target_box", "target_id": "a", "box_px": None, "distractors": ["b"]},
        "prompt": {"mode": "deployed"},
    }
    canned = generate_canned(_write_manifest(tmp_path, [row]))
    dec = _decision_of(canned, "EPO-REAL-0003")
    assert dec["target_id"] == "a"
    assert 0.0 <= dec["confidence"] <= 1.0


def test_canned_decision_no_target_is_none(tmp_path: Path) -> None:
    """No-target (target_id == "unknown"): decision -- отказ "none"."""
    row = {
        "case_id": "EPO-REAL-NT1",
        "gold": {
            "type": "target_box",
            "target_id": "unknown",
            "box_px": None,
            "distractors": ["a"],
        },
        "prompt": {"mode": "deployed"},
    }
    canned = generate_canned(_write_manifest(tmp_path, [row]))
    assert _decision_of(canned, "EPO-REAL-NT1")["target_id"] == "none"


def test_canned_no_decision_for_non_pointing(tmp_path: Path) -> None:
    """Не-pointing кейсы (count/action/claims): decision-фазы нет."""
    rows = [
        {
            "case_id": "C-1",
            "gold": {"type": "count", "count": 3},
            "prompt": {"mode": "deployed"},
        },
        {
            "case_id": "A-1",
            "gold": {"type": "action", "tool": "reply", "args": {"text": "x"}},
            "prompt": {"mode": "deployed"},
        },
        {
            "case_id": "S-1",
            "gold": {"type": "claims", "claims": ["c1"]},
            "prompt": {"mode": "freeform"},
        },
    ]
    canned = generate_canned(_write_manifest(tmp_path, rows))
    for cid in ("C-1", "A-1", "S-1"):
        assert "decision" not in canned[cid]
