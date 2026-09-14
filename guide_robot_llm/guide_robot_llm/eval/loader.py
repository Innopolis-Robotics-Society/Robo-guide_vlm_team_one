"""Загрузчики унифицированных кейсов.

Два входа в одну схему (дизайн: `docs/eval_harness_design.md`):
* `load_manifest` -- готовый JSONL унифицированного манифеста
  (собирают адаптеры внешних источников, T6–T9);
* `load_pilot` -- прямая проекция пилотного `pilot/manifest.jsonl`
  (формат `episode_template.json`) без переписывания пилота.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from guide_robot_llm.eval.schema import (
    Case,
    CaseError,
    MediaRef,
    case_from_dict,
    load_cases_from_jsonl,
)

_SHA256_LEN = 64

# source_family пилота → источник унифицированной схемы.
_FAMILY_TO_SOURCE = {"controlled": "pilot-cc", "surrogate_real": "pilot-sr"}


def _sha256_of_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _normalize_gold(raw_gold: dict[str, Any], where: str) -> dict[str, Any]:
    """Gold пилота (`episode_template.json`) → плоский gold схемы.

    Пилотные `target_box` хранят цель вложенно (`target.candidate_id`);
    схема требует плоского `target_id` (единая форма для всех источников).
    """
    gold_type = raw_gold.get("type")
    if gold_type == "target_box":
        target = raw_gold.get("target")
        if not isinstance(target, dict) or not target.get("candidate_id"):
            msg = f"{where}: gold.target_box без `target.candidate_id`"
            raise CaseError(msg)
        return {
            "type": "target_box",
            "target_id": target["candidate_id"],
            "box_px": target.get("box_px"),
            "distractors": list(target.get("distractors", [])),
        }
    if gold_type == "count":
        return {"type": "count", "count": raw_gold.get("count")}
    if gold_type == "action":
        if raw_gold.get("abstention_reason"):
            return {"type": "action", "abstention_reason": raw_gold["abstention_reason"]}
        return {
            "type": "action",
            "tool": raw_gold.get("tool"),
            "args": dict(raw_gold.get("args", {})),
        }
    if gold_type == "claims":
        return {"type": "claims", "claims": list(raw_gold.get("claims", []))}
    if gold_type == "abstention":
        # Пилот хранит отказ как отдельный тип; унифицированная схема
        # выражает его gold-ом action с abstention_reason (дизайн: "gold types").
        reason = raw_gold.get("reason")
        if not isinstance(reason, str) or not reason:
            msg = f"{where}: gold.abstention без `reason`"
            raise CaseError(msg)
        return {"type": "action", "abstention_reason": reason}
    if gold_type == "unanswerable":
        result = {"type": "unanswerable"}
        if isinstance(raw_gold.get("reason"), str):
            result["reason"] = raw_gold["reason"]
        return result
    msg = f"{where}: неизвестный gold.type {gold_type!r}"
    raise CaseError(msg)


def _episode_to_case(episode: dict[str, Any], pilot_root: Path, *, version: str) -> Case:
    """Строка пилотного манифеста → словарь унифицированной схемы.

    `pilot_root` -- каталог пакета (там лежат и `pilot/`, и медия).
    `media.uri` в пилоте задан относительно корня пакета
    (`pilot/media/...`), путь схемы строим так же -- без ре-базирования.
    """
    where = f"пилот {episode.get('episode_id', '<без id>')}"
    family = episode.get("source_family")
    source = _FAMILY_TO_SOURCE.get(family)
    if source is None:
        raise CaseError(f"{where}: неизвестный source_family {family!r}")

    media_raw = episode.get("media")
    if not isinstance(media_raw, dict) or not media_raw.get("uri"):
        raise CaseError(f"{where}: нет media.uri")
    uri = media_raw["uri"]
    ext = Path(uri).suffix.lstrip(".") or "bin"
    sha = media_raw.get("sha256")
    if not (isinstance(sha, str) and len(sha) == _SHA256_LEN):
        # sha256 в пилоте -- обязательное поле; пересчёт делаем только
        # при проверке (require_media), здесь -- отклонение.
        raise CaseError(f"{where}: media.sha256 отсутствует или не hex-64")
    media_path = pilot_root / uri
    if not media_path.is_file():
        raise CaseError(f"{where}: медиафайл {uri} не найден относительно {pilot_root}")
    media = MediaRef(path=uri, sha256=sha.lower(), format=ext)

    utterance = episode.get("utterance")
    if not isinstance(utterance, dict) or not utterance.get("text"):
        raise CaseError(f"{where}: нет utterance.text")

    mission = episode.get("mission_snapshot", {})
    candidates = tuple(mission.get("visible_candidate_ids", []))
    allowed_tools = tuple(mission.get("allowed_tools", []))

    gold = _normalize_gold(episode.get("gold", {}), where)

    slices: dict[str, Any] = {}
    if gold["type"] == "target_box":
        slices["n_distractors"] = len(gold.get("distractors", []))
    if gold["type"] == "count":
        slices["count_bucket"] = str(gold.get("count"))
    venue = media_raw.get("venue")
    if isinstance(venue, str):
        slices["venue"] = venue

    prov_raw = media_raw.get("rights", {})
    rights_status = prov_raw.get("status", "unknown")
    license_note = f"self-captured/pre-approved (rights_ledger: {rights_status})"
    return case_from_dict(
        {
            "case_id": episode["episode_id"],
            "source": source,
            "track": episode.get("track"),
            "split_group_id": episode.get("split_group_id", episode["episode_id"]),
            "media": {"path": media.path, "sha256": media.sha256, "format": media.format},
            "prompt": {
                "mode": "deployed",
                "user_text": utterance["text"],
                "language": utterance.get("language", "ru"),
            },
            "candidates": list(candidates),
            "allowed_tools": list(allowed_tools),
            "gold": gold,
            "provenance": {
                "source": "pilot-manifest",
                "license": license_note,
                "version": version,
                "rights_note": prov_raw.get("consent_ref", "") or "pilot rights ledger",
            },
            "slices": slices,
        }
    )


def load_manifest(path: str | Path) -> list[Case]:
    """Унифицированный JSONL-манифест → список кейсов (валидация схемы)."""
    return load_cases_from_jsonl(path)


def load_pilot(
    manifest_path: str | Path, pilot_root: str | Path, *, require_media: bool = False
) -> list[Case]:
    """Пилотный манифест → унифицированные кейсы.

    `pilot_root` -- корень, относительно которого заданы `media.uri`
    (для репозитория это каталог пакета `guide_robot_llm/`).
    `require_media=True` дополнительно сверяет sha256 файла с манифестом
    (полный прогон перед раном; `False` -- быстрая валидация схемы).
    Версия провиенса -- дата-строка из `manifest_version`, иначе mtime.
    """
    root = Path(pilot_root)
    raw = Path(manifest_path)
    text = raw.read_text(encoding="utf-8")
    version = ""
    mtime_version = time.strftime("%Y-%m-%d", time.localtime(raw.stat().st_mtime))
    cases: list[Case] = []
    seen: set[str] = set()
    for line_no, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        episode = json.loads(line)
        if not version:
            version = str(episode.get("manifest_version") or mtime_version)
        case = _episode_to_case(episode, root, version=version)
        if case.case_id in seen:
            raise CaseError(f"{raw}:{line_no}: дублирующийся case_id `{case.case_id}`")
        seen.add(case.case_id)
        if require_media:
            file_sha = _sha256_of_file(root / case.media.path)
            if file_sha != case.media.sha256:
                raise CaseError(f"{case.case_id}: sha256 файла не совпадает с манифестом")
        cases.append(case)
    return cases
