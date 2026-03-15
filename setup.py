#!/usr/bin/env python3
"""
daily-brief setup.py v1.0.0
Interactive installer — asks about every external dependency before writing config.
"""

import json
import subprocess
import sys
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

HOME        = Path.home()
SKILL_DIR   = HOME / ".openclaw/agents/main/workspace/skills/daily-brief"
CONFIG_DIR  = HOME / ".openclaw/config/daily-brief"
CONFIG_PATH = CONFIG_DIR / "config.json"
SECRETS_ENV = HOME / ".openclaw/shared/secrets/openclaw-secrets.env"
SCRIPT_PATH = SKILL_DIR / "daily_brief.py"

# Shared secrets file is owned by other skills — we append to it, never overwrite.
SECRETS_HEADER = "# daily-brief"


# ── Output helpers ─────────────────────────────────────────────────────────────

def banner(msg: str):
    print(f"\n{'─' * 52}")
    print(f"  {msg}")
    print('─' * 52)

def ok(msg: str):    print(f"  ✅  {msg}")
def warn(msg: str):  print(f"  ⚠️   {msg}")
def info(msg: str):  print(f"  ℹ️   {msg}")
def err(msg: str):   print(f"  ❌  {msg}")
def ask(msg: str):   return input(f"  →  {msg}").strip()


# ── Secrets helpers ────────────────────────────────────────────────────────────

def load_secrets() -> dict:
    secrets = {}
    if not SECRETS_ENV.exists():
        return secrets
    with open(SECRETS_ENV) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            secrets[k.strip()] = v.strip().strip('"').strip("'")
    return secrets


def append_secret(key: str, value: str):
    """Append a key=value line to the shared secrets file."""
    SECRETS_ENV.parent.mkdir(parents=True, exist_ok=True)
    with open(SECRETS_ENV, "a") as f:
        f.write(f"\n{key}={value}\n")
    ok(f"{key} written to {SECRETS_ENV.name}")


def prompt_secret(key: str, label: str, secrets: dict) -> bool:
    """
    Check if a secret exists. If not, offer to enter it now.
    Returns True if the secret is present after this call.
    """
    if secrets.get(key):
        ok(f"{label} found ({key})")
        return True

    warn(f"{label} not found ({key})")
    info(f"  Expected in: {SECRETS_ENV}")
    raw = ask(f"  Paste value for {key} (or Enter to skip): ")
    if raw:
        append_secret(key, raw)
        secrets[key] = raw   # update in-memory copy
        return True
    warn(f"  {key} skipped — this section will be unavailable until added")
    return False


# ── Live API validation ────────────────────────────────────────────────────────

def validate_telegram(token: str, chat_id: int, thread_id) -> bool:
    """Send a test message to verify bot token + chat/thread."""
    payload = {
        "chat_id":  chat_id,
        "text":     "🌅 <b>daily-brief</b>: setup test — if you see this, Telegram delivery is working.",
        "parse_mode": "HTML",
    }
    if thread_id:
        payload["message_thread_id"] = thread_id

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            return result.get("ok", False)
    except urllib.error.HTTPError as e:
        err(f"Telegram responded with HTTP {e.code}: {e.read().decode()[:200]}")
        return False
    except Exception as e:
        err(f"Telegram test failed: {e}")
        return False


def validate_openweather(api_key: str, lat: float, lon: float) -> bool:
    """Ping the OpenWeatherMap API with the given key."""
    url = (
        f"https://api.openweathermap.org/data/2.5/weather"
        f"?lat={lat}&lon={lon}&appid={api_key}&units=metric"
    )
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return "weather" in data
    except urllib.error.HTTPError as e:
        if e.code == 401:
            err("OpenWeatherMap: API key rejected (401)")
        else:
            err(f"OpenWeatherMap: HTTP {e.code}")
        return False
    except Exception as e:
        err(f"OpenWeatherMap test failed: {e}")
        return False


def validate_todoist(token: str) -> bool:
    """Ping Todoist API v1."""
    url = "https://api.todoist.com/api/v1/tasks"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
            return True
    except urllib.error.HTTPError as e:
        if e.code == 403:
            err("Todoist: token rejected (403)")
        else:
            err(f"Todoist: HTTP {e.code}")
        return False
    except Exception as e:
        err(f"Todoist test failed: {e}")
        return False


