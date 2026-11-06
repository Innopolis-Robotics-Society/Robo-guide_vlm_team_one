# Design

## Context

See proposal.md — Why. Under the project's own CI conditions (`fabook/iros:x86-cpu`, pytest 8.4.2, `colcon build` + `colcon test --return-code-on-test-failure`), 22 lint checks fail: uncrustify ×3 in `guide_robot_hardware`, uncrustify + cpplint legal/copyright + copyright in `guide_robot_bt_nodes/src/say_action.cpp`, flake8 E402 ×7 + pep257 D213 ×3 in `guide_robot_sonar/scripts/`. All functional tests pass; only the lint gate is red.

## Goals / Non-Goals

**Goals:**
- `colcon test --return-code-on-test-failure` exits 0 in `fabook/iros:x86-cpu`.

**Non-Goals:**
- Any functional change — formatting, copyright headers, and import ordering only.
- Relaxing lint configuration to make failures disappear (the config is the contract).

## Decisions

1. **Fix the code, not the linter.** Each failure is a real deviation from the project's own `.clang-format`/`.clang-tidy`/ruff/copyright rules. Formatting via the project tools (`uncrustify` per `.clang-format`, ruff for the Python files) keeps the diff mechanical.
2. **E402 in `sonar_node_mult.py`**: move the `sys.path` bootstrap before all non-`__future__`/standard imports, or guard it so module imports precede code — whichever the file's structure allows without changing behavior. The `sys.path` insert must stay (it is load-bearing for the `furo_sonars_cpp` layout described in CLAUDE.md); only its position relative to imports changes.

## Risks / Trade-offs

- [Reformatting a C++ file touches many lines] → run the project's uncrustify config, review the diff for semantic neutrality, rely on the existing test suite.
- [E402 fix changes import order] → verify `sonar_node_mult.py` still imports `furo_sonars_cpp` correctly (pure-Python test suite + flake8).

## Migration Plan

Per-package fixes, each verified by `colcon test --packages-select <pkg>`; final full-flow check at the end.

## Open Questions

None.
