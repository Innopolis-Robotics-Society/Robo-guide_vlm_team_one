"""Раннер офлайн-оценки: один кейс или целый манифест → run-директория.

Повторяет production-контракт через существующий `llm_client`
(дизайн: `docs/eval_harness_design.md`, раздел "Runner"): транспорт
`Backend`, кадры `build_content`, грамматики `grammar`, host-парсеры
`visual_context.parse_observation` / `tools.validate.parse_action`.

Два режима контракта на кейс:
* `deployed` -- фаза наблюдения (observation-грамма + host-парсер),
  для gold типа `action` добавляется фаза действия (action-грамма);
* `freeform` -- строгий JSON-ответ `{answer, confidence, abstain}`
  (авторский QA-протокол EgoPoint-Bench).

Инструкции фаз (константы ниже) -- самодостаточные: harness обязан
работать без ROS, а каталог описаний production-инструментов живёт в
`tools.schema` (там `guide_robot_msgs`). Контракт, который измеряет
harness, задают грамматика + host-парсер (общие с production,
`llm_client`/`visual_context`/`tools.validate`); инструкции -- вспомогательный
контекст для модели.

Токены: текущий `Backend.complete()` серверный `usage` не захватывает
-- записываем `tokens: null` с пометкой (известный gap, расширение
`llm_client` вне скоупа #10).

Промпт-варианты (Taiga #16, P4): `--prompt-variant <id|all>` -- инструкция
варианта из `prompt_variants.json` заменяет встроенную production-инструкцию
фазы (моду `deployed`/`freeform` и execution `single`/`cot_2pass` задаёт
вариант, не кейс); few-shot-примеры (`*4`) вставляются парами (кадр, ответ)
до кейсовых сообщений; `cot_2pass` = проход 1 без грамматики (рассуждение)
+ проход 2 со строгой грамматикой и текстом прохода 1 в контексте
(`PhaseRecord.cot_reason`, `calls=2`). `execution=loop` (P5) -- контракт
остановки F3: до K вызовов (дефолт 3, K -- все вызовы, включая первый),
каждый вызов -- свежий прогон навыка на следующем кадре `slices.frames`
(после исчерпания последовательности -- последний кадр; без последовательности
-- кадр кейса), тик-бюджет B (дефолт 5, 1 кадр = 1 тик); остановка при
engaged >= `slices.min_engaged` (дефолт 2; сигнал есть только в freeform)
или исчерпании K/бюджета; финальное «запроси уточнение» -- terminal
abstain=true (посетителя в бенчмарке нет); запись `calls_per_case`,
`terminal_reason`, `loop.json`. Без флага -- поведение байт-в-байт как
production-базлиния (`*_base`).
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import mimetypes
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol

from guide_robot_llm.eval.schema import Case, case_to_dict
from guide_robot_llm.llm_client.backend import Backend, BackendConfig, build_content
from guide_robot_llm.llm_client.grammar import (
    _CONFIDENCE_RULE,
    _JSON_RULES,
    build_action_grammar,
    build_observation_grammar,
)
from guide_robot_llm.llm_client.telemetry import ClientTelemetry
from guide_robot_llm.tools.validate import parse_action
from guide_robot_llm.visual_context import (
    QUALITY_OK,
    Observation,
    parse_observation,
    render_observation,
)

# Потолок scene_facts как в production (vision.observation_max_chars=400).
OBSERVATION_MAX_CHARS = 400
# Серверный usage в llm_client не захватывается -- честно пишем null.
TOKENS_NOTE = "server usage not captured by llm_client (known gap, out of scope for #10)"
DEFAULT_MAX_ATTEMPTS = 2

# Корень freeform-грамматики: ровно {answer, confidence, abstain}.
# Экранирование как в grammar.py: в GBNF-строковом литерале `\"` даёт
# литеральный кавычный ключ JSON.
_FREEFORM_ROOT = (
    'root ::= "{" ws "\\"answer\\"" ws ":" ws (string) ws "," ws '
    '"\\"confidence\\"" ws ":" ws (confidence) ws "," ws '
    '"\\"abstain\\"" ws ":" ws ("true" | "false") ws "}" ws'
)

# Инструкция фазы наблюдения (сжатый аналог production
# `dialog.prompt.build_observation_instruction`; id кандидатов inline --
# в production они приходят в контекстном сообщении, здесь -- в списке).
_OBSERVATION_INSTRUCTION = (
    "Перед выбором действия посмотри ПРИЛОЖЁННЫЕ кадры с камеры и ответь "
    "ТОЛЬКО одним JSON-объектом вида "
    '{"people_count": <целое 0..20>, "exhibit_candidates": ["<id>"], '
    '"pointing_evidence": "none"|"yes"|"uncertain", '
    '"pointing_box": [x0, y0, x1, y1] | null, "scene_facts": "<короткий текст>"} '
    "без какого-либо текста до или после него. people_count -- сколько людей "
    "в кадре. exhibit_candidates -- id ТОЛЬКО из списка доступных (внешние id "
    "не существует, лучше пусто, чем выдумка); повторять id нельзя. "
    "pointing_evidence -- видит ли кто-то в кадре явный жест-указание "
    "(на экспонат/направление): none/yes/uncertain. pointing_box -- "
    "НОРМИРОВАННЫЙ бокс [x0, y0, x1, y1] (координаты в долях кадра, 0..1), "
    "охватывающий жест/указываемую зону; ставь его ТОЛЬКО когда "
    'pointing_evidence "yes", иначе null. scene_facts -- одна-две фразы '
    "по-русски: что реально видно, только устойчивые детали, без домысливания. "
    "Если кадров нет или их не разобрать -- people_count 0, пустой список, "
    'pointing_evidence "uncertain", pointing_box null, scene_facts "кадры не разобрать".'
)

# Инструкция фазы действия (аналог production `build_action_instruction`;
# каталог -- имена из кейса, без описаний: описания живут в tools.schema).
_ACTION_INSTRUCTION_TEMPLATE = (
    "[Инструкция фазы действия]\n"
    "Выбери ровно одно действие, соответствующее намерению посетителя, и "
    "ответь ТОЛЬКО одним JSON-объектом вида "
    '{"tool": "<имя>", "args": {...}, "confidence": <0..1>, "abstain": true|false} '
    "без какого-либо текста до или после него.\n"
    "Доступные инструменты: {TOOLS}.\n"
    "reply -- выбор ПО УМОЛЧАНИЮ: ответы, уточнения, приветствия, "
    "светская беседа. Инструменты с физическим эффектом -- только по "
    "однозначному намерению посетителя. Если намерение неоднозначно или "
    "подходящего инструмента нет -- tool=reply, abstain=true."
)

# Инструкция freeform-режима (авторский QA-протокол EgoPoint-Bench).
_FREEFORM_INSTRUCTION = (
    "Ответь ТОЛЬКО одним JSON-объектом вида "
    '{"answer": "<короткий ответ>", "confidence": <0..1>, "abstain": true|false} '
    "без какого-либо текста до или после него. answer -- краткий ответ на "
    "вопрос (имя объекта, число, факт). Если по кадру вопрос ответить "
    "нельзя -- abstain=true."
)

_MIME_BY_FORMAT = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}


def build_freeform_answer_grammar() -> str:
    """Строгая GBNF-грамма ответа freeform-режима (answer/confidence/abstain)."""
    return "\n".join([_FREEFORM_ROOT, *_JSON_RULES.splitlines(), _CONFIDENCE_RULE])


def parse_freeform_answer(text: str) -> dict[str, Any] | None:
    """Строгий host-парсер freeform-ответа; `None` = malformed.

    Правила те же, что у `parse_action`: ровно три ключа, `confidence`
    -- число в [0, 1] (bool отклоняется), `abstain` -- bool.
    """
    try:
        data = json.loads(text.strip())
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict) or set(data) != {"answer", "confidence", "abstain"}:
        return None
    if not isinstance(data["answer"], str):
        return None
    confidence = data["confidence"]
    if isinstance(confidence, bool) or not isinstance(confidence, int | float):
        return None
    confidence = float(confidence)
    if not 0.0 <= confidence <= 1.0:
        return None
    if not isinstance(data["abstain"], bool):
        return None
    return {"answer": data["answer"], "confidence": confidence, "abstain": data["abstain"]}


def media_to_data_url(media_path: Path) -> str:
    """Медиафайл → data-URL (кадры `build_content` приходят в этом виде)."""
    mime = _MIME_BY_FORMAT.get(media_path.suffix.lstrip(".").lower())
    if mime is None:
        guessed, _ = mimetypes.guess_type(media_path.name)
        mime = guessed or "application/octet-stream"
    encoded = base64.b64encode(media_path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _candidate_suffix(candidates: tuple[str, ...]) -> str:
    """Inline-список id кандидатов (production-формат, общий с вариантами)."""
    ids = ", ".join(candidates) if candidates else "(список пуст -- отвечай пустым)"
    return f"\nДоступные id экспонатов: {ids}."


def _observation_instruction(candidates: tuple[str, ...]) -> str:
    """Инструкция фазы наблюдения с inline-списком id кандидатов."""
    return _OBSERVATION_INSTRUCTION + _candidate_suffix(candidates)


# --- Промпт-варианты (Taiga #16, P4) ---------------------------------------


class PromptVariantError(ValueError):
    """Некорректный манифест/спецификация промпт-варианта."""


# Контракт остановки execution=loop (F3, Taiga #16, заморожен): K_max --
# всего вызовов навыка на кейс (включая первый); B -- тик-бюджет (1 кадр =
# 1 тик); N = slices.min_engaged (дефолт DEFAULT_MIN_ENGAGED).
LOOP_MAX_CALLS = 3
LOOP_BUDGET_TICKS = 5
DEFAULT_MIN_ENGAGED = 2

# «Готовы слушать» в freeform-ответе: число после слова «готов*»/«слуша*»
# (короткий зазор), «N из M», либо «всего X, ... Y» (ровно два целых,
# второе <= первого -- формат A2/A3).
_ENGAGED_PATTERNS = (
    re.compile(r"готов\w*[^0-9]{0,40}?(\d+)"),
    re.compile(r"слуша\w*[^0-9]{0,40}?(\d+)"),
    re.compile(r"(\d+)\s+из\s+\d+"),
)


def extract_engaged_freeform(text: str) -> int | None:
    """Число «готовых слушать» из freeform-ответа; `None` -- не извлекается.

    Детерминированный host-парсер: один и тот же для loop-стоп-проверки (F3)
    и скоринга (P6). Устойчивая привязка числа к «готовым» обязательна --
    ответ без неё (`None`) цикл не останавливает (стоп только по K/бюджету).
    """
    for pattern in _ENGAGED_PATTERNS:
        match = pattern.search(text)
        if match is not None:
            return int(match.group(1))
    numbers = [int(number) for number in re.findall(r"\d+", text)]
    if len(numbers) == 2 and numbers[1] <= numbers[0]:
        return numbers[1]
    return None


# Корень пакета `guide_robot_llm/` (каталог, в котором лежит `pilot/`):
# медиа few-shot-примеров лежат в `pilot/media/cc/` относительно него.
_PACKAGE_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_VARIANTS_MANIFEST = Path(__file__).with_name("prompt_variants.json")


@dataclass(frozen=True)
class VariantSpec:
    """Один промпт-вариант из `prompt_variants.json` (Taiga #16, P3)."""

    id: str
    skill: str
    track: str  # кейсы какого трека вариант исполняет
    axis: str
    technique: str
    source: str | None
    mode: str  # "deployed" | "freeform" -- режим контракта (заменяет кейсовый)
    execution: str  # "single" | "cot_2pass" | "loop"
    text: str | None  # None → встроенная production-инструкция (`*_base`)
    examples: tuple[dict[str, Any], ...] = ()


def load_prompt_variants(
    path: str | Path | None = None,
    examples_root: str | Path | None = None,
) -> dict[str, VariantSpec]:
    """Манифест промпт-вариантов → `{id: VariantSpec}` (порядок -- как в файле).

    Few-shot-примеры заморожены: медиа каждого примера обязано существовать
    и совпадать по sha256 с манифестом -- рассинхронизация, как у кейсового
    медиа, ошибка загрузки, а не предупреждение.
    """
    manifest_path = Path(path) if path is not None else _DEFAULT_VARIANTS_MANIFEST
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    root = Path(examples_root) if examples_root is not None else _PACKAGE_ROOT
    variants: dict[str, VariantSpec] = {}
    for entry in data["variants"]:
        vid = entry["id"]
        if entry["mode"] not in ("deployed", "freeform"):
            raise PromptVariantError(f"{vid}: mode '{entry['mode']}' не известен")
        if entry["execution"] not in ("single", "cot_2pass", "loop"):
            raise PromptVariantError(f"{vid}: execution '{entry['execution']}' не известен")
        text: str | None = None
        if entry.get("text") is not None:
            text = (manifest_path.parent / entry["text"]).read_text(encoding="utf-8")
        examples = tuple(entry.get("examples") or ())
        for ex in examples:
            media = ex["media"]
            media_path = root / media["path"]
            if not media_path.is_file():
                raise PromptVariantError(f"{vid}: медиа примера {media['path']} не найдено")
            digest = hashlib.sha256(media_path.read_bytes()).hexdigest()
            if digest != media["sha256"]:
                raise PromptVariantError(
                    f"{vid}: sha256 медиа примера {media['path']} не совпадает"
                )
        variants[vid] = VariantSpec(
            id=vid,
            skill=entry["skill"],
            track=entry["track"],
            axis=entry["axis"],
            technique=entry["technique"],
            source=entry.get("source"),
            mode=entry["mode"],
            execution=entry["execution"],
            text=text,
            examples=examples,
        )
    return variants


def _action_instruction(allowed_tools: tuple[str, ...]) -> str:
    """Инструкция фазы действия; пустой список деградирует до reply."""
    tools = ", ".join(allowed_tools) if allowed_tools else "reply"
    return _ACTION_INSTRUCTION_TEMPLATE.replace("{TOOLS}", tools)


def _action_to_dict(action: Any | None) -> dict[str, Any] | None:
    """`ParsedAction` → плоский dict для записи в run-директорию."""
    if action is None:
        return None
    return {
        "tool": action.tool,
        "args": dict(action.args),
        "confidence": action.confidence,
        "abstain": action.abstain,
    }


def _observation_to_dict(observation: Observation | None) -> dict[str, Any] | None:
    """Наблюдение → плоский dict для записи в run-директорию."""
    if observation is None:
        return None
    return {
        "people_count": observation.people_count,
        "exhibit_candidates": list(observation.exhibit_candidates),
        "pointing_evidence": observation.pointing_evidence,
        "pointing_box": observation.pointing_box,
        "scene_facts": observation.scene_facts,
    }


def _parse_observation(
    text: str, *, candidates: tuple[str, ...], max_chars: int = OBSERVATION_MAX_CHARS
) -> Observation | None:
    """Host-валидация наблюдения (production-парсер, та же строга)."""
    return parse_observation(
        text,
        candidate_ids=frozenset(candidates),
        max_chars=max_chars,
    )


class Llm(Protocol):
    """Подмножество интерфейса `Backend.complete`, нужное раннеру."""

    def complete(
        self,
        messages: list[dict],
        *,
        grammar: str | None = None,
        max_tokens: int = 512,
        temperature: float = 0.2,
        telemetry: ClientTelemetry | None = None,
    ) -> Any:
        """Один вызов модели (подпись как у `Backend.complete`)."""
        ...


class MockBackend:
    """Тестовый/драйв-раннер бэкенд: заранее заготовленные ответы без сети.

    Ключи ответов -- пары `(case_id, phase)`, где фаза --
    `observation` / `action` / `freeform`. Раннер перед каждым вызовом
    вызывает `set_context(case_id, phase)`; неизвестный кейс/фаза →
    пустой текст (host-парсер отметит `parse_failed` -- прогон фиксирует
    сбой, а не молча пропускает кейс).
    """

    def __init__(
        self, responses: dict[tuple[str, str] | tuple[str, str, str], str] | None = None
    ) -> None:
        """Словарь предзаданных ответов `MockBackend`.

        `responses` -- словарь {(case_id, phase): text} и/или
        {(case_id, phase, pass_label): text} (cot_2pass-проходы);
        `None` -- пустой бэкенд.
        """
        self._responses = dict(responses or {})
        self._context: tuple[str, str, str | None] = ("", "", None)

    def set_context(self, case_id: str, phase: str, pass_label: str | None = None) -> None:
        """Указать кейс и фазу следующего вызова (осознанное состояние).

        `pass_label` (cot_2pass: pass1/pass2; loop: call0..callN): ответ
        берётся по трёхчастному ключу, с фолбэком на `(case_id, phase)`.
        """
        self._context = (case_id, phase, pass_label)

    def _lookup(self) -> str:
        if self._context[2] is not None:
            text = self._responses.get(self._context)
            if text is not None:
                return text
            return self._responses.get((self._context[0], self._context[1]), "")
        return self._responses.get(self._context[:2], "")

    def complete(
        self,
        messages: list[dict],
        *,
        grammar: str | None = None,
        max_tokens: int = 512,
        temperature: float = 0.2,
        telemetry: ClientTelemetry | None = None,
    ) -> Any:
        """Возвращает заготовленный текст для текущего (кейс, фаза[, проход])."""
        from guide_robot_llm.llm_client.backend import CompletionResult

        return CompletionResult(text=self._lookup(), finish_reason="stop")


@dataclass
class PhaseRecord:
    """Результат одной фазы кейса (raw + parsed + тайминги + попытки).

    `calls` -- логических вызовов модели в фазе (1 = single, 2 = cot_2pass);
    `attempts` -- суммарных попыток транспорта (ретраи считаются). Для
    cot_2pass `raw_text`/`parsed` -- результат прохода 2 (строгий ответ),
    `cot_reason` -- raw прохода 1 (рассуждение, без грамматики).
    """

    raw_text: str
    parsed: dict[str, Any] | None
    parse_status: str  # "ok" | "failed" | "skipped" (проход без парсинга)
    finish_reason: str
    latency_ms: float
    attempts: int
    timings: dict[str, Any] = field(default_factory=dict)
    cot_reason: str | None = None
    calls: int = 1


@dataclass
class LoopCallRecord:
    """Один тик (вызов) в цикле execution=loop (F3, P5)."""

    tick: int
    frame: str  # путь кадра вызова (относительно data_root)
    raw_text: str
    parse_status: str  # "ok" | "failed" | "skipped"
    engaged: int | None  # сигнал остановки (freeform); deployed -- None
    latency_ms: float
    attempts: int
    finish_reason: str


@dataclass
class LoopResult:
    """Итог кейса execution=loop (контракт F3).

    `final` -- последний вызов (идёт в `run.observation`/`run.freeform`);
    `calls` -- лог по тикам; `terminal_reason` -- путь остановки
    (`engaged_threshold` | `k_exhausted` | `budget_exhausted`);
    `terminal_abstain` -- финальное «запроси уточнение» → abstain.
    """

    final: PhaseRecord | None
    calls: list[LoopCallRecord]
    terminal_reason: str
    terminal_abstain: bool | None


@dataclass
class CaseRun:
    """Итог прогона одного кейса (что пишется в run-директорию)."""

    case_id: str
    source: str
    track: str
    status: str  # "ok" | "parse_failed" | "backend_error"
    prompt_mode: str
    observation: PhaseRecord | None = None
    action: PhaseRecord | None = None
    freeform: PhaseRecord | None = None
    error: str = ""
    variant_id: str | None = None
    # execution=loop (F3): число вызовов, путь остановки, терминальный
    # «запроси уточнение» → abstain, лог по тикам.
    calls_per_case: int | None = None
    terminal_reason: str | None = None
    terminal_abstain: bool | None = None
    loop_calls: list[LoopCallRecord] | None = None


class _PhaseBackendError(RuntimeError):
    """Все попытки фазы упали на транспорте (для записи backend_error)."""


def _run_phase(
    llm: Llm,
    messages: list[dict],
    *,
    case_id: str,
    grammar: str | None,
    phase: str,
    max_attempts: int,
    parse_fn: Any,
    pass_label: str | None = None,
) -> PhaseRecord:
    """Одна фаза (или один проход cot_2pass); ретрай только на сбое транспорта.

    `parse_fn=None` -- проход без парсинга (cot pass-1, `parse_status
    "skipped"`); `pass_label` -- метка прохода/вызова (cot_2pass: pass1/pass2;
    loop: callN) для `MockBackend`.
    """
    raw_text = ""
    finish_reason = ""
    telemetry = ClientTelemetry()
    attempts = 0
    last_error = ""
    succeeded = False
    phase_start = time.monotonic()
    while attempts < max_attempts:
        attempts += 1
        try:
            if isinstance(llm, MockBackend):
                llm.set_context(case_id, phase, pass_label)
            completion = llm.complete(messages, grammar=grammar, telemetry=telemetry)
        except Exception as error:  # noqa: BLE001 -- любой сбой транспорта → ретрай/запись
            last_error = f"{type(error).__name__}: {error}"
            continue
        raw_text = completion.text or ""
        finish_reason = getattr(completion, "finish_reason", "") or ""
        succeeded = True
        break
    if not succeeded:
        # Все попытки упали на транспорте -- кейс backend_error, парсинг не нужен.
        raise _PhaseBackendError(last_error)

    latency_ms = (time.monotonic() - phase_start) * 1000.0
    timings = telemetry.snapshot()
    if parse_fn is None:
        parsed, parse_status = None, "skipped"
    else:
        parsed = parse_fn(raw_text)
        parse_status = "ok" if parsed is not None else "failed"
    return PhaseRecord(
        raw_text=raw_text,
        parsed=parsed,
        parse_status=parse_status,
        finish_reason=finish_reason,
        latency_ms=latency_ms,
        attempts=attempts,
        timings=timings,
    )


def _merge_cot_passes(pass1: PhaseRecord, pass2: PhaseRecord) -> PhaseRecord:
    """cot_2pass → одна запись фазы: ответ прохода 2 + рассуждение прохода 1."""
    return PhaseRecord(
        raw_text=pass2.raw_text,
        parsed=pass2.parsed,
        parse_status=pass2.parse_status,
        finish_reason=pass2.finish_reason,
        latency_ms=pass1.latency_ms + pass2.latency_ms,
        attempts=pass1.attempts + pass2.attempts,
        timings={"pass1": pass1.timings, "pass2": pass2.timings},
        cot_reason=pass1.raw_text,
        calls=2,
    )


def _cot_bridge_message(reason_text: str) -> dict:
    """Сообщение прохода 2: рассуждение прохода 1 в контексте."""
    return {
        "role": "user",
        "content": (
            "Проход 1 (твоё рассуждение):\n"
            f"{reason_text}\n\n"
            "Теперь дай окончательный ответ строго в формате из инструкции."
        ),
    }


def _variant_deployed_instruction(variant: VariantSpec | None, candidates: tuple[str, ...]) -> str:
    """Инструкция observation-фазы: вариант или встроенная production."""
    if variant is None or variant.text is None:
        return _observation_instruction(candidates)
    return variant.text + _candidate_suffix(candidates)


def _variant_freeform_instruction(variant: VariantSpec | None) -> str:
    """Инструкция freeform-фазы: вариант или встроенная production."""
    if variant is None or variant.text is None:
        return _FREEFORM_INSTRUCTION
    return variant.text


def _example_messages(variant: VariantSpec, examples_root: Path) -> list[dict]:
    """Few-shot-пары (кадр примера, эталонный ответ) до кейсовых сообщений.

    Вопрос примера = текст самого варианта (D4/P4/A4 -- тексты D1/P1/A1);
    для deployed-примеров с кандидатами добавляется тот же inline-список id.
    """
    messages: list[dict] = []
    text = variant.text or ""
    for ex in variant.examples:
        media_path = examples_root / ex["media"]["path"]
        frame = media_to_data_url(media_path)
        question = text
        context = ex.get("context")
        if variant.mode == "deployed" and isinstance(context, dict) and context.get("candidates"):
            question = question + _candidate_suffix(tuple(context["candidates"]))
        messages.append({"role": "user", "content": build_content(question, (frame,))})
        messages.append({"role": "assistant", "content": ex["answer"]})
    return messages


def _phase_messages(
    case: Case,
    variant: VariantSpec | None,
    ex_root: Path,
    instruction: str,
    frames: tuple[str, ...],
) -> list[dict]:
    """Кейсовые сообщения фазы: (few-shot-пары) + кадр(ы) кейса + инструкция."""
    messages: list[dict] = []
    if variant is not None and variant.examples:
        messages.extend(_example_messages(variant, ex_root))
    messages.append({"role": "user", "content": build_content(case.prompt.user_text, frames)})
    messages.append({"role": "user", "content": instruction})
    return messages


def _frame_entry_ok(item: Any) -> bool:
    """Правильная запись `slices.frames`: dict со строковым `path`."""
    return isinstance(item, dict) and isinstance(item.get("path"), str)


def _loop_frame_set(case: Case, data_root: Path) -> list[tuple[str, tuple[str, ...]]]:
    """Кадры циклических вызовов: `(путь, data-URL)` для каждого тика.

    `slices.frames` -- следующий кадр на каждый вызов; без последовательности
    -- кадр кейса для каждого вызова. Отсутствующий файл -- вызов без кадра
    (то же поведение, что у основного медиа).
    """
    raw_frames = case.slices.get("frames")
    is_sequence = (
        isinstance(raw_frames, list)
        and bool(raw_frames)
        and all(_frame_entry_ok(item) for item in raw_frames)
    )
    if is_sequence:
        paths = [item["path"] for item in raw_frames]
    else:
        paths = [case.media.path]
    result: list[tuple[str, tuple[str, ...]]] = []
    for path in paths:
        media_path = data_root / path
        result.append((path, (media_to_data_url(media_path),) if media_path.is_file() else ()))
    return result


def _case_min_engaged(case: Case) -> int:
    """Порог остановки N (F3): `slices.min_engaged`, иначе дефолт 2."""
    value = case.slices.get("min_engaged")
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return DEFAULT_MIN_ENGAGED


def _loop_engaged(record: PhaseRecord, mode: str) -> int | None:
    """Сигнал остановки «engaged» по записи вызова (F3).

    freeform -- извлекается из текста `answer` (`extract_engaged_freeform`);
    deployed -- в замороженном контракте наблюдения поля engaged нет
    (грамматики не трогаем) → `None`, остановка только по K/бюджету.
    """
    if mode != "freeform" or record.parsed is None:
        return None
    answer = record.parsed.get("answer")
    if not isinstance(answer, str):
        return None
    return extract_engaged_freeform(answer)


def _loop_terminal_abstain(record: PhaseRecord | None, mode: str) -> bool | None:
    """Терминальное «запроси уточнение» → abstain (посетителя в бенчмарке нет).

    freeform -- собственный `abstain` ответа модели; deployed -- в финальном
    наблюдении нет уверенного кандидата (ровно один кандидат и evidence
    "yes"), нераспарсенный финал → True; нераспарсенный freeform → `None`.
    """
    if record is None:
        return None
    if mode == "freeform":
        if record.parsed is None:
            return None
        return bool(record.parsed["abstain"])
    if record.parsed is None:
        return True
    return not (
        len(record.parsed.exhibit_candidates) == 1
        and record.parsed.pointing_evidence == "yes"
    )


def _run_loop(
    llm: Llm,
    case: Case,
    variant: VariantSpec,
    *,
    ex_root: Path,
    data_root: Path,
    max_attempts: int,
    max_calls: int,
    budget_ticks: int,
) -> LoopResult:
    """Исполнитель execution=loop (контракт F3, P5).

    Каждый вызов -- свежий прогон основной фазы навыка на своём кадре
    (без кросс-вызовной истории: «повтори навык»). Остановка: engaged >= N
    (сигнал только в freeform), исчерпание K (max_calls -- все вызовы,
    включая первый) или тик-бюджета (1 вызов = 1 тик). Фаза действия в
    цикл не входит (F3 о ней не договаривается; loop-варианты P3/A3 на
    кейсах с gold action не исполняются).
    """
    mode = variant.mode
    if mode == "deployed":
        instruction = _variant_deployed_instruction(variant, case.candidates)
        grammar = build_observation_grammar(list(case.candidates))
    else:
        instruction = _variant_freeform_instruction(variant)
        grammar = build_freeform_answer_grammar()
    frames = _loop_frame_set(case, data_root)
    min_engaged = _case_min_engaged(case)

    calls: list[LoopCallRecord] = []
    final: PhaseRecord | None = None
    terminal_reason = "budget_exhausted"
    for tick in range(budget_ticks):
        if tick >= max_calls:
            terminal_reason = "k_exhausted"
            break
        frame_path, frame_urls = frames[min(tick, len(frames) - 1)]
        messages = _phase_messages(case, variant, ex_root, instruction, frame_urls)
        if mode == "deployed":
            final = _run_phase(
                llm,
                messages,
                case_id=case.case_id,
                grammar=grammar,
                phase="observation",
                max_attempts=max_attempts,
                parse_fn=lambda text: _parse_observation(text, candidates=case.candidates),
                pass_label=f"call{tick}",
            )
        else:
            final = _run_phase(
                llm,
                messages,
                case_id=case.case_id,
                grammar=grammar,
                phase="freeform",
                max_attempts=max_attempts,
                parse_fn=parse_freeform_answer,
                pass_label=f"call{tick}",
            )
        engaged = _loop_engaged(final, mode)
        calls.append(
            LoopCallRecord(
                tick=tick,
                frame=frame_path,
                raw_text=final.raw_text,
                parse_status=final.parse_status,
                engaged=engaged,
                latency_ms=final.latency_ms,
                attempts=final.attempts,
                finish_reason=final.finish_reason,
            )
        )
        if engaged is not None and engaged >= min_engaged:
            terminal_reason = "engaged_threshold"
            break

    terminal_abstain = _loop_terminal_abstain(final, mode)
    if final is not None and mode == "deployed" and final.parsed is not None:
        # Как в single-путе: запись -- плоский dict, не Observation.
        final.parsed = _observation_to_dict(final.parsed)
    return LoopResult(
        final=final,
        calls=calls,
        terminal_reason=terminal_reason,
        terminal_abstain=terminal_abstain,
    )


def run_case(
    case: Case,
    llm: Llm,
    *,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    data_root: Path | None = None,
    variant: VariantSpec | None = None,
    examples_root: Path | None = None,
    loop_max_calls: int = LOOP_MAX_CALLS,
    loop_budget_ticks: int = LOOP_BUDGET_TICKS,
) -> CaseRun:
    """Прогнать один кейс (без записи -- см. `write_case_run`).

    `data_root` -- корень, относительно которого лежит `media.path`.
    `variant` (Taiga #16, P4): режим (`deployed`/`freeform`) и execution
    задаёт вариант, а не кейс; текст варианта заменяет встроенную
    production-инструкцию фазы, `text=None` (`*_base`) -- тот же запрос,
    что и без варианта. `examples_root` -- корень медиа few-shot-примеров
    (по умолчанию корень пакета). `execution=loop` (P5, контракт F3):
    `loop_max_calls` -- K (всего вызовов, дефолт `LOOP_MAX_CALLS`),
    `loop_budget_ticks` -- B (тиков, дефолт `LOOP_BUDGET_TICKS`).
    """
    if loop_max_calls < 1 or loop_budget_ticks < 1:
        raise ValueError("loop_max_calls и loop_budget_ticks должны быть >= 1")
    mode = variant.mode if variant is not None else case.prompt.mode
    execution = variant.execution if variant is not None else "single"
    ex_root = Path(examples_root) if examples_root is not None else _PACKAGE_ROOT

    media_path = (data_root or Path(".")) / case.media.path
    frames = (media_to_data_url(media_path),) if media_path.is_file() else ()

    run = CaseRun(
        case_id=case.case_id,
        source=case.source,
        track=case.track,
        status="ok",
        prompt_mode=mode,
        variant_id=variant.id if variant is not None else None,
    )

    try:
        if variant is not None and variant.execution == "loop":
            loop = _run_loop(
                llm,
                case,
                variant,
                ex_root=ex_root,
                data_root=data_root or Path("."),
                max_attempts=max_attempts,
                max_calls=loop_max_calls,
                budget_ticks=loop_budget_ticks,
            )
            if mode == "deployed":
                run.observation = loop.final
            else:
                run.freeform = loop.final
            run.calls_per_case = len(loop.calls)
            run.terminal_reason = loop.terminal_reason
            run.terminal_abstain = loop.terminal_abstain
            run.loop_calls = loop.calls
        elif mode == "deployed":
            base_messages = _phase_messages(
                case,
                variant,
                ex_root,
                _variant_deployed_instruction(variant, case.candidates),
                frames,
            )
            if execution == "cot_2pass":
                pass1 = _run_phase(
                    llm,
                    base_messages,
                    case_id=case.case_id,
                    grammar=None,
                    phase="observation",
                    max_attempts=max_attempts,
                    parse_fn=None,
                    pass_label="pass1",
                )
                pass2 = _run_phase(
                    llm,
                    [*base_messages, _cot_bridge_message(pass1.raw_text)],
                    case_id=case.case_id,
                    grammar=build_observation_grammar(list(case.candidates)),
                    phase="observation",
                    max_attempts=max_attempts,
                    parse_fn=lambda text: _parse_observation(text, candidates=case.candidates),
                    pass_label="pass2",
                )
                run.observation = _merge_cot_passes(pass1, pass2)
            else:
                run.observation = _run_phase(
                    llm,
                    base_messages,
                    case_id=case.case_id,
                    grammar=build_observation_grammar(list(case.candidates)),
                    phase="observation",
                    max_attempts=max_attempts,
                    parse_fn=lambda text: _parse_observation(text, candidates=case.candidates),
                )
            observation: Observation | None = (
                run.observation.parsed if run.observation is not None else None
            )
            # Запись -- плоский dict; Observation нужен для рендера фазе действия.
            if run.observation is not None:
                run.observation.parsed = _observation_to_dict(observation)

            if case.gold.get("type") == "action":
                action_messages = [
                    *base_messages,
                    {"role": "user", "content": _action_instruction(case.allowed_tools)},
                ]
                if observation is not None:
                    # Визуальный суффикс фазы действия -- как в production
                    # (render_observation, тот же потолок max_chars).
                    action_messages.append(
                        {
                            "role": "user",
                            "content": render_observation(
                                observation,
                                quality=QUALITY_OK,
                                max_chars=OBSERVATION_MAX_CHARS,
                            ),
                        }
                    )
                run.action = _run_phase(
                    llm,
                    action_messages,
                    case_id=case.case_id,
                    grammar=build_action_grammar(list(case.allowed_tools)),
                    phase="action",
                    max_attempts=max_attempts,
                    parse_fn=lambda text: _action_to_dict(parse_action(text)),
                )
        else:
            freeform_messages = _phase_messages(
                case, variant, ex_root, _variant_freeform_instruction(variant), frames
            )
            if execution == "cot_2pass":
                pass1 = _run_phase(
                    llm,
                    freeform_messages,
                    case_id=case.case_id,
                    grammar=None,
                    phase="freeform",
                    max_attempts=max_attempts,
                    parse_fn=None,
                    pass_label="pass1",
                )
                pass2 = _run_phase(
                    llm,
                    [*freeform_messages, _cot_bridge_message(pass1.raw_text)],
                    case_id=case.case_id,
                    grammar=build_freeform_answer_grammar(),
                    phase="freeform",
                    max_attempts=max_attempts,
                    parse_fn=parse_freeform_answer,
                    pass_label="pass2",
                )
                run.freeform = _merge_cot_passes(pass1, pass2)
            else:
                run.freeform = _run_phase(
                    llm,
                    freeform_messages,
                    case_id=case.case_id,
                    grammar=build_freeform_answer_grammar(),
                    phase="freeform",
                    max_attempts=max_attempts,
                    parse_fn=parse_freeform_answer,
                )
    except _PhaseBackendError as error:
        run.status = "backend_error"
        run.error = str(error)
        return run

    if run.status == "ok":
        failed = [
            name
            for name, phase in _phase_records(run)
            if phase is not None and phase.parse_status == "failed"
        ]
        if failed:
            run.status = "parse_failed"
    return run


def write_case_run(case: Case, run: CaseRun, out_dir: Path) -> Path:
    """Записать run-директорию кейса: raw + parsed + meta (дизайн: "Runner")."""
    case_dir = out_dir / "cases" / run.case_id
    case_dir.mkdir(parents=True, exist_ok=True)

    for phase_name, record in _phase_records(run):
        if record is None:
            continue
        raw_file = f"raw_{phase_name}.txt"
        parsed_file = f"parsed_{phase_name}.json"
        (case_dir / raw_file).write_text(record.raw_text, encoding="utf-8")
        with open(case_dir / parsed_file, "w", encoding="utf-8") as fh:
            json.dump(
                record.parsed if record.parsed is not None else {"parse_status": "failed"},
                fh,
                ensure_ascii=False,
                indent=2,
            )

    phases: dict[str, Any] = {}
    for phase_name in ("observation", "action", "freeform"):
        record = getattr(run, phase_name)
        if record is None:
            continue
        phases[phase_name] = {
            "latency_ms": round(record.latency_ms, 3),
            "attempts": record.attempts,
            "calls": record.calls,
            "finish_reason": record.finish_reason,
            "parse_status": record.parse_status,
            "timings": record.timings,
        }
        if record.cot_reason is not None:
            phases[phase_name]["cot_reason"] = record.cot_reason
    latency_ms, attempts = _case_totals(run)
    meta = {
        "case_id": run.case_id,
        "source": run.source,
        "track": run.track,
        "prompt_mode": run.prompt_mode,
        "variant_id": run.variant_id,
        "calls_per_case": run.calls_per_case,
        "terminal_reason": run.terminal_reason,
        "terminal_abstain": run.terminal_abstain,
        "status": run.status,
        "error": run.error or None,
        "tokens": None,
        "tokens_note": TOKENS_NOTE,
        "phases": phases,
        "latency_ms": latency_ms,
        "attempts": attempts,
        "case": case_to_dict(case),
    }
    with open(case_dir / "meta.json", "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)
    if run.loop_calls is not None:
        with open(case_dir / "loop.json", "w", encoding="utf-8") as fh:
            json.dump([asdict(call) for call in run.loop_calls], fh, ensure_ascii=False, indent=2)
    return case_dir


def run_manifest(
    cases: list[Case],
    llm: Llm,
    out_dir: Path,
    *,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    data_root: Path | None = None,
    variant: VariantSpec | None = None,
    examples_root: Path | None = None,
    loop_max_calls: int = LOOP_MAX_CALLS,
    loop_budget_ticks: int = LOOP_BUDGET_TICKS,
) -> list[dict[str, Any]]:
    """Прогнать список кейсов → run-директория + `run_manifest.json`.

    Возврат -- строки манифеста (одна на кейс: case_id, source, track,
    status, pass=None, latency_ms, attempts, variant). Сбои кейса не
    прерывают прогон: записываются и фиксируются в отчёте. С `variant`
    (Taiga #16, P4) исполняются только кейсы трека варианта -- вариант
    навыковой, инструкция чужого трека не имеет смысла.
    """
    if variant is not None:
        cases = [case for case in cases if case.track == variant.track]
    out_dir.mkdir(parents=True, exist_ok=True)
    lines: list[dict[str, Any]] = []
    for case in cases:
        run = run_case(
            case,
            llm,
            max_attempts=max_attempts,
            data_root=data_root,
            variant=variant,
            examples_root=examples_root,
            loop_max_calls=loop_max_calls,
            loop_budget_ticks=loop_budget_ticks,
        )
        write_case_run(case, run, out_dir)
        latency_ms, attempts = _case_totals(run)
        lines.append(
            {
                "case_id": run.case_id,
                "source": run.source,
                "track": run.track,
                "status": run.status,
                "pass": None,  # оценка -- T4
                "variant": run.variant_id,
                "calls_per_case": run.calls_per_case,
                "terminal_reason": run.terminal_reason,
                "terminal_abstain": run.terminal_abstain,
                "latency_ms": latency_ms,
                "attempts": attempts,
            }
        )
    with open(out_dir / "run_manifest.json", "w", encoding="utf-8") as fh:
        json.dump(lines, fh, ensure_ascii=False, indent=2)
    return lines


def _phase_records(run: CaseRun) -> tuple[tuple[str, PhaseRecord | None], ...]:
    """Пары (имя_фазы, PhaseRecord|None) в фиксированном порядке записи."""
    return (
        ("observation", run.observation),
        ("action", run.action),
        ("freeform", run.freeform),
    )


def _phase_dict(run: CaseRun) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for name, record in _phase_records(run):
        if record is not None:
            result[name] = {"latency_ms": record.latency_ms, "attempts": record.attempts}
    return result


def _case_totals(run: CaseRun) -> tuple[float, int]:
    """Латентность/попытки кейса: для loop -- по всем тикам, иначе по фазам."""
    if run.loop_calls is not None:
        return (
            round(sum(call.latency_ms for call in run.loop_calls), 3),
            sum(call.attempts for call in run.loop_calls),
        )
    phases = _phase_dict(run)
    return (
        round(sum(p["latency_ms"] for p in phases.values()), 3),
        sum(p["attempts"] for p in phases.values()),
    )


def build_backend_from_config(config: dict[str, Any]) -> Backend:
    """`Backend` из словаря конфигурации (эндпоинт только из конфигов)."""
    return Backend(
        BackendConfig(
            base_url=config["base_url"],
            api_key=config.get("api_key") or "",
            model_name=config.get("model_name") or "",
            connect_timeout_s=float(config.get("connect_timeout_s", 5.0)),
            read_timeout_s=float(config.get("read_timeout_s", 60.0)),
            multimodal_enabled=bool(config.get("multimodal_enabled", True)),
            max_images=int(config.get("max_images", 4)),
        )
    )


def main(argv: list[str] | None = None) -> int:
    """CLI: манифест кейсов → run-директория (см. модульный докстринг)."""
    parser = argparse.ArgumentParser(description="Офлайн-прогон кейсов оценки VLM (Taiga #10)")
    parser.add_argument("--manifest", required=True, help="унифицированный JSONL-манифест кейсов")
    parser.add_argument("--out", required=True, help="каталог run-директории")
    parser.add_argument("--backend-config", help="JSON-конфиг эндпоинта (base_url и т.д.)")
    parser.add_argument("--mock-responses", help="JSON {case_id: {phase: text}}, прогон без сети")
    parser.add_argument("--data-root", default=".", help="корень путей media (по умолчанию CWD)")
    parser.add_argument("--max-attempts", type=int, default=DEFAULT_MAX_ATTEMPTS)
    parser.add_argument(
        "--loop-max-calls",
        type=int,
        default=LOOP_MAX_CALLS,
        help="F3: K_max -- всего вызовов навыка в execution=loop (дефолт 3)",
    )
    parser.add_argument(
        "--loop-budget-ticks",
        type=int,
        default=LOOP_BUDGET_TICKS,
        help="F3: B -- тик-бюджет execution=loop, 1 кадр = 1 тик (дефолт 5)",
    )
    parser.add_argument(
        "--prompt-variant",
        help="id промпт-варианта из prompt_variants.json или 'all' (Taiga #16, P4)",
    )
    parser.add_argument(
        "--examples-root",
        help="корень медиа few-shot-примеров (по умолчанию корень пакета)",
    )
    args = parser.parse_args(argv)

    from guide_robot_llm.eval.loader import load_manifest as _load_manifest

    cases = _load_manifest(args.manifest)
    out_dir = Path(args.out)

    if args.mock_responses:
        canned_all = json.loads(Path(args.mock_responses).read_text(encoding="utf-8"))
        llm: Llm = MockBackend(_flatten_canned(canned_all))
    elif args.backend_config:
        config = json.loads(Path(args.backend_config).read_text(encoding="utf-8"))
        llm = build_backend_from_config(config)
    else:
        parser.error("нужен --backend-config или --mock-responses")
        return 2

    common = dict(
        max_attempts=args.max_attempts,
        data_root=Path(args.data_root),
        examples_root=Path(args.examples_root) if args.examples_root else None,
        loop_max_calls=args.loop_max_calls,
        loop_budget_ticks=args.loop_budget_ticks,
    )

    if not args.prompt_variant:
        lines = run_manifest(cases, llm, out_dir, **common)
        failed = [line for line in lines if line["status"] != "ok"]
        print(f"прогоно кейсов: {len(lines)}; сбоев: {len(failed)}; run: {out_dir}")
        return 0

    variants = load_prompt_variants(examples_root=common["examples_root"])
    if args.prompt_variant == "all":
        for spec in variants.values():
            sub_out = out_dir / spec.id
            lines = run_manifest(cases, llm, sub_out, variant=spec, **common)
            failed = [line for line in lines if line["status"] != "ok"]
            print(
                f"вариант {spec.id}: кейсов: {len(lines)}, сбоев: {len(failed)}; run: {sub_out}"
            )
        return 0

    try:
        spec = variants[args.prompt_variant]
    except KeyError:
        parser.error(f"вариант '{args.prompt_variant}' не найден в prompt_variants.json")
        return 2
    lines = run_manifest(cases, llm, out_dir, variant=spec, **common)
    failed = [line for line in lines if line["status"] != "ok"]
    print(f"прогоно кейсов: {len(lines)}; сбоев: {len(failed)}; run: {out_dir}")
    return 0


def _flatten_canned(canned_all: dict[str, dict[str, str]]) -> dict[tuple[str, str], str]:
    """`{case_id: {phase: text}}` (JSON) → `{(case_id, phase): text}`.

    JSON не умеет tuple-ключи -- вложенный словарь разворачивается здесь.
    """
    flat: dict[tuple[str, str], str] = {}
    for case_id, phases in canned_all.items():
        for phase, text in phases.items():
            flat[(case_id, phase)] = text
    return flat


if __name__ == "__main__":
    raise SystemExit(main())
