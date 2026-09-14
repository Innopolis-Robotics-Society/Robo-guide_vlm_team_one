"""Единая схема кейса оценки -- одна форма для всех пяти источников.

Дизайн: `docs/eval_harness_design.md`, раздел "Unified case record".
Схема должна выражать все источники БЕЗ ветвления раннера: различия
живут в данных (`source`, `track`, `gold`, `slices`), а не в коде.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

TRACKS: tuple[str, ...] = ("pointing", "audience", "scene", "tool")
SOURCES: tuple[str, ...] = ("dp", "egopoint", "yourifit", "aghri", "pilot-cc", "pilot-sr")
PROMPT_MODES: tuple[str, ...] = ("deployed", "freeform")

GOLD_TYPES: tuple[str, ...] = ("target_box", "count", "action", "claims", "unanswerable")

_SHA256_LEN = 64
# Тот же потолок, что у production-парсера наблюдения (vision.observation_max_chars).
_MAX_PEOPLE_COUNT = 20


class CaseError(ValueError):
    """Кейс не проходит валидацию схемы -- запись отклоняется целиком."""


@dataclass(frozen=True)
class Provenance:
    """Происхождение данных кейса; лицензионная строка -- обязательна.

    `license` обязан цитировать датированную строку верификации из
    `docs/vlm_deixis_audience_datasets.md` -- кейс без проверенной
    лицензии не входит в набор (правило #10).
    """

    source: str
    license: str
    version: str
    rights_note: str = ""


@dataclass(frozen=True)
class MediaRef:
    """Медиафайл кейса: путь относительно корня данных + sha256.

    `sha256` вычисляется при сборке манифеста, никогда не правится
    руками: рассинхронизация файла и хэша -- ошибка загрузки, а не
    предупреждение.
    """

    path: str
    sha256: str
    format: str


@dataclass(frozen=True)
class PromptSpec:
    """Запрос модели для кейса.

    `mode` -- `deployed` (production-контракт observation→action,
    измерить то, что поедет в #11) или `freeform` (строгий JSON-ответ
    для авторского QA-протокола EgoPoint-Bench).
    """

    mode: str
    user_text: str
    language: str = "en"


@dataclass
class Case:
    """Единая запись оценки: один кейс = одна модель-вызовная единица.

    `candidates` -- замкнутый набор id, из которого модель может
    отвечать (семантическая карта -- единственный источник id,
    инвариант #4). Для кейсов без выбора цели (count) -- пусто.
    `gold` -- словарь с обязательным `type` (см. `GOLD_TYPES`) и
    полями трека. `slices` -- метаданные для срезов отчёта (размер
    цели, число дистракторов, bucket счётчика и т.п.).
    """

    case_id: str
    source: str
    track: str
    split_group_id: str
    media: MediaRef
    prompt: PromptSpec
    candidates: tuple[str, ...] = ()
    allowed_tools: tuple[str, ...] = ()
    gold: dict[str, Any] = field(default_factory=dict)
    provenance: Provenance | None = None
    slices: dict[str, Any] = field(default_factory=dict)


def _require_str(data: dict[str, Any], key: str, where: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        msg = f"{where}: поле `{key}` -- непустая строка обязательно"
        raise CaseError(msg)
    return value


def _require_sha256(data: dict[str, Any], where: str) -> str:
    value = data.get("sha256")
    if (
        not isinstance(value, str)
        or len(value) != _SHA256_LEN
        or not all(c in "0123456789abcdef" for c in value.lower())
    ):
        msg = f"{where}: `sha256` -- 64 hex-символа (вычисляется при загрузке)"
        raise CaseError(msg)
    return value.lower()


def _validate_gold(gold: dict[str, Any], where: str) -> None:
    if not isinstance(gold, dict) or not gold:
        msg = f"{where}: `gold` -- непустой словарь"
        raise CaseError(msg)
    gold_type = gold.get("type")
    if gold_type not in GOLD_TYPES:
        msg = f"{where}: `gold.type` из {GOLD_TYPES}, получено {gold_type!r}"
        raise CaseError(msg)
    if gold_type == "target_box":
        if not isinstance(gold.get("target_id"), str) or not gold["target_id"]:
            msg = f"{where}: gold target_box требует `target_id`"
            raise CaseError(msg)
        box = gold.get("box_px")
        if box is not None and (
            not isinstance(box, list) or len(box) != 4 or not all(isinstance(v, int) for v in box)
        ):
            msg = f"{where}: gold `box_px` -- [x0,y0,x1,y1] из int или null"
            raise CaseError(msg)
        distractors = gold.get("distractors", [])
        if not isinstance(distractors, list) or not all(isinstance(v, str) for v in distractors):
            msg = f"{where}: gold `distractors` -- список строк"
            raise CaseError(msg)
    elif gold_type == "count":
        count = gold.get("count")
        is_count = isinstance(count, int) and not isinstance(count, bool)
        if not is_count or not 0 <= count <= _MAX_PEOPLE_COUNT:
            msg = f"{where}: gold `count` -- int 0..{_MAX_PEOPLE_COUNT}"
            raise CaseError(msg)
    elif gold_type == "action":
        if not gold.get("abstention_reason") and (
            not isinstance(gold.get("tool"), str) or not isinstance(gold.get("args"), dict)
        ):
            msg = f"{where}: gold action -- `tool`+`args` либо `abstention_reason`"
            raise CaseError(msg)
    elif gold_type == "claims":
        claims = gold.get("claims")
        if not isinstance(claims, list) or not all(isinstance(v, str) for v in claims):
            msg = f"{where}: gold `claims` -- список строк"
            raise CaseError(msg)


def case_from_dict(data: dict[str, Any]) -> Case:
    """Строгая валидация словаря → `Case`. Любое отклонение -- `CaseError`.

    Кейс без `provenance` (source/license/version) отклоняется: в набор
    не попадает данные, за которые нельзя указать право (правило #10).
    """
    where = f"кейс {data.get('case_id', '<без id>')}"
    case_id = _require_str(data, "case_id", where)
    where = f"кейс {case_id}"
    source = _require_str(data, "source", where)
    if source not in SOURCES:
        raise CaseError(f"{where}: `source` из {SOURCES}, получено {source!r}")
    track = _require_str(data, "track", where)
    if track not in TRACKS:
        raise CaseError(f"{where}: `track` из {TRACKS}, получено {track!r}")
    split_group_id = _require_str(data, "split_group_id", where)

    media_raw = data.get("media")
    if not isinstance(media_raw, dict):
        raise CaseError(f"{where}: `media` -- объект")
    media = MediaRef(
        path=_require_str(media_raw, "path", where),
        sha256=_require_sha256(media_raw, where),
        format=_require_str(media_raw, "format", where),
    )

    prompt_raw = data.get("prompt")
    if not isinstance(prompt_raw, dict):
        raise CaseError(f"{where}: `prompt` -- объект")
    mode = prompt_raw.get("mode")
    if mode not in PROMPT_MODES:
        raise CaseError(f"{where}: `prompt.mode` из {PROMPT_MODES}, получено {mode!r}")
    language_raw = prompt_raw.get("language", "en")
    prompt = PromptSpec(
        mode=mode,
        user_text=_require_str(prompt_raw, "user_text", where),
        language=language_raw if isinstance(language_raw, str) else "en",
    )

    candidates = data.get("candidates", [])
    if not isinstance(candidates, list) or not all(isinstance(v, str) for v in candidates):
        raise CaseError(f"{where}: `candidates` -- список строк")
    allowed_tools = data.get("allowed_tools", [])
    if not isinstance(allowed_tools, list) or not all(isinstance(v, str) for v in allowed_tools):
        raise CaseError(f"{where}: `allowed_tools` -- список строк")

    gold = data.get("gold")
    if not isinstance(gold, dict):
        raise CaseError(f"{where}: `gold` -- объект")
    _validate_gold(gold, where)

    prov_raw = data.get("provenance")
    if not isinstance(prov_raw, dict):
        raise CaseError(f"{where}: `provenance` обязателен (source/license/version)")
    rights_note_raw = prov_raw.get("rights_note", "")
    provenance = Provenance(
        source=_require_str(prov_raw, "source", where),
        license=_require_str(prov_raw, "license", where),
        version=_require_str(prov_raw, "version", where),
        rights_note=rights_note_raw if isinstance(rights_note_raw, str) else "",
    )

    slices = data.get("slices", {})
    if not isinstance(slices, dict):
        raise CaseError(f"{where}: `slices` -- объект")

    return Case(
        case_id=case_id,
        source=source,
        track=track,
        split_group_id=split_group_id,
        media=media,
        prompt=prompt,
        candidates=tuple(candidates),
        allowed_tools=tuple(allowed_tools),
        gold=gold,
        provenance=provenance,
        slices=slices,
    )


def case_to_dict(case: Case) -> dict[str, Any]:
    """Обратное сериализация в плоский словарь (JSON-совместимо)."""
    return {
        "case_id": case.case_id,
        "source": case.source,
        "track": case.track,
        "split_group_id": case.split_group_id,
        "media": {
            "path": case.media.path,
            "sha256": case.media.sha256,
            "format": case.media.format,
        },
        "prompt": {
            "mode": case.prompt.mode,
            "user_text": case.prompt.user_text,
            "language": case.prompt.language,
        },
        "candidates": list(case.candidates),
        "allowed_tools": list(case.allowed_tools),
        "gold": dict(case.gold),
        "provenance": {
            "source": case.provenance.source,
            "license": case.provenance.license,
            "version": case.provenance.version,
            "rights_note": case.provenance.rights_note,
        },
        "slices": dict(case.slices),
    }


def load_cases_from_jsonl(path: str | Path) -> list[Case]:
    """Загрузить унифицированный манифест (JSONL) со строгой валидацией.

    Пустые строки пропускаются; дубли `case_id` -- ошибка (манифест
    замороженный артефакт, дублирование -- признак битой сборки).
    """
    cases: list[Case] = []
    seen: set[str] = set()
    with open(path, encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError as error:
                raise CaseError(f"{path}:{line_no}: битая JSON-строка ({error})") from error
            case = case_from_dict(data)
            if case.case_id in seen:
                raise CaseError(f"{path}:{line_no}: дублирующийся case_id `{case.case_id}`")
            seen.add(case.case_id)
            cases.append(case)
    return cases
