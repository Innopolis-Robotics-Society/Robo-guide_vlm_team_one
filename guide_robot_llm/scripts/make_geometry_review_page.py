"""Страница-ревью виртуальной геометрии (V2.3).

OpenSpec: `add-pointing-virtual-replay` (дизайн D3). Собирает самодостаточный
HTML (одна страница, картинки встроены base64): все 30 кейсов обоих
manifests, на каждой картинке нарисованы якоря A--D, золотая область,
тексты опций, позиции (x, y) и clamped-флаги. Для human review:
подтвердить геометрию или пометить спорные кейсы.

Запуск:

    cd guide_robot_llm && python3 scripts/make_geometry_review_page.py
"""

from __future__ import annotations

import base64
import html
import json
import sys
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG_ROOT))

MANIFEST_DIR = PKG_ROOT / "eval_manifests"
IMAGE_ROOT = PKG_ROOT
OUT_PATH = MANIFEST_DIR / "geometry_review.html"

# Порядок букв для якорей: позиция в `candidates` манифеста == A, B, C, D.
LETTERS = "ABCD"


def _img_data_uri(path: Path) -> str:
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def _case_block(manifest: str, case: dict, entry: dict) -> str:
    question = html.escape(case["prompt"]["user_text"].split("\n")[0])
    candidates = case["candidates"]
    gold_id = case["gold"]["target_id"]
    clamped = [
        cid for cid, p in entry["positions"].items() if p["clamped"]
    ]
    badge = (
        f'<span class="badge clamped">clamped: '
        + ", ".join(html.escape(c) for c in clamped)
        + "</span>"
        if clamped
        else ""
    )
    same = len({(a["u"], a["v"]) for a in entry["anchors"].values()}) == 1
    same_note = (
        ' <span class="badge same">все якоря совпадают → '
        "ожидаемо `ambiguous` (unjudged)</span>"
        if same
        else ""
    )

    # SVG-оверлей в координатах [0, 100]².
    gold = entry["gold_region"]
    parts = [
        f'<rect x="{gold[0]*100:.2f}" y="{gold[1]*100:.2f}" '
        f'width="{(gold[2]-gold[0])*100:.2f}" height="{(gold[3]-gold[1])*100:.2f}" '
        'fill="none" stroke="#e11d48" stroke-width="1.2" '
        'vector-effect="non-scaling-stroke" />'
    ]
    for i, cid in enumerate(candidates):
        a = entry["anchors"][cid]
        is_gold = cid == gold_id
        color = "#16a34a" if is_gold else "#f59e0b"
        x, y = a["u"] * 100, a["v"] * 100
        parts.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="1.6" fill="{color}" '
            'stroke="white" stroke-width="0.5" vector-effect="non-scaling-stroke" />'
        )
        parts.append(
            f'<text x="{x:.2f}" y="{y - 2.5:.2f}" font-size="5" '
            f'fill="{color}" text-anchor="middle" '
            'font-weight="bold" paint-order="stroke" stroke="white" '
            f'stroke-width="1.2">{LETTERS[i]}</text>'
        )

    rows = []
    for i, cid in enumerate(candidates):
        a = entry["anchors"][cid]
        p = entry["positions"][cid]
        label = html.escape(
            case["slices"]["answer_map"][
                next(
                    k
                    for k, v in case["slices"]["answer_map"].items()
                    if v == cid
                )
            ]
        )
        flag = (
            ' <span class="badge clamped small">clamped</span>'
            if p["clamped"]
            else ""
        )
        gold_mark = " ⬅ gold" if cid == gold_id else ""
        rows.append(
            f"<tr><td>{LETTERS[i]}</td><td>{label}{gold_mark}</td>"
            f"<td class='mono'>{cid}</td>"
            f"<td class='mono'>({a['u']:.3f}, {a['v']:.3f})</td>"
            f"<td class='mono'>({p['x']:.2f}, {p['y']:.2f}) m</td>"
            f"<td>{flag}</td></tr>"
        )

    return f"""
<section class="case" id="{html.escape(case['case_id'])}">
  <h2>{html.escape(case['case_id'])}
    <span class="muted">· {html.escape(manifest)}</span>{badge}{same_note}
  </h2>
  <p class="q">{question}</p>
  <div class="imgwrap">
    <img src="{_img_data_uri(IMAGE_ROOT / case['media']['path'])}" alt="{html.escape(case['case_id'])}">
    <svg class="overlay" viewBox="0 0 100 100" preserveAspectRatio="none">{''.join(parts)}</svg>
  </div>
  <table>
    <tr><th></th><th>опция</th><th>id</th><th>якорь (u, v)</th><th>позиция (x, y)</th><th></th></tr>
    {''.join(rows)}
  </table>
</section>
"""


