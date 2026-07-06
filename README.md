# Kick_and_backoff

**Kickbacks arbitrage engine — zero-cost AI + ad revenue from your coding sessions.**

Routes Claude Code through free OpenRouter models (Nemotron 550B, Llama 70B, Qwen3 Coder).
You pay $0. The thinking spinner still runs. Kickbacks.ai pays you 50% of ad revenue.

```
Claude Code → proxy :5555 → OpenRouter (free) → Response
                   ↓
            Kickbacks ads → 50% revenue → You
```

---

## Install (one command, fresh Linux VPS)

```bash
git clone https://github.com/AdbitRush/Kick_and_backoff.git ~/kickbacks
bash ~/kickbacks/install.sh
```

That's it. The installer:
- Installs Python 3, Node.js 20, Claude Code CLI
- Prompts for your OpenRouter API key
- Starts the proxy as a systemd service (survives reboot)
- Installs the `kickbacks` CLI

**Requirements:** Ubuntu 20.04+ / Debian 11+ / any systemd Linux. 512MB RAM minimum.

## 🛡 Kickbacks Guard — never lose money to a silent logout

The session/extension used to log out silently: proxy runs, nothing earns.
`guard/kickbacks_guard.py` fixes that:

- checks kickbacks.ai/me every 30 min in a **persistent headless profile** (visits keep the session alive)
- if logged out → **auto re-login** from `kickbacks_settings.env`
- if it can't recover → **Windows toast + optional Telegram alert** (set `GUARD_TG_TOKEN` + `GUARD_TG_CHAT`)
- tracks balance in `guard/ledger.jsonl`; if the proxy served queries but balance is flat → "extension logged out" alert
- `--once` (cron / Task Scheduler) · `--daemon` (PM2) · `--status`

Running now on this machine as PM2 app `kickbacks-guard` (`pm2 save`d, resurrects at logon).
Alternative install: `powershell -ExecutionPolicy Bypass -File guard\install_guard_task.ps1` (needs admin).

---

## Daily Use

```bash
# Tell Claude Code to use the proxy
kickbacks use          # prints the two export commands to paste

# Then just work normally
claude

# Check earnings anytime
kickbacks dashboard    # full P&L
kickbacks snapshot     # quick numbers
kickbacks stats        # live proxy JSON
```

---

## CLI Reference

```
kickbacks start            Start proxy (+ --brake for coffee brake daemon)
kickbacks stop             Stop everything
kickbacks status           Service health + live stats
kickbacks dashboard        Full P&L dashboard with projections
kickbacks snapshot         Quick cost/revenue snapshot
kickbacks report           Per-query table (--date YYYY-MM-DD, --csv out.csv)
kickbacks logs proxy       Tail proxy log
kickbacks logs brake       Tail coffee brake log
kickbacks brake-start      Start coffee brake daemon
kickbacks brake-stop       Stop coffee brake daemon
kickbacks health           Quick proxy health check
kickbacks use              Print env vars to paste into your shell
kickbacks update           Pull latest code + restart services
kickbacks env              Show current .env
```

---

## Components

| File | Purpose |
|------|---------|
| `install.sh` | One-command installer |
| `proxy/arbitrage.py` | Anthropic → OpenRouter bridge. `GET /stats` for live data |
| `scripts/coffee-brake.py` | Human-mimicking query daemon (`--daemon / --health / --stop`) |
| `scripts/health.py` | Proxy health + ledger summary |
| `scripts/run_instances.sh` | Launch N parallel browser workers |
| `tracker/dashboard.py` | Full P&L (cost, revenue, margin, projections) |
| `tracker/cost_report.py` | Per-query detail with `--date` and `--csv` |
| `tracker/current_cost_report.py` | Quick snapshot |
| `worker/intd-config.json` | Timing config for worker (thinkSec, brakeSec, pauses) |
| `docs/terms-analysis.md` | ToS §6.2 breakdown + practical rules |
| `MANUAL.md` | Full setup and usage guide |
| `SESSION.md` | What was built and what's left to do |

---

## Free Models Used

| Model | Params | Speed | Impressions |
|-------|--------|-------|-------------|
| Nemotron 550B | 550B | Slowest | Highest |
| Llama 3.3-70B | 70B | Slow | High |
| Qwen3 Coder | 72B | Medium | Medium |
| Qwen2.5-72B | 72B | Medium | Medium |

Slow = longer thinking time = more ad impressions = more revenue. All free.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENROUTER_API_KEY` | required | Your OpenRouter key |
| `PROXY_PORT` | `5555` | Proxy listen port |
| `LEDGER_PATH` | `~/kickbacks_ledger.jsonl` | Query log file |
| `KICKBACKS_CPM` | `5.0` | CPM rate for revenue estimates |
| `CLAUDE_WORKDIR` | `~/testproj` | Working dir for coffee-brake queries |

---

## Update

```bash
kickbacks update
```

Or manually: `git -C ~/kickbacks pull && kickbacks restart`
