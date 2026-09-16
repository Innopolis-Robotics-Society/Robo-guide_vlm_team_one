"""Скоринг и диагностический отчёт раннера (Taiga #10, план T4).

Вход -- run-директория раннера: `run_manifest.json` + `cases/<id>/meta.json`
(снапшот кейса + фазы) + `parsed_*.json`. Выход -- `score.json` (вердикты
на кейс + агрегаты) и `report.md`; поле `pass` в `run_manifest.json`
заполняется тем же проходом.

Перцепция и политика -- РАЗНЫЕ метрические группы (дизайн:
`docs/eval_harness_design.md`, "Scoring and report"): перцепция -- фаза
наблюдения (evidence, бокс, кандидаты, число людей), политика -- выбор
цели/инструмента и отказ (abstention). Правильный счёт при неверном
действии -- проблема политики, и отчёт обязан позволять ревьюеру их
различать.

Диагностика только: нет финальной проектной оценки и нет выбора для #11.
`STATEMENT` присутствует в каждом отчёте.

Freeform-ответ → id цели (кандидатная таблица): точное совпадение после
нормализации через `slices.answer_map` (lowercase, схлоп пробелов,
отброс начального "the ") либо прямой ответ id-ом кандидата.

Промпт-варианты (Taiga #16, P6): отдельная метрическая группа engaged
(человек, смотрящих в камеру): MAE + exact по кейсам с
`gold.engaged_count`; предсказание -- `extract_engaged_freeform` из
freeform-ответа (в грамматике deployed-наблюдения поля engaged нет --
такие кейсы исключаются из метрик, а не заполняются нулями; то же для
кейсов без gold и без извлекаемого сигнала). В отчёте -- per-variant-
группы (id из meta раннера, без варианта -- `(no variant)`): pass,
count/engaged MAE+exact, pointing, сцены (записаны, не судимы),
calls-per-case (loop -- meta `calls_per_case`, иначе сумма `calls` по
фазам: single = 1, cot_2pass = 2) и задержка.

Модуль чистый Python (без `rclpy`), юнит-тесты -- фикстуры без сети.

Bootstrap 95% CI (дизайн: "Bootstrap 95% confidence intervals grouped by
recording session"): единица ресэмплинга -- `split_group_id` (сессия
записи), headline-метрики (counts MAE/exact, pointing top-1, tool exact,
no-target FPR, pass-rate); секция в отчёте + строки скоупа `ci` в
`summary.csv`; `None` при <2 группах (детерминировано при зафиксированном
seed).
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import random
import re
import struct
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from guide_robot_llm.eval.runner import extract_count_freeform, extract_engaged_freeform
from guide_robot_llm.eval.schema import Case, CaseError, case_from_dict

# Gold-цель «нет цели / неоднозначно» для deployed-трека (в freeform
# no-target выражается gold-ом `unanswerable`). Служебный id никогда не
# встречается в кандидатах реальных источников.
NO_TARGET_ID = "unknown"
# Обязательное заявление отчёта (режим диагностики, #10).
STATEMENT = "Diagnostic only — no final project score, no #11 selection."


def box_iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    """IoU двух нормированных боксов [x0, y0, x1, y1]; вырожденный/пустой → 0.0."""
    inter_w = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    inter_h = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = inter_w * inter_h
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    union = area_a + area_b - inter
    if union <= 0:
        return 0.0
    return inter / union


def image_size(path: Path) -> tuple[int, int] | None:
    """(width, height) из PNG IHDR / JPEG SOF, чистый Python (без PIL).

    `None` -- файла нет или формат не читается: в этом случае box IoU
    помечается `image_size_unknown` и не вычисляется, а не гадается.
    """
    try:
        # PNG IHDR лежит в первых 29 байтах; JPEG SOF0 может сидеть за
        # APP-сегментами -- читаем до 1 МБ и покрываем оба случая.
        with open(path, "rb") as fh:
            data = fh.read(1 << 20)
    except OSError:
        return None
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack(">II", data[16:24])
        return w, h
    if data[:2] != b"\xff\xd8":
        return None
    # JPEG: SOF0-маркер сканируем по цепочке сегментов до EOF/конца буфера.
    i = 2
    n = len(data)
    while i + 4 <= n:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        # SOF0..SOF15, кроме DHT(0xC4)/JPG(0xC8)/DAC(0xCC) -- не несут размеров.
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            if i + 9 > n:
                break
            h, w = struct.unpack(">HH", data[i + 5 : i + 9])
            return w, h
        if marker in (0x01, 0xD8) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        seglen = int.from_bytes(data[i + 2 : i + 4], "big")
        i += 2 + seglen
    return None


def _norm_answer(text: str) -> str:
    """Нормализация freeform-ответа для сопоставления с кандидатной таблицей."""
    t = " ".join(text.lower().split())
    if t.startswith("the "):
        t = t[4:]
    return t


def _case_calls(meta: dict[str, Any]) -> int | None:
    """Логических вызовов модели на кейс (P6).

    loop -- meta `calls_per_case` (K всего вызовов); иначе сумма `calls`
    по фазам (single = 1, cot_2pass = 2); старых/чужих meta без полей --
    `None`.
    """
    calls = meta.get("calls_per_case")
    if isinstance(calls, int) and not isinstance(calls, bool):
        return calls
    phase_calls = [
        phase.get("calls")
        for phase in (meta.get("phases") or {}).values()
        if isinstance(phase, dict) and isinstance(phase.get("calls"), int)
    ]
    return sum(phase_calls) if phase_calls else None


def _letter_option_phrase(prompt_text: str, letter: str) -> str | None:
    """Буква опции A–D → фраза опции из текста вопроса (MC-протокол).

    Строки EgoPoint-Bench Multiple_Choice требуют в вопросе буквальный ответ
    буквой ("Answer directly using the letters"), а `answer_map` держит
    фразы опций → без этого моста буквенные ответы структурно
    засчитываются бы как промахи.
    """
    if not (len(letter) == 1 and "A" <= letter <= "D"):
        return None
    # опция -- одна строка: захват до конца строки, без lookahead'ов,
    # иначе последняя опция (D) захватит хвост вопроса (инструкцию
    # "Answer directly using the letters..."), и фраза не совпадёт с таблицей
    match = re.search(rf"{re.escape(letter)}[.\)]\s+([^\n]+)", prompt_text)
    if match is None:
        return None
    return " ".join(match.group(1).split())


def _answer_to_id(answer: str, case: Case) -> str | None:
    """Freeform-ответ → id кандидата (`None` -- ответ не в таблице)."""
    if answer in case.candidates:
        return answer
    raw_map = case.slices.get("answer_map")
    if isinstance(raw_map, dict):
        norm = _norm_answer(answer)
        for key, cid in raw_map.items():
            if isinstance(cid, str) and _norm_answer(str(key)) == norm:
                return cid
        # MC-протокол: ответ буквой ("C") → фраза опции из вопроса → таблица.
        phrase = _letter_option_phrase(case.prompt.user_text, answer.strip().upper())
        if phrase is not None:
            norm_phrase = _norm_answer(phrase)
            for key, cid in raw_map.items():
                if isinstance(cid, str) and _norm_answer(str(key)) == norm_phrase:
                    return cid
    return None


def _read_parsed(path: Path) -> dict[str, Any] | None:
    """`parsed_<phase>.json` → dict; отсутствующий/failed-файл → `None`."""
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict) or data.get("parse_status") == "failed":
        return None
    return data


def _resolve_media(case: Case, run_dir: Path | None, data_root: Path | None) -> Path | None:
    """Путь медиафайла: сначала рядом с run-директорией, потом под `data_root`."""
    for root in (run_dir, data_root):
        if root is not None:
            candidate = root / case.media.path
            if candidate.is_file():
                return candidate
    return None


def _pointing_box_iou(
    case: Case, obs: dict[str, Any], run_dir: Path | None, data_root: Path | None
) -> tuple[float | None, str | None]:
    """IoU gold-бокса (px) и наблюдаемого нормированного бокса.

    Возврат `(iou, reason)`: `reason` не `None` → не вычислен. Пересчёт
    px→доли требует размера кадра (читается из файла); размера нет --
    честно `image_size_unknown`, а не оценка.
    """
    gold_box = case.gold.get("box_px")
    if gold_box is None:
        return None, "gold_box_null"
    obs_box = obs.get("pointing_box")
    if obs_box is None:
        return None, "no_observation_box"
    size = None
    media = _resolve_media(case, run_dir, data_root)
    if media is not None:
        size = image_size(media)
    if size is None:
        return None, "image_size_unknown"
    w, h = size
    gold_norm = (gold_box[0] / w, gold_box[1] / h, gold_box[2] / w, gold_box[3] / h)
    return round(box_iou(gold_norm, tuple(obs_box)), 4), None


def score_case(
    case: Case,
    case_dir: Path,
    *,
    run_dir: Path | None = None,
    data_root: Path | None = None,
) -> dict[str, Any]:
    """Вердикт кейса: метрические группы `perception`/`policy` + `pass`.

    `pass` -- `None` (не судим): фаза не выполнялась, её парсинг сломан
    (`parse_failed`/`backend_error`) или трек записывается без вердикта
    (scene: claims/unanswerable -- записываем как есть). Пустые/отказные
    предсказания метрикам не крашат: отсутствующее поле просто не входит
    в агрегаты (AC #10: "no metric crashes on empty or abstained predictions").
    """
    gold = case.gold
    gtype = gold.get("type")
    meta: dict[str, Any] = {}
    meta_path = case_dir / "meta.json"
    if meta_path.is_file():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    # Эффективный режим: `meta.prompt_mode` пишет раннер (вариант может
    # переопределить кейсовый режим, а снапшот `case` сохраняет режим
    # манифеста). Без meta -- снапшот (старые run-директории).
    mode = meta.get("prompt_mode") or case.prompt.mode
    obs = _read_parsed(case_dir / "parsed_observation.json")
    act = _read_parsed(case_dir / "parsed_action.json")
    ff = _read_parsed(case_dir / "parsed_freeform.json")
    result: dict[str, Any] = {
        "case_id": case.case_id,
        "source": case.source,
        "track": case.track,
        "prompt_mode": mode,
        "variant_id": meta.get("variant_id"),
        "split_group_id": case.split_group_id,
        "slices": dict(case.slices),
        "status": meta.get("status", "ok"),
        "kind": None,
        "perception": {},
        "policy": {},
        "pass": None,
        "calls": _case_calls(meta),
        "latency_ms": meta.get("latency_ms"),
    }

    if gtype == "target_box":
        no_target = gold.get("target_id") == NO_TARGET_ID
        if mode == "deployed":
            result["kind"] = "pointing-no-target" if no_target else "pointing-target-deployed"
            if obs is not None:
                evidence = obs.get("pointing_evidence")
                candidates = list(obs.get("exhibit_candidates") or ())
                if no_target:
                    answered = bool(candidates) or evidence == "yes"
                    result["policy"]["answered"] = answered
                    result["policy"]["false_positive"] = answered
                    result["policy"]["abstention_credit"] = not answered
                    result["pass"] = not answered
                else:
                    target = gold["target_id"]
                    in_candidates = target in candidates
                    result["perception"]["evidence_correct"] = evidence == "yes"
                    result["perception"]["target_in_candidates"] = in_candidates
                    result["perception"]["top2_hit"] = target in candidates[:2]
                    result["perception"]["n_candidates"] = len(candidates)
                    iou, reason = _pointing_box_iou(case, obs, run_dir, data_root)
                    result["perception"]["box_iou"] = iou
                    if reason is not None:
                        result["perception"]["box_iou_skipped"] = reason
                    result["pass"] = in_candidates
        else:  # freeform (авторский QA-протокол)
            result["kind"] = "pointing-no-target" if no_target else "pointing-target-freeform"
            if ff is not None:
                if no_target:
                    credit = ff.get("abstain") is True
                    result["policy"]["false_positive"] = not credit
                    result["policy"]["abstention_credit"] = credit
                    result["pass"] = credit
                else:
                    answer = ff.get("answer", "")
                    mapped = _answer_to_id(answer, case)
                    result["policy"]["answer"] = answer
                    result["policy"]["mapped_target_id"] = mapped
                    result["policy"]["top1_correct"] = mapped == gold["target_id"]
                    result["pass"] = bool(result["policy"]["top1_correct"])
    elif gtype == "count":
        result["kind"] = "audience-count"
        if obs is not None:
            pred = obs.get("people_count")
            gold_n = gold.get("count")
            result["perception"]["count_pred"] = pred
            result["perception"]["count_gold"] = gold_n
            result["perception"]["count_exact"] = pred == gold_n
            result["perception"]["abs_error"] = abs(pred - gold_n)
            result["pass"] = bool(result["perception"]["count_exact"])
        elif ff is not None:
            # Freeform-подсчёт (матричный A-слайс bench_50): число людей из
            # текста ответа. Неизвлекаемое (отказ) -- кейс остаётся unjudged.
            answer = ff.get("answer")
            if isinstance(answer, str):
                pred = extract_count_freeform(answer)
                gold_n = gold.get("count")
                result["perception"]["count_pred"] = pred
                result["perception"]["count_gold"] = gold_n
                result["perception"]["count_pred_source"] = "freeform"
                if pred is not None:
                    result["perception"]["count_exact"] = pred == gold_n
                    result["perception"]["abs_error"] = abs(pred - gold_n)
                    result["pass"] = bool(pred == gold_n)
        # Engaged (P6): только кейсы с gold.engaged_count. Предсказание --
        # text-парсер freeform-ответа (один на loop-стоп и скоринг); в
        # deployed-грамматике поля нет (ff -- None) → предсказание None,
        # кейс исключается из engaged-метрик, а не заполняется нулями.
        engaged_gold = gold.get("engaged_count")
        if engaged_gold is not None:
            engaged_pred = None
            if ff is not None:
                answer = ff.get("answer")
                if isinstance(answer, str):
                    engaged_pred = extract_engaged_freeform(answer)
            result["perception"]["engaged_gold"] = engaged_gold
            result["perception"]["engaged_pred"] = engaged_pred
            if engaged_pred is not None:
                result["perception"]["engaged_exact"] = engaged_pred == engaged_gold
                result["perception"]["engaged_abs_error"] = abs(engaged_pred - engaged_gold)
    elif gtype == "action":
        if gold.get("abstention_reason"):
            result["kind"] = "tool-abstention"
            if act is not None:
                credit = act.get("abstain") is True
                result["policy"]["tool"] = act.get("tool")
                result["policy"]["false_positive"] = not credit
                result["policy"]["abstention_credit"] = credit
                result["pass"] = credit
        else:
            result["kind"] = "tool-action"
            if act is not None:
                exact = act.get("tool") == gold.get("tool") and act.get("args") == gold.get("args")
                result["policy"]["tool"] = act.get("tool")
                result["policy"]["exact_match"] = bool(exact)
                result["policy"]["abstained"] = act.get("abstain") is True
                result["pass"] = bool(exact) and not result["policy"]["abstained"]
    elif gtype == "unanswerable":
        if mode == "freeform" and case.track == "pointing":
            # No-target кейс в авторском QA-протоколе: верный ответ -- отказ.
            result["kind"] = "pointing-no-target"
            if ff is not None:
                credit = ff.get("abstain") is True
                result["policy"]["false_positive"] = not credit
                result["policy"]["abstention_credit"] = credit
                result["pass"] = credit
        else:
            result["kind"] = "scene-recorded"
            result["recorded"] = {
                "gold_type": "unanswerable",
                "scene_facts": obs.get("scene_facts") if obs is not None else None,
            }
    else:  # claims (scene) -- записываем как есть, без вердикта
        result["kind"] = "scene-recorded"
        recorded: dict[str, Any] = {
            "gold_type": gtype,
            "scene_facts": obs.get("scene_facts") if obs is not None else None,
        }
        if gtype == "claims":
            recorded["claims"] = list(gold.get("claims") or ())
        result["recorded"] = recorded
    return result


def _mean(values: list[Any]) -> dict[str, Any] | None:
    """Среднее по непустым значениям; пустое/все-None → `None`."""
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return {"value": round(sum(vals) / len(vals), 4), "n": len(vals)}


def _put_metric(target: dict[str, Any], key: str, metric: dict[str, Any] | None) -> None:
    """В группу кладём только непустые метрики (нет данных ≠ ноль)."""
    if metric is not None:
        target[key] = metric


def _aggregate(per_case: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Агрегаты: `perception` и `policy` -- отдельными группами."""
    perception: dict[str, Any] = {"pointing": {}, "audience": {}}
    policy: dict[str, Any] = {"pointing": {}, "tool": {}}
    p_ev: list[Any] = []
    p_in: list[Any] = []
    p_top2: list[Any] = []
    p_iou: list[Any] = []
    p_iou_skipped = 0
    c_mae: list[Any] = []
    c_exact: list[Any] = []
    c_eng_mae: list[Any] = []
    c_eng_exact: list[Any] = []
    f_top1: list[Any] = []
    nt_fp: list[Any] = []
    nt_credit: list[Any] = []
    t_exact: list[Any] = []
    t_nt_fp: list[Any] = []
    t_nt_credit: list[Any] = []
    for r in per_case.values():
        kind = r["kind"]
        p, pol = r["perception"], r["policy"]
        if kind == "pointing-target-deployed":
            p_ev.append(p.get("evidence_correct"))
            p_in.append(p.get("target_in_candidates"))
            p_top2.append(p.get("top2_hit"))
            if "box_iou" in p:
                p_iou.append(p.get("box_iou"))
                if p.get("box_iou") is None:
                    p_iou_skipped += 1
        elif kind == "pointing-target-freeform":
            f_top1.append(pol.get("top1_correct"))
        elif kind == "pointing-no-target":
            nt_fp.append(pol.get("false_positive"))
            nt_credit.append(pol.get("abstention_credit"))
        elif kind == "audience-count":
            c_mae.append(p.get("abs_error"))
            c_exact.append(p.get("count_exact"))
            c_eng_mae.append(p.get("engaged_abs_error"))
            c_eng_exact.append(p.get("engaged_exact"))
        elif kind == "tool-action":
            t_exact.append(pol.get("exact_match"))
        elif kind == "tool-abstention":
            t_nt_fp.append(pol.get("false_positive"))
            t_nt_credit.append(pol.get("abstention_credit"))

    def put(target: dict[str, Any], key: str, metric: dict[str, Any] | None) -> None:
        if metric is not None:
            target[key] = metric

    put(perception["pointing"], "evidence_accuracy", _mean(p_ev))
    put(perception["pointing"], "target_in_candidates", _mean(p_in))
    put(perception["pointing"], "top2_recall", _mean(p_top2))
    put(perception["pointing"], "box_iou_mean", _mean(p_iou))
    if p_iou_skipped:
        perception["pointing"]["box_iou_not_computed"] = p_iou_skipped
    put(perception["audience"], "mae", _mean(c_mae))
    put(perception["audience"], "exact_accuracy", _mean(c_exact))
    put(perception["audience"], "engaged_mae", _mean(c_eng_mae))
    put(perception["audience"], "engaged_exact_accuracy", _mean(c_eng_exact))
    put(policy["pointing"], "top1_target_accuracy", _mean(f_top1))

    block = _no_target_block(len(nt_fp), nt_fp, nt_credit)
    if block is not None:
        policy["pointing"]["no_target"] = block
    put(policy["tool"], "exact_match_accuracy", _mean(t_exact))
    block = _no_target_block(len(t_nt_fp), t_nt_fp, t_nt_credit)
    if block is not None:
        policy["tool"]["no_target"] = block
    return {"perception": perception, "policy": policy}


# --- bootstrap 95% CI, сгруппированный по сессии записи -----------------------


def _ci_counts_mae(subset: list[dict[str, Any]]) -> tuple[float, int] | None:
    errs = [
        r["perception"].get("abs_error")
        for r in subset
        if r.get("kind") == "audience-count" and r["perception"].get("abs_error") is not None
    ]
    if not errs:
        return None
    return sum(errs) / len(errs), len(errs)


def _ci_counts_exact(subset: list[dict[str, Any]]) -> tuple[float, int] | None:
    xs = [
        r["perception"].get("count_exact")
        for r in subset
        if r.get("kind") == "audience-count" and r["perception"].get("count_exact") is not None
    ]
    if not xs:
        return None
    return sum(1 for x in xs if x) / len(xs), len(xs)


def _ci_engaged_mae(subset: list[dict[str, Any]]) -> tuple[float, int] | None:
    errs = [
        r["perception"].get("engaged_abs_error")
        for r in subset
        if r.get("kind") == "audience-count"
        and r["perception"].get("engaged_abs_error") is not None
    ]
    if not errs:
        return None
    return sum(errs) / len(errs), len(errs)


def _ci_engaged_exact(subset: list[dict[str, Any]]) -> tuple[float, int] | None:
    xs = [
        r["perception"].get("engaged_exact")
        for r in subset
        if r.get("kind") == "audience-count" and r["perception"].get("engaged_exact") is not None
    ]
    if not xs:
        return None
    return sum(1 for x in xs if x) / len(xs), len(xs)


def _ci_pointing_top1(subset: list[dict[str, Any]]) -> tuple[float, int] | None:
    xs = [
        r["policy"].get("top1_correct")
        for r in subset
        if r.get("kind") == "pointing-target-freeform"
        and r["policy"].get("top1_correct") is not None
    ]
    if not xs:
        return None
    return sum(1 for x in xs if x) / len(xs), len(xs)


def _ci_tool_exact(subset: list[dict[str, Any]]) -> tuple[float, int] | None:
    xs = [
        r["policy"].get("exact_match")
        for r in subset
        if r.get("kind") == "tool-action" and r["policy"].get("exact_match") is not None
    ]
    if not xs:
        return None
    return sum(1 for x in xs if x) / len(xs), len(xs)


def _ci_no_target_fpr(subset: list[dict[str, Any]]) -> tuple[float, int] | None:
    xs = [
        r["policy"].get("false_positive")
        for r in subset
        if r.get("kind") in ("pointing-no-target", "tool-abstention")
        and r["policy"].get("false_positive") is not None
    ]
    if not xs:
        return None
    return sum(1 for x in xs if x) / len(xs), len(xs)


def _ci_pass_rate(subset: list[dict[str, Any]]) -> tuple[float, int] | None:
    judged = [r["pass"] for r in subset if r.get("pass") is not None]
    if not judged:
        return None
    return sum(1 for p in judged if p) / len(judged), len(judged)


def _bootstrap_ci(
    per_case: dict[str, dict[str, Any]],
    n_resamples: int = 1000,
    seed: int = 0,
) -> dict[str, Any] | None:
    """Bootstrap-доверительные интервалы 95%, сгруппированные по сессии записи.

    Единица ресэмплинга -- `split_group_id` (сессия записи / фото), а не
    кейс: кейсы одной сессии коррелированы (те же люди, свет, камера),
    ресэмплинг по кейсам даёт зауженный интервал. Возврат `None`, если
    групп меньше двух (честный ответ, а не ложный интервал).

    Headline-метрики пересчитываются на каждом ресэмплe из per-case-строк:
    counts (MAE/exact), pointing top-1, tool exact, no-target FPR,
    pass-rate. Детерминировано при зафиксированном `seed`.
    """
    rows = [r for r in per_case.values() if r.get("split_group_id")]
    if not rows:
        return None
    groups: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        groups.setdefault(r["split_group_id"], []).append(r)
    if len(groups) < 2:
        return None
    excluded = len(per_case) - len(rows)

    rng = random.Random(seed)
    keys = list(groups)

    def resample(
        extract: Callable[[list[dict[str, Any]]], tuple[float, int] | None],
    ) -> tuple[float, float] | None:
        stats: list[float] = []
        for _ in range(n_resamples):
            subset: list[dict[str, Any]] = []
            for key in rng.choices(keys, k=len(keys)):
                subset.extend(groups[key])
            got = extract(subset)
            if got is not None:
                stats.append(got[0])
        if not stats:
            return None
        stats.sort()
        low = stats[min(len(stats) - 1, int(0.025 * len(stats)))]
        high = stats[min(len(stats) - 1, int(0.975 * len(stats)))]
        return round(low, 4), round(high, 4)

    metrics: dict[str, Any] = {}

    def add(
        family: str, name: str, extract: Callable[[list[dict[str, Any]]], tuple[float, int] | None]
    ) -> None:
        got = extract(rows)
        if got is None:
            return
        value, n = got
        band = resample(extract)
        if band is None:
            return
        entry = {"value": round(value, 4), "ci_low": band[0], "ci_high": band[1], "n": n}
        if family:
            metrics.setdefault(family, {})[name] = entry
        else:
            metrics[name] = entry

    add("counts", "mae", _ci_counts_mae)
    add("counts", "exact_accuracy", _ci_counts_exact)
    add("counts", "engaged_mae", _ci_engaged_mae)
    add("counts", "engaged_exact_accuracy", _ci_engaged_exact)
    add("policy", "pointing_top1_accuracy", _ci_pointing_top1)
    add("policy", "tool_exact_match_accuracy", _ci_tool_exact)
    add("policy", "no_target_false_positive_rate", _ci_no_target_fpr)
    add("", "pass_rate", _ci_pass_rate)
    if not metrics:
        return None
    return {
        "method": "bootstrap",
        "grouping": "split_group_id",
        "n_groups": len(groups),
        "n_cases": len(rows),
        "cases_excluded_no_group": excluded,
        "n_resamples": n_resamples,
        "seed": seed,
        "metrics": metrics,
    }


def _add_group(bucket: dict[str, dict[str, Any]], key: str, r: dict[str, Any]) -> None:
    group = bucket.setdefault(key, {"n": 0, "pass": 0, "fail": 0, "unjudged": 0, "_errs": []})
    group["n"] += 1
    if r["pass"] is True:
        group["pass"] += 1
    elif r["pass"] is False:
        group["fail"] += 1
    else:
        group["unjudged"] += 1
    err = r["perception"].get("abs_error")
    if err is not None:
        group["_errs"].append(err)
    judged = group["pass"] + group["fail"]
    if judged:
        group["pass_rate"] = {"value": round(group["pass"] / judged, 4), "n": judged}


def _no_target_block(n: int, fp: list[Any], credit: list[Any]) -> dict[str, Any] | None:
    """No-target-блок (FP-статистика + abstention credit); пустой → None."""
    if not n:
        return None
    block: dict[str, Any] = {"n": n}
    rate = _mean(fp)
    if rate is not None:
        block["false_positive_rate"] = rate
    credited = _mean(credit)
    if credited is not None:
        block["abstention_credit"] = credited
    return block


def _variant_groups(per_case: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Per-variant-группы (P6, Taiga #16) -- основа сравнения 18 вариантов.

    Группировка по `variant_id` из meta раннера; прогон без варианта --
    `(no variant)`. Метрики: pass, count MAE/exact, engaged MAE/exact,
    pointing (top-2, freeform top-1, no-target abstention), сцены
    (записаны, без вердикта), calls-per-case и задержка. Пустые группы
    не пишутся (нет данных ≠ ноль).
    """
    acc: dict[str, dict[str, Any]] = {}
    for r in per_case.values():
        name = r.get("variant_id") or "(no variant)"
        g = acc.setdefault(
            name,
            {
                "n": 0,
                "pass": 0,
                "fail": 0,
                "unjudged": 0,
                "scene_recorded": 0,
                "_count_errs": [],
                "_count_exact": [],
                "_eng_errs": [],
                "_eng_exact": [],
                "_top2": [],
                "_top1": [],
                "_fp": [],
                "_credit": [],
                "_calls": [],
                "_latency": [],
            },
        )
        g["n"] += 1
        if r["pass"] is True:
            g["pass"] += 1
        elif r["pass"] is False:
            g["fail"] += 1
        else:
            g["unjudged"] += 1
        if r["kind"] == "scene-recorded":
            g["scene_recorded"] += 1
        p, pol = r["perception"], r["policy"]
        g["_count_errs"].append(p.get("abs_error"))
        g["_count_exact"].append(p.get("count_exact"))
        g["_eng_errs"].append(p.get("engaged_abs_error"))
        g["_eng_exact"].append(p.get("engaged_exact"))
        g["_top2"].append(p.get("top2_hit"))
        g["_top1"].append(pol.get("top1_correct"))
        if r["kind"] == "pointing-no-target":
            g["_fp"].append(pol.get("false_positive"))
            g["_credit"].append(pol.get("abstention_credit"))
        g["_calls"].append(r.get("calls"))
        g["_latency"].append(r.get("latency_ms"))
    groups: dict[str, Any] = {}
    for name, g in acc.items():
        block: dict[str, Any] = {
            "n": g["n"],
            "pass": g["pass"],
            "fail": g["fail"],
            "unjudged": g["unjudged"],
            "scene_recorded": g["scene_recorded"],
        }
        judged = g["pass"] + g["fail"]
        if judged:
            block["pass_rate"] = {"value": round(g["pass"] / judged, 4), "n": judged}
        _put_metric(block, "count_mae", _mean(g["_count_errs"]))
        _put_metric(block, "count_exact_accuracy", _mean(g["_count_exact"]))
        _put_metric(block, "engaged_mae", _mean(g["_eng_errs"]))
        _put_metric(block, "engaged_exact_accuracy", _mean(g["_eng_exact"]))
        pointing: dict[str, Any] = {}
        _put_metric(pointing, "top2_recall", _mean(g["_top2"]))
        _put_metric(pointing, "top1_target_accuracy", _mean(g["_top1"]))
        nt = _no_target_block(len(g["_fp"]), g["_fp"], g["_credit"])
        if nt is not None:
            pointing["no_target"] = nt
        if pointing:
            block["pointing"] = pointing
        _put_metric(block, "calls_per_case", _mean(g["_calls"]))
        _put_metric(block, "latency_ms", _mean(g["_latency"]))
        groups[name] = block
    return groups


def _slice_groups(per_case: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Срезы по `source`, `split_group_id` и каждому ключу `slices`."""
    groups: dict[str, Any] = {"by_source": {}, "by_split_group": {}, "by_metadata": {}}
    for r in per_case.values():
        _add_group(groups["by_source"], str(r.get("source") or "?"), r)
        _add_group(groups["by_split_group"], str(r.get("split_group_id") or r["case_id"]), r)
        for key, value in (r.get("slices") or {}).items():
            _add_group(groups["by_metadata"].setdefault(str(key), {}), str(value), r)
    flat_tables: list[dict[str, dict[str, Any]]] = [
        groups["by_source"],
        groups["by_split_group"],
        *groups["by_metadata"].values(),
    ]
    for table in flat_tables:
        for group in table.values():
            errs = group.pop("_errs", [])
            if errs:
                group["count_mae"] = {
                    "value": round(sum(errs) / len(errs), 4),
                    "n": len(errs),
                }
    return groups


def score_run(
    run_dir: str | Path,
    *,
    data_root: str | Path | None = None,
    n_resamples: int = 1000,
    bootstrap_seed: int = 0,
    bootstrap: bool = True,
) -> dict[str, Any]:
    """Run-директория → score-словарь (структура -- в `score.json`).

    Кейс без `meta.json`/снапшота не роняет прогон: он фиксируется в
    `errors` и не входит в судимые (AC #10). `bootstrap` -- 95% CI,
    сгруппированные по сессии записи (`split_group_id`); `None` в `ci`,
    если групп меньше двух.
    """
    run = Path(run_dir)
    lines = json.loads((run / "run_manifest.json").read_text(encoding="utf-8"))
    # Freeze-метаданные прогона (эндпоинт/модель/seed/манифест) -- если
    # раннер их записал (`run_config.json`); старые run-директории без них
    # не роняются (Taiga #10, AC «freeze metadata»).
    run_config: dict[str, Any] | None = None
    try:
        run_config = json.loads((run / "run_config.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        run_config = None
    root = Path(data_root) if data_root is not None else None
    per_case: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for line in lines:
        case_id = line["case_id"]
        case_dir = run / "cases" / case_id
        try:
            meta = json.loads((case_dir / "meta.json").read_text(encoding="utf-8"))
            case = case_from_dict(meta["case"])
        except (OSError, json.JSONDecodeError, CaseError, KeyError, TypeError) as error:
            errors.append(f"{case_id}: meta/case snapshot unreadable ({error})")
            per_case[case_id] = {
                "case_id": case_id,
                "source": line.get("source"),
                "track": line.get("track"),
                "prompt_mode": None,
                "variant_id": line.get("variant"),
                "split_group_id": None,
                "slices": {},
                "status": line.get("status"),
                "kind": None,
                "perception": {},
                "policy": {},
                "pass": None,
                "calls": line.get("calls_per_case"),
                "latency_ms": line.get("latency_ms"),
            }
            continue
        per_case[case_id] = score_case(case, case_dir, run_dir=run, data_root=root)
    status_counts = {"ok": 0, "parse_failed": 0, "backend_error": 0}
    pass_counts = {"pass": 0, "fail": 0, "unjudged": 0}
    for result in per_case.values():
        if result["status"] in status_counts:
            status_counts[result["status"]] += 1
        if result["pass"] is True:
            pass_counts["pass"] += 1
        elif result["pass"] is False:
            pass_counts["fail"] += 1
        else:
            pass_counts["unjudged"] += 1
    return {
        "statement": STATEMENT,
        "run_dir": str(run),
        "generated": datetime.now().astimezone().isoformat(timespec="seconds"),
        "n_cases": len(per_case),
        "status_counts": status_counts,
        "pass_counts": pass_counts,
        "run_config": run_config,
        "per_case": per_case,
        "metrics": _aggregate(per_case),
        "variants": _variant_groups(per_case),
        "slices": _slice_groups(per_case),
        "ci": _bootstrap_ci(per_case, n_resamples, bootstrap_seed) if bootstrap else None,
        "errors": errors,
    }


_MARK = {"true": "✓", "false": "✗", "none": "–"}


def _bool_mark(value: Any) -> str:
    if value is True:
        return "✓"
    if value is False:
        return "✗"
    return "–"


def _perception_summary(r: dict[str, Any]) -> str:
    p = r["perception"]
    parts: list[str] = []
    if "evidence_correct" in p:
        parts.append(f"evidence {_bool_mark(p['evidence_correct'])}")
    if "target_in_candidates" in p:
        parts.append(f"target {_bool_mark(p['target_in_candidates'])}")
    if "top2_hit" in p:
        parts.append(f"top2 {_bool_mark(p['top2_hit'])}")
    if "box_iou" in p:
        if p["box_iou"] is not None:
            parts.append(f"iou {p['box_iou']}")
        else:
            parts.append(f"iou – ({p.get('box_iou_skipped', '?')})")
    if "count_pred" in p:
        parts.append(f"count {p['count_pred']}/{p['count_gold']}")
    if "engaged_pred" in p:
        parts.append(f"engaged {p['engaged_pred']}/{p['engaged_gold']}")
    return ", ".join(parts) if parts else "–"


def _policy_summary(r: dict[str, Any]) -> str:
    pol = r["policy"]
    parts: list[str] = []
    if "top1_correct" in pol:
        parts.append(f"top1 {_bool_mark(pol['top1_correct'])}")
    if pol.get("mapped_target_id") is not None:
        parts.append(f"mapped {pol['mapped_target_id']}")
    if "false_positive" in pol:
        parts.append(f"fp {_bool_mark(pol['false_positive'])}")
    if "abstention_credit" in pol:
        parts.append(f"credit {_bool_mark(pol['abstention_credit'])}")
    if "exact_match" in pol:
        parts.append(f"{pol.get('tool', '?')} {_bool_mark(pol['exact_match'])}")
    if pol.get("abstained"):
        parts.append("abstained")
    if "tool" in pol and "exact_match" not in pol and "abstention_credit" not in pol:
        parts.append(f"tool {pol['tool']}")
    return ", ".join(parts) if parts else "–"


def _fmt_metric(value: Any) -> str:
    if isinstance(value, dict) and "value" in value:
        v = value["value"]
        return f"{v} (n={value['n']})" if v is not None else "– (n=0)"
    if value is None:
        return "–"
    return str(value)


def _metric_table(
    title: str, metrics: dict[str, Any], rows: tuple[tuple[str, str], ...]
) -> list[str]:
    out = [f"### {title}", ""]
    if not metrics:
        out.append("_нет данных (нет судимых кейсов трека)_")
        out.append("")
        return out
    out.append("| metric | value |")
    out.append("|---|---|")
    for key, label in rows:
        if key in metrics:
            out.append(f"| {label} | {_fmt_metric(metrics[key])} |")
    if "no_target" in metrics:
        block = metrics["no_target"]
        has_fp = "false_positive_rate" in block
        fp = _fmt_metric(block.get("false_positive_rate")) if has_fp else "–"
        has_credit = "abstention_credit" in block
        credit = _fmt_metric(block.get("abstention_credit")) if has_credit else "–"
        out.append(f"| false positive (no-target) | {fp} |")
        out.append(f"| abstention credit (no-target) | {credit} |")
    if "box_iou_not_computed" in metrics:
        out.append(f"| box IoU not computed | {metrics['box_iou_not_computed']} |")
    out.append("")
    return out


_POINTING_PERCEPTION_ROWS: tuple[tuple[str, str], ...] = (
    ("evidence_accuracy", "pointing evidence accuracy"),
    ("target_in_candidates", "target in candidates (exact ID)"),
    ("top2_recall", "top-2 recall"),
    ("box_iou_mean", "pointing box IoU (mean)"),
)
_AUDIENCE_ROWS: tuple[tuple[str, str], ...] = (
    ("mae", "people count MAE"),
    ("exact_accuracy", "exact-count accuracy"),
    ("engaged_mae", "engaged count MAE (facing camera)"),
    ("engaged_exact_accuracy", "exact engaged-count accuracy"),
)
_POINTING_POLICY_ROWS: tuple[tuple[str, str], ...] = (
    ("top1_target_accuracy", "top-1 target (freeform answer)"),
)
_TOOL_ROWS: tuple[tuple[str, str], ...] = (("exact_match_accuracy", "{tool, args} exact match"),)


def _group_table(title: str, groups: dict[str, dict[str, Any]]) -> list[str]:
    out = [f"### {title}", ""]
    if not groups:
        out.append("_нет данных_")
        out.append("")
        return out
    out.append("| group | n | pass | fail | unjudged | pass rate | count MAE |")
    out.append("|---|---|---|---|---|---|---|")
    for name, g in groups.items():
        out.append(
            f"| {name} | {g['n']} | {g['pass']} | {g['fail']} | {g['unjudged']} "
            f"| {_fmt_metric(g.get('pass_rate'))} | {_fmt_metric(g.get('count_mae'))} |"
        )
    out.append("")
    return out


def _variant_block(vid: str, g: dict[str, Any]) -> list[str]:
    """Один per-variant-блок отчёта (P6): метрики по трекам + calls + задержка."""
    out = [f"### {vid}", ""]
    out.append("| metric | value |")
    out.append("|---|---|")
    out.append(
        f"| cases | {g['n']} (pass {g.get('pass', 0)}, fail {g.get('fail', 0)}, "
        f"unjudged {g.get('unjudged', 0)}) |"
    )
    if "pass_rate" in g:
        out.append(f"| pass rate | {_fmt_metric(g['pass_rate'])} |")
    out.append(f"| scene cases (recorded, not judged) | {g.get('scene_recorded', 0)} |")
    out.append(f"| count MAE | {_fmt_metric(g.get('count_mae'))} |")
    out.append(f"| exact count | {_fmt_metric(g.get('count_exact_accuracy'))} |")
    out.append(f"| engaged MAE | {_fmt_metric(g.get('engaged_mae'))} |")
    out.append(f"| exact engaged | {_fmt_metric(g.get('engaged_exact_accuracy'))} |")
    pointing = g.get("pointing") or {}
    out.append(f"| pointing top-2 | {_fmt_metric(pointing.get('top2_recall'))} |")
    out.append(
        f"| pointing top-1 (freeform) | {_fmt_metric(pointing.get('top1_target_accuracy'))} |"
    )
    if "no_target" in pointing:
        out.append(
            f"| pointing no-target false positive | "
            f"{_fmt_metric(pointing['no_target'].get('false_positive_rate'))} |"
        )
        out.append(
            f"| pointing no-target abstention credit | "
            f"{_fmt_metric(pointing['no_target'].get('abstention_credit'))} |"
        )
    out.append(f"| calls per case | {_fmt_metric(g.get('calls_per_case'))} |")
    out.append(f"| latency (ms) | {_fmt_metric(g.get('latency_ms'))} |")
    out.append("")
    return out


def build_report(score: dict[str, Any], notes: str | None = None) -> str:
    """Markdown-отчёт: перцепция и политика -- РАЗДЕЛЬНЫЕ секции.

    Обязательное заявление `STATEMENT` -- всегда в шапке. `notes` -- текстовые
    пометки прогона (состав/исключения срезов, T10) -- сразу после заявления.
    Per-variant-секция (P6, Taiga #16) -- после срезов, перед ошибками.
    """
    lines: list[str] = []
    add = lines.append
    add(f"# VLM eval diagnostic report — {Path(score['run_dir']).name}")
    add("")
    add(f"- Run: `{score['run_dir']}`")
    add(f"- Generated: {score['generated']}")
    sc = score["status_counts"]
    add(
        f"- Cases: {score['n_cases']} (ok {sc['ok']}, parse_failed {sc['parse_failed']}, "
        f"backend_error {sc['backend_error']})"
    )
    pc = score["pass_counts"]
    judged = pc["pass"] + pc["fail"]
    add(f"- Judged: {judged} (pass {pc['pass']}, fail {pc['fail']}, unjudged {pc['unjudged']})")
    freeze_added = False
    for line in _freeze_header_lines(score.get("run_config")):
        add(line)
        freeze_added = True
    if freeze_added:
        add("")
    add(f"> **{STATEMENT}**")
    add("")
    if notes:
        add("## Run notes")
        add("")
        lines.extend(notes.rstrip().splitlines())
        add("")
    add("## Perception")
    add("")
    perception = score["metrics"]["perception"]
    policy = score["metrics"]["policy"]
    lines.extend(
        _metric_table("Pointing", perception.get("pointing", {}), _POINTING_PERCEPTION_ROWS)
    )
    lines.extend(_metric_table("Audience", perception.get("audience", {}), _AUDIENCE_ROWS))
    add("## Policy")
    add("")
    lines.extend(_metric_table("Pointing", policy.get("pointing", {}), _POINTING_POLICY_ROWS))
    lines.extend(_metric_table("Tool", policy.get("tool", {}), _TOOL_ROWS))
    ci = score.get("ci")
    if ci:
        add("## Confidence intervals (session-grouped bootstrap)")
        add("")
        excluded = ci["cases_excluded_no_group"]
        tail = f"; исключено без группы: {excluded}" if excluded else ""
        add(
            f"Единица ресэмплинга -- сессия записи (`{ci['grouping']}`), не кейс: "
            f"кейсы одной сессии коррелированы. {ci['n_resamples']} ресэмплов, "
            f"seed {ci['seed']}, групп {ci['n_groups']}, кейсов {ci['n_cases']}{tail}."
        )
        add("")
        add("| metric | value | 95% CI | n |")
        add("|---|---|---|---|")
        for family, block in ci["metrics"].items():
            if "value" in block:
                items = [(family, block)]
            else:
                items = [(f"{family}: {name}", m) for name, m in block.items()]
            for label, m in items:
                add(
                    f"| {label} | {m['value']:.4f} "
                    f"| [{m['ci_low']:.4f}, {m['ci_high']:.4f}] | {m['n']} |"
                )
        add("")
    add("## Slices")
    add("")
    slices = score["slices"]
    lines.extend(_group_table("By source", slices.get("by_source", {})))
    lines.extend(_group_table("By split group", slices.get("by_split_group", {})))
    for key, table in slices.get("by_metadata", {}).items():
        lines.extend(_group_table(f"Metadata: {key}", table))
    add("## Variants")
    add("")
    variants = score.get("variants") or {}
    if not variants:
        add("_нет данных_")
        add("")
    for vid, g in variants.items():
        lines.extend(_variant_block(vid, g))
    if score.get("errors"):
        add("## Errors")
        add("")
        for error in score["errors"]:
            add(f"- {error}")
        add("")
    add("## Per-case")
    add("")
    add("| case | source | track | mode | status | perception | policy | pass |")
    add("|---|---|---|---|---|---|---|---|")
    for r in score["per_case"].values():
        mode = r.get("prompt_mode") or "–"
        add(
            f"| {r['case_id']} | {r.get('source') or '–'} | {r.get('track') or '–'} | {mode} "
            f"| {r.get('status') or '–'} | {_perception_summary(r)} | {_policy_summary(r)} "
            f"| {_MARK[str(r['pass']).lower()]} |"
        )
    add("")
    return "\n".join(lines)


def _freeze_header_lines(run_config: dict[str, Any] | None) -> list[str]:
    """Шапка отчёта: что заморожено прогоном (эндпоинт/модель/seed/манифест)."""
    if not run_config:
        return []
    lines: list[str] = []
    backend = run_config.get("backend") or {}
    if backend.get("kind") == "http":
        model = f" · model `{backend['model_name']}`" if backend.get("model_name") else ""
        seed = f" · seed `{backend['seed']}`" if "seed" in backend else ""
        lines.append(f"- Backend: `{backend.get('base_url', '?')}`{model}{seed}")
    elif backend.get("kind") == "mock":
        digest = str(backend.get("canned_sha256") or "?")
        lines.append(f"- Backend: mock (canned {digest[:12]}…)")
    manifest = run_config.get("manifest") or {}
    if manifest.get("sha256"):
        lines.append(
            f"- Manifest: `{manifest.get('path')}` (sha256 {str(manifest['sha256'])[:12]}…)"
        )
    prompt = run_config.get("prompt") or {}
    if prompt.get("variant_id"):
        lines.append(f"- Prompt variant: `{prompt['variant_id']}`")
    return lines


def _csv_cell(value: Any) -> str:
    return "" if value is None else str(value)


def _flat_metric_rows(
    scope: str, group: str, block: dict[str, Any], key_prefix: str = ""
) -> list[list[Any]]:
    """Блок метрик → плоские строки CSV: {value, n} / вложенные блоки / счётчики."""
    rows: list[list[Any]] = []
    for key, value in block.items():
        name = f"{key_prefix}{key}"
        if isinstance(value, dict) and "value" in value:
            rows.append([scope, group, name, _csv_cell(value.get("value")), value.get("n", "")])
        elif isinstance(value, dict):
            rows.extend(_flat_metric_rows(scope, group, value, f"{name}."))
        elif value is None:
            rows.append([scope, group, name, "", ""])
        else:
            rows.append([scope, group, name, _csv_cell(value), ""])
    return rows


def _summary_csv(score: dict[str, Any]) -> str:
    """`summary.csv`: плоский экспорт агрегатов (counts, метрики, срезы, варианты).

    Колонки: `scope, group, metric, value, n`. Скоупы: `counts`,
    `perception`/`policy` (group -- трек), `slice` (group --
    `source:…`/`split_group:…`/`metadata:ключ:значение`), `variant`.
    """
    rows: list[list[Any]] = [["scope", "group", "metric", "value", "n"]]
    rows.append(["counts", "", "n_cases", score["n_cases"], ""])
    for key, value in score["status_counts"].items():
        rows.append(["counts", "", f"status_{key}", value, ""])
    for key, value in score["pass_counts"].items():
        rows.append(["counts", "", key, value, ""])
    for section in ("perception", "policy"):
        for track, block in (score["metrics"].get(section) or {}).items():
            rows.extend(_flat_metric_rows(section, track, block))
    slices = score.get("slices") or {}
    for name, group in (slices.get("by_source") or {}).items():
        rows.extend(_flat_metric_rows("slice", f"source:{name}", group))
    for name, group in (slices.get("by_split_group") or {}).items():
        rows.extend(_flat_metric_rows("slice", f"split_group:{name}", group))
    for key, table in (slices.get("by_metadata") or {}).items():
        for name, group in table.items():
            rows.extend(_flat_metric_rows("slice", f"metadata:{key}:{name}", group))
    for vid, block in (score.get("variants") or {}).items():
        rows.extend(_flat_metric_rows("variant", vid, block))
    ci = score.get("ci")
    if ci:
        for key, value in (
            ("method", ci["method"]),
            ("grouping", ci["grouping"]),
            ("n_groups", ci["n_groups"]),
            ("n_cases", ci["n_cases"]),
            ("cases_excluded_no_group", ci["cases_excluded_no_group"]),
            ("n_resamples", ci["n_resamples"]),
            ("seed", ci["seed"]),
        ):
            rows.append(["ci", "meta", key, value, ""])
        for family, block in ci["metrics"].items():
            if "value" in block:
                for name, metric in ((family, block),):
                    rows.append(["ci", "", name, metric["value"], metric["n"]])
                    rows.append(["ci", "", f"{name}.ci_low", metric["ci_low"], ""])
                    rows.append(["ci", "", f"{name}.ci_high", metric["ci_high"], ""])
            else:
                for name, metric in block.items():
                    label = f"{family}.{name}"
                    rows.append(["ci", "", label, metric["value"], metric["n"]])
                    rows.append(["ci", "", f"{label}.ci_low", metric["ci_low"], ""])
                    rows.append(["ci", "", f"{label}.ci_high", metric["ci_high"], ""])
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerows(rows)
    return buf.getvalue()


def write_outputs(run_dir: Path, score: dict[str, Any], notes: str | None = None) -> None:
    """`score.json` + `report.md` + `results.jsonl` + `summary.csv` + заполнение `pass`.

    `results.jsonl` -- построчный экспорт per-episode результатов (одна JSON-
    строка на кейс, порядок как в `run_manifest.json`, `pass` уже заполнен);
    `summary.csv` -- плоская сводка агрегатов (Taiga #10, AC «JSONL and CSV
    summary export»).
    """
    (run_dir / "score.json").write_text(
        json.dumps(score, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (run_dir / "report.md").write_text(build_report(score, notes=notes), encoding="utf-8")
    (run_dir / "results.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in score["per_case"].values()),
        encoding="utf-8",
    )
    (run_dir / "summary.csv").write_text(_summary_csv(score), encoding="utf-8")
    manifest_path = run_dir / "run_manifest.json"
    lines = json.loads(manifest_path.read_text(encoding="utf-8"))
    for line in lines:
        result = score["per_case"].get(line["case_id"])
        if result is not None:
            line["pass"] = result["pass"]
    manifest_path.write_text(json.dumps(lines, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    """CLI: run-директория раннера → score.json + report.md."""
    parser = argparse.ArgumentParser(
        description="Скоринг и диагностический отчёт прогона оценки VLM (Taiga #10)"
    )
    parser.add_argument("--run-dir", required=True, help="run-директория раннера")
    parser.add_argument("--data-root", default=None, help="корень путей медиа (для box IoU)")
    parser.add_argument(
        "--notes-file",
        default=None,
        help="markdown-пометки прогона (состав, исключения срезов) -- секция 'Run notes'",
    )
    parser.add_argument(
        "--n-resamples",
        type=int,
        default=1000,
        help="bootstrap CI: число ресэмплов (по умолчанию 1000)",
    )
    parser.add_argument(
        "--bootstrap-seed",
        type=int,
        default=0,
        help="bootstrap CI: seed ГСЧ (детерминизм, по умолчанию 0)",
    )
    parser.add_argument(
        "--no-bootstrap",
        action="store_true",
        help="не вычислять bootstrap CI по сессиям записи",
    )
    args = parser.parse_args(argv)
    if args.n_resamples < 1:
        parser.error("--n-resamples должен быть >= 1 (для отключения -- --no-bootstrap)")
    run_dir = Path(args.run_dir)
    score = score_run(
        run_dir,
        data_root=args.data_root,
        n_resamples=args.n_resamples,
        bootstrap_seed=args.bootstrap_seed,
        bootstrap=not args.no_bootstrap,
    )
    notes = Path(args.notes_file).read_text(encoding="utf-8") if args.notes_file else None
    write_outputs(run_dir, score, notes=notes)
    pc = score["pass_counts"]
    print(
        f"кейсов: {score['n_cases']}; pass {pc['pass']}, fail {pc['fail']}, "
        f"unjudged {pc['unjudged']}; отчёт: {run_dir / 'report.md'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
