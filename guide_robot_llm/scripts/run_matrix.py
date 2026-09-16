#!/usr/bin/env python3
"""Матричный драйвер Taiga #11: полный прогон VLM-матрицы без присмотра.

Что делает:
* берёт сетку моделей из ``scripts/matrix.json`` (по умолчанию 4 модели:
  gemma4-e2b, gemma4-e4b, qwen3.5-4b, qwen3.5-9b);
* для КАЖДОЙ модели: проверяет свободную VRAM → поднимает нативный
  ``llama-server`` (порт 11436, профиль из ``llm_server/config/models/``) →
  греет (warmup-запрос) → запускает #10-раннер
  ``python -m guide_robot_llm.eval.runner --prompt-variant all`` на
  замороженном ``eval_manifests/bench_50.jsonl`` (50 кейсов, все 18
  промпт-вариантов) → останавливает сервер;
* фиксирует состояние в ``<campaign>/state.json`` (обрыв → перезапуск
  продолжает с первой несделанной модели, раннер сам догоняет обрыв
  внутри модели по run-директориям);
* в конце собирает ``summary_matrix.csv`` / ``summary_matrix.json``
  (статусы, число вызовов, латентности по каждой модели x варианту) и
  время wall по каждой модели.

Запуск (из каталога пакета ``guide_robot_llm/``):

    # самодиагностика без GPU и без сети (mock-бэкенд, canned из gold):
    python3 scripts/run_matrix.py --mock

    # dry-run: план прогона (пути, команды сервера, команды раннера) без запусков:
    python3 scripts/run_matrix.py --dry-run

    # боевой прогон (llama-server на 11434 СТОП, свободна >=9GB VRAM):
    #   лог НЕ в /dev/null — неожиданный traceback иначе теряется:
    nohup python3 scripts/run_matrix.py \
        > eval_runs/<campaign>/nohup.log 2>&1 &

    # одна модель / один вариант (смоук перед полным прогоном):
    python3 scripts/run_matrix.py --models gemma4-e2b --variants P0

Важно (безопасность хоста): драйвер НЕ трогает llama-server на 11434
(бэкенд агента + 27B-референс) — только поднимает/убивает СВОЙ сервер
на 11436 (11435 на хосте занят API Taiga). VRAM-проверка перед каждой
моделью не даст начать, пока 11434
не остановлен и карта не освобождена (переопределение: --allow-low-vram).

Только stdlib; раннер запускается тем же интерпретатором (``requests``
обязателен для раннера — проверить: ``python3 -c "import requests"``).
"""

from __future__ import annotations

import argparse
import csv
import json
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

_PKG_ROOT = Path(__file__).resolve().parent.parent  # .../guide_robot_llm
_REPO_ROOT = _PKG_ROOT.parent
_LLM_SERVER = _REPO_ROOT / "llm_server"

# canned-генератор dry-рана (#10): gold-верные ответы на каждый кейс.
sys.path.insert(0, str(_PKG_ROOT / "eval_manifests"))
from make_bench import _mock_observation  # noqa: E402

_CANNED_ABSTAIN = (
    '{"tool": "reply", "args": {"text": "mock abstention"}, "confidence": 0.9, "abstain": true}'
)


class Campaign:
    """Состояние кампании: лог, state.json, каталог."""

    def __init__(self, campaign_dir: Path) -> None:
        """Каталог кампании, лог-файл и state.json (чтение при наличии)."""
        self.dir = campaign_dir
        self.dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.dir / "campaign.log"
        self.state_path = self.dir / "state.json"
        self.state: dict[str, Any] = {"started": _now(), "updated": _now(), "models": {}}
        if self.state_path.exists():
            self.state = json.loads(self.state_path.read_text(encoding="utf-8"))
        self._stop_flag = False

    def log(self, msg: str) -> None:
        """Напечатать строку и дописать её в campaign.log."""
        line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
        print(line, flush=True)
        with self.log_file.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def save_state(self) -> None:
        """Сохранить state.json на диск."""
        self.state["updated"] = _now()
        text = json.dumps(self.state, indent=1, ensure_ascii=False) + "\n"
        self.state_path.write_text(text, encoding="utf-8")

    def model_status(self, model_id: str) -> str:
        """Текущий статус модели (pending/running/done/failed/skipped)."""
        return str(self.state["models"].get(model_id, {}).get("status", "pending"))

    def set_model(self, model_id: str, **fields: Any) -> None:
        """Обновить поля записи модели и сохранить state.json."""
        entry = self.state["models"].setdefault(model_id, {})
        entry.update(fields)
        self.save_state()

    def request_stop(self) -> None:
        """Поставить флаг остановки (SIGTERM/SIGINT): завершить текущий этап."""
        self._stop_flag = True


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Профили сервера и VRAM
# ---------------------------------------------------------------------------


