"""`llm_client.grammar.build_action_grammar()` -- форма, не содержимое.

Контракт ADR-0001 §2: ровно {tool, args, confidence, abstain}, порядок
полей фиксирован, confidence прижато к [0, 1] на уровне грамматики.
"""

from __future__ import annotations

from guide_robot_llm.llm_client.grammar import build_action_grammar, build_observation_grammar
from guide_robot_llm.tools.validate import parse_action
from guide_robot_llm.visual_context import parse_observation


def test_grammar_contains_root_and_tool_name_rules() -> None:
    grammar = build_action_grammar(["say", "confirm"])

    assert "root ::=" in grammar
    assert "tool-name ::=" in grammar


def test_grammar_lists_exactly_given_tool_names_as_alternatives() -> None:
    grammar = build_action_grammar(["say", "confirm", "stop_tour"])
    tool_name_rule = next(
        line for line in grammar.splitlines() if line.startswith("tool-name ::=")
    )

    assert '"\\"say\\""' in tool_name_rule
    assert '"\\"confirm\\""' in tool_name_rule
    assert '"\\"stop_tour\\""' in tool_name_rule
    # Ничего лишнего -- ровно 3 альтернативы через " | ".
    assert tool_name_rule.count("|") == 2


def test_grammar_args_uses_generic_json_object_not_per_tool_fields() -> None:
    grammar = build_action_grammar(["finish_answer", "tour_by_points"])

    # root ссылается на общее правило object для args -- не на finish_answer-
    # специфичное или tour_by_points-специфичное правило.
    root_rule = next(line for line in grammar.splitlines() if line.startswith("root ::="))
    assert "args" in root_rule
    assert "object" in root_rule
    assert "finish_answer" not in root_rule
    # Ни одно специфичное для конкретного инструмента имя поля не просочилось
    # в грамматику -- args остаётся типизирован только как object везде.
    assert "outcome" not in grammar
    assert "location_ids" not in grammar


def test_grammar_is_stable_regardless_of_tool_order_content() -> None:
    # Форма грамматики (JSON-правила) не зависит от того, какие именно
    # инструменты переданы -- меняется только tool-name.
    grammar_a = build_action_grammar(["say"])
    grammar_b = build_action_grammar(["stop_tour", "pause", "resume"])

    def _without_tool_name_line(text: str) -> str:
        return "\n".join(
            line for line in text.splitlines() if not line.startswith("tool-name ::=")
        )

    assert _without_tool_name_line(grammar_a) == _without_tool_name_line(grammar_b)


def test_empty_tool_list_still_produces_syntactically_plausible_grammar() -> None:
    grammar = build_action_grammar([])

    assert "root ::=" in grammar
    assert "tool-name ::=" in grammar


def test_grammar_root_has_all_four_contract_fields_in_order() -> None:
    """ADR-0001 §2: tool -> args -> confidence -> abstain, без think."""
    grammar = build_action_grammar(["say"])
    root_rule = next(line for line in grammar.splitlines() if line.startswith("root ::="))

    assert '\\"think\\"' not in root_rule
    assert "think" not in grammar
    assert root_rule.index("tool") < root_rule.index("args")
    assert root_rule.index("args") < root_rule.index("confidence")
    assert root_rule.index("confidence") < root_rule.index("abstain")


def test_grammar_confidence_is_pinned_to_zero_one() -> None:
    """confidence ::= "1" | "0"."<12 знаков>" -- вне [0,1] не сгенерировать."""
    grammar = build_action_grammar(["say"])
    confidence_rule = next(
        line for line in grammar.splitlines() if line.startswith("confidence ::=")
    )

    assert '"1"' in confidence_rule
    assert '"0"' in confidence_rule
    # Никаких [0-9]+ в головах целых/дробных -- только "0" или "1".
    assert "[0-9]+" not in confidence_rule


def test_grammar_abstain_is_boolean_literal() -> None:
    grammar = build_action_grammar(["say"])
    root_rule = next(line for line in grammar.splitlines() if line.startswith("root ::="))

    assert '"true" | "false"' in root_rule


def test_action_root_keys_are_json_quoted() -> None:
    """Regression (живой смоук 2026-09-13): GBNF-литерал `"tool"` матчит `tool`
    без кавычек → грамматика форсила невалидный JSON, который strict
    `json.loads` в parse_action отклонял. Ключи обязаны генерироваться с
    кавычками: в GBNF это `\\"tool\\"` (экранированная кавычка в литерале).
    """
    grammar = build_action_grammar(["say"])
    root_rule = next(line for line in grammar.splitlines() if line.startswith("root ::="))

    for key in ("tool", "args", "confidence", "abstain"):
        assert f'\\"{key}\\"' in root_rule, key


