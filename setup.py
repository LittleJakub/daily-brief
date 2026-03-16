#!/usr/bin/env python3
"""
daily-brief setup.py v1.1.0
Interactive installer — asks about every external dependency before writing config.
"""

import json
import subprocess
import sys
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
import os
OC          = Path(os.environ.get("OPENCLAW_STATE_DIR", str(Path.home() / ".openclaw")))
SKILL_DIR   = Path(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR  = OC / "config/daily-brief"
CONFIG_PATH = CONFIG_DIR / "config.json"
SECRETS_ENV = OC / ".env"
SCRIPT_PATH = SKILL_DIR / "daily_brief.py"


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
    SECRETS_ENV.parent.mkdir(parents=True, exist_ok=True)
    with open(SECRETS_ENV, "a") as f:
        f.write(f"\n{key}={value}\n")
    ok(f"{key} written to {SECRETS_ENV.name}")


def prompt_secret(key: str, label: str, secrets: dict) -> bool:
    if secrets.get(key):
        ok(f"{label} found ({key})")
        return True
    warn(f"{label} not found ({key})")
    info(f"  Expected in: {SECRETS_ENV}")
    raw = ask(f"  Paste value for {key} (or Enter to skip): ")
    if raw:
        append_secret(key, raw)
        secrets[key] = raw
        return True
    warn(f"  {key} skipped — this section will be unavailable until added")
    return False


# ── Live API validation ────────────────────────────────────────────────────────

def validate_telegram(token: str, chat_id: int, thread_id) -> bool:
    payload = {
        "chat_id":    chat_id,
        "text":       "🌅 <b>daily-brief</b>: setup test — if you see this, Telegram delivery is working.",
        "parse_mode": "HTML",
    }
    if thread_id:
        payload["message_thread_id"] = thread_id
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read()).get("ok", False)
    except urllib.error.HTTPError as e:
        err(f"Telegram HTTP {e.code}: {e.read().decode()[:200]}")
        return False
    except Exception as e:
        err(f"Telegram test failed: {e}")
        return False


def validate_openweather(api_key: str, lat: float, lon: float) -> bool:
    url = (
        f"https://api.openweathermap.org/data/2.5/weather"
        f"?lat={lat}&lon={lon}&appid={api_key}&units=metric"
    )
    try:
        with urllib.request.urlopen(urllib.request.Request(url), timeout=10) as resp:
            return "weather" in json.loads(resp.read())
    except urllib.error.HTTPError as e:
        err(f"OpenWeatherMap: HTTP {e.code}" + (" (key rejected)" if e.code == 401 else ""))
        return False
    except Exception as e:
        err(f"OpenWeatherMap test failed: {e}")
        return False