def load_profile(profile_path: Path) -> dict[str, str]:
    """``KEY=VALUE`` из .env-профиля (комментарии/# игнорируются)."""
    env: dict[str, str] = {}
    for line in profile_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip()
    return env


def profile_model_paths(profile: dict[str, str]) -> list[Path]:
    """Пути весов из профиля: `MODELS_DIR` + `MODEL_FILE`/`MM_PROJ` (с подкаталогом)."""
    models_dir = Path(profile.get("MODELS_DIR", "")).expanduser()
    paths: list[Path] = []
    for key in ("MODEL_FILE", "MM_PROJ"):
        f = profile.get(key, "")
        if f:
            paths.append(models_dir / f)
    return paths


def server_cmd(cfg: dict[str, Any], model: dict[str, Any], profile: dict[str, str]) -> list[str]:
    """Команда llama-server по профилю модели (флаги 1:1 с пилотом)."""
    models_dir = Path(profile["MODELS_DIR"]).expanduser()
    cmd = [
        cfg["llama_server_bin"],
        "-m",
        str(models_dir / profile["MODEL_FILE"]),
        "-a",
        profile.get("MODEL_ALIAS", model["id"]),
    ]
    if profile.get("MM_PROJ"):
        cmd += ["-mm", str(models_dir / profile["MM_PROJ"])]
    cmd += [
        "--host",
        cfg["host"],
        "--port",
        str(cfg["port"]),
        "--ctx-size",
        str(profile.get("CTX_SIZE", "16384")),
        "-np",
        "1",
        "-b",
        "8192",
        "-ub",
        "2048",
        "--flash-attn",
        "on",
    ]
    if profile.get("REASONING", "off").lower() == "off":
        cmd += ["--reasoning", "off"]
    return cmd


def free_vram_gb() -> float | None:
    """Свободная VRAM в ГБ (nvidia-smi); None, если GPU недоступен."""
    out = subprocess.run(
        ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    if out.returncode != 0:
        return None
    used, total = out.stdout.strip().splitlines()[0].split(", ")
    return (int(total) - int(used)) / 1024


def check_vram(camp: Campaign, model: dict[str, Any], allow_low: bool) -> None:
    """Отказаться от запуска, если свободной VRAM меньше min_free_gb."""
    need = float(model.get("min_free_gb", 6))
    free = free_vram_gb()
    if free is None:
        camp.log(f"model {model['id']}: nvidia-smi недоступен — пропуск VRAM-проверки")
        return
    if free < need:
        msg = f"model {model['id']}: свободна {free:.1f}GB < {need:.0f}GB — не запускаю сервер"
        if not allow_low:
            raise RuntimeError(
                msg + " (вероятно, на карте занят llama-server 11434/27B; остановьте его "
                "вручную или используйте --allow-low-vram)"
            )
        camp.log(msg + " — ПРопускаю проверку (--allow-low-vram)")
    else:
        camp.log(f"model {model['id']}: VRAM ok ({free:.1f}GB свободно, нужно {need:.0f}GB)")


# ---------------------------------------------------------------------------
# Живой сервер: запуск, здоровье, warmup, остановка
# ---------------------------------------------------------------------------


def start_server(cmd: list[str], log_path: Path) -> subprocess.Popen:
    """Поднять llama-server, stdout/stderr — в лог-файл."""
    with log_path.open("ab") as log:
        proc = subprocess.Popen(cmd, stdout=log, stderr=log, cwd=str(_PKG_ROOT))
    camp_log = log_path
    time.sleep(2.0)
    if proc.poll() is not None:
        tail = _tail(camp_log, 25)
        raise RuntimeError(f"llama-server упал сразу после старта ({proc.returncode}):\n{tail}")
    return proc


def _tail(path: Path, n: int) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(lines[-n:])
    except OSError:
        return "(нет лога)"


def wait_health(base_url: str, alias: str, timeout_s: int, camp: Campaign) -> None:
    """Ждать OpenAI-совместимый health (GET /v1/models) до timeout."""
    import urllib.request

    deadline = time.time() + timeout_s
    last = ""
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url}/health", timeout=5) as resp:
                body = resp.read().decode()
            if resp.status == 200:
                camp.log(f"health ok: {body[:120]}")
                return
            last = f"status {resp.status}"
        except Exception as exc:  # noqa: BLE001 — любой сбой транспорта = ещё не готов
            last = str(exc)
        time.sleep(3.0)
    raise RuntimeError(f"сервер {alias} не вышел в health за {timeout_s}s (последнее: {last})")


