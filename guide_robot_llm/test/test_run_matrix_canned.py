"""Тесты `scripts/run_matrix.py`: canned-генератор (W1: фаза решения).

Драйвер безприсмотрный, GPU-зависимую часть не тестируем; покрываем
чистую логику `generate_canned` — в particular, что на pointing-кейсы
заготавливается gold-верный ответ decision-фазы (W1-fix) — а также
сборку команды сервера и backend-конфига (пиннинг seed, PROVENANCE.md).
"""

import json
import sys
from pathlib import Path

import pytest

_PKG_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PKG_ROOT / "scripts"))

from run_matrix import (  # noqa: E402
    backend_config,
    generate_canned,
    models_dir,
    server_cmd,
)


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


# ---------------------------------------------------------------------------
# Пиннинг seed: профиль → команда сервера → run_config.json (backend-freeze)
# ---------------------------------------------------------------------------


def _profile(seed: str | None = "42") -> dict:
    profile = {
        "MODELS_DIR": "/models",
        "MODEL_FILE": "m/model.gguf",
        "MM_PROJ": "m/mmproj.gguf",
        "MODEL_ALIAS": "m-alias",
        "CTX_SIZE": "16384",
        "REASONING": "off",
    }
    if seed is not None:
        profile["SEED"] = seed
    return profile


def _cfg() -> dict:
    return {"llama_server_bin": "/bin/llama-server", "host": "127.0.0.1", "port": 1234}


def test_server_cmd_appends_seed_from_profile(tmp_path, monkeypatch) -> None:
    """`SEED` в профиле → `--seed 42` в команде llama-server."""
    monkeypatch.setenv("MODELS_DIR", str(tmp_path))
    cmd = server_cmd(_cfg(), {"id": "m"}, _profile())
    assert cmd[-2:] == ["--seed", "42"]


def test_server_cmd_without_seed_has_no_flag(tmp_path, monkeypatch) -> None:
    """Без `SEED` флаг не добавляется (старые профили не ломаются)."""
    monkeypatch.setenv("MODELS_DIR", str(tmp_path))
    cmd = server_cmd(_cfg(), {"id": "m"}, _profile(seed=None))
    assert "--seed" not in cmd


def test_backend_config_carries_seed_as_int() -> None:
    """`SEED` из профиля уходит в backend-конфиг как int (для freeze)."""
    backend = backend_config("http://127.0.0.1:1234/v1", _cfg(), _profile())
    assert backend["seed"] == 42


def test_seed_reaches_run_config_freeze() -> None:
    """Seed доходит до записи `run_config.json.backend` (декларативный freeze)."""
    sys.path.insert(0, str(_PKG_ROOT.parent))
    from guide_robot_llm.eval.runner import _backend_freeze_info

    backend = backend_config("http://127.0.0.1:1234/v1", _cfg(), _profile())
    info = _backend_freeze_info(backend)
    assert info["seed"] == 42
    assert "api_key" not in info


# ---------------------------------------------------------------------------
# Portable MODELS_DIR: env-переменная в приоритете, нет каталога — ошибка
# ---------------------------------------------------------------------------


def test_models_dir_env_override_wins(monkeypatch, tmp_path) -> None:
    """Env `MODELS_DIR` переопределяет значение из профиля."""
    monkeypatch.setenv("MODELS_DIR", str(tmp_path))
    assert models_dir({"MODELS_DIR": "/nonexistent"}) == tmp_path


def test_models_dir_missing_gives_clear_error(monkeypatch, tmp_path) -> None:
    """Каталог не найден — понятная SystemExit, а не тихий неверный путь."""
    monkeypatch.delenv("MODELS_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit, match="MODELS_DIR"):
        models_dir({"MODELS_DIR": "models/pilot"})
