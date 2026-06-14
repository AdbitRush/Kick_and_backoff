# Kick_and_backoff

**Kickbacks arbitrage engine — best of Kick_Ai + kickbacks-multi-instance.**

Routes Claude Code through OpenRouter's free models (Nemotron 550B, Llama 70B, Qwen3 Coder) while
Kickbacks.ai generates ad revenue from the thinking spinner. Zero AI cost, 100% arbitrage margin.

```
You / Claude Code  →  proxy :5555  →  Free models (OpenRouter)
                                    ↓
                             Kickbacks ads  →  50% revenue → You
```

## Quick Start

```bash
export OPENROUTER_API_KEY='sk-or-...'
python3 proxy/arbitrage.py
```

In a new terminal:

```bash
export ANTHROPIC_BASE_URL=http://127.0.0.1:5555
export ANTHROPIC_AUTH_TOKEN='any-value'
claude
```

**Full setup guide → [MANUAL.md](./MANUAL.md)**

## Components

| Path | Purpose |
|------|---------|
| `proxy/arbitrage.py` | Anthropic → OpenRouter protocol bridge |
| `worker/intd-config.json` | Timing knobs (thinkSec, brakeSec, pauses) |
| `tracker/dashboard.py` | Full P&L dashboard with projections |
| `tracker/cost_report.py` | Per-query table, `--date`, `--csv` |
| `tracker/current_cost_report.py` | Quick snapshot |
| `scripts/health.py` | Proxy health + stats |
| `scripts/run_instances.sh` | Launch N parallel workers |

## Track Earnings

```bash
python3 tracker/dashboard.py
python3 tracker/current_cost_report.py
python3 tracker/cost_report.py --date $(date +%F) --csv today.csv
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENROUTER_API_KEY` | required | Your OpenRouter key |
| `PROXY_PORT` | `5555` | Proxy listen port |
| `LEDGER_PATH` | `/tmp/kickbacks_ledger.jsonl` | Query log |
| `KICKBACKS_CPM` | `5.0` | CPM rate for revenue estimates |