def main() -> None:
    sections = []
    status_map = {}
    for manifest in ("egopoint_15", "pointing_holdout_15"):
        doc = json.loads(
            (MANIFEST_DIR / f"{manifest}.geometry.json").read_text(encoding="utf-8")
        )
        status_map[manifest] = doc["provenance"]["review_status"]
        cases = [
            json.loads(line)
            for line in (MANIFEST_DIR / f"{manifest}.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        ]
        for case in cases:
            entry = doc["cases"][case["case_id"]]
            sections.append(_case_block(manifest, case, entry))
    cam = doc["camera"]
    status_note = (
        "подтверждено (confirmed)"
        if all(s == "confirmed" for s in status_map.values())
        else "ожидает human review (pending)"
    )
    page = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>Виртуальная геометрия pointing — review (30 кейсов)</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 0; background: #f8fafc; color: #0f172a; }}
  header {{ background: #0f172a; color: white; padding: 16px 24px; position: sticky; top: 0; z-index: 5; }}
  header h1 {{ margin: 0 0 4px; font-size: 20px; }}
  header .meta {{ font-size: 13px; color: #cbd5e1; }}
  .case {{ max-width: 1100px; margin: 24px auto; background: white; border: 1px solid #e2e8f0;
           border-radius: 10px; padding: 16px 20px; }}
  .case h2 {{ margin: 0 0 4px; font-size: 17px; }}
  .q {{ margin: 2px 0 10px; color: #334155; font-size: 14px; }}
  .muted {{ color: #94a3b8; font-size: 13px; font-weight: normal; }}
  .imgwrap {{ position: relative; max-width: 860px; }}
  .imgwrap img {{ width: 100%; display: block; border-radius: 6px; }}
  .overlay {{ position: absolute; inset: 0; width: 100%; height: 100%; }}
  table {{ border-collapse: collapse; font-size: 13px; margin-top: 10px; }}
  th, td {{ border: 1px solid #e2e8f0; padding: 4px 10px; text-align: left; }}
  th {{ background: #f1f5f9; }}
  .mono {{ font-family: ui-monospace, monospace; font-size: 12px; }}
  .badge {{ display: inline-block; border-radius: 999px; font-size: 11px; padding: 2px 8px;
            vertical-align: middle; margin-left: 6px; }}
  .clamped {{ background: #fef3c7; color: #92400e; }}
  .same {{ background: #e0e7ff; color: #3730a3; }}
  .small {{ font-size: 10px; }}
  .legend {{ font-size: 13px; color: #475569; }}
  .legend b.g {{ color: #16a34a; }} .legend b.o {{ color: #f59e0b; }}
</style>
</head>
<body>
<header>
  <h1>Виртуальная геометрия pointing — review</h1>
  <div class="meta">
    схема: pointing_virtual_geometry.v1 · камера: {cam['width_px']}×{cam['height_px']},
    HFOV {cam['hfov_deg']}°, VFOV {cam['vfov_deg']}°, z={cam['mount_z']} м,
    pitch {cam['pitch_deg']}° · d_max {doc['d_max_m']} м ·
    gold-область {doc['gold_region_fraction']*100:.0f}% меньшей стороны ·
    статус: {status_note}
    <br><span class="legend">
      <b class="g">●</b> gold-цель &nbsp; <b class="o">●</b> distractor &nbsp;
      <span style="color:#e11d48">▭</span> золотая область (для box_iou)
    </span>
  </div>
</header>
{''.join(sections)}
</body>
</html>
"""
    OUT_PATH.write_text(page, encoding="utf-8")
    n = len(sections)
    print(f"wrote {OUT_PATH} ({n} cases, {OUT_PATH.stat().st_size // 1024} KiB)")
    assert n == 30, f"ожидалось 30 кейсов, получено {n}"


if __name__ == "__main__":
    main()
