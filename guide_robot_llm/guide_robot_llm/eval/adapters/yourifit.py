"""YouRefIt → единая схема кейса (Taiga #10, T8).

Данные: YouRefIt (UCLA/HKUST, ICCV 2021, Chen et al.) — 4195 embodied
reference-инстансов в 432 indoor-сценах. Доступ — только через
регистрацию (форма ``request.html``, некоммерческое научное
исследование, один архив, без репродукции/модификации/распространения).
Сплит-аннотации (``yourefit_{train,val,test}.pth``) публичны в
код-репозитории авторов ``yixchen/YouRefIt_ERU``; изображения — по
зарегистрированному архиву.

Статус (решение команды 2026-09-16): регистрация данных НЕ планируется —
датасет снят с плана, bench остаётся 40 кейсами. Адаптер оставлен в
кодовой базе (T8) вместе с тестами; данных нет и не будет.

GO-гейт T1 (2026-09-15, ``docs/vlm_deixis_audience_datasets.md``,
раздел «License verification»): GO только для использования в авторском
протоколе БЕЗ модификации — NO-GO для адаптации, релейблинга,
производных (включая русскоязычные) и перераспространения. Отсюда:

* 5 кейсов только из test-сплита, авторский Image-ERU-протокол:
  канонический кадр + дословная транскрипция фразы → референт. В
  freeform-режиме harness'а вопрос — harness-надстройка над
  шаблоном дизайна («Can you show me the ... the person is referring
  to?»); фраза передаётся модели ДОСЛОВНО, без переписывания;
* один кандидат на кейс: в аннотации ровно один референт на
  инстанс (distactor-объекты не аннотированы) — ``n_distractors=0``;
* сборка read-only относительно данных: адаптер не пишет в каталог
  данных; по контракту дизайна CLI пишет ``PROVENANCE.md`` в корень
  данных (как DP/EgoPoint-адаптеры);
* неизменность исходной аннотации доказана пинг-суммой:
  ``yourefit_test.pth`` сверяется с верифицированной 2026-09-15
  копией из ``yixchen/YouRefIt_ERU`` (main), sha256 — ниже.

Файлы ``.pth`` — zip-архивы torch с ``archive/data.pkl``; данные
чистый Python (кортежи str/list) без тензоров, поэтому читаются
``zipfile``+``pickle`` без torch. Пин-сумма проверяется ДО разбора
pickle.

Агент не регистрируется и не скачивает датасет — точные шаги
регистрации/загрузки в ``provenance_text()`` (пишется в
``eval_data/yourifit/PROVENANCE.md``) и выполняются пользователем.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pickle
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from guide_robot_llm.eval.schema import Case, case_from_dict, case_to_dict

SOURCE = "yourifit"

# Лицензия: строка из верификации T1 (2026-09-15) — см.
# docs/vlm_deixis_audience_datasets.md, раздел «License verification».
LICENSE_LINE = (
    "non-commercial scientific research only; no reproduction, modification, "
    "or distribution without written permission (License.pdf, verified "
    "2026-09-15, T1)"
)
RIGHTS_NOTE = (
    "unmodified protocol use; one archive copy; no relabelling, no "
    "derivatives, no redistribution (T1, 2026-09-15)"
)

# Регистрация и публичные файлы (проверено 2026-09-15):
REGISTRATION_PAGE_URL = "https://yixchen.github.io/YouRefIt/request.html"
REGISTRATION_FORM_URL = (
    "https://docs.google.com/forms/d/e/1FAIpQLSdg0uNO_RWors2gkT3CYq_1Q0"
    "DELovVEukn4pDe_bY4u7BxiQ/viewform"
)
LICENSE_URL = "https://yixchen.github.io/YouRefIt/file/License.pdf"
CODE_REPO_URL = "https://github.com/yixchen/YouRefIt_ERU"
SPLIT_RAW_URL = "https://github.com/yixchen/YouRefIt_ERU/raw/main/data/yourefit/"

DEFAULT_REGISTRATION_REF = f"pending — форма {REGISTRATION_PAGE_URL}"

# Файл test-сплита из публичного код-репозитория авторов (main,
# проверено 2026-09-15): 1251 инстанс, уникальные имена файлов. Адаптер
# требует совпадения sha256: изменённая исходная аннотация сборку
# останавливает.
SPLIT_REL_PATH = "splits/yourefit_test.pth"
SPLIT_SHA256_EXPECTED = "c3f459252e9adb79cb61cb99b19e9da1407c97281d21cd9dec6d8f322cfdf8a0"
IMAGES_DIR = "images"

DEFAULT_N_CASES = 5
DEFAULT_MEDIA_PREFIX = "eval_data/yourifit"

# Имя изображения: ``<env>_p_<session>_<clip>_0_<frame>.jpg``
# (env ∈ {cs, lab} — две среды съёмки).
_IMG_NAME_RE = re.compile(r"^(?P<env>\w+)_p_(?P<session>\d+)_(?P<clip>\d+)_0_(?P<frame>\d+)\.jpg$")


class YourifitAdapterError(RuntimeError):
    """Ошибка адаптера YouRefIt (формат, гейт, целостность)."""


def author_prompt(phrase: str) -> str:
    """Вопрос harness'а для Image-ERU-протокола авторов.

    Вход протокола — канонический кадр + транскрипция фразы; фраза
    подставляется в вопрос ДОСЛОВНО (без модификации, гейт T1).
    """
    return (
        f"The person in the image says: '{phrase}'. "
        "Can you show me the object the person is referring to?"
    )


def load_split(split_file: Path) -> list[tuple[Any, ...]]:
    """Читает split-файл ``.pth`` (zip с ``archive/data.pkl``).

    Данные — чистый Python без тензоров, torch не нужен. Вызывается
    только после сверки sha256 файла с ``SPLIT_SHA256_EXPECTED``
    (pickle исполняет код — недоверенному файлу не верим).
    """
    try:
        with zipfile.ZipFile(split_file) as zf:
            if "archive/data.pkl" not in zf.namelist():
                raise YourifitAdapterError(
                    f"{split_file.name}: не ожидаемый .pth-архив " "(нет 'archive/data.pkl')"
                )
            raw = zf.read("archive/data.pkl")
    except YourifitAdapterError:
        raise
    except (OSError, zipfile.BadZipFile) as exc:
        raise YourifitAdapterError(f"{split_file.name}: не zip-архив: {exc}") from exc
    try:
        data = pickle.loads(raw)
    except Exception as exc:
        raise YourifitAdapterError(f"{split_file.name}: pickle-разбор не удался: {exc}") from exc
    if not isinstance(data, list) or not data:
        raise YourifitAdapterError(f"{split_file.name}: ожидался непустой список инстансов")
    return data


def _validate_entry(entry: Any) -> str:
    """Строгая проверка инстанса сплита (формат, верифицированный 2026-09-15).

    Инстанс — 5-кортеж ``(img_file, aux_pth, bbox, phrase, attri)``;
    ``bbox`` — ``[x1, y1, w, h]`` из int (координаты могут лежать на
    границе кадра: x1=0/y1=0 легальны, w/h > 0). ``attri`` (семантический
    разбор фразы) не используется — в test-сплите все метки ``none``.
    Возвращает проверенное имя файла.
    """
    if not (isinstance(entry, tuple) and len(entry) == 5):
        raise YourifitAdapterError(f"инстанс не 5-кортеж: {entry!r}")
    img_file, aux_pth, bbox, phrase, attri = entry
    if not (isinstance(img_file, str) and _IMG_NAME_RE.match(img_file)):
        raise YourifitAdapterError(f"img_file {img_file!r} вне ожидаемого формата")
    if not (isinstance(aux_pth, str) and aux_pth.endswith(".pth")):
        raise YourifitAdapterError(f"{img_file}: aux_pth {aux_pth!r} не .pth")
    if not (isinstance(bbox, list) and len(bbox) == 4 and all(isinstance(v, int) for v in bbox)):
        raise YourifitAdapterError(f"{img_file}: bbox {bbox!r} — список из 4 int")
    x1, y1, w, h = bbox
    if x1 < 0 or y1 < 0 or w <= 0 or h <= 0:
        raise YourifitAdapterError(f"{img_file}: bbox {bbox!r} — вне кадра или вырожден")
    if not (isinstance(phrase, str) and phrase.strip()):
        raise YourifitAdapterError(f"{img_file}: фраза {phrase!r} пуста")
    if not isinstance(attri, list):
        raise YourifitAdapterError(f"{img_file}: attri {attri!r} не список")
    return img_file


def select_yourifit_entries(
    entries: list[tuple[Any, ...]], n_cases: int = DEFAULT_N_CASES
) -> list[tuple[Any, ...]]:
    """Детерминированный выбор: первый инстанс каждой группы съёмки.

    Группа — ``(env, session)`` по имени файла; берётся первый инстанс
    группы в порядке файла, пока не набрано ``n_cases``. Файл закреплён
    pin-суммой — порядок в нём стабилен, поэтому выбор воспроизводим.
    Группировка по сессии гарантирует, что 5 кейсов не из одной сцены.
    Нарушение формата любого инстанса — ошибка, а не тихий skip.
    """
    if n_cases < 1:
        raise YourifitAdapterError(f"n_cases={n_cases} должно быть не меньше 1")
    selected: list[tuple[Any, ...]] = []
    seen: set[tuple[str, str]] = set()
    for entry in entries:
        img_file = _validate_entry(entry)
        m = _IMG_NAME_RE.match(img_file)
        key = (m.group("env"), m.group("session"))
        if key in seen:
            continue
        seen.add(key)
        selected.append(entry)
        if len(selected) == n_cases:
            break
    if len(selected) < n_cases:
        raise YourifitAdapterError(
            f"в сплите только {len(selected)} групп (env, session) — "
            f"недостаточно для n_cases={n_cases}"
        )
    return selected


def _candidate_id(img_file: str, instance_index: int) -> str:
    """Id кандидата: ``yri-<env>-<session>-t<n>`` (шаблон дизайна 'yri-0114-t1')."""
    m = _IMG_NAME_RE.match(img_file)
    assert m is not None  # имя проверено в _validate_entry
    return f"yri-{m.group('env')}-{m.group('session')}-t{instance_index}"


def _make_case(
    entry: tuple[Any, ...],
    image_file: Path,
    media_prefix: str,
    split_sha256: str,
    registration_ref: str,
) -> Case:
    """Инстанс сплита → кейс единой схемы (через `case_from_dict`)."""
    img_file, _aux_pth, bbox, phrase, _attri = entry
    x1, y1, w, h = bbox
    m = _IMG_NAME_RE.match(img_file)
    assert m is not None  # имя проверено в _validate_entry
    target_id = _candidate_id(img_file, 1)
    data = {
        "case_id": f"YRI-{m.group('env')}-{m.group('session')}-{m.group('frame')}",
        "source": SOURCE,
        "track": "pointing",
        "split_group_id": f"g-yri-{m.group('env')}-{m.group('session')}",
        "media": {
            "path": f"{media_prefix}/{IMAGES_DIR}/{img_file}",
            "sha256": hashlib.sha256(image_file.read_bytes()).hexdigest(),
            "format": "jpg",
        },
        "prompt": {
            "mode": "freeform",
            "user_text": author_prompt(phrase),
            "language": "en",
        },
        # Один кандидат: в авторской аннотации ровно один референт на
        # инстанс, дистракторы не аннотированы (n_distractors = 0).
        "candidates": [target_id],
        "allowed_tools": [],
        "gold": {
            "type": "target_box",
            "target_id": target_id,
            # Бокс авторов [x1, y1, w, h] → [x0, y0, x1, y1] px, дословно.
            "box_px": [x1, y1, x1 + w, y1 + h],
            "distractors": [],
        },
        "provenance": {
            "source": "YouRefIt (UCLA/HKUST, ICCV 2021)",
            "license": LICENSE_LINE,
            "version": f"yourefit_test.pth sha256:{split_sha256[:16]}",
            "rights_note": f"{RIGHTS_NOTE}; registration: {registration_ref}",
        },
        "slices": {
            "split": "test",
            "session": f"{m.group('env')}-{m.group('session')}",
            "phrase": phrase,
            "n_distractors": 0,
            # Таблица «ответ → id кандидата» для freeform-скоринга:
            # _answer_to_id() (eval/scoring.py) сопоставляет ответ модели
            # с дословной фразой после нормализации.
            "answer_map": {phrase: target_id},
        },
    }
    return case_from_dict(data)


def build_yourifit_cases(
    data_root: Path,
    *,
    n_cases: int = DEFAULT_N_CASES,
    media_prefix: str = DEFAULT_MEDIA_PREFIX,
    expected_split_sha256: str | None = SPLIT_SHA256_EXPECTED,
    registration_ref: str = DEFAULT_REGISTRATION_REF,
) -> tuple[list[Case], dict[str, Any]]:
    """Собирает кейсы YouRefIt из ``data_root``.

    ``data_root`` — каталог ``eval_data/yourifit``: ``splits/
    yourefit_test.pth`` (публичная split-аннотация из код-репозитория
    авторов) + ``images/*.jpg`` (зарегистрированная загрузка).
    Read-only: в каталог ничего не записывается.
    """
    data_root = Path(data_root)
    split_file = data_root / SPLIT_REL_PATH
    if not split_file.is_file():
        raise YourifitAdapterError(
            f"не найден {split_file}; см. PROVENANCE.md (раздел " "'Регистрация и загрузка')"
        )
    raw = split_file.read_bytes()
    split_sha256 = hashlib.sha256(raw).hexdigest()
    if expected_split_sha256 is not None and split_sha256 != expected_split_sha256:
        raise YourifitAdapterError(
            f"sha256 {split_file.name} = {split_sha256[:16]}… ≠ "
            f"верифицированной {expected_split_sha256[:16]}… — исходная "
            "аннотация изменена; сборка остановлена"
        )
    entries = load_split(split_file)
    selected = select_yourifit_entries(entries, n_cases=n_cases)
    images_dir = data_root / IMAGES_DIR
    cases: list[Case] = []
    for entry in selected:
        image_file = images_dir / str(entry[0])
        if not image_file.is_file():
            raise YourifitAdapterError(f"не найдено изображение {image_file} (кейс из {entry[0]})")
        cases.append(_make_case(entry, image_file, media_prefix, split_sha256, registration_ref))
    cases.sort(key=lambda c: c.case_id)
    if len({c.case_id for c in cases}) != len(cases):
        raise YourifitAdapterError("дубликаты case_id в выборке — нарушение формата")

    groups: set[tuple[str, str]] = set()
    for e in entries:
        m = _IMG_NAME_RE.match(str(e[0]))
        assert m is not None  # имя проверено в _validate_entry
        groups.add((m.group("env"), m.group("session")))
    report = {
        "source": SOURCE,
        "n_cases": len(cases),
        "split_file": SPLIT_REL_PATH,
        "split_sha256": split_sha256,
        "total_instances": len(entries),
        "n_capture_groups": len(groups),
        "selection_rule": (
            "первый инстанс каждой группы съёмки (env, session) в порядке "
            "файла; split закреплён sha256 — порядок стабилен"
        ),
        "registration_ref": registration_ref,
        "selected": [
            {
                "case_id": c.case_id,
                "session": c.slices["session"],
                "phrase": c.slices["phrase"],
                "answer_id": c.gold["target_id"],
                "box_px": c.gold["box_px"],
            }
            for c in cases
        ],
    }
    return cases, report


def load(data_root: Path) -> list[Case]:
    """Протокол адаптера (дизайн, раздел «Adapter interface»)."""
    cases, _report = build_yourifit_cases(data_root)
    return cases


def provenance_text(cases: list[Case], report: dict[str, Any]) -> str:
    """Текст ``PROVENANCE.md`` (контракт дизайна, раздел "Provenance")."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# YouRefIt — Provenance (сгенерировано guide_robot_llm.eval.adapters.yourifit)",
        "",
        f"- Время генерации: {now}",
        "- Источник: YouRefIt (UCLA/HKUST, ICCV 2021, Chen et al.) — 4195 "
        "embodied reference-инстансов, 432 indoor-сцены",
        f"- Лицензия: {LICENSE_LINE} (текст: {LICENSE_URL})",
        "- Использование: read-only, авторский Image-ERU-протокол без "
        "модификации; один архив, без релейблинга/производных/"
        "распространения; адаптер не пишет в каталог данных",
        f"- Регистрация: {report['registration_ref']}",
        f"- Split-аннотация: `{SPLIT_REL_PATH}`, sha256 = "
        f"`{report['split_sha256']}` (совпадает с верифицированной "
        f"2026-09-15 копией из `{CODE_REPO_URL}`, ветка main)",
        f"- Инстансов в test-сплите: {report['total_instances']} "
        f"({report['n_capture_groups']} групп (env, session))",
        f"- Правило выбора: {report['selection_rule']}",
        "- Примечание: ``attri`` (семантический разбор фразы) не "
        "используется — в test-сплите все метки `none`; baseline-выводы "
        "авторов в сплит-файлах отсутствуют",
        "",
        "## Регистрация и загрузка (выполняет пользователь — агент не скачивает)",
        "",
        "1. Заполнить форму регистрации: "
        f"<{REGISTRATION_FORM_URL}> (страница: <{REGISTRATION_PAGE_URL}>). "
        f"Условия — {LICENSE_URL}.",
        "2. Дождаться письма авторов со ссылкой на архив данных "
        "(один архив; репродукция/модификация/распространение запрещены).",
        "3. Разложить изображения в "
        f"`eval_data/yourifit/{IMAGES_DIR}/` (плоско: "
        "``cs_p_*.jpg`` / ``lab_p_*.jpg``; в архиве авторов — "
        "``ln_data/yourefit/images/``).",
        "4. Скачать публичную split-аннотацию из код-репозитория авторов:",
        "```bash",
        "cd guide_robot_llm && mkdir -p eval_data/yourifit/splits",
        f"curl -L -o eval_data/yourifit/{SPLIT_REL_PATH} {SPLIT_RAW_URL}yourefit_test.pth",
        f"sha256sum eval_data/yourifit/{SPLIT_REL_PATH}  # ожидается: {report['split_sha256']}",
        "```",
        "",
        "Сборка манифеста после загрузки:",
        "",
        "```bash",
        "python -m guide_robot_llm.eval.adapters.yourifit --data-root "
        "./eval_data/yourifit --out eval_manifests/yourifit_5.jsonl "
        "--registration-ref '<дата/номер регистрации>'",
        "```",
        "",
        "## Выбранные кейсы",
        "",
        "| case_id | session | phrase | answer_id | box_px |",
        "|---|---|---|---|---|",
    ]
    for item in report["selected"]:
        lines.append(
            f"| {item['case_id']} | {item['session']} | {item['phrase']} | "
            f"{item['answer_id']} | {item['box_px']} |"
        )
    lines += [
        "",
        f"Кейсов: {len(cases)}. Все — из test-сплита, авторский "
        "Image-ERU-протокол (канонический кадр + дословная фраза), "
        "одно изображение на кейс, один референт на кейс.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """CLI: сборка манифеста YouRefIt (JSONL) + отчёт + PROVENANCE.md."""
    parser = argparse.ArgumentParser(
        description=(
            "Сборка манифеста YouRefIt (5 кейсов, авторский Image-ERU-"
            "протокол, unmodified) — read-only относительно каталога данных"
        )
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=Path(__file__).resolve().parents[3] / "eval_data" / "yourifit",
        help=f"Каталог с {IMAGES_DIR}/ и {SPLIT_REL_PATH} (по умолчанию "
        "guide_robot_llm/eval_data/yourifit)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parents[3] / "eval_manifests" / "yourifit_5.jsonl",
        help="Выходной JSONL-манифест",
    )
    parser.add_argument(
        "--n-cases",
        type=int,
        default=DEFAULT_N_CASES,
        help=f"Число кейсов (по умолчанию {DEFAULT_N_CASES})",
    )
    parser.add_argument(
        "--media-prefix",
        default=DEFAULT_MEDIA_PREFIX,
        help="Префикс пути в media.path (логический, от корня eval_data)",
    )
    parser.add_argument(
        "--registration-ref",
        default=DEFAULT_REGISTRATION_REF,
        help="Ссылка/свидетельство регистрации (дата, номер письма) — "
        "записывается в provenance каждого кейса и в PROVENANCE.md",
    )
    args = parser.parse_args(argv)

    cases, report = build_yourifit_cases(
        args.data_root,
        n_cases=args.n_cases,
        media_prefix=args.media_prefix,
        registration_ref=args.registration_ref,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        for case in cases:
            fh.write(json.dumps(case_to_dict(case), ensure_ascii=False) + "\n")
    sidecar = args.out.with_name(args.out.name + ".sidecar.json")
    sidecar.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    # PROVENANCE.md в корне данных — по контракту дизайна (аналог
    # DP/EgoPoint-адаптеров); сами данные адаптер не изменяет.
    (args.data_root / "PROVENANCE.md").write_text(provenance_text(cases, report), encoding="utf-8")
    print(
        f"YouRefIt: кейсов {len(cases)} → {args.out}\n"
        f"  отчёта → {sidecar}\n"
        f"  provenance → {args.data_root / 'PROVENANCE.md'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
