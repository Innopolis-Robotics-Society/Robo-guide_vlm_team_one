#!/usr/bin/env bash
# Taiga #16 P7: запуск матричного прогона 18 промпт-вариантов на production
# Qwen3.8-27B — выделенный llama-server на порту 11436, --reasoning off.
#
# Требование: llama-server на 11434 (27B, бэкенд агента) СТОП — он держит
# ~21GB из 24GB VRAM, выделенный сервер 27B в карту не влезет. Если карта не
# освобождена, скрипт отказывается запускать кампанию.
#
# Запуск (из каталога пакета guide_robot_llm/):
#   bash scripts/run_pv16_matrix.sh
#
# Наблюдение:
#   tail -f eval_runs/2026-09-16-pv16-qwen3.8-27b/campaign.log
#   cat   eval_runs/2026-09-16-pv16-qwen3.8-27b/state.json
#
# Завершение: в state.json у модели qwen3.8-27b "status": "done", в
# campaign.log — строка "кампания завершена". Тогда llama-server на 11434
# запускается обратно (стандартной командой), агент продолжает с отчётом.
set -euo pipefail
cd "$(dirname "$0")/.."

CAMPAIGN_DIR="eval_runs/2026-09-16-pv16-qwen3.8-27b"
mkdir -p "$CAMPAIGN_DIR"

free_mi=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits)
if [ "$free_mi" -lt 20480 ]; then
  echo "ОТКАЗ: свободна VRAM ${free_mi}MiB < 20480MiB." >&2
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