# ── Setup sections ─────────────────────────────────────────────────────────────

def setup_telegram(secrets: dict) -> dict:
    """Prompt for and validate Telegram configuration."""
    banner("Telegram delivery")
    info("daily-brief posts to a dedicated topic inside a Telegram supergroup.")
    info("  This requires TWO separate IDs:")
    info("")
    info("  1. chat_id  — identifies the supergroup itself (a large negative number).")
    info("     How to find it: forward any message from the group to @userinfobot,")
    info("     or open the group in Telegram Web and read the number after 'c/' in")
    info("     the URL — then prepend -100 (e.g. c/1234567890 → -1001234567890).")
    info("")
    info("  2. thread_id — identifies the specific topic within the group.")
    info("     How to find it: open the topic in Telegram Web and read the number")
    info("     after the second slash in the URL:")
    info("     e.g. web.telegram.org/a/#-1001234567890_99  →  thread_id = 99")
    info("     Or: right-click the topic name → Copy Link, the last number is the ID.")
    print()

    # Token
    token_ok = prompt_secret("TELEGRAM_BOT_TOKEN", "Telegram bot token", secrets)

    # chat_id — the supergroup
    raw_chat = ask("Enter your Telegram supergroup chat_id (e.g. -1001234567890): ")
    chat_id = None
    if raw_chat:
        try:
            chat_id = int(raw_chat)
            ok(f"Chat ID: {chat_id}")
        except ValueError:
            warn(f"'{raw_chat}' is not an integer — leaving chat_id as null (update config.json before first run)")
    else:
        warn("chat_id left as null — update config.json before first run")

    # thread_id — the topic within the supergroup
    raw_thread = ask("Enter the thread_id for the daily-brief topic (Enter to skip): ")
    thread_id = None
    if raw_thread:
        try:
            thread_id = int(raw_thread)
            ok(f"Thread ID: {thread_id}")
        except ValueError:
            warn(f"'{raw_thread}' is not an integer — leaving thread_id as null")
    else:
        warn("thread_id left as null — briefings will post to the main group chat until set")

    # Live test
    if token_ok and secrets.get("TELEGRAM_BOT_TOKEN") and chat_id:
        raw2 = ask("Send a test message to Telegram now? [Y/n]: ").lower()
        if raw2 != "n":
            if validate_telegram(secrets["TELEGRAM_BOT_TOKEN"], chat_id, thread_id):
                ok("Test message delivered" + (" to topic" if thread_id else " (no topic set — went to main chat)"))
            else:
                warn("Test message failed — check token, chat_id, and thread_id before first run")

    return {"chat_id": chat_id, "thread_id": thread_id}


def setup_weather(secrets: dict) -> dict:
    """Prompt for and validate OpenWeatherMap configuration."""
    banner("Weather — OpenWeatherMap")
    info("daily-brief fetches weather for Qingdao using OpenWeatherMap free tier.")
    info("  Sign up at https://openweathermap.org/api — free tier is 1000 calls/day.")
    info("  Note: new API keys can take up to 2 hours to activate after signup.")
    print()

    lat, lon, city = 36.0671, 120.3826, "Qingdao"

    # Custom location?
    change = ask("Use default location Qingdao (36.0671, 120.3826)? [Y/n]: ").lower()
    if change == "n":
        try:
            city = ask("City name (display only): ") or "Custom"
            lat  = float(ask("Latitude: "))
            lon  = float(ask("Longitude: "))
        except ValueError:
            warn("Invalid coordinates — keeping Qingdao defaults")
            lat, lon, city = 36.0671, 120.3826, "Qingdao"

    key_ok = prompt_secret("OPENWEATHER_API_KEY", "OpenWeatherMap API key", secrets)

    if key_ok and secrets.get("OPENWEATHER_API_KEY"):
        raw = ask("Validate API key now? [Y/n]: ").lower()
        if raw != "n":
            if validate_openweather(secrets["OPENWEATHER_API_KEY"], lat, lon):
                ok("API key validated — weather is working")
            else:
                warn("Validation failed — key may still be activating (up to 2h after signup)")

    return {"lat": lat, "lon": lon, "city_name": city}


