#!/usr/bin/env bash
# Taiga #16 P7: запуск матричного прогона 18 промпт-вариантов на 4 малых
# моделях-кандидатах (#11: gemma4-e2b, gemma4-e4b, qwen3.5-4b, qwen3.5-9b)
# — выделенный llama-server на порту 11436, --reasoning off, по модели
# (драйвер сам поднимает/гасит сервер на каждый run).
#
# Требование: llama-server на 11434 (27B, бэкенд агента) СТОП — он держит
# ~21GB из 24GB VRAM, а малым моделям нужно до ~9GB; при живом 11434 места
# не хватает. Если карта не освобождена, скрипт отказывается запускать.
#
# Запуск (из каталога пакета guide_robot_llm/):
#   bash scripts/run_pv16_matrix.sh
#
# Наблюдение:
#   tail -f eval_runs/2026-09-16-pv16-small/campaign.log
#   cat   eval_runs/2026-09-16-pv16-small/state.json
#
# Завершение: в state.json у всех четырёх моделей "status": "done", в
# campaign.log — строка «кампания завершена». Тогда llama-server на 11434
# запускается обратно (стандартной командой), агент продолжает с отчётом.
# Оценка длительности: ~35–45 мин (4 сервера по 18 variant-run на 57 кейсах).
set -euo pipefail
cd "$(dirname "$0")/.."

CAMPAIGN_DIR="eval_runs/2026-09-16-pv16-small"
mkdir -p "$CAMPAIGN_DIR"

free_mi=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits)
if [ "$free_mi" -lt 10240 ]; then
  echo "ОТКАЗ: свободна VRAM ${free_mi}MiB < 10240MiB." >&2
  echo "Сначала остановите llama-server на 11434 (27B, бэкенд агента) и повторите." >&2
  exit 1
fi
echo "Свободна VRAM: ${free_mi}MiB — запуск кампании ($CAMPAIGN_DIR)"

nohup python3 scripts/run_matrix.py \
  --config scripts/matrix_pv16.json \
  --campaign-dir "$CAMPAIGN_DIR" \
  > "$CAMPAIGN_DIR/nohup.log" 2>&1 &
echo "Кампания pid $! — state: $CAMPAIGN_DIR/state.json, лог: $CAMPAIGN_DIR/campaign.log"
echo "После завершения (state.json: status=done) запустите llama-server на 11434 обратно."
