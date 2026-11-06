"""Авторинг виртуальной геометрии pointing-кейсов (V2.1/V2.2).

OpenSpec: `add-pointing-virtual-replay` (дизайн D3). Агент прочитал все 30
картинок, по тексту опций манифеста определил объекты-кандидаты и поставил
якоря (u, v) ∈ [0, 1]². Кейсы, где опции -- ответы/свойства одного объекта
(напр. «выше/ниже»), получают 4 одинаковых якоря на этом объекте: в
replay-резолюции это ожидаемо даёт `ambiguous` (нет уникального лидера) --
задокументированное поведение для таких кейсов EgoPoint.

Сайдкар пишется рядом с манифестом; каталог данных бенчмарка -- только
чтение (T1). Запуск:

    cd guide_robot_llm && python3 scripts/author_pointing_geometry.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG_ROOT))

from guide_robot_llm.eval.geometry import (  # noqa: E402
    PRODUCTION_CAMERA,
    build_case_geometry,
    write_geometry_sidecar,
)

MANIFEST_DIR = PKG_ROOT / "eval_manifests"
IMAGE_ROOT = PKG_ROOT

AUTHOR = "pi-agent (Claude)"
METHOD = (
    "agent-authored: each image read visually; anchors placed on the "
    "option objects per manifest answer_map text; same-object cases "
    "(answer options about one pointed item) get 4 coincident anchors"
)
DATE = "2026-11-06"

# case_id -> {candidate_id: (u, v)}. Якорь цели == gold-объект.
ANCHORS: dict[str, dict[str, tuple[float, float]]] = {
    # --- egopoint_15 ---
    # Витрина овощей: отдельные пакеты под опции A--D.
    "EPO-REAL-0003": {
        "epobj-3-a": (0.72, 0.75),  # чеснок -- белые головки справа
        "epobj-3-b": (0.56, 0.67),  # брюссельская капуста -- зелёные пакеты
        "epobj-3-c": (0.36, 0.64),  # красный лук -- пакет у пальца
        "epobj-3-d": (0.22, 0.64),  # редис -- розовые пакеты слева
    },
    # Повисной товар с изображением женщины в центре (gold: тепло от
    # жидкости) -- по review: палец на нём, не на термосах справа.
    "EPO-REAL-0008": {
        "epobj-8-a": (0.43, 0.53),
        "epobj-8-b": (0.43, 0.53),
        "epobj-8-c": (0.43, 0.53),
        "epobj-8-d": (0.43, 0.53),
    },
    # Коробки ликёра: оранжевая 海之蓝 (gold), жёлтые 红星, синие 梦之蓝,
    # золотые нижние.
    "EPO-REAL-0013": {
        "epobj-13-a": (0.45, 0.52),
        "epobj-13-b": (0.22, 0.55),
        "epobj-13-c": (0.72, 0.50),
        "epobj-13-d": (0.20, 0.88),
    },
    # Мясной отсек: тёмная курица (silkie, gold) в центре, бледные справа,
    # мясо в верхнем лотке, желтоватая птица в правом нижнем углу.
    "EPO-REAL-0027": {
        "epobj-27-a": (0.52, 0.44),
        "epobj-27-b": (0.72, 0.66),
        "epobj-27-c": (0.52, 0.64),
        "epobj-27-d": (0.82, 0.78),
    },
    # Знак «не для авто» ВЫШЕ знака 15 (gold: above).
    "EPO-REAL-0028": {
        "epobj-28-a": (0.49, 0.475),
        "epobj-28-b": (0.49, 0.475),
        "epobj-28-c": (0.49, 0.475),
        "epobj-28-d": (0.49, 0.475),
    },
    # Подсветка «быстрая стрижка» над дверью салона (gold: above doorway).
    "EPO-REAL-0036": {
        "epobj-36-a": (0.55, 0.35),
        "epobj-36-b": (0.55, 0.35),
        "epobj-36-c": (0.55, 0.35),
        "epobj-36-d": (0.55, 0.35),
    },
    # Стенд ухода за кожей (gold: skincare).
    "EPO-REAL-0069": {
        "epobj-69-a": (0.55, 0.75),
        "epobj-69-b": (0.55, 0.75),
        "epobj-69-c": (0.55, 0.75),
        "epobj-69-d": (0.55, 0.75),
    },
    # ТЦ: Nike слева, UNIQLO (gold) на здании, H&M/Adidas в далёком ряду.
    "EPO-REAL-0096": {
        "epobj-96-a": (0.13, 0.52),
        "epobj-96-b": (0.56, 0.31),
        "epobj-96-c": (0.78, 0.57),
        "epobj-96-d": (0.88, 0.57),
    },
    # Жёлтая упаковка продукта на нижней полке (gold: ingredient).
    "EPO-REAL-0099": {
        "epobj-99-a": (0.42, 0.68),
        "epobj-99-b": (0.42, 0.68),
        "epobj-99-c": (0.42, 0.68),
        "epobj-99-d": (0.42, 0.68),
    },
    # Прямоугольная белая бутылка в нижнем левом центре стола (gold:
    # on the desk) -- по review: не прозрачная с этикеткой.
    # Стеклянная бутылка с серой крышкой: выше синих салфеток, слева от
    # носового спрея, справа от чёрной банки (gold: on the desk).
    "EPO-REAL-0100": {
        "epobj-100-a": (0.41, 0.65),
        "epobj-100-b": (0.41, 0.65),
        "epobj-100-c": (0.41, 0.65),
        "epobj-100-d": (0.41, 0.65),
    },

    # Пачки чипсов: Lay's в среднем ряду, Orion (gold) -- красная пачка
    # на нижней полке (по review: чище читается, та же марка);
    # Pringles/Oishi не видны -- якоря в зоне той же полки.
    "EPO-REAL-0103": {
        "epobj-103-a": (0.19, 0.73),
        "epobj-103-b": (0.38, 0.82),
        "epobj-103-c": (0.50, 0.50),
        "epobj-103-d": (0.62, 0.62),
    },
    # Выкладка хлеба: gold (red bean) -- светлый тост справа (по review),
    # 高纤维全麦 в пакетиках справа, молоко слева, тёмный хлеб влево-центр.
    "EPO-REAL-0167": {
        "epobj-167-a": (0.55, 0.65),
        "epobj-167-b": (0.72, 0.64),
        "epobj-167-c": (0.06, 0.62),
        "epobj-167-d": (0.21, 0.65),
    },
    # Баночка с конфетами на столе (gold: no, не мышь).
    "EPO-REAL-0405": {
        "epobj-405-a": (0.50, 0.78),
        "epobj-405-b": (0.50, 0.78),
        "epobj-405-c": (0.50, 0.78),
        "epobj-405-d": (0.50, 0.78),
    },
    # Блокноты/бумага на полке (gold: нет электронных функций).
    "EPO-REAL-1204": {
        "epobj-1204-a": (0.55, 0.80),
        "epobj-1204-b": (0.55, 0.80),
        "epobj-1204-c": (0.55, 0.80),
        "epobj-1204-d": (0.55, 0.80),
    },
    # Отдел средств гигиены: тёмный металлический борт полки (gold),
    # жёлтые пакеты снизу, пластиковые контейнеры сверху, синие влажные
    # салфетки -- самый правый синий пакет в верхнем левом ряду (по review).
    "EPO-REAL-1270": {
        "epobj-1270-a": (0.70, 0.10),
        "epobj-1270-b": (0.45, 0.93),
        "epobj-1270-c": (0.50, 0.20),
        "epobj-1270-d": (0.42, 0.45),
    },
    # --- pointing_holdout_15 ---
    # Красная пачка в витрине (gold: red).
    "EPO-REAL-0004": {
        "epobj-4-a": (0.35, 0.78),
        "epobj-4-b": (0.35, 0.78),
        "epobj-4-c": (0.35, 0.78),
        "epobj-4-d": (0.35, 0.78),
    },
    # Пешеходный переход (gold: safe crossing).
    "EPO-REAL-0018": {
        "epobj-18-a": (0.45, 0.72),
        "epobj-18-b": (0.45, 0.72),
        "epobj-18-c": (0.45, 0.72),
        "epobj-18-d": (0.45, 0.72),
    },
    # Чёрный колокольчик на руле велосипеда, ближайшего к камере (с
    # красной тряпкой) -- по review: чёрный предмет на руле у руки.
    "EPO-REAL-0021": {
        "epobj-21-a": (0.57, 0.92),
        "epobj-21-b": (0.57, 0.92),
        "epobj-21-c": (0.57, 0.92),
        "epobj-21-d": (0.57, 0.92),
    },
    # Сухофрукты: 银耳 (tremella, gold) жёлтые пакеты, 腐竹 в центре,
    # 百合干 справа-центр, 黄花菜 (daylily) справа-низ.
    "EPO-REAL-0023": {
        "epobj-23-a": (0.45, 0.78),
        "epobj-23-b": (0.78, 0.80),
        "epobj-23-c": (0.72, 0.50),
        "epobj-23-d": (0.33, 0.72),
    },
    # Полка кухонной утвари: дуршлаг (gold) в центре, половник слева,
    # сковорода в левом верху, силиконовая лопатка справа.
    "EPO-REAL-0055": {
        "epobj-55-a": (0.53, 0.60),
        "epobj-55-b": (0.16, 0.65),
        "epobj-55-c": (0.22, 0.35),
        "epobj-55-d": (0.80, 0.50),
    },
    # Постамент под бюстом (gold: on a pedestal).
    "EPO-REAL-0061": {
        "epobj-61-a": (0.52, 0.78),
        "epobj-61-b": (0.52, 0.78),
        "epobj-61-c": (0.52, 0.78),
        "epobj-61-d": (0.52, 0.78),
    },
    # Стеклоперила ограждения у спуска (gold: safety).
    "EPO-REAL-0092": {
        "epobj-92-a": (0.47, 0.55),
        "epobj-92-b": (0.47, 0.55),
        "epobj-92-c": (0.47, 0.55),
        "epobj-92-d": (0.47, 0.55),
    },
    # Товар на нижней полке у руки (gold: outdoors).
    "EPO-REAL-0141": {
        "epobj-141-a": (0.33, 0.85),
        "epobj-141-b": (0.33, 0.85),
        "epobj-141-c": (0.33, 0.85),
        "epobj-141-d": (0.33, 0.85),
    },
    # Поилка «开水区» в коридоре (gold: boiling water).
    "EPO-REAL-0162": {
        "epobj-162-a": (0.25, 0.58),
        "epobj-162-b": (0.25, 0.58),
        "epobj-162-c": (0.25, 0.58),
        "epobj-162-d": (0.25, 0.58),
    },
    # Ж/д пути на зелёной территории (gold: park/green space).
    "EPO-REAL-0168": {
        "epobj-168-a": (0.50, 0.75),
        "epobj-168-b": (0.50, 0.75),
        "epobj-168-c": (0.50, 0.75),
        "epobj-168-d": (0.50, 0.75),
    },
    # Класс: стул слева, доска в левом верху, парта (gold) в центре,
    # стол у двери сзади.
    "EPO-REAL-0187": {
        "epobj-187-a": (0.37, 0.72),
        "epobj-187-b": (0.15, 0.25),
        "epobj-187-c": (0.55, 0.75),
        "epobj-187-d": (0.57, 0.58),
    },
    # Шлагбаум/турникет, перекрывающий проезд (gold: blocking the path).
    "EPO-REAL-0234": {
        "epobj-234-a": (0.52, 0.72),
        "epobj-234-b": (0.52, 0.72),
        "epobj-234-c": (0.52, 0.72),
        "epobj-234-d": (0.52, 0.72),
    },
    # Корешки книг: 大学物理, 模拟电子技术, C程序设计 (gold), 工程制图.
    "EPO-REAL-0235": {
        "epobj-235-a": (0.43, 0.55),
        "epobj-235-b": (0.53, 0.55),
        "epobj-235-c": (0.37, 0.50),
        "epobj-235-d": (0.25, 0.45),
    },
    # Красные люки: J155 (gold) справа, J154 в центре; JISS/T155 не
    # читаются -- якоря на крайнем левом и промежуточном люках.
    "EPO-REAL-0242": {
        "epobj-242-a": (0.04, 0.75),
        "epobj-242-b": (0.19, 0.82),
        "epobj-242-c": (0.47, 0.88),
        "epobj-242-d": (0.30, 0.90),
    },
    # Фирка с белыми шариками (gold: glutinous rice flour).
    "EPO-REAL-0385": {
        "epobj-385-a": (0.50, 0.83),
        "epobj-385-b": (0.50, 0.83),
        "epobj-385-c": (0.50, 0.83),
        "epobj-385-d": (0.50, 0.83),
    },
}


def author_manifest(manifest_name: str) -> Path:
    manifest_path = MANIFEST_DIR / manifest_name
    cases = [
        json.loads(line)
        for line in manifest_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    out_path = MANIFEST_DIR / f"{manifest_name.removesuffix('.jsonl')}.geometry.json"
    built = []
    for case in cases:
        case_id = case["case_id"]
        anchors = ANCHORS.get(case_id)
        if anchors is None:
            raise SystemExit(f"нет якорей для кейса {case_id}")
        target = case["gold"]["target_id"]
        image_path = IMAGE_ROOT / case["media"]["path"]
        if not image_path.exists():
            raise SystemExit(f"нет картинки {image_path}")
        built.append(
            build_case_geometry(
                case_id=case_id,
                image_path=image_path,
                anchors=anchors,
                target_anchor=anchors[target],
            )
        )
    write_geometry_sidecar(
        manifest_path,
        built,
        out_path,
        author=AUTHOR,
        method=METHOD,
        date=DATE,
    )
    return out_path


def main() -> None:
    for name in ("egopoint_15.jsonl", "pointing_holdout_15.jsonl"):
        path = author_manifest(name)
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
