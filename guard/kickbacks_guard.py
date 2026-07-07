"""
Kickbacks Guard — session watchdog. Never lose ad money to a silent logout again.

The problem: the Kickbacks session/extension logs out silently; the proxy keeps
running, the spinner spins, and nobody earns anything until you notice days later.

What this does, every check (default: every 30 min):
  1. Opens kickbacks.ai/me in a PERSISTENT headless browser profile
     (guard/profile/). Regular visits keep the session cookie fresh, so the
     guard's own session effectively never expires.
  2. If logged OUT → auto re-login with KICKBACKS_USER / KICKBACKS_PASS from
     kickbacks_settings.env (same file kickbacks_fetch.py already uses).
  3. If re-login fails (or Google-only auth) → LOUD ALERT:
     Windows toast + optional Telegram + guard/status.json goes red.
  4. Records the balance to guard/ledger.jsonl. If the proxy (:5555/stats)
     served queries since the last check but the balance did NOT move,
     that means the EXTENSION in your real browser is logged out even though
     the site session works → separate loud alert telling you to re-login
     in Chrome.

Run:
  python guard/kickbacks_guard.py --once      # single check (cron/Task Scheduler)
  python guard/kickbacks_guard.py --daemon    # loop forever (interval below)
  python guard/kickbacks_guard.py --status    # print last status.json

Install as a Windows scheduled task:  powershell guard/install_guard_task.ps1
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:  # Windows consoles default to cp1252 — don't let an emoji kill an alert
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
GUARD_DIR = Path(__file__).resolve().parent
PROFILE_DIR = GUARD_DIR / "profile"
STATUS_FILE = GUARD_DIR / "status.json"
LEDGER_FILE = GUARD_DIR / "ledger.jsonl"

BASE = "https://kickbacks.ai"
PROXY_STATS = "http://127.0.0.1:5555/stats"
CHECK_INTERVAL_MIN = int(os.getenv("GUARD_INTERVAL_MIN", "30"))

ENV_CANDIDATES = [
    ROOT / "kickbacks_settings.env",
    Path("/root/.openclaw/workspace/kickbacks_settings.env"),
]


def load_env() -> None:
    for envf in ENV_CANDIDATES:
        if envf.is_file():
            for line in envf.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
            return


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ── Alerts ────────────────────────────────────────────────────────────────────
def toast(title: str, msg: str) -> None:
    """Native notification: Windows toast / Linux notify-send. Never raises."""
    try:
        if sys.platform == "win32":
            ps = f"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$xml = @"
<toast scenario='urgent'><visual><binding template='ToastGeneric'>
<text>{title}</text><text>{msg}</text>
</binding></visual><audio src='ms-winsoundevent:Notification.Looping.Alarm2' loop='false'/></toast>
"@
$doc = New-Object Windows.Data.Xml.Dom.XmlDocument
$doc.LoadXml($xml)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Kickbacks Guard').Show($doc)
"""
            subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                           capture_output=True, timeout=20)
        else:
            subprocess.run(["notify-send", "-u", "critical", title, msg],
                           capture_output=True, timeout=10)
    except Exception:
        pass


def telegram(msg: str) -> None:
    """Optional: set GUARD_TG_TOKEN + GUARD_TG_CHAT in kickbacks_settings.env."""
    token, chat = os.getenv("GUARD_TG_TOKEN"), os.getenv("GUARD_TG_CHAT")
    if not token or not chat:
        return
    try:
        import requests
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id": chat, "text": msg}, timeout=10)
    except Exception:
        pass


def alert(title: str, msg: str) -> None:
    print(f"🚨 {title}: {msg}")
    toast(title, msg)
    telegram(f"🚨 {title}\n{msg}")


# ── Proxy activity ────────────────────────────────────────────────────────────
def proxy_queries() -> int | None:
    """Total queries served by the arbitrage proxy, or None if proxy is down."""
    try:
        import requests
        r = requests.get(PROXY_STATS, timeout=4)
        d = r.json()
        for key in ("queries", "total_queries", "requests"):
            if key in d:
                return int(d[key])
        return 0
    except Exception:
        return None