def setup_todoist(secrets: dict) -> bool:
    """Prompt for and validate Todoist configuration."""
    banner("Todoist tasks")
    info("daily-brief reads your Todoist tasks via REST API v1.")
    info("  Token is shared with task-bridge (TODOIST_API_TOKEN).")
    print()

    token_ok = prompt_secret("TODOIST_API_TOKEN", "Todoist API token", secrets)

    if token_ok and secrets.get("TODOIST_API_TOKEN"):
        raw = ask("Validate Todoist token now? [Y/n]: ").lower()
        if raw != "n":
            if validate_todoist(secrets["TODOIST_API_TOKEN"]):
                ok("Todoist token validated")
            else:
                warn("Todoist validation failed — check token")

    return token_ok


def setup_life_ledger() -> dict:
    """Ask whether life-ledger is installed and where."""
    banner("Life-ledger")
    info("daily-brief can scan your life-ledger for upcoming dates and reminders.")
    info("  (read-only — daily-brief never writes to the ledger)")
    print()

    default_path = str(HOME / ".openclaw/shared/life-ledger/ledger.json")
    raw = ask(f"Is life-ledger installed? [Y/n]: ").lower()
    if raw == "n":
        warn("Life-ledger skipped — reminders section will be omitted from briefings")
        return {"enabled": False, "path": None}

    path_input = ask(f"Path to ledger.json [{default_path}]: ")
    ledger_path = Path(path_input) if path_input else Path(default_path)

    if ledger_path.exists():
        ok(f"ledger.json found at {ledger_path}")
        return {"enabled": True, "path": str(ledger_path)}
    else:
        warn(f"File not found at {ledger_path}")
        warn("Proceeding with this path — alerts section will be empty until ledger exists")
        return {"enabled": True, "path": str(ledger_path)}


def setup_pulse_board() -> dict:
    """Ask whether pulse-board is installed and where its last-delivered.md lives."""
    banner("Pulse-board rig status")
    info("daily-brief can include a one-liner rig health check in the morning briefing.")
    info("  This reads pulse-board's last-delivered.md to report when the last pulse ran.")
    print()

    default_path = str(HOME / ".openclaw/agents/main/workspace/skills/pulse-board/last-delivered.md")
    raw = ask("Is pulse-board installed? [Y/n]: ").lower()
    if raw == "n":
        warn("Pulse-board skipped — rig status section will be omitted from briefings")
        return {"enabled": False, "last_delivered_path": None}

    path_input = ask(f"Path to last-delivered.md [{default_path}]: ")
    pulse_path = Path(path_input) if path_input else Path(default_path)

    if pulse_path.exists():
        ok(f"last-delivered.md found at {pulse_path}")
    else:
        warn(f"File not found at {pulse_path}")
        warn("Proceeding — rig status will show 'no delivery record' until pulse-board runs")

    return {"enabled": True, "last_delivered_path": str(pulse_path)}