def validate_todoist(token: str) -> bool:
    req = urllib.request.Request(
        "https://api.todoist.com/api/v1/tasks",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
            return True
    except urllib.error.HTTPError as e:
        err(f"Todoist: HTTP {e.code}" + (" (token rejected)" if e.code == 403 else ""))
        return False
    except Exception as e:
        err(f"Todoist test failed: {e}")
        return False


def validate_ics(url: str) -> bool:
    """Fetch the ICS URL and check it looks like a valid iCalendar feed."""
    req = urllib.request.Request(url, headers={"User-Agent": "daily-brief/1.1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            chunk = resp.read(512).decode("utf-8", errors="replace")
            return "BEGIN:VCALENDAR" in chunk
    except urllib.error.HTTPError as e:
        err(f"ICS fetch HTTP {e.code}")
        return False
    except Exception as e:
        err(f"ICS fetch failed: {e}")
        return False


# ── Setup sections ─────────────────────────────────────────────────────────────

def setup_telegram(secrets: dict) -> dict:
    banner("Telegram delivery")
    info("daily-brief posts to a dedicated topic inside a Telegram supergroup.")
    info("  This requires TWO separate IDs:")
    info("")
    info("  1. chat_id  — identifies the supergroup itself (a large negative number).")
    info("     How to find it: forward any message from the group to @userinfobot,")
    info("     or open the group in Telegram Web — the number after 'c/' in the URL,")
    info("     prepended with -100  (e.g. c/1234567890 → -1001234567890).")
    info("")
    info("  2. thread_id — identifies the specific topic within the group.")
    info("     How to find it: open the topic in Telegram Web, read the number")
    info("     after the second slash in the URL:")
    info("     e.g.  web.telegram.org/a/#-1001234567890_99  →  thread_id = 99")
    info("     Or: right-click the topic name → Copy Link, the last number is the ID.")
    print()

    token_ok = prompt_secret("TELEGRAM_BOT_TOKEN", "Telegram bot token", secrets)

    raw_chat = ask("Enter your Telegram supergroup chat_id (e.g. -1001234567890): ")
    chat_id  = None
    if raw_chat:
        try:
            chat_id = int(raw_chat)
            ok(f"Chat ID: {chat_id}")
        except ValueError:
            warn(f"'{raw_chat}' is not an integer — leaving null (update config.json before first run)")
    else:
        warn("chat_id left as null — update config.json before first run")

    raw_thread = ask("Enter the thread_id for the daily-brief topic (Enter to skip): ")
    thread_id  = None
    if raw_thread:
        try:
            thread_id = int(raw_thread)
            ok(f"Thread ID: {thread_id}")
        except ValueError:
            warn(f"'{raw_thread}' is not an integer — leaving null")
    else:
        warn("thread_id left as null — briefings will post to the main group chat until set")

    if token_ok and secrets.get("TELEGRAM_BOT_TOKEN") and chat_id:
        if ask("Send a test message to Telegram now? [Y/n]: ").lower() != "n":
            if validate_telegram(secrets["TELEGRAM_BOT_TOKEN"], chat_id, thread_id):
                ok("Test message delivered" + (" to topic" if thread_id else " (no topic — went to main chat)"))
            else:
                warn("Test message failed — check token, chat_id, and thread_id")

    return {"chat_id": chat_id, "thread_id": thread_id}


def setup_weather(secrets: dict) -> dict:
    banner("Weather — OpenWeatherMap")
    info("daily-brief fetches weather using OpenWeatherMap free tier (1000 calls/day).")
    info("  Sign up at https://openweathermap.org/api")
    info("  Note: new API keys can take up to 2 hours to activate after signup.")
    print()

    lat, lon, city = 0.0, 0.0, "My City"

    city  = ask("City name (display only, e.g. Qingdao): ") or "My City"
    try:
        lat = float(ask("Latitude (e.g. 51.5074 for London): "))
        lon = float(ask("Longitude (e.g. -0.1278 for London): "))
    except ValueError:
        warn("Invalid coordinates — defaulting to 0,0. Update config.json before first run.")

    key_ok = prompt_secret("OPENWEATHER_API_KEY", "OpenWeatherMap API key", secrets)

    if key_ok and secrets.get("OPENWEATHER_API_KEY"):
        if ask("Validate API key now? [Y/n]: ").lower() != "n":
            if validate_openweather(secrets["OPENWEATHER_API_KEY"], lat, lon):
                ok("API key validated — weather is working")
            else:
                warn("Validation failed — key may still be activating (up to 2h after signup)")

    return {"lat": lat, "lon": lon, "city_name": city}


def setup_todoist(secrets: dict) -> bool:
    banner("Todoist tasks")
    info("daily-brief reads your Todoist tasks via REST API v1.")
    info("  Token is shared with task-bridge (TODOIST_API_TOKEN).")
    print()

    token_ok = prompt_secret("TODOIST_API_TOKEN", "Todoist API token", secrets)

    if token_ok and secrets.get("TODOIST_API_TOKEN"):
        if ask("Validate Todoist token now? [Y/n]: ").lower() != "n":
            if validate_todoist(secrets["TODOIST_API_TOKEN"]):
                ok("Todoist token validated")
            else:
                warn("Todoist validation failed — check token")

    return token_ok


def setup_calendar(secrets: dict) -> dict:
    """
    Ask how many calendars to add, prompt for label + secret key per calendar.
    ICS URLs are stored in secrets only — never in config.json.
    Supports any number of calendars (personal, work, shared, etc.).
    """
    banner("Calendar — ICS feeds")
    info("daily-brief can display events from any calendar that provides an ICS URL.")
    info("  Works with: Outlook.com, Office 365, Google Calendar, iCloud, etc.")
    info("")
    info("  ICS URLs are stored in openclaw-secrets.env — not in config.json.")
    info("  Each calendar needs:")
    info("    • A display label  (e.g. 'Personal', 'Work')")
    info("    • A secret key     (e.g. DAILY_BRIEF_ICS_PERSONAL)")
    info("      The URL for that key must already be in openclaw-secrets.env.")
    info("")
    info("  How to get your ICS URL:")
    info("    Outlook.com:  Settings → View all Outlook settings →")
    info("                  Calendar → Shared calendars → Publish a calendar")
    info("                  → Can view all details → Publish → copy ICS link")
    info("    Office 365:   Same flow at outlook.office.com")
    info("    Google:       Calendar settings → [calendar] → Integrate calendar")
    info("                  → Secret address in iCal format")
    print()

    raw = ask("Enable calendar integration? [Y/n]: ").lower()
    if raw == "n":
        warn("Calendar skipped — briefings will show 'nothing scheduled' until enabled")
        return {"enabled": False, "calendars": []}

    calendars = []
    while True:
        print()
        info(f"  Calendar #{len(calendars) + 1}")
        label = ask("  Display label (e.g. Personal, Work): ")
        if not label:
            warn("  No label entered — skipping this calendar")
            break

        secret_key = ask(f"  Secret key for ICS URL (e.g. DAILY_BRIEF_ICS_{label.upper().replace(' ', '_')}): ")
        if not secret_key:
            warn("  No secret key entered — skipping this calendar")
            break

        # Check the key exists in secrets
        if secrets.get(secret_key):
            ok(f"  '{secret_key}' found in secrets")
            if ask("  Validate ICS URL now? [Y/n]: ").lower() != "n":
                if validate_ics(secrets[secret_key]):
                    ok(f"  ICS feed valid — calendar '{label}' ready")
                else:
                    warn(f"  ICS validation failed — check the URL for '{label}'")
        else:
            warn(f"  '{secret_key}' not found in secrets")
            info(f"  Add it to {SECRETS_ENV} before first run:")
            info(f"    echo \"{secret_key}=<your ICS URL>\" >> {SECRETS_ENV}")

        calendars.append({"label": label, "ics_secret_key": secret_key})
        ok(f"  Calendar '{label}' added")

        another = ask("Add another calendar? [y/N]: ").lower()
        if another != "y":
            break

    if calendars:
        ok(f"{len(calendars)} calendar(s) configured: {', '.join(c['label'] for c in calendars)}")
    else:
        warn("No calendars configured — calendar sections will be empty")

    return {"enabled": bool(calendars), "calendars": calendars}


def setup_life_ledger() -> dict:
    banner("Life-ledger")
    info("daily-brief can scan your life-ledger for upcoming dates and reminders.")
    info("  (read-only — daily-brief never writes to the ledger)")
    print()

    default_path = str(OC / "data/life-ledger/ledger.json")
    if ask("Is life-ledger installed? [Y/n]: ").lower() == "n":
        warn("Life-ledger skipped — reminders section will be omitted")
        return {"enabled": False, "path": None}

    path_input  = ask(f"Path to ledger.json [{default_path}]: ")
    ledger_path = Path(path_input) if path_input else Path(default_path)

    if ledger_path.exists():
        ok(f"ledger.json found at {ledger_path}")
    else:
        warn(f"File not found at {ledger_path}")
        warn("Proceeding — alerts section will be empty until the ledger exists")

    return {"enabled": True, "path": str(ledger_path)}


def setup_pulse_board() -> dict:
    banner("Pulse-board rig status")
    info("daily-brief can include a one-liner rig health check in the morning briefing.")
    info("  This reads pulse-board's last-delivered.md to report when the last pulse ran.")
    print()

    default_path = str(Path(os.environ.get("PULSE_HOME", str(OC / "pulse-board"))) / "logs/last-delivered.md")
    if ask("Is pulse-board installed? [Y/n]: ").lower() == "n":
        warn("Pulse-board skipped — rig status section will be omitted")
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
    banner("Cron schedule")

    if not SCRIPT_PATH.exists():
        err(f"Script not found at {SCRIPT_PATH}")
        err("Make sure daily_brief.py is in the skill directory before running setup.")
        return False

    python   = sys.executable
    npm_bin  = HOME / ".npm-global/bin"
    path_line = f"PATH={npm_bin}:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

    new_entries = [
        "# daily-brief",
        f"0 6  * * *  {python} {SCRIPT_PATH} morning >> {SKILL_DIR}/daily-brief.log 2>&1",
        f"0 21 * * *  {python} {SCRIPT_PATH} evening >> {SKILL_DIR}/daily-brief.log 2>&1",
    ]

    try:
        result   = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        existing = result.stdout if result.returncode == 0 else ""
    except Exception as e:
        err(f"Could not read crontab: {e}")
        return False

    clean_lines = []
    for line in existing.splitlines():
        stripped = line.strip()
        if "daily-brief" in stripped or "daily_brief" in stripped:
            continue
        if stripped.startswith(f"PATH={npm_bin}"):
            continue
        clean_lines.append(line)

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
    info("Cron uses system TZ. Verify with: crontab -l | grep daily-brief")
    return True


# ── Config write ───────────────────────────────────────────────────────────────

def write_config(telegram: dict, weather: dict, calendar: dict,
                 life_ledger: dict, pulse_board: dict) -> dict:
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
        "calendar":        calendar,
        "life_ledger":     life_ledger,
        "pulse_board":     pulse_board,
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

    cal = cfg.get("calendar", {})
    if cal.get("enabled"):
        cals = cal.get("calendars", [])
        ok(f"Calendars: {', '.join(c['label'] for c in cals)}")
    else:
        warn("Calendar: disabled")

    if not cfg["life_ledger"]["enabled"]:
        warn("Life-ledger: disabled")
    if not cfg["pulse_board"]["enabled"]:
        warn("Pulse-board: disabled")

    print()
    print("  Manual test:")
    print(f"    python3 {SCRIPT_PATH} morning")
    print(f"    python3 {SCRIPT_PATH} evening")
    print()
    print("  Cron: 06:00 morning / 21:00 evening")
    print()


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("\n🌅  daily-brief setup — v1.1.0")
    print("    This script will ask about every external dependency.")
    print("    Press Ctrl+C at any time to abort without making changes.\n")

    SKILL_DIR.mkdir(parents=True, exist_ok=True)
    ok(f"Skill directory ready: {SKILL_DIR}")

    secrets = load_secrets()

    telegram    = setup_telegram(secrets)
    weather     = setup_weather(secrets)
    _           = setup_todoist(secrets)
    calendar    = setup_calendar(secrets)
    life_ledger = setup_life_ledger()
    pulse_board = setup_pulse_board()

    banner("Writing config")
    cfg = write_config(telegram, weather, calendar, life_ledger, pulse_board)

    setup_cron()
    print_summary(cfg)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Aborted — no changes written.\n")
        sys.exit(1)