# ── Browser session check ─────────────────────────────────────────────────────
def check_session() -> dict:
    """Returns {logged_in, balance, relogin_attempted, relogin_ok, error}."""
    from playwright.sync_api import sync_playwright

    result = {"logged_in": False, "balance": None,
              "relogin_attempted": False, "relogin_ok": False, "error": None}
    user, pw = os.getenv("KICKBACKS_USER"), os.getenv("KICKBACKS_PASS")

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(str(PROFILE_DIR), headless=True)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            page.goto(f"{BASE}/me", wait_until="networkidle", timeout=45000)

            def is_logged_in() -> bool:
                if "/login" in page.url or "/signin" in page.url:
                    return False
                # a login form on the page means we were bounced
                return not page.query_selector('input[type="password"]')

            if not is_logged_in() and user and pw:
                result["relogin_attempted"] = True
                page.goto(f"{BASE}/login", wait_until="networkidle", timeout=45000)
                email_el = (page.query_selector('input[name="email"]')
                            or page.query_selector('input[type="email"]'))
                pass_el = page.query_selector('input[type="password"]')
                if email_el and pass_el:
                    email_el.fill(user)
                    pass_el.fill(pw)
                    # submit buttons on kickbacks.ai stay disabled until a JS
                    # validation tick — pressing Enter in the password field is
                    # the reliable path; clicking is only a fallback.
                    try:
                        pass_el.press("Enter")
                        page.wait_for_load_state("networkidle", timeout=45000)
                    except Exception:
                        btn = (page.query_selector('button[type="submit"]:not([disabled])')
                               or page.query_selector("button:not([disabled])"))
                        if btn:
                            btn.click(timeout=10000)
                            page.wait_for_load_state("networkidle", timeout=45000)
                    page.goto(f"{BASE}/me", wait_until="networkidle", timeout=45000)
                    result["relogin_ok"] = is_logged_in()

            result["logged_in"] = is_logged_in()

            if result["logged_in"]:
                # best-effort balance scrape: first $-number on /me
                import re
                text = page.inner_text("body")
                m = re.search(r"\$\s*([0-9][0-9,]*\.?[0-9]*)", text)
                if m:
                    result["balance"] = float(m.group(1).replace(",", ""))
        except Exception as e:
            result["error"] = str(e)[:300]
        finally:
            ctx.close()
    return result


# ── Ledger + correlation ──────────────────────────────────────────────────────
def last_ledger() -> dict | None:
    try:
        lines = LEDGER_FILE.read_text(encoding="utf-8").strip().splitlines()
        return json.loads(lines[-1]) if lines else None
    except Exception:
        return None


def append_ledger(entry: dict) -> None:
    with LEDGER_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def run_check() -> dict:
    load_env()
    prev = last_ledger()
    sess = check_session()
    queries = proxy_queries()

    status = {
        "ts": now_iso(),
        "logged_in": sess["logged_in"],
        "balance": sess["balance"],
        "relogin_attempted": sess["relogin_attempted"],
        "relogin_ok": sess["relogin_ok"],
        "proxy_queries": queries,
        "error": sess["error"],
        "ok": sess["logged_in"] and not sess["error"],
        "alerts": [],
    }

    # Alert 1: logged out and could not recover
    if not sess["logged_in"]:
        if sess["relogin_attempted"] and sess["relogin_ok"]:
            pass  # recovered silently — that's the whole point
        else:
            status["alerts"].append("logged_out")
            alert("Kickbacks LOGGED OUT",
                  "Auto re-login failed or no credentials set. "
                  "Open kickbacks.ai and sign in NOW — you are earning nothing.")
    elif sess["relogin_attempted"] and sess["relogin_ok"]:
        status["alerts"].append("recovered")
        toast("Kickbacks Guard", "Session had expired — auto re-login succeeded ✅")

    # Alert 2: proxy active but balance flat → extension (real browser) logged out
    if (sess["logged_in"] and prev and sess["balance"] is not None
            and prev.get("balance") is not None
            and queries is not None and prev.get("proxy_queries") is not None
            and queries > prev["proxy_queries"]
            and sess["balance"] <= prev["balance"]):
        status["alerts"].append("earning_stalled")
        alert("Kickbacks NOT EARNING",
              f"Proxy served {queries - prev['proxy_queries']} queries since last "
              f"check but balance is stuck at ${sess['balance']:.2f}. "
              "The browser EXTENSION is probably logged out — re-login in Chrome.")

    append_ledger(status)
    STATUS_FILE.write_text(json.dumps(status, indent=2), encoding="utf-8")
    return status


def main() -> None:
    ap = argparse.ArgumentParser(description="Kickbacks session watchdog")
    ap.add_argument("--once", action="store_true", help="run one check and exit")
    ap.add_argument("--daemon", action="store_true", help="loop forever")
    ap.add_argument("--status", action="store_true", help="print last status")
    args = ap.parse_args()

    if args.status:
        print(STATUS_FILE.read_text(encoding="utf-8") if STATUS_FILE.exists()
              else "no status yet — run --once first")
        return

    if args.daemon:
        print(f"Kickbacks Guard daemon — checking every {CHECK_INTERVAL_MIN} min")
        while True:
            s = run_check()
            print(f"[{s['ts']}] logged_in={s['logged_in']} balance={s['balance']} "
                  f"alerts={s['alerts'] or 'none'}")
            time.sleep(CHECK_INTERVAL_MIN * 60)
    else:
        s = run_check()
        print(json.dumps(s, indent=2))
        sys.exit(0 if s["ok"] else 1)


if __name__ == "__main__":
    main()