def warmup(base_url: str, alias: str) -> None:
    """Один короткий non-stream запрос: прогревает KV/CUDA до боевого прогона."""
    import urllib.request

    payload = json.dumps(
        {
            "model": alias,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 8,
            "stream": False,
            "temperature": 0,
        }
    ).encode()
    req = urllib.request.Request(
        f"{base_url}/chat/completions", data=payload, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        resp.read()


def stop_server(proc: subprocess.Popen | None, camp: Campaign, model_id: str) -> None:
    """Остановить сервер (TERM→KILL); чужой процесс — только зафиксировать."""
    if proc is None or proc.poll() is not None:
        return
    camp.log(f"model {model_id}: остановка llama-server (pid {proc.pid})")
    proc.terminate()
    try:
        proc.wait(timeout=60)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)
    camp.log(f"model {model_id}: сервер остановлен")


# ---------------------------------------------------------------------------
# Mock-режим: canned-ответы из gold (самопроверка драйвера без GPU)
# ---------------------------------------------------------------------------


def generate_canned(manifest_path: Path) -> dict[str, dict[str, str]]:
    """Gold-верные canned-ответы на каждый кейс (логика #10 make_bench.mock).

    Каждая фаза (freeform / observation / action) заготовлена независимо от
    нативного режима кейса: промпт-варианты (#16) перекрашивают режим
    выполнения (deployed ↔ freeform, cot_2pass, loop), и мок-бэкенд должен
    отвечать на любой из них.
    """
    canned: dict[str, dict[str, str]] = {}
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        case = json.loads(line)
        gold = case["gold"]
        answer = gold.get("target_id") or gold.get("count") or "mock"
        phases: dict[str, str] = {
            "freeform": json.dumps(
                {"answer": str(answer), "confidence": 1, "abstain": False}, ensure_ascii=False
            ),
            "observation": json.dumps(_mock_observation(gold), ensure_ascii=False),
        }
        if case["prompt"]["mode"] != "freeform" and gold.get("type") == "action":
            if "abstention_reason" in gold:
                phases["action"] = _CANNED_ABSTAIN
            else:
                action = {
                    "tool": gold["tool"],
                    "args": gold.get("args") or {},
                    "confidence": 1,
                    "abstain": False,
                }
                phases["action"] = json.dumps(action, ensure_ascii=False)
        canned[case["case_id"]] = phases
    return canned


# ---------------------------------------------------------------------------
# Прогон одной модели
# ---------------------------------------------------------------------------


