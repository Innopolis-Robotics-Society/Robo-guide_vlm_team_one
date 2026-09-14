"""Офлайн-харнес оценки VLM (Taiga #10, план vlm-bench-50).

Диагностика только: воспроизведение пилотных эпизодов + 50 внешних
кейсов, запись выходов, срезы метрик. Без финальных оценок и без
подбора промптов на замороженных наборах (это #11). Дизайн:
`docs/eval_harness_design.md`.
"""

from guide_robot_llm.eval.schema import (
    PROMPT_MODES,
    SOURCES,
    TRACKS,
    Case,
    CaseError,
    MediaRef,
    PromptSpec,
    Provenance,
    case_from_dict,
    case_to_dict,
)

__all__ = [
    "PROMPT_MODES",
    "SOURCES",
    "TRACKS",
    "Case",
    "CaseError",
    "MediaRef",
    "PromptSpec",
    "Provenance",
    "case_from_dict",
    "case_to_dict",
]
