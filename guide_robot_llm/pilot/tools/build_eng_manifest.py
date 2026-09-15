#!/usr/bin/env python3
"""Сборка унифицированного audience_engagement-манифеста (Taiga #16, F1).

Читает ground truth ENG/SEQ-сцен из cc_scene_gen (pilot/fixtures/cc/),
пишет унифицированный манифест для eval-хarnessa:
  eval_manifests/audience_engagement.jsonl             -- кейсы
  eval_manifests/audience_engagement.jsonl.sidecar.json -- провиенс сборки

Почему не пилотный manifest.jsonl: пилот заморожен (15 эпизодов, check_cc.py,
adjudication); новые данные идут в унифицированную схему (источник "pilot-cc").

Кейсы:
  ENG-CC-001..004 -- статичные кадры: gold {count, engaged_count}, freeform-режим
  (ответ = оба числа: всего людей и готовых слушать);
  SEQ-CC-001..003 -- последовательности кадров (loop-вариант A3): медиа = f0,
  `slices.frames` -- полный порядок кадров (путь + sha256), gold = терминальный
  кадр (count/engaged_count), `slices.min_engaged` -- порог N контракта остановки.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parents[2]  # guide_robot_llm/
GT_DIR = PKG / "pilot" / "fixtures" / "cc"
OUT = PKG / "eval_manifests" / "audience_engagement.jsonl"
SIDECAR = OUT.with_suffix(".jsonl.sidecar.json")

USER_TEXT = ("Посчитай людей на кадре и определи, сколько из них готовы "
             "слушать дальше.")
MIN_ENGAGED = 2
LICENSE = ("self-generated synthetic (PIL, deterministic spec, seed 20260914); "
           "no real persons; no redistribution")
VERSION = "eng-manifest-v1 (2026-09-15, Taiga #16 F1)"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _visible_people(gt: dict) -> list[dict]:
    """Замороженное правило видимых людей (как в build_cc_manifest)."""
    return [p for p in gt.get("people", [])
            if p.get("counts_as_person") and p["visible_fraction"] >= 0.5]


def _counts(gt: dict) -> tuple[int, int]:
    ppl = _visible_people(gt)
    return len(ppl), sum(1 for p in ppl if p.get("facing_camera"))


def _media(scene_id: str) -> dict:
    rel = f"pilot/media/cc/{scene_id}.png"
    return {"path": rel, "sha256": _sha256(PKG / rel), "format": "png"}


def _case(case_id: str, scene_id: str, gold: dict, slices: dict) -> dict:
    return {
        "case_id": case_id,
        "source": "pilot-cc",
        "track": "audience",
        "split_group_id": f"g-eng-{case_id}",
        "media": _media(scene_id),
        "prompt": {"mode": "freeform", "user_text": USER_TEXT, "language": "ru"},
        "candidates": [],
        "allowed_tools": [],
        "gold": {"type": "count", **gold},
        "provenance": {
            "source": "pilot-cc",
            "license": LICENSE,
            "version": VERSION,
            "rights_note": "synthetic, no real persons (rights_ledger: n/a)",
        },
        "slices": slices,
    }


def _static_cases() -> list[dict]:
    cases = []
    for gt_file in sorted(GT_DIR.glob("ENG-*.json")):
        gt = json.loads(gt_file.read_text(encoding="utf-8"))
        n, e = _counts(gt)
        if gt.get("engaged_count") != e:
            raise SystemExit(
                f"{gt_file.name}: engaged_count={gt.get('engaged_count')} не "
                f"сходится с GT-людьми ({e}) -- перегенерируй сцены")
        cases.append(_case(
            case_id=gt_file.stem, scene_id=gt_file.stem,
            gold={"count": n, "engaged_count": e},
            slices={"venue": "synthetic (PIL, deterministic spec)",
                    "min_engaged": MIN_ENGAGED, "count_bucket": str(n)}))
    return cases


def _sequence_cases() -> list[dict]:
    seqs: dict[str, list[tuple[int, str]]] = {}
    for gt_file in sorted(GT_DIR.glob("SEQ-*_f*.json")):
        seq_id, _, frame = gt_file.stem.rpartition("_f")
        seqs.setdefault(seq_id, []).append((int(frame), gt_file.stem))
    cases = []
    for seq_id in sorted(seqs):
        frames = [sid for _, sid in sorted(seqs[seq_id])]
        first_gt = json.loads((GT_DIR / f"{frames[0]}.json").read_text(encoding="utf-8"))
        last_gt = json.loads((GT_DIR / f"{frames[-1]}.json").read_text(encoding="utf-8"))
        if first_gt.get("sequence_id") != seq_id or first_gt.get("frame_index") != 0:
            raise SystemExit(f"{seq_id}: первому кадру нужен frame_index=0")
        n, e = _counts(last_gt)
        if last_gt.get("engaged_count") != e:
            raise SystemExit(f"{frames[-1]}: engaged_count не сходится с GT-людьми")
        cases.append(_case(
            case_id=seq_id, scene_id=frames[0],
            gold={"count": n, "engaged_count": e},
            slices={
                "venue": "synthetic (PIL, deterministic spec)",
                "min_engaged": MIN_ENGAGED,
                "count_bucket": str(n),
                "sequence": seq_id,
                "n_frames": len(frames),
                # Порядок кадров для loop-варианта (A3): путь -- относительно
                # корня данных (package root), sha256 -- как у медиа кейса.
                "frames": [_media(sid) for sid in frames],
            }))
    return cases


def main() -> None:
    """Собирает eval_manifests/audience_engagement.jsonl (7 кейсов) + sidecar."""
    cases = _static_cases() + _sequence_cases()
    if len(cases) != 7:
        raise SystemExit(f"ожидается 7 кейсов (4 ENG + 3 SEQ), построено {len(cases)}")

    OUT.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in cases),
                   encoding="utf-8")
    SIDECAR.write_text(json.dumps({
        "source": "pilot-cc",
        "n_cases": len(cases),
        "gt_dir": "pilot/fixtures/cc (ENG-*/SEQ-*_f*.json)",
        "generator": "pilot/tools/cc_scene_gen.py (seed 20260914, deterministic)",
        "selection_rule": ("4 статичных ENG-кадра (count/engaged по GT-атрибуту "
                           "facing_camera) + 3 SEQ-последовательности (loop-контракт A3)"),
        "loop_contract": ("K_max=3 повторных вызова; 1 кадр = 1 тик; порог N="
                          "min_engaged; gold = терминальный кадр"),
        "selected": [{"case_id": c["case_id"], "count": c["gold"]["count"],
                      "engaged_count": c["gold"]["engaged_count"]} for c in cases],
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Самопроверка: схема + sha256 (первичное медиа и все кадры последовательностей).
    sys.path.insert(0, str(PKG))
    from guide_robot_llm.eval.schema import load_cases_from_jsonl  # noqa: PLC0415

    loaded = load_cases_from_jsonl(OUT)
    if len(loaded) != len(cases):
        raise SystemExit(f"round-trip: {len(loaded)} кейсов != {len(cases)}")
    for c in loaded:
        refs = [(c.media.path, c.media.sha256)]
        refs += [(f["path"], f["sha256"]) for f in c.slices.get("frames", [])]
        for path, expected in refs:
            if _sha256(PKG / path) != expected:
                raise SystemExit(f"{c.case_id}: sha256 {path} не сходится")
    print(f"audience_engagement manifest: {len(loaded)} cases -> "
          f"{OUT.relative_to(PKG)}")
    for c in loaded:
        print(f"  {c.case_id}: count={c.gold['count']} engaged="
              f"{c.gold['engaged_count']} frames={len(c.slices.get('frames', []))}")


if __name__ == "__main__":
    main()
