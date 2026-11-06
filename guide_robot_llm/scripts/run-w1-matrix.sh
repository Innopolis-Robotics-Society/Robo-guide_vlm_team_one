#!/usr/bin/env bash
# W1-fix pointing matrix — один bounded GPU-запуск (Taiga, ветка fix/eval-w1-pointing-final-choice).
#
# Что делает:
#   1. Проверяет, что локальный llama-server (:11434) остановлен (он держит ~20 GB
#      VRAM; matrix-драйвер откажется поднимать модели ниже min-free-VRAM).
#   2. Запускает `run_matrix.py --config scripts/matrix_w1_fix.json` — 8 ног:
#      {egopoint_15, pointing_holdout_15} × {P3, P0, P4, baseline}, 16 модель-запусков.
#   3. Каждый запуск: свой llama-server на :11436 + 15 кейсов + остановка.
#      Прогон resuming: state.json в campaign-дире, повторный запуск продолжает.
#
# Использование:
#   bash scripts/run-w1-matrix.sh            # полный прогон
#   bash scripts/run-w1-matrix.sh --dry-run  # только план (без GPU)
#
# Ожидается 2–4 ч. Это НЕ фоновая задача: запускать, когда машина свободна.
set -euo pipefail
cd "$(dirname "$0")/.."

# Передаём доп. аргументы (например --dry-run) дальше в run_matrix.py.
MAPFILE_CMD=(python3 scripts/run_matrix.py --config scripts/matrix_w1_fix.json "$@")

# GPU-гейт не нужен для --dry-run/--mock (сервер не поднимается).
NEEDS_GPU=1
for a in "$@"; do
  case "$a" in --dry-run | --mock) NEEDS_GPU=0 ;; esac
done

# Мягкий пред-гейт: если :11434 жив, почти наверняка не хватит VRAM.
if [ "$NEEDS_GPU" -eq 1 ] && command -v ss >/dev/null 2>&1; then
  if ss -ltn 2>/dev/null | awk '{print $4}' | grep -qE '(:|^)11434$'; then
    echo "ОШИБКА: что-то слушает :11434 (локальный llama-server?). Он держит ~20 GB VRAM."
    echo "Остановите его (~/starters/ скрипты), затем запустите этот скрипт снова."
    echo "(--dry-run не требует GPU: bash scripts/run-w1-matrix.sh --dry-run)"
    exit 1
  fi
fi

echo "Запускаю W1-fix pointing matrix: ${MAPFILE_CMD[*]}"
exec "${MAPFILE_CMD[@]}"