def test_grammar_conformed_action_output_parses_as_contract_json() -> None:
    """Текст, который ДОПУСКАЕТ исправленная грамматика (ключи с кавычками,
    whitespace по правилу ws, вкл. табы/переносы), обязан проходить strict
    parse_action. Старый формат (ключи без кавычек) -- обязан падать.
    """
    grammar = build_action_grammar(["reply"])
    assert '\\"tool\\"' in grammar

    conformed = (
        '{\n  \t\t  "tool"\n  \t:  "reply",'
        '\n  "args": {},\n  "confidence": 0.75,\n  "abstain": false\n}'
    )
    action = parse_action(conformed)
    assert action is not None
    assert action.tool == "reply"
    assert action.confidence == 0.75
    assert action.abstain is False

    # До-исправление формат грамматики (без кавычек) -- malformed:
    assert parse_action('{tool: "reply", args: {}, confidence: 0.75, abstain: false}') is None


def test_observation_root_keys_are_json_quoted_and_output_parses() -> None:
    """Тот же regression для фазы наблюдения: parse_observation -- strict.
    Ключи наблюдений обязаны генерироваться с кавычками.
    """
    grammar = build_observation_grammar(["cand-1"])
    root_rule = next(line for line in grammar.splitlines() if line.startswith("root ::="))
    for key in ("people_count", "exhibit_candidates", "pointing_evidence", "scene_facts"):
        assert f'\\"{key}\\"' in root_rule, key

    # Значения pointing -- JSON-строки (regression: голые none/yes/uncertain
    # падали в strict json.loads).
    pointing_rule = next(line for line in grammar.splitlines() if line.startswith("pointing ::="))
    for value in ("none", "yes", "uncertain"):
        assert f'\\"{value}\\"' in pointing_rule, value

    conformed = (
        '{\n  "people_count": 1,\n  "exhibit_candidates": ["cand-1"],'
        '\n  "pointing_evidence": "none",'
        '\n  "scene_facts": "камер виден один экспонат"\n}'
    )
    observation = parse_observation(conformed, candidate_ids=frozenset({"cand-1"}), max_chars=400)
    assert observation is not None
    assert observation.people_count == 1
    assert observation.exhibit_candidates == ("cand-1",)

    assert (
        parse_observation(
            '{people_count: 1, exhibit_candidates: ["cand-1"],'
            ' pointing_evidence: "none", scene_facts: ""}',
            candidate_ids=frozenset({"cand-1"}),
            max_chars=400,
        )
        is None
    )


def _gbnf_literals(line: str) -> list[str | None]:
    """GBNF-литералы строки: содержимое каждого (экраны сняты).

    `None`-элемент -- незакрытый литерал (грамматика невалидна). Классы
    `[...]` пропускаются: `"` внутри класса -- не разделитель.
    """
    literals: list[str | None] = []
    i, n = 0, len(line)
    in_class = False
    while i < n:
        c = line[i]
        if c == "[":
            in_class = True
            i += 1
        elif c == "]":
            in_class = False
            i += 1
        elif c == "#" and not in_class:
            break  # комментарий
        elif c == '"' and not in_class:
            j = i + 1
            buf: list[str] = []
            while j < n:
                d = line[j]
                if d == "\\" and j + 1 < n and line[j + 1] in ('"', "\\"):
                    buf.append(line[j + 1])
                    j += 2
                    continue
                if d == '"':
                    break
                buf.append(d)
                j += 1
            if j >= n:
                literals.append(None)
                break
            literals.append("".join(buf))
            i = j + 1
        else:
            i += 1
    return literals


def test_all_grammar_literals_terminated_and_key_literals_exactly_quoted() -> None:
    """Структурный regression (2026-09-15): пропущенная closing-кавычка
    GBNF-литерала проглатывает соседние токены (` ws `, ` | `) как
    содержимое либо оставляет литерал незакрытым -- llama.cpp отклоняет
    всю грамматику: HTTP 400 "failed to parse grammar" (проверено живым
    сервером). Подстрочные проверки это НЕ ловят: `\\"key\\"` присутствует
    и в сломанном тексте. Проверяем ГРАНИЦЫ: каждый литерал закрыт, а
    ключевой литерал матчит ровно `"key"`.
    """
    grammars = (
        build_action_grammar(["reply", "start_tour"]),
        build_observation_grammar(["cabinet-01", "frame-02"]),
    )
    for grammar in grammars:
        for line in grammar.splitlines():
            for literal in _gbnf_literals(line):
                assert literal is not None, f"unterminated literal in {line[:60]!r}"

    for line, keys in (
        (
            next(rule for rule in grammars[0].splitlines() if rule.startswith("root ::=")),
            {"tool", "args", "confidence", "abstain"},
        ),
        (
            next(rule for rule in grammars[1].splitlines() if rule.startswith("root ::=")),
            {
                "people_count",
                "exhibit_candidates",
                "pointing_evidence",
                "pointing_box",
                "scene_facts",
            },
        ),
    ):
        literals = set(_gbnf_literals(line))
        for key in keys:
            assert f'"{key}"' in literals, key

    pointing_line = next(
        rule for rule in grammars[1].splitlines() if rule.startswith("pointing ::=")
    )
    assert {'"none"', '"yes"', '"uncertain"'} <= set(_gbnf_literals(pointing_line))