def run_model(
    cfg: dict[str, Any],
    model: dict[str, Any],
    camp: Campaign,
    *,
    variant: str,
    mock: bool,
    allow_low: bool,
) -> int:
    """Один этап кампании: сервер → раннер (все варианты) → остановка."""
    model_id = model["id"]
    profile = load_profile(_LLM_SERVER / model["profile"])
    manifest = _PKG_ROOT / cfg["manifest"]
    if not manifest.exists():
        raise RuntimeError(f"нет манифеста {manifest} — сначала: python3 scripts/make_bench50.py")
    model_dir = camp.dir / f"{datetime.now().strftime('%Y-%m-%d')}-{model_id}"
    model_dir.mkdir(parents=True, exist_ok=True)
    base_url = f"http://{cfg['host']}:{cfg['port']}/v1"

    runner_cmd = [
        sys.executable,
        "-m",
        "guide_robot_llm.eval.runner",
        "--manifest",
        str(manifest),
        "--out",
        str(model_dir),
        "--data-root",
        str(_PKG_ROOT),
        "--prompt-variant",
        variant,
        "--max-attempts",
        str(cfg.get("max_attempts", 2)),
    ]
    proc: subprocess.Popen | None = None
    t0 = time.time()
    try:
        if mock:
            canned_path = camp.dir / "canned.json"
            if not canned_path.exists():
                canned_path.write_text(
                    json.dumps(generate_canned(manifest), indent=1, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
            runner_cmd += ["--mock-responses", str(canned_path)]
            camp.log(f"model {model_id}: MOCK-режим (canned: {canned_path.name})")
        else:
            check_vram(camp, model, allow_low)
            cmd = server_cmd(cfg, model, profile)
            server_log = model_dir / f"server_{model_id}.log"
            camp.log(f"model {model_id}: сервер: {cmd[0]} -m {cmd[2]} (лог: {server_log.name})")
            proc = start_server(cmd, server_log)
            health_timeout = int(cfg.get("health_timeout_s", 300))
            wait_health(base_url, profile["MODEL_ALIAS"], health_timeout, camp)
            warmup(base_url, profile["MODEL_ALIAS"])
            backend_cfg = model_dir / f"backend_{model_id}.json"
            backend_cfg.write_text(
                json.dumps(
                    {
                        "base_url": base_url,
                        "api_key": "",
                        "model_name": profile["MODEL_ALIAS"],
                        "connect_timeout_s": 5.0,
                        "read_timeout_s": float(cfg.get("read_timeout_s", 180.0)),
                        "multimodal_enabled": True,
                        "max_images": 4,
                    },
                    indent=1,
                )
                + "\n",
                encoding="utf-8",
            )
            runner_cmd += ["--backend-config", str(backend_cfg)]
        runner_log = model_dir / "runner.log"
        camp.log(f"model {model_id}: раннер: {' '.join(runner_cmd)}")
        proc_rc = subprocess.run(
            runner_cmd,
            cwd=str(_PKG_ROOT),
            stdout=runner_log.open("ab"),
            stderr=subprocess.STDOUT,
        ).returncode
        wall = time.time() - t0
        camp.set_model(
            model_id,
            status="done" if proc_rc == 0 else "failed",
            exit_code=proc_rc,
            wall_s=round(wall, 1),
            out=str(model_dir),
            finished=_now(),
        )
        if proc_rc != 0:
            camp.log(f"model {model_id}: раннер: код {proc_rc} (см. {runner_log.name})")
        return proc_rc
    finally:
        stop_server(proc, camp, model_id)


# ---------------------------------------------------------------------------
# Агрегация: все run-директории → summary_matrix
# ---------------------------------------------------------------------------


def _collect_run_dirs(model_dir: Path) -> list[tuple[str, Path]]:
    """(variant_id, dir) — run-директории раннера (маркер: run_manifest.json).

    Результаты лежат либо в model_dir (прогон одного варианта), либо в
    model_dir/<variant_id>/ (режим `--prompt-variant all`).
    """
    found: list[tuple[str, Path]] = []
    if (model_dir / "run_manifest.json").exists():
        found.append(("-", model_dir))
    for sub in sorted(model_dir.iterdir()):
        if sub.is_dir() and (sub / "run_manifest.json").exists():
            found.append((sub.name, sub))
    return found


def _read_case_lines(rdir: Path) -> list[dict[str, Any]]:
    """Строки кейсов run-директории.

    Источник: `run_manifest.json` (сырой выход раннера), а при его отсутствии
    `results.jsonl` (пост-скоринговый экспорт).
    """
    manifest = rdir / "run_manifest.json"
    if manifest.exists():
        return json.loads(manifest.read_text(encoding="utf-8"))
    results = rdir / "results.jsonl"
    if results.exists():
        return [
            json.loads(line)
            for line in results.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    return []


def score_runs(camp: Campaign) -> None:
    """Пост-скоринг (#10 scoring) по каждому run-дир: score.json + report.md.

    Ошибки скоринга не роняют кампанию (прогон сам по себе уже зафиксирован).
    """
    model_entries = camp.state.get("models", {}).values()
    for model_dir in (Path(e["out"]) for e in model_entries if e.get("out")):
        if not model_dir.exists():
            continue
        for _variant, rdir in _collect_run_dirs(model_dir):
            if (rdir / "score.json").exists():
                continue
            cmd = [
                sys.executable,
                "-m",
                "guide_robot_llm.eval.scoring",
                "--run-dir",
                str(rdir),
                "--data-root",
                str(_PKG_ROOT),
            ]
            proc = subprocess.run(cmd, cwd=str(_PKG_ROOT), capture_output=True, text=True)
            if proc.returncode != 0:
                tail = proc.stderr.strip().splitlines()[-3:]
                camp.log(f"scoring: {rdir.name}: код {proc.returncode}: {' | '.join(tail)}")
            else:
                camp.log(f"scoring: {model_dir.name}/{rdir.name} ok")


def aggregate(camp: Campaign) -> Path:
    """Итоги из state.json (model_id → out-дир) — не парсим имена каталогов."""
    rows: list[dict[str, Any]] = []
    for model_id, entry in sorted(camp.state.get("models", {}).items()):
        out = entry.get("out")
        if not out:
            continue
        model_dir = Path(out)
        if not model_dir.exists():
            camp.log(f"aggregate: каталог {model_dir} не найден (model {model_id}) — пропускаю")
            continue
        for variant, rdir in _collect_run_dirs(model_dir):
            results = _read_case_lines(rdir)
            lats = sorted(r.get("latency_ms") or 0 for r in results)
            statuses = [r.get("status") for r in results]
            rows.append(
                {
                    "model": model_id,
                    "variant": variant,
                    "n_cases": len(results),
                    "n_ok": statuses.count("ok"),
                    "n_parse_failed": statuses.count("parse_failed"),
                    "n_backend_error": statuses.count("backend_error"),
                    "latency_mean_ms": round(sum(lats) / len(lats), 1) if lats else None,
                    "latency_median_ms": round(lats[len(lats) // 2], 1) if lats else None,
                }
            )
    if not rows:
        camp.log("aggregate: run-директории с результатами не найдены")
        return camp.dir / "summary_matrix.csv"
    csv_path = camp.dir / "summary_matrix.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    json_path = camp.dir / "summary_matrix.json"
    json_path.write_text(
        json.dumps(
            {"generated": _now(), "models_wall_s": camp.state.get("models", {}), "rows": rows},
            indent=1,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    camp.log(f"aggregate: {len(rows)} строк → {csv_path.name}")
    return csv_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """CLI-входная точка; описание аргументов — в шапке модуля."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--config", default=str(_PKG_ROOT / "scripts" / "matrix.json"))
    parser.add_argument(
        "--campaign-dir", default=None, help="по умолчанию eval_runs/<дата>-matrix"
    )
    parser.add_argument("--models", default=None, help="csv-список id (все enabled)")
    parser.add_argument("--variants", default="all", help="'all' или id одного варианта")
    parser.add_argument("--dry-run", action="store_true", help="показать план и команды")
    parser.add_argument("--mock", action="store_true", help="без сервера: canned-ответы из gold")
    parser.add_argument("--skip-missing", action="store_true", help="пропустить модели без весов")
    parser.add_argument("--force", action="store_true", help="перепускать модели с status=done")
    parser.add_argument(
        "--allow-low-vram", action="store_true", help="игнорировать низкий свободный VRAM"
    )
    args = parser.parse_args(argv)

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    if args.campaign_dir:
        campaign_dir = Path(args.campaign_dir)
    else:
        suffix = "-mock" if args.mock else ""
        date = datetime.now().strftime("%Y-%m-%d")
        campaign_dir = _PKG_ROOT / "eval_runs" / f"{date}-matrix{suffix}"
    camp = Campaign(campaign_dir)
    camp.log(f"кампания: {campaign_dir} (mock={args.mock}, variant={args.variants})")

    models = [m for m in cfg["models"] if m.get("enabled", True)]
    if args.models:
        wanted = {m.strip() for m in args.models.split(",") if m.strip()}
        models = [m for m in models if m["id"] in wanted]
        if not models:
            parser.error(f"--models: ни одна модель из {sorted(wanted)} не найдена/не enabled")

    # Проверка весов до каких-либо запусков (fail-fast со списком всех дыр).
    missing: list[str] = []
    for model in models:
        profile = load_profile(_LLM_SERVER / model["profile"])
        for path in profile_model_paths(profile):
            if not path.exists():
                missing.append(f"{model['id']}: {path}")
    missing_ids = {m.split(":", 1)[0] for m in missing}
    if args.mock:
        camp.log("mock-режим: проверка весов не нужна (сервер не поднимается)")
    elif missing:
        text = "отсутствующие веса:\n  " + "\n  ".join(missing)
        if args.dry_run:
            camp.log("PLAN-предупреждение: " + text.replace("\n", "; "))
        elif args.skip_missing:
            models = [m for m in models if m["id"] not in missing_ids]
            camp.log(f"--skip-missing: пропускаю {sorted(missing_ids)}")
        else:
            raise SystemExit(text)
    if not args.dry_run and not args.mock and not models:
        raise SystemExit("после --skip-missing не осталось моделей с весами")

    if args.dry_run:
        manifest = _PKG_ROOT / cfg["manifest"]
        n_cases = sum(
            1 for line in manifest.read_text(encoding="utf-8").splitlines() if line.strip()
        )
        camp.log(
            f"PLAN: {manifest} ({n_cases} кейсов), порт {cfg['port']}, variant={args.variants}"
        )
        for model in models:
            profile = load_profile(_LLM_SERVER / model["profile"])
            cmd = server_cmd(cfg, model, profile)
            status = camp.model_status(model["id"])
            mark = "SKIP(done)" if status == "done" and not args.force else "RUN"
            camp.log(f"  {mark} {model['id']}: {' '.join(cmd)}")
        camp.log(
            f"PLAN: раннер: {sys.executable} -m guide_robot_llm.eval.runner --manifest ... "
            f"--prompt-variant {args.variants} (по 1 вызову на кейс+фазу; loop ≤3)"
        )
        return 0

    _install_signal_handlers(camp)

    failures = 0
    for model in models:
        if camp._stop_flag:
            camp.log("стоп-сигнал — завершаю кампанию")
            break
        if not args.force and camp.model_status(model["id"]) == "done":
            camp.log(f"model {model['id']}: done — пропускаю (переопределение: --force)")
            continue
        camp.set_model(model["id"], status="running", started=_now())
        try:
            rc = run_model(
                cfg,
                model,
                camp,
                variant=args.variants,
                mock=args.mock,
                allow_low=args.allow_low_vram,
            )
            if rc != 0:
                failures += 1
        except Exception as exc:  # noqa: BLE001 — безприсмотрный прогон: фиксация и далее
            camp.log(f"model {model['id']}: ОШИБКА: {exc}")
            camp.set_model(model["id"], status="failed", error=str(exc))
            failures += 1

    score_runs(camp)
    csv_path = aggregate(camp)
    camp.log(f"кампания завершена: провалов моделей: {failures}; итоги: {csv_path}")
    return 1 if failures else 0


def _install_signal_handlers(camp: Campaign) -> None:
    def _handler(signum: int, _frame: Any) -> None:
        camp.log(f"сигнал {signum} — останавливаюсь (state сохранён, перезапуск продолжит)")
        camp.request_stop()

    signal.signal(signal.SIGTERM, _handler)
    signal.signal(signal.SIGINT, _handler)


if __name__ == "__main__":
    raise SystemExit(main())