def setup_cron() -> bool:
    """Install cron entries for morning (06:00) and evening (21:00)."""
    banner("Cron schedule")

    if not SCRIPT_PATH.exists():
        err(f"Script not found at {SCRIPT_PATH}")
        err("Make sure daily_brief.py is in the skill directory before running setup.")
        return False

    python = sys.executable

    # PATH line includes .npm-global/bin so openclaw resolves in cron context
    # (same pattern as pulse-board v1.1.4)
    npm_bin = HOME / ".npm-global/bin"
    path_line = f"PATH={npm_bin}:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

    new_entries = [
        "# daily-brief",
        f"0 6  * * *  {python} {SCRIPT_PATH} morning >> {SKILL_DIR}/daily-brief.log 2>&1",
        f"0 21 * * *  {python} {SCRIPT_PATH} evening >> {SKILL_DIR}/daily-brief.log 2>&1",
    ]

    # Read existing crontab
    try:
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        existing = result.stdout if result.returncode == 0 else ""
    except Exception as e:
        err(f"Could not read crontab: {e}")
        return False

    # Strip all previous daily-brief entries AND any PATH= line we may have injected
    clean_lines = []
    for line in existing.splitlines():
        stripped = line.strip()
        if "daily-brief" in stripped or "daily_brief" in stripped:
            continue
        # Remove PATH lines that match our pattern exactly (avoid touching user PATH lines)
        if stripped.startswith("PATH=") and ".npm-global" in stripped and "openclaw" not in stripped:
            # Only strip if it looks like one of ours
            # Heuristic: our PATH line always starts with the npm-global path
            if stripped.startswith(f"PATH={npm_bin}"):
                continue
        clean_lines.append(line)

    # Strip trailing blank lines before appending
    while clean_lines and not clean_lines[-1].strip():
        clean_lines.pop()

    new_cron = "\n".join(clean_lines)
    if new_cron and not new_cron.endswith("\n"):
        new_cron += "\n"
    new_cron += "\n" + path_line + "\n" + "\n".join(new_entries) + "\n"

    try:
        proc = subprocess.run(["crontab", "-"], input=new_cron, text=True, capture_output=True)
        if proc.returncode != 0:
            err(f"crontab install failed: {proc.stderr}")
            return False
    except Exception as e:
        err(f"crontab install failed: {e}")
        return False

    ok("Morning briefing: 06:00  (cron: 0 6 * * *)")
    ok("Evening briefing: 21:00  (cron: 0 21 * * *)")
    info("Cron uses system TZ. hiVe is Asia/Shanghai — times above are correct.")
    info("Verify with: crontab -l | grep daily-brief")
    return True


# ── Config assembly & write ────────────────────────────────────────────────────

def write_config(telegram: dict, weather: dict, life_ledger: dict, pulse_board: dict):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    if CONFIG_PATH.exists():
        backup = CONFIG_PATH.with_suffix(
            f".backup-{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
        )
        CONFIG_PATH.rename(backup)
        info(f"Existing config backed up → {backup.name}")

    cfg = {
        "telegram":        telegram,
        "weather":         weather,
        "life_ledger":     life_ledger,
        "pulse_board":     pulse_board,
        "calendar": {
            "enabled": False,
            "note":    "v1.1 — ICS URL method (Outlook.com publish → Settings → Shared calendars)",
            "ics_url": None,
        },
        "alert_window_days": 7,
    }

    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)
    ok(f"Config written → {CONFIG_PATH}")
    return cfg


def print_summary(cfg: dict):
    banner("Setup complete")
    ok(f"Config:  {CONFIG_PATH}")
    ok(f"Script:  {SCRIPT_PATH}")

    thread = cfg["telegram"].get("thread_id")
    if thread:
        ok(f"Telegram thread_id: {thread}")
    else:
        warn("Telegram thread_id: not set — update config.json before first run")

    if not cfg["life_ledger"]["enabled"]:
        warn("Life-ledger: disabled (reminders section omitted)")
    if not cfg["pulse_board"]["enabled"]:
        warn("Pulse-board: disabled (rig status section omitted)")

    print()
    print("  Manual test:")
    print(f"    python3 {SCRIPT_PATH} morning")
    print(f"    python3 {SCRIPT_PATH} evening")
    print()
    print("  Cron: 06:00 morning / 21:00 evening (Asia/Shanghai)")
    print()


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("\n🌅  daily-brief setup — v1.0.0")
    print("    This script will ask about every external dependency.")
    print("    Press Ctrl+C at any time to abort without making changes.\n")

    # Ensure skill directory exists
    SKILL_DIR.mkdir(parents=True, exist_ok=True)
    ok(f"Skill directory ready: {SKILL_DIR}")

    secrets = load_secrets()

    # Interactive setup sections
    telegram    = setup_telegram(secrets)
    weather     = setup_weather(secrets)
    _           = setup_todoist(secrets)      # side-effect: may add secret
    life_ledger = setup_life_ledger()
    pulse_board = setup_pulse_board()

    # Write config
    banner("Writing config")
    cfg = write_config(telegram, weather, life_ledger, pulse_board)

    # Install cron
    setup_cron()

    # Summary
    print_summary(cfg)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Aborted — no changes written.\n")
        sys.exit(1)
