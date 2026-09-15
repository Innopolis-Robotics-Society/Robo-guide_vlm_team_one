"""AGHRI → единая схема кейса (Taiga #10, T9).

Данные: AGHRI (University of Lincoln, LCAS) — 65 последовательностей
(~70 GB в 10 архивах, DOI 10.24385/lincoln.32982638) с синхронизированными
ZED RGB/depth, fisheye, LiDAR и identity-consistent 2D/3D аннотациями
людей. Датасет распространяется отдельно от кода бенчмарка под
**CC BY 4.0** (проверено 2026-09-15, T1,
``docs/vlm_deixis_audience_datasets.md`` — раздел «License verification»):
модификация с атрибуцией разрешена.

Задача T9: 15 кадров счётчиков аудитории (0–5 человек, одиночные +
много-человеческие последовательности) из ≥5 разных последовательностей
(≤3 кадра на последовательность). Модель получает ТОЛЬКО front ZED RGB
кадр; gold-счётчик выводится детерминированно из identity-consistent
**не-ignored** 2D боксов ``annotations/cam_zed_rgb_ann.json``
(уникальные цифровые идентичности), без ручного ввода. Fisheye/depth/
3D/gaze в кейсы не попадают.

Двухэтапный CLI (данные скачивает пользователь — агент не скачивает,
сайт за AWS WAF, прямых URL нет):

* ``plan`` — читает ``dataset_summary.csv`` (маленький index-файл
  релиза), выбирает последовательности, покрывающие счётчики 1–5
  (0 — на уровне кадров: аннотированный кадр без людей), пишет
  ``selection.json`` и печатает part-level команды загрузки (только
  архивы ``dataset_partN.zip`` с выбранными последовательностями —
  не весь ~70 GB).
* ``build`` — читает ``selection.json`` + скачанные данные, пишет
  ``cases.jsonl`` (единая схема, sha256 на кадр) + sidecar-отчёт +
  ``PROVENANCE.md`` в корне данных.

Формат аннотаций — по toolkit авторов (``LCAS/AGHRI-dataset-tools``,
``yolo/yolo_export_session.py``, проверено 2026-09-16): список записей
``{"File": "<кадр>.png", "Labels": [{"Class": "human1",
"BoundingBoxes": [x, y, w, h]}, …]}`` (либо dict с ключом ``frames`` /
по именам файлов). Классы людей: цифровая идентичность (``01``, ``10``)
или legacy ``human``/``human1..human5``/``person``. Бокс может быть
обёрнут: ``[{"Position": [x, y, w, h]}]``. Ignored-флаг не задокументирован
в toolkit — проверяем устойчиво (``Ignore``/``Ignored``/``IsIgnored``/
``IgnoreFlag``, ``Valid: false``). Кадр БЕЗ записи в ann JSON никогда не
выбирается: отсутствие записи ≠ пустая сцена.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from guide_robot_llm.eval.schema import Case, MediaRef, PromptSpec, Provenance, case_to_dict

SOURCE = "aghri"

# Лицензия: строка из верификации T1 (2026-09-15) — см.
# docs/vlm_deixis_audience_datasets.md, раздел «License verification».
LICENSE_LINE = "CC BY 4.0 (verified 2026-09-15, T1)"
RIGHTS_NOTE = (
    "attribution (CC BY 4.0); selected sequences only; no redistribution "
    "beyond this eval set (T1, 2026-09-15)"
)
DOI_URL = "https://doi.org/10.24385/lincoln.32982638"
TOOLS_REPO_URL = "https://github.com/LCAS/AGHRI-dataset-tools"
BENCHMARK_REPO_URL = "https://github.com/LCAS/AGHRI-dataset-benchmark"

# Единственная камера в кейсах: front ZED RGB (RGB + 2D боксы только).
CAMERA = "cam_zed_rgb"
ANNOTATIONS_REL = f"annotations/{CAMERA}_ann.json"
FRAMES_REL = f"sensor_data/{CAMERA}"

SUMMARY_NAME = "dataset_summary.csv"
SELECTION_NAME = "selection.json"
SELECTION_SCHEMA = "aghri-selection/1"

DEFAULT_N_FRAMES = 15
DEFAULT_MAX_PER_SEQ = 3
DEFAULT_MEDIA_PREFIX = "eval_data/aghri"

# Вопрос deployed-контракта (пример кейса AGHRI в
# docs/eval_harness_design.md; gold — счётчик людей рядом с роботом).
PROMPT_TEXT = "Сколько людей сейчас рядом с роботом?"

# Жёсткое требование к покрытию на уровне последовательностей:
# счётчики 1..5 обязаны быть представлены выбранной последовательностью.
# 0 — мягкое требование: в HRI-датасете «пустой» последовательности может
# не быть, gold-0 приходит из аннотированных кадров без людей.
REQUIRED_COUNTS: tuple[int, ...] = (1, 2, 3, 4, 5)
MAX_COUNT = 5

# Заголовки summary CSV не задокументированы — устойчивый поиск:
# нижний регистр, всё, кроме [a-z0-9], вырезается. Роль → алиасы.
_SEQ_ALIASES = (
    "sequence",
    "sequencename",
    "sequencefolder",
    "session",
    "sessionname",
    "seq",
    "seqname",
    "sequenceid",
    "sessionid",
    "folder",
    "foldername",
    "bag",
    "bagname",
    "name",
    # реальный v2-релиз (2026-08-21): заголовок «Scene Name»
    "scene",
    "scenename",
    "sceneid",
)
_COUNT_ALIASES = (
    "participants",
    "numberofparticipants",
    "numparticipants",
    "nparticipants",
    "npeople",
    "numpeople",
    "numberofpeople",
    "people",
    "persons",
    "numpersons",
    "npersons",
    "nperson",
    "personcount",
    # реальный v2-релиз: заголовок «Number of Humans»
    "humans",
    "numberofhumans",
    "nhumans",
    "numhumans",
    "humancount",
)
_ARCHIVE_ALIASES = (
    "archive",
    "archivefile",
    "archivepart",
    "archivenumber",
    "part",
    "partnumber",
    "datasetpart",
    "zip",
    "zipfile",
    "file",
    "filepart",
    "download",
    # реальный v2-релиз: «Dataset compressed part it belongs to» (целое)
    "datasetcompressedpartitbelongsto",
    "partitbelongsto",
    "compressedpart",
)
_FRAMES_ALIASES = (
    "frames",
    "numberofframes",
    "nframes",
    "numframes",
    "cameraframes",
    "annotatedframes",
)
_SPLIT_ALIASES = ("split",)
# v2-релиз: срезы напрямую из CSV (точнее, чем парсинг имени)
_ENV_ALIASES = ("environment", "env", "sceneenvironment")
_ROBOT_ALIASES = ("robotmovements", "robotmovement", "robotstate")


class AghriAdapterError(RuntimeError):
    """Ошибка адаптера AGHRI (формат, покрытие, целостность)."""


@dataclass(frozen=True)
class SummaryRow:
    """Строка ``dataset_summary.csv`` с разобранным счётчиком."""

    seq: str
    row_no: int
    declared_count: int | None
    count_source: str  # "csv" | "name" | ""
    archive: str | None
    frames: int | None
    split: str | None
    environment: str | None = None  # CSV-колонка v2 (по имени — fallback в build)
    robot_state: str | None = None


@dataclass(frozen=True)
class SelectedSeq:
    """Выбранная последовательность с распределённой кадровой квотой."""

    seq: str
    seq_no: int  # позиция в summary CSV (1-based) — стабильный номер кейса
    declared_count: int
    count_source: str
    archive: str | None
    split: str | None
    environment: str | None
    robot_state: str | None
    frames_wanted: int


# ---------------------------------------------------------------------------
# Имя последовательности → объявленное число людей
# ---------------------------------------------------------------------------

# Активность-токен: цифра-префикс + код активности (плюс-конъюнкция тех же
# кодов = «те же люди делают ещё и это», не добавляет счётчик).
_ACTIVITY_CODES = ("walk", "stand", "talk", "check", "push", "carry", "swap", "pick")
_ACTIVITY_RE = re.compile(
    r"^(\d+)(?:" + "|".join(_ACTIVITY_CODES) + r")"
    r"(?:\+(?:" + "|".join(_ACTIVITY_CODES) + r"))*$"
)


def declared_count_from_name(seq_name: str) -> int | None:
    """Число людей по имени последовательности (fallback без CSV-колонки).

    Формат имени (toolkit README): ``<env>_<N-activity>[_<N-activity>...]_
    <robot-state>_<MM_DD_YYYY>_<instance>[_<section>]_label``; цифра ПЕРЕД
    активностью = число людей в группе, ``+`` объединяет действия ТЕХ ЖЕ
    людей. Чистые цифры (даты, instance, env-префикс) не считаются.
    ``footpath1_2walk+stand_mv_11_20_2024_1`` → 2;
    ``in_vine_2push_1pick_diff_mv_ly_11_06_2024_3_a`` → 3;
    ``out_vine_5swap_walk_st_ly_11_06_2024_2`` → 5 (``walk`` без цифры =
    те же 5). Нет ни одной группы → ``None``.
    """
    name = seq_name[: -len("_label")] if seq_name.endswith("_label") else seq_name
    total = 0
    found = False
    for token in name.split("_"):
        match = _ACTIVITY_RE.match(token)
        if match:
            total += int(match.group(1))
            found = True
    return total if found else None


# ---------------------------------------------------------------------------
# dataset_summary.csv
# ---------------------------------------------------------------------------


def _norm_header(column: str | None) -> str:
    """Нормализация заголовка: регистр и разделители не важны."""
    return re.sub(r"[^a-z0-9]+", "", (column or "").lower())


def _find_columns(fieldnames: list[str]) -> dict[str, int]:
    """Роль → индекс колонки (устойчивый поиск по алиасам, первый победил)."""
    found: dict[str, int] = {}
    for idx, column in enumerate(fieldnames):
        key = _norm_header(column)
        for role, aliases in (
            ("seq", _SEQ_ALIASES),
            ("count", _COUNT_ALIASES),
            ("archive", _ARCHIVE_ALIASES),
            ("frames", _FRAMES_ALIASES),
            ("split", _SPLIT_ALIASES),
            ("env", _ENV_ALIASES),
            ("robot", _ROBOT_ALIASES),
        ):
            if key in aliases and role not in found:
                found[role] = idx
    return found


_ARCHIVE_PART_RE = re.compile(r"^dataset_part(\d+)\.zip$")


def _archive_to_zip(raw: str | None) -> str | None:
    """Значение archive-колонки → имя zip-архива.

    v2-релиз кладёт в колонку целое число части («1»..«10»), a не имя
    файла — нормализуем в ``dataset_partN.zip``. Пустое → ``None``.
    """
    value = (raw or "").strip()
    if not value:
        return None
    if value.isdigit():
        return f"dataset_part{value}.zip"
    return value


def _zip_to_part(archive: str | None) -> int | None:
    """Имя zip-архива → номер части (для ``--parts``-фильтра)."""
    match = _ARCHIVE_PART_RE.match(archive or "")
    return int(match.group(1)) if match else None


def _parse_count(raw: str) -> int | None:
    """Негативное/дробное/пустое → ``None`` (строка не отбрасывается)."""
    try:
        value = float(raw)
    except ValueError:
        return None
    if value < 0 or not value.is_integer():
        return None
    return int(value)


def _field_has_content(value: Any) -> bool:
    """Есть ли содержимое в значении поля (None и пустые строки — нет)."""
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list | tuple):
        return any(_field_has_content(item) for item in value)
    return True


def _row_is_blank(values: dict[str, Any]) -> bool:
    """Полностью пустая строка-заглушка (хвост v2-CSV).

    Строка с частью полей — в т.ч. с лишними сверх заголовка (csv restkey)
    — заглушкой НЕ считается: её пустое имя дальше станет ошибкой.
    """
    if values.get(None):
        return False
    return not any(_field_has_content(value) for value in values.values())


def load_summary_csv(path: Path) -> list[SummaryRow]:
    """Читает index-CSV релиза (устойчивый поиск заголовков).

    Счётчик берётся из колонки, если она есть и разбирается; иначе —
    из имени последовательности (``declared_count_from_name``). Строка
    без имени — ошибка; без счётчика — ``declared_count=None`` (строка
    исключается выбором с заметкой, не с падением).
    """
    path = Path(path)
    if not path.is_file():
        raise AghriAdapterError(f"не найден {path} (index-файл релиза AGHRI)")
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        fieldnames = [name for name in (reader.fieldnames or []) if name is not None]
        cols = _find_columns(fieldnames)
        if "seq" not in cols:
            raise AghriAdapterError(
                f"{path.name}: колонка с именем последовательности не найдена "
                f"(заголовки: {fieldnames!r}); поддерживаются алиасы: "
                f"{', '.join(_SEQ_ALIASES[:6])}…"
            )
        seq_col = fieldnames[cols["seq"]]
        count_col = fieldnames[cols["count"]] if "count" in cols else None
        archive_col = fieldnames[cols["archive"]] if "archive" in cols else None
        frames_col = fieldnames[cols["frames"]] if "frames" in cols else None
        split_col = fieldnames[cols["split"]] if "split" in cols else None
        env_col = fieldnames[cols["env"]] if "env" in cols else None
        robot_col = fieldnames[cols["robot"]] if "robot" in cols else None
        rows: list[SummaryRow] = []
        for row_no, record in enumerate(reader, start=1):
            values = record or {}
            # v2-релиз: хвост CSV содержит полностью пустые строки-заглушки —
            # пропускаем их (строка с частью полей, но без имени — ошибка).
            if _row_is_blank(values):
                continue  # хвостовая заглушка, данных нет
            seq = (values.get(seq_col) or "").strip()
            if not seq:
                raise AghriAdapterError(f"{path.name}:{row_no}: пустое имя последовательности")
            declared = None
            source = ""
            if count_col is not None:
                declared = _parse_count((values.get(count_col) or "").strip())
                if declared is not None:
                    source = "csv"
            if declared is None:
                declared = declared_count_from_name(seq)
                if declared is not None:
                    source = "name"
            frames = None
            if frames_col is not None:
                frames = _parse_count((values.get(frames_col) or "").strip())
            rows.append(
                SummaryRow(
                    seq=seq,
                    row_no=row_no,
                    declared_count=declared,
                    count_source=source,
                    archive=_archive_to_zip(
                        (values.get(archive_col) or "").strip()
                        if archive_col is not None
                        else None
                    ),
                    frames=frames,
                    split=(values.get(split_col) or "").strip() or None
                    if split_col is not None
                    else None,
                    environment=(values.get(env_col) or "").strip() or None
                    if env_col is not None
                    else None,
                    robot_state=(values.get(robot_col) or "").strip() or None
                    if robot_col is not None
                    else None,
                )
            )
    if not rows:
        raise AghriAdapterError(f"{path.name}: пустой index (нет строк)")
    return rows


# ---------------------------------------------------------------------------
# Выбор последовательностей (plan-стадия)
# ---------------------------------------------------------------------------


def select_sequences(
    rows: list[SummaryRow],
    n_frames: int = DEFAULT_N_FRAMES,
    max_per_seq: int = DEFAULT_MAX_PER_SEQ,
    parts: tuple[int, ...] | None = None,
    required_counts: tuple[int, ...] = REQUIRED_COUNTS,
) -> tuple[list[SelectedSeq], dict[str, Any]]:
    """Детерминированный выбор: покрытие счётчиков, round-robin ≤ ``max_per_seq``.

    1) Строки с ``declared_count`` 0..5 группируются по счётчику
       (порядок строк summary сохраняется); ядро = первая строка каждого
       счётчика. Счётчик > 5 — за gold-диапазоном (схема: ≤20, но T9
       фиксирует 0–5), без имени и без счётчика — исключаются с
       заметкой. ``parts`` — фильтр по zip-частям релиза: строка без
       archive-колонки или из другой части исключается (данных у
       пользователя нет; scope-решение vlm-bench-50, T10, 2026-09-15).
    2) Счётчики ``required_counts`` (по умолчанию 1..5) ОБЯЗАТЕЛЬНО
       представлены в ядре — иначе ошибка (нельзя достроить покрытие из
       кадров); отсутствие 0 — только заметка (gold-0 дадут аннотированные
       пустые кадры).
    3) Квоты: round-robin по ядру (порядок (count, строка)), по 1 кадру за
       проход, до ``max_per_seq`` на последовательность. Если квот не
       хватает — добавляются резервные строки (дубликаты счётчиков)
       тем же round-robin'ом; не хватило и после резерва — ошибка.
    """
    if n_frames < 1:
        raise AghriAdapterError(f"n_frames < 1: {n_frames}")
    if max_per_seq < 1:
        raise AghriAdapterError(f"max_per_seq < 1: {max_per_seq}")
    notes: list[str] = []
    excluded: list[dict[str, Any]] = []
    buckets: dict[int, list[SummaryRow]] = {}
    for row in rows:
        if parts is not None:
            part = _zip_to_part(row.archive)
            if part not in parts:
                excluded.append(
                    {
                        "seq": row.seq,
                        "row_no": row.row_no,
                        "declared_count": row.declared_count,
                        "reason": (f"archive part {part} not in --parts {sorted(parts)}"),
                    }
                )
                notes.append(
                    f"строка {row.row_no} ({row.seq}): часть {part} вне "
                    f"фильтра {sorted(parts)} — не скачивается, исключена"
                )
                continue
        count = row.declared_count
        if count is None:
            excluded.append(
                {
                    "seq": row.seq,
                    "row_no": row.row_no,
                    "reason": (
                        "count not declared (CSV column missing/unparseable, "
                        "name has no N-activity groups)"
                    ),
                }
            )
            notes.append(
                f"строка {row.row_no} ({row.seq}): счётчик не объявлен — "
                "строка исключена из выбора"
            )
            continue
        if count > MAX_COUNT:
            excluded.append(
                {
                    "seq": row.seq,
                    "row_no": row.row_no,
                    "declared_count": count,
                    "reason": f"declared count {count} > {MAX_COUNT}",
                }
            )
            notes.append(
                f"строка {row.row_no} ({row.seq}): объявлено {count} человек "
                f"> {MAX_COUNT} — вне диапазона T9, исключена"
            )
            continue
        buckets.setdefault(count, []).append(row)
    core = [buckets[count][0] for count in range(0, MAX_COUNT + 1) if count in buckets]
    missing = [count for count in required_counts if count not in buckets]
    if missing:
        raise AghriAdapterError(
            "покрытие сбоем: в summary нет последовательностей со "
            f"счётчиком(ами) {missing} — нельзя собрать {n_frames} кейсов "
            f"по покрытию {sorted(required_counts)}"
        )
    if 0 not in buckets:
        notes.append(
            "в summary нет последовательности с 0 участниками; gold-0 "
            "будут взяты из аннотированных кадров без людей"
        )
    core.sort(key=lambda row: (row.declared_count, row.row_no))
    pool = sorted(
        (
            row
            for count in range(0, MAX_COUNT + 1)
            if count in buckets
            for row in buckets[count][1:]
        ),
        key=lambda row: (row.declared_count, row.row_no),
    )
    selected: list[SummaryRow] = list(core)
    quota: dict[str, int] = {row.seq: 0 for row in selected}
    budget = n_frames
    while budget > 0:
        progressed = False
        for row in selected:
            if budget <= 0:
                break
            if quota[row.seq] < max_per_seq:
                quota[row.seq] += 1
                budget -= 1
                progressed = True
        if not progressed:
            if pool:
                row = pool.pop(0)
                selected.append(row)
                quota[row.seq] = 0
                continue
            raise AghriAdapterError(
                f"недостаточно кадровой ёмкости: {n_frames} кадров при "
                f"{max_per_seq}/последовательность требуют ≥ "
                f"{(n_frames + max_per_seq - 1) // max_per_seq} "
                "последовательностей, доступно "
                f"{len(selected) + len(pool)}"
            )
    chosen: list[SelectedSeq] = []
    for row in selected:
        chosen.append(
            SelectedSeq(
                seq=row.seq,
                seq_no=row.row_no,
                declared_count=row.declared_count,
                count_source=row.count_source,
                archive=row.archive,
                split=row.split,
                environment=row.environment,
                robot_state=row.robot_state,
                frames_wanted=quota[row.seq],
            )
        )
    cover_row = {row.declared_count: row.row_no for row in core}
    for row in rows:
        count = row.declared_count
        if count is None or count > MAX_COUNT:
            continue
        if count not in cover_row:
            continue  # этот count не в core: его строки уже отфильтрованы
        if row in selected:
            continue
        excluded.append(
            {
                "seq": row.seq,
                "row_no": row.row_no,
                "declared_count": count,
                "reason": (f"duplicate of count {count} (covered by row {cover_row[count]})"),
            }
        )
    declared_coverage = {
        str(count): sum(1 for row in selected if row.declared_count == count)
        for count in range(0, MAX_COUNT + 1)
    }
    report: dict[str, Any] = {
        "n_selected": len(chosen),
        "n_frames_selected": sum(quota.values()),
        "n_excluded": len(excluded),
        "declared_coverage": declared_coverage,
        "archives": sorted({row.archive for row in selected if row.archive}),
        "parts": sorted(parts) if parts is not None else None,
        "required_counts": sorted(required_counts),
        "notes": notes,
    }
    return chosen, {"excluded": excluded, "report": report}


# ---------------------------------------------------------------------------
# Кадровые выборки и аннотации (build-стадия)
# ---------------------------------------------------------------------------


def pick_frame_indices(n_frames: int, n_wanted: int) -> list[int]:
    """Квази-равномерные 0-based индексы кадров (first/mid/last).

    n=100, k=3 → [0, 49, 99]; k >= n → все кадры; k == 1 → первый.
    Детерминированно; стабильность case_id при пересборке сохраняется,
    т.к. номер кадра = позиция в аннотационном списке.
    """
    if n_frames < 1:
        raise AghriAdapterError(f"нет аннотированных кадров (n={n_frames})")
    if n_wanted < 1:
        raise AghriAdapterError(f"frames_wanted < 1: {n_wanted}")
    if n_wanted >= n_frames:
        return list(range(n_frames))
    if n_wanted == 1:
        return [0]
    return [j * (n_frames - 1) // (n_wanted - 1) for j in range(n_wanted)]


def load_ann_frames(ann_path: Path) -> list[tuple[str, list[dict[str, Any]]]]:
    """Читает ``cam_zed_rgb_ann.json`` → отсортированный список ``(file, labels)``.

    Устойчивость формата — по ``yolo_export_session.py`` авторов:
    список ``{"File": ..., "Labels": [...]}`` (алиасы ``frames``/
    ``labels``/``objects``), dict с ключом ``frames`` или dict
    ``{file: labels}`` (и ``{file: {"Labels": [...]}}``). Дубликат имени
    файла — объединение записей (как в toolkit'е).
    """
    ann_path = Path(ann_path)
    if not ann_path.is_file():
        raise AghriAdapterError(f"не найдены аннотации: {ann_path}")
    try:
        data = json.loads(ann_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AghriAdapterError(f"битый JSON аннотаций {ann_path.name}: {exc}") from exc
    entries: dict[str, list[dict[str, Any]]] = {}

    def add(file: Any, labels: Any) -> None:
        if not isinstance(file, str) or not file:
            raise AghriAdapterError(f"{ann_path.name}: запись без имени кадра: {file!r}")
        if labels is None:
            labels = []
        if not isinstance(labels, list):
            raise AghriAdapterError(f"{ann_path.name}: `Labels` для {file} — не список")
        entries.setdefault(file, []).extend(labels)

    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                raise AghriAdapterError(f"{ann_path.name}: элемент списка — не объект: {item!r}")
            add(
                item.get("File") or item.get("file") or item.get("Image"),
                item.get("Labels", item.get("labels", item.get("objects"))),
            )
    elif isinstance(data, dict):
        inner = data.get("frames", data)
        if isinstance(inner, list):
            for item in inner:
                add(
                    item.get("File") or item.get("file") or item.get("Image"),
                    item.get("Labels", item.get("labels", item.get("objects"))),
                )
        else:
            for file, value in inner.items():
                if isinstance(value, dict) and "Labels" in value:
                    add(file, value["Labels"])
                elif isinstance(value, list):
                    add(file, value)
    else:
        raise AghriAdapterError(f"{ann_path.name}: неожиданный формат (list/dict)")
    return sorted(entries.items())


def parse_box(raw: Any) -> tuple[float, ...] | None:
    """``[x, y, w, h]`` либо обёртка ``[{"Position": [x, y, w, h]}]``.

    Мусор/пустое/неполное → ``None`` (бокс игнорируется, не падение).
    """
    if not isinstance(raw, list) or not raw:
        return None
    if isinstance(raw[0], dict):
        for item in raw:
            position = item.get("Position", item.get("position"))
            if (
                isinstance(position, list)
                and len(position) >= 4
                and all(isinstance(v, int | float) and not isinstance(v, bool) for v in position)
            ):
                return tuple(float(v) for v in position[:4])
        return None
    if len(raw) >= 4 and all(
        isinstance(v, int | float) and not isinstance(v, bool) for v in raw[:4]
    ):
        return tuple(float(v) for v in raw[:4])
    return None


_IGNORED_KEYS = ("ignore", "ignored", "isignored", "ignoreflag", "ignoreflag_")
_IGNORED_TRUTHY = (True, 1, "1", "true", "True", "TRUE", "yes", "Yes")


def _is_ignored(label: dict[str, Any]) -> bool:
    """Ignored-флаг: устойчивая проверка (формат не задокументирован)."""
    for key in label:
        norm = re.sub(r"[^a-z0-9]+", "", str(key).lower())
        if norm in _IGNORED_KEYS and label[key] in _IGNORED_TRUTHY:
            return True
    return label.get("Valid", label.get("valid", True)) in (False, 0)


_HUMAN_IDENTITY_RE = re.compile(r"^(?:human)?(\d+)$")


def _human_identity(cls: Any) -> str | None:
    """Цифровая идентичность человека; ``None`` — не человек/не человек.

    ``01``/``1`` → ``"1"`` (нормализация ведущего нуля); ``human1``/
    ``HUMAN2`` → ``"1"``/``"2"``; ``person``/``human`` без цифры —
    безымянная идентичность (``"person"``, каждая запись своя);
    ``0`` — не человек (в toolkit ``int("0") > 0 == False``); остальное —
    не человек.
    """
    if not isinstance(cls, str):
        return None
    name = cls.strip().lower()
    match = _HUMAN_IDENTITY_RE.match(name)
    if match and int(match.group(1)) > 0:
        return str(int(match.group(1)))
    if name in ("person", "human"):
        return "person"
    return None


def frame_person_count(labels: list[dict[str, Any]]) -> int:
    """Gold-счётчик кадра: уникальные НЕ-ignored идентичности людей.

    Identity-consistent боксы: человек с одной идентичностью в N боксах
    = 1 человек. Безымянная запись ``person``/``human`` (без цифры)
    считается отдельной личностью на запись (консервативно для legacy-
    секций). Не-ignored-проверка и фильтрация не-человеческих классов —
    ДО подсчёта.
    """
    identities: set[str] = set()
    for index, label in enumerate(labels):
        if not isinstance(label, dict):
            continue
        if _is_ignored(label):
            continue
        identity = _human_identity(label.get("Class", label.get("class", label.get("label"))))
        if identity is None:
            continue
        box = parse_box(label.get("BoundingBoxes", label.get("boundingboxes")))
        if box is None:
            continue
        if identity.isdigit():
            identities.add(identity)
        else:
            identities.add(f"person-{index}")
    return len(identities)


# ---------------------------------------------------------------------------
# Сборка кейсов (build-стадия)
# ---------------------------------------------------------------------------


def _package_root() -> Path:
    """Корень пакета ``guide_robot_llm/`` (как в dp/yourifit-адаптерах)."""
    return Path(__file__).resolve().parents[3]


def _seq_slices(seq: str) -> tuple[str, str]:
    """Срезы отчёта по имени: среда (``in_straw``, ``footpath1``…) и состояние робота.

    Значения берутся из имени последовательности (fallback, когда в CSV нет
    соответствующих колонок): среда — префикс (``footpath``, ``farmside``…),
    состояние робота — ``st``/``mv``.
    """
    name = seq[: -len("_label")] if seq.endswith("_label") else seq
    tokens = name.split("_")
    if tokens[0] in ("in", "out") and len(tokens) > 1:
        environment = f"{tokens[0]}_{tokens[1]}"
    else:
        environment = tokens[0]
    robot_state = "unknown"
    for token in tokens:
        if token in ("st", "mv"):
            robot_state = token
            break
    return environment, robot_state


def _case_for_frame(
    *,
    seq: str,
    seq_no: int,
    ann_pos: int,
    file_name: str,
    img_path: Path,
    media_prefix: str,
    gold_count: int,
    declared_count: int,
    environment: str,
    robot_state: str,
    split: str | None,
    summary_sha256: str,
) -> Case:
    """Один кейс: front ZED RGB кадр + deployed-вопрос + gold-счётчик."""
    sha256 = hashlib.sha256(img_path.read_bytes()).hexdigest()
    return Case(
        case_id=f"AGHRI-SEQ-{seq_no:04d}-F{ann_pos:03d}",
        source=SOURCE,
        track="audience",
        split_group_id=f"g-aghri-seq-{seq_no:04d}",
        media=MediaRef(
            path=f"{media_prefix}/{seq}/{FRAMES_REL}/{file_name}",
            sha256=sha256,
            format="png",
        ),
        prompt=PromptSpec(mode="deployed", user_text=PROMPT_TEXT, language="ru"),
        candidates=(),
        allowed_tools=(),
        gold={"type": "count", "count": gold_count},
        provenance=Provenance(
            source="AGHRI (University of Lincoln, LCAS)",
            license=LICENSE_LINE,
            version=f"dataset_summary.csv sha256:{summary_sha256[:16]}",
            rights_note=RIGHTS_NOTE,
        ),
        slices={
            "count_bucket": str(gold_count),
            "declared_count": declared_count,
            "environment": environment,
            "robot_state": robot_state,
            "split": split or "unknown",
        },
    )


def build_aghri_cases(
    data_root: str | Path,
    selection_path: str | Path | None = None,
    *,
    media_prefix: str = DEFAULT_MEDIA_PREFIX,
) -> tuple[list[Case], dict[str, Any]]:
    """Собирает кейсы из скачанных данных по ``selection.json``.

    Gold детерминированно из не-ignored identity-бокс'ов; отсутствие
    кадра или аннотаций — ошибка (read-only относительно данных, кроме
    ``PROVENANCE.md`` в корне данных по контракту дизайна).
    """
    data_root = Path(data_root)
    if not data_root.is_dir():
        raise AghriAdapterError(f"не найден корень данных: {data_root}")
    sel_path = Path(selection_path) if selection_path is not None else data_root / SELECTION_NAME
    if not sel_path.is_file():
        raise AghriAdapterError(
            f"не найдена {sel_path.name}: сначала `plan` (печатает команды "
            "загрузки), потом скачивание архивов и `build`"
        )
    selection = json.loads(sel_path.read_text(encoding="utf-8"))
    if selection.get("schema") != SELECTION_SCHEMA:
        raise AghriAdapterError(
            f"{sel_path.name}: schema {selection.get('schema')!r} != {SELECTION_SCHEMA!r}"
        )
    summary_sha256 = selection.get("summary_sha256", "unknown")
    cases: list[Case] = []
    frames_per_sequence: dict[str, int] = {}
    selected_table: list[dict[str, Any]] = []
    for item in selection.get("selected", []):
        seq = item["seq"]
        frames = load_ann_frames(data_root / seq / ANNOTATIONS_REL)
        if not frames:
            raise AghriAdapterError(f"{seq}: аннотации пусты ({ANNOTATIONS_REL})")
        # Срезы: CSV-колонки v2-релиза точнее парсинга имени; fallback — имя.
        name_env, name_robot = _seq_slices(seq)
        environment = item.get("environment") or name_env
        robot_state = item.get("robot_state") or name_robot
        indexes = pick_frame_indices(len(frames), item["frames_wanted"])
        for j in indexes:
            img_path = data_root / seq / FRAMES_REL / frames[j][0]
            if not img_path.is_file():
                raise AghriAdapterError(f"{seq}: кадр не найден {FRAMES_REL}/{frames[j][0]}")
            cases.append(
                _case_for_frame(
                    seq=seq,
                    seq_no=item["seq_no"],
                    ann_pos=j + 1,
                    file_name=frames[j][0],
                    img_path=img_path,
                    media_prefix=media_prefix,
                    gold_count=frame_person_count(frames[j][1]),
                    declared_count=item["declared_count"],
                    environment=environment,
                    robot_state=robot_state,
                    split=item.get("split"),
                    summary_sha256=summary_sha256,
                )
            )
        frames_per_sequence[seq] = len(indexes)
        selected_table.append(
            {
                "row": item["seq_no"],
                "seq": seq,
                "declared_count": item["declared_count"],
                "frames": frames_per_sequence[seq],
                "archive": item.get("archive"),
                "split": item.get("split"),
                "environment": environment,
                "robot_state": robot_state,
            }
        )
    cases.sort(key=lambda case: case.case_id)
    coverage: dict[str, int] = {}
    for case in cases:
        bucket = str(case.gold["count"])
        coverage[bucket] = coverage.get(bucket, 0) + 1
    report: dict[str, Any] = {
        "source": SOURCE,
        "track": "audience",
        "n_cases": len(cases),
        "n_sequences": len(frames_per_sequence),
        "prompt": PROMPT_TEXT,
        "media_prefix": media_prefix,
        "summary_sha256": summary_sha256,
        "selection_file": str(sel_path),
        "archives": selection.get("report", {}).get("archives", []),
        "gold_coverage": coverage,
        "frames_per_sequence": frames_per_sequence,
        "selected": selected_table,
        "notes": selection.get("report", {}).get("notes", []),
    }
    return cases, report


def load(data_root: str | Path) -> list[Case]:
    """Протокол загрузчика (контракт дизайна адаптеров)."""
    return build_aghri_cases(data_root)[0]


def write_manifest(cases: list[Case], report: dict[str, Any], out_path: Path) -> Path:
    """Пишет ``cases.jsonl`` (единая схема) + sidecar-отчёт; возвращает путь."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for case in cases:
            fh.write(json.dumps(case_to_dict(case), ensure_ascii=False) + "\n")
    sidecar = out_path.with_name(out_path.name + ".sidecar.json")
    sidecar.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return sidecar


# ---------------------------------------------------------------------------
# PROVENANCE и команды загрузки
# ---------------------------------------------------------------------------


def download_instructions(archives: list[str]) -> str:
    """Part-level команды загрузки (печатает `plan`, кладёт в PROVENANCE).

    Агент ДАННЫЕ НЕ СКАЧИВАЕТ: сайт за JS/WAF-челленджем, прямых URL нет;
    пользователь качает только файлы ниже (не весь ~70 GB релиза).
    """
    files = sorted(set(archives))
    lines = [
        "ИСТОЧНИК: " + DOI_URL + " (Lincoln Repository, CC BY 4.0).",
        "Скачивает ПОЛЬЗОВАТЕЛЬ (агент не скачивает — JS/WAF-челлендж,",
        "прямых URL нет). Открыть страницу в браузере и скачать ТОЛЬКО:",
        "",
        f"  1. {SUMMARY_NAME} — index последовательностей (уже есть, plan прочитал его)",
    ]
    for index, archive in enumerate(files, start=2):
        lines.append(f"  {index}. {archive}")
    lines += [
        "",
        "Распаковать в корень данных:",
        "",
        "    mkdir -p eval_data/aghri && cd eval_data/aghri",
    ]
    lines += [f"    unzip -q {archive}" for archive in files]
    lines += [
        "",
        "Положить selection.json (вывод `plan`) в корень данных и выполнить `build`",
        "(команда сборки — в PROVENANCE.md).",
    ]
    return "\n".join(lines)


def provenance_text(cases: list[Case], report: dict[str, Any]) -> str:
    """Текст ``PROVENANCE.md`` в корне данных (контракт дизайна)."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# AGHRI eval set — PROVENANCE",
        "",
        f"Сгенерировано: {now}, `guide_robot_llm/eval/adapters/aghri.py build` (T9, Taiga #10).",
        "",
        "## Источник и лицензия",
        "",
        f"- Датасет: AGHRI, University of Lincoln (LCAS), {DOI_URL}",
        f"- Tools авторов: {TOOLS_REPO_URL}; бенчмарк: {BENCHMARK_REPO_URL}",
        f"- Лицензия: {LICENSE_LINE}",
        f"- Ограничения: {RIGHTS_NOTE}",
        f"- Index `{SUMMARY_NAME}`: sha256 `{report['summary_sha256']}` "
        "(selection закреплён на этот файл)",
        "",
        "## Структура данных (корень данных)",
        "",
        "```",
        "<data_root>/",
        "├── selection.json   # вывод `plan` (пinned)",
        "├── PROVENANCE.md    # этот файл",
        "└── <seq>_label/",
        "    ├── annotations/cam_zed_rgb_ann.json",
        "    └── sensor_data/cam_zed_rgb/<кадр>.png",
        "```",
        "",
        "## Выбранные последовательности",
        "",
        "| строка | последовательность | объявлено | кадров | архив |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in report["selected"]:
        lines.append(
            f"| {item['row']} | {item['seq']} | {item['declared_count']} "
            f"| {item['frames']} | {item['archive'] or '?'} |"
        )
    lines += [
        "",
        f"## Кейсы (n={report['n_cases']})",
        "",
        "| case_id | кадр | gold | объявлено | bucket |",
        "| --- | --- | --- | --- | --- |",
    ]
    for case in cases:
        lines.append(
            f"| {case.case_id} | {case.media.path.rsplit('/', 1)[-1]} "
            f"| {case.gold['count']} | {case.slices['declared_count']} "
            f"| {case.slices['count_bucket']} |"
        )
    lines += ["", "## Gold-покрытие (по gold-счётчику)", ""]
    for bucket in sorted(report["gold_coverage"]):
        lines.append(f"- {bucket} чел: {report['gold_coverage'][bucket]}")
    lines += ["", "## Загрузка (только пользователь)", "", "```text"]
    lines.append(download_instructions(report.get("archives", [])))
    lines += [
        "```",
        "",
        "## Команда сборки",
        "",
        "```bash",
        "python3 -m guide_robot_llm.eval.adapters.aghri build "
        "--data-root <data_root> --out eval_manifests/aghri_15.jsonl",
        "```",
    ]
    if report.get("notes"):
        lines += ["", "## Заметки `plan`", ""]
        lines += [f"- {note}" for note in report["notes"]]
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """CLI: ``plan`` (выбор + команды загрузки) / ``build`` (манифест)."""
    parser = argparse.ArgumentParser(
        prog="aghri.py",
        description="AGHRI → единая схема: 15 count-кейсов аудитории (T9)",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    plan_p = sub.add_parser("plan", help="выбор последовательностей по dataset_summary.csv")
    plan_p.add_argument("--summary", type=Path, required=True, help=SUMMARY_NAME)
    plan_p.add_argument("--n-frames", type=int, default=DEFAULT_N_FRAMES)
    plan_p.add_argument("--max-per-seq", type=int, default=DEFAULT_MAX_PER_SEQ)
    plan_p.add_argument(
        "--parts",
        default=None,
        help="только эти zip-части релиза, напр. 1,2,3 (без фильтра — все)",
    )
    plan_p.add_argument(
        "--required",
        default=None,
        help="обязательное покрытие счётчиков, напр. 1,2,3 (по умолчанию 1-5)",
    )
    plan_p.add_argument("--out", type=Path, default=Path(SELECTION_NAME))
    build_p = sub.add_parser("build", help="cases.jsonl + PROVENANCE.md из selection + данных")
    build_p.add_argument(
        "--data-root",
        type=Path,
        default=_package_root() / "eval_data" / "aghri",
    )
    build_p.add_argument("--selection", type=Path, default=None)
    build_p.add_argument(
        "--out", type=Path, default=_package_root() / "eval_manifests" / "aghri_15.jsonl"
    )
    build_p.add_argument("--media-prefix", default=DEFAULT_MEDIA_PREFIX)
    args = parser.parse_args(argv)
    if args.command == "plan":
        from dataclasses import asdict

        parts = tuple(int(p) for p in args.parts.split(",") if p.strip()) if args.parts else None
        required = (
            tuple(int(c) for c in args.required.split(",") if c.strip())
            if args.required
            else REQUIRED_COUNTS
        )
        rows = load_summary_csv(args.summary)
        selected, extra = select_sequences(
            rows,
            args.n_frames,
            args.max_per_seq,
            parts=parts,
            required_counts=required,
        )
        report = extra["report"]
        payload = {
            "schema": SELECTION_SCHEMA,
            "generated_by": "guide_robot_llm/eval/adapters/aghri.py plan (T9)",
            "summary_file": str(args.summary),
            "summary_sha256": hashlib.sha256(args.summary.read_bytes()).hexdigest(),
            "n_frames": args.n_frames,
            "max_frames_per_seq": args.max_per_seq,
            "parts": sorted(parts) if parts is not None else None,
            "required_counts": sorted(required),
            "selected": [asdict(item) for item in selected],
            "excluded": extra["excluded"],
            "report": report,
        }
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(
            f"selection: {args.out} — {len(selected)} последовательностей, "
            f"{report['n_frames_selected']} кадров"
        )
        for note in report["notes"]:
            print(f"  note: {note}")
        for item in extra["excluded"]:
            print(f"  excluded: строка {item['row_no']} ({item['seq']}): " f"{item['reason']}")
        print()
        print(download_instructions(report["archives"]))
        return 0
    cases, report = build_aghri_cases(
        args.data_root, args.selection, media_prefix=args.media_prefix
    )
    sidecar = write_manifest(cases, report, args.out)
    provenance = args.data_root / "PROVENANCE.md"
    provenance.write_text(provenance_text(cases, report) + "\n", encoding="utf-8")
    print(
        f"cases: {args.out} ({len(cases)}); sidecar-отчёт: {sidecar}; " f"provenance: {provenance}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
