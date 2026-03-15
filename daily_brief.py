#!/usr/bin/env python3
"""
daily-brief v1.0.0
Morning and evening personal briefings via Telegram.
Usage: python3 daily_brief.py [morning|evening]
"""

import json
import sys
import urllib.request
import urllib.error
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional
import logging

# ── Paths ──────────────────────────────────────────────────────────────────────
HOME          = Path.home()
SKILL_DIR     = HOME / ".openclaw/agents/main/workspace/skills/daily-brief"
CONFIG_PATH   = HOME / ".openclaw/config/daily-brief/config.json"
SECRETS_PATH  = HOME / ".openclaw/shared/secrets/openclaw-secrets.env"
LOG_PATH      = SKILL_DIR / "daily-brief.log"

logging.basicConfig(
    filename=str(LOG_PATH),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("daily-brief")


# ── Config & secrets ───────────────────────────────────────────────────────────

def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return json.load(f)

def load_secrets() -> dict:
    secrets = {}
    if not SECRETS_PATH.exists():
        return secrets
    with open(SECRETS_PATH) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            secrets[k.strip()] = v.strip().strip('"').strip("'")
    return secrets


# ── HTTP helper ────────────────────────────────────────────────────────────────

def http_get_json(url: str, headers: Optional[dict] = None) -> dict:
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


# ── Weather ────────────────────────────────────────────────────────────────────

def fetch_weather(cfg: dict, secrets: dict, target: str = "today") -> str:
    """
    Fetch and format a weather summary for 'today' or 'tomorrow'.
    Uses OpenWeatherMap /data/2.5/forecast (free tier).
    """
    api_key = secrets.get("OPENWEATHER_API_KEY", "")
    if not api_key:
        return "⚠️ Weather unavailable (OPENWEATHER_API_KEY not set)"

    lat  = cfg["weather"]["lat"]
    lon  = cfg["weather"]["lon"]
    city = cfg["weather"]["city_name"]

    url = (
        f"https://api.openweathermap.org/data/2.5/forecast"
        f"?lat={lat}&lon={lon}&appid={api_key}&units=metric&cnt=16"
    )
    try:
        data = http_get_json(url)
    except Exception as e:
        log.warning(f"Weather fetch failed: {e}")
        return f"⚠️ Weather unavailable ({type(e).__name__})"

    target_date = date.today() if target == "today" else date.today() + timedelta(days=1)
    slots = [
        item for item in data.get("list", [])
        if datetime.fromtimestamp(item["dt"]).date() == target_date
    ]

    if not slots:
        return f"☁️ No forecast data available for {city}"

    temps = [s["main"]["temp"] for s in slots]
    feels = [s["main"]["feels_like"] for s in slots]
    desc  = slots[len(slots) // 2]["weather"][0]["description"].capitalize()
    pop   = max(s.get("pop", 0) for s in slots) * 100
    t_min, t_max = min(temps), max(temps)

    rain_icon = "🌧️" if pop >= 50 else ("🌦️" if pop >= 25 else "☀️")
    label = "Today" if target == "today" else "Tomorrow"

    line = (
        f"{rain_icon} <b>{label} in {city}:</b> {desc}\n"
        f"   🌡️ {t_min:.0f}°C – {t_max:.0f}°C  (feels {min(feels):.0f}–{max(feels):.0f}°C)"
    )
    if pop >= 15:
        line += f"\n   🌧️ Rain chance: {pop:.0f}%"
    return line


# ── Todoist ────────────────────────────────────────────────────────────────────

def fetch_todoist(secrets: dict, horizon_days: int = 0) -> list:
    """
    Fetch tasks due on or before today + horizon_days.
    Todoist REST API v1 — envelope format: {"results": [...]}.
    """
    token = secrets.get("TODOIST_API_TOKEN", "")
    if not token:
        return []

    try:
        data = http_get_json(
            "https://api.todoist.com/api/v1/tasks",
            headers={"Authorization": f"Bearer {token}"},
        )
    except Exception as e:
        log.warning(f"Todoist fetch failed: {e}")
        return []

    raw = data.get("results", data) if isinstance(data, dict) else data
    today  = date.today()
    cutoff = today + timedelta(days=horizon_days)

    tasks = []
    for t in raw:
        due = t.get("due")
        if not due:
            continue
        try:
            due_date = date.fromisoformat(due["date"][:10])
        except Exception:
            continue
        if due_date <= cutoff:
            tasks.append({
                "content":      t.get("content", ""),
                "due_date":     due_date,
                "priority":     t.get("priority", 1),
                "is_completed": t.get("is_completed", False),
            })

    tasks.sort(key=lambda x: (x["due_date"], -x["priority"]))
    return tasks


def _prio_icon(priority: int) -> str:
    return "🔴" if priority == 4 else ("🟠" if priority == 3 else "")


def format_todoist_morning(tasks: list) -> str:
    today    = date.today()
    overdue  = [t for t in tasks if t["due_date"] < today  and not t["is_completed"]]
    due_now  = [t for t in tasks if t["due_date"] == today and not t["is_completed"]]

    if not overdue and not due_now:
        return "✅ <b>Tasks:</b> Nothing due today — clear runway!"

    lines = ["📋 <b>Tasks for today:</b>"]
    if overdue:
        lines.append(f"   <i>Overdue ({len(overdue)}):</i>")
        for t in overdue[:5]:
            lines.append(f"   {_prio_icon(t['priority'])}• {t['content']}")
        if len(overdue) > 5:
            lines.append(f"   <i>…and {len(overdue) - 5} more overdue</i>")
    if due_now:
        lines.append(f"   <i>Due today ({len(due_now)}):</i>")
        for t in due_now[:7]:
            lines.append(f"   {_prio_icon(t['priority'])}• {t['content']}")
        if len(due_now) > 7:
            lines.append(f"   <i>…and {len(due_now) - 7} more</i>")
    return "\n".join(lines)


def format_todoist_unfinished(tasks: list) -> str:
    today      = date.today()
    unfinished = [t for t in tasks if t["due_date"] == today and not t["is_completed"]]
    if not unfinished:
        return "✅ <b>Today's wrap:</b> Everything done — well played."
    lines = [f"🌙 <b>Still open from today ({len(unfinished)}):</b>"]
    for t in unfinished[:6]:
        lines.append(f"   • {t['content']}")
    if len(unfinished) > 6:
        lines.append(f"   <i>…and {len(unfinished) - 6} more</i>")
    return "\n".join(lines)


def format_todoist_horizon(tasks: list, days: int) -> str:
    today    = date.today()
    upcoming = [
        t for t in tasks
        if today < t["due_date"] <= today + timedelta(days=days)
        and not t["is_completed"]
    ]
    if not upcoming:
        return f"📆 <b>Next {days} days:</b> Nothing on the horizon."
    lines = [f"📆 <b>Coming up ({days}-day view):</b>"]
    for t in upcoming[:8]:
        # %-d is Linux-specific (no leading zero). Fine for hiVe/Ubuntu.
        day_label = t["due_date"].strftime("%a %-d %b")
        lines.append(f"   {_prio_icon(t['priority'])}• {t['content']} <i>({day_label})</i>")
    if len(upcoming) > 8:
        lines.append(f"   <i>…and {len(upcoming) - 8} more</i>")
    return "\n".join(lines)


# ── Life-ledger ────────────────────────────────────────────────────────────────

_DATE_KEYS = {
    "birthday", "born", "anniversary", "contract_end", "appointment",
    "deadline", "expires", "renewal", "reminder", "date",
}

def _parse_date(val: str) -> Optional[date]:
    """
    Parse a date string. Supports YYYY-MM-DD and month-day (MM-DD).
    Year-agnostic dates are mapped to the current or next occurrence.
    """
    for fmt in ("%Y-%m-%d", "%m-%d"):
        try:
            d = datetime.strptime(val, fmt).date()
            if fmt == "%m-%d":
                today = date.today()
                d = d.replace(year=today.year)
                if d < today:
                    d = d.replace(year=today.year + 1)
            return d
        except ValueError:
            continue
    return None


def scan_ledger(ledger_path: Path, window_days: int) -> list:
    """
    Scan the life-ledger JSON for upcoming dates within window_days.
    Returns a list of alert dicts. Reads the path passed by the caller
    (resolved from config so the caller can check existence first).
    """
    if not ledger_path.exists():
        return []
    try:
        with open(ledger_path) as f:
            ledger = json.load(f)
    except Exception as e:
        log.warning(f"Ledger read failed: {e}")
        return []

    today   = date.today()
    cutoff  = today + timedelta(days=window_days)
    alerts  = []
    entries = ledger if isinstance(ledger, list) else ledger.get("entries", [])

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        label = (
            entry.get("name") or entry.get("title") or
            entry.get("label") or "Entry"
        )
        # Scan top-level keys
        for key, val in entry.items():
            if not isinstance(val, str):
                continue
            if key.lower() in _DATE_KEYS or "date" in key.lower():
                d = _parse_date(val)
                if d and today <= d <= cutoff:
                    alerts.append({
                        "label": label,
                        "key":   key,
                        "date":  d,
                        "delta": (d - today).days,
                    })
        # Scan notes for keyword-prefixed dates
        for note in entry.get("notes", []):
            if not isinstance(note, dict):
                continue
            text = note.get("text", "")
            if any(kw in text.lower() for kw in ("reminder:", "remind:", "birthday:", "due:")):
                for word in text.split():
                    d = _parse_date(word)
                    if d and today <= d <= cutoff:
                        alerts.append({
                            "label": label,
                            "key":   "note",
                            "date":  d,
                            "delta": (d - today).days,
                            "text":  text,
                        })

    alerts.sort(key=lambda x: x["date"])
    return alerts


def format_ledger_alerts(alerts: list) -> str:
    if not alerts:
        return ""
    lines = ["🗂️ <b>Life-ledger reminders:</b>"]
    for a in alerts:
        if a["delta"] == 0:
            when = "today"
        elif a["delta"] == 1:
            when = "tomorrow"
        else:
            when = f"in {a['delta']} days"
        date_str = a["date"].strftime("%-d %b")
        if "text" in a:
            lines.append(f"   📌 {a['label']}: {a['text'][:60]} ({when})")
        else:
            key_label = a["key"].replace("_", " ")
            lines.append(f"   📌 {a['label']} — {key_label} {when} ({date_str})")
    return "\n".join(lines)


# ── Pulse-board rig status ─────────────────────────────────────────────────────

def rig_status_line(pulse_delivered_path: Path) -> str:
    """
    One-liner rig health check based on pulse-board's last-delivered.md.
    Path is passed from config so the caller can gate on pulse_board_enabled.
    """
    if not pulse_delivered_path:
        return ""  # pulse-board not configured — omit section silently

    try:
        if not pulse_delivered_path.exists():
            return "🔧 <b>Rig:</b> pulse-board installed but no delivery record yet"
        text = pulse_delivered_path.read_text().strip()
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                ts    = datetime.fromisoformat(line[:19])
                age_h = (datetime.now() - ts).total_seconds() / 3600
                if age_h > 24:
                    return f"⚠️ <b>Rig:</b> last pulse {age_h:.0f}h ago — may need attention"
                return f"💚 <b>Rig:</b> pulse delivered {age_h:.0f}h ago — all good"
            except ValueError:
                continue
        return "❓ <b>Rig:</b> pulse-board timestamp unreadable"
    except Exception as e:
        log.warning(f"Rig status check failed: {e}")
        return "❓ <b>Rig:</b> status unknown"


# ── Calendar placeholder ───────────────────────────────────────────────────────

def calendar_placeholder(day: str = "today") -> str:
    label = "Today" if day == "today" else "Tomorrow"
    return f"📅 <b>{label}'s calendar:</b> <i>not yet connected (v1.1)</i>"


# ── Telegram ───────────────────────────────────────────────────────────────────

def send_telegram(text: str, cfg: dict, secrets: dict) -> bool:
    token = secrets.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        log.error("TELEGRAM_BOT_TOKEN not set in secrets")
        return False

    chat_id   = cfg["telegram"]["chat_id"]
    thread_id = cfg["telegram"].get("thread_id")

    payload = {
        "chat_id":                 chat_id,
        "text":                    text,
        "parse_mode":              "HTML",
        "disable_web_page_preview": True,
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
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            if not result.get("ok"):
                log.error(f"Telegram API error: {result}")
                return False
            return True
    except urllib.error.HTTPError as e:
        log.error(f"Telegram HTTP {e.code}: {e.read().decode()}")
        return False
    except Exception as e:
        log.error(f"Telegram send failed: {e}")
        return False


# ── Briefing builders ──────────────────────────────────────────────────────────

def _resolve_paths(cfg: dict) -> dict:
    """
    Resolve optional external paths from config.
    Returns a dict of Path objects (or None) so briefing functions
    don't have to know about config structure.
    """
    ledger_raw = cfg.get("life_ledger", {}).get("path")
    ledger_path = Path(ledger_raw).expanduser() if ledger_raw else None

    pulse_raw = cfg.get("pulse_board", {}).get("last_delivered_path")
    pulse_path = Path(pulse_raw).expanduser() if pulse_raw else None

    return {
        "ledger": ledger_path,
        "pulse":  pulse_path,
    }


def morning_briefing(cfg: dict, secrets: dict) -> str:
    paths    = _resolve_paths(cfg)
    now      = datetime.now()
    date_str = now.strftime("%A, %-d %B %Y")
    sections = [f"🌅 <b>Good morning, Jakub!</b>\n{date_str}\n"]

    # Weather — today
    try:
        sections.append(fetch_weather(cfg, secrets, "today"))
    except Exception as e:
        log.warning(f"Weather section failed: {e}")
        sections.append("⚠️ Weather: unavailable")

    # Calendar — v1.1 placeholder
    sections.append(calendar_placeholder("today"))

    # Todoist — overdue + due today
    try:
        tasks = fetch_todoist(secrets, horizon_days=0)
        sections.append(format_todoist_morning(tasks))
    except Exception as e:
        log.warning(f"Todoist section failed: {e}")
        sections.append("⚠️ Tasks: unavailable")

    # Life-ledger alerts
    if paths["ledger"]:
        try:
            alerts = scan_ledger(paths["ledger"], cfg.get("alert_window_days", 7))
            alert_text = format_ledger_alerts(alerts)
            if alert_text:
                sections.append(alert_text)
        except Exception as e:
            log.warning(f"Ledger section failed: {e}")

    # Rig status (one-liner from pulse-board)
    if paths["pulse"]:
        line = rig_status_line(paths["pulse"])
        if line:
            sections.append(line)

    return "\n\n".join(sections)


def evening_briefing(cfg: dict, secrets: dict) -> str:
    paths    = _resolve_paths(cfg)
    now      = datetime.now()
    date_str = now.strftime("%A, %-d %B %Y")
    sections = [f"🌆 <b>Evening briefing</b>\n{date_str}\n"]

    # Calendar — tomorrow, v1.1 placeholder
    sections.append(calendar_placeholder("tomorrow"))

    # Weather — tomorrow
    try:
        sections.append(fetch_weather(cfg, secrets, "tomorrow"))
    except Exception as e:
        log.warning(f"Weather section failed: {e}")
        sections.append("⚠️ Weather: unavailable")

    # Todoist — unfinished today
    try:
        tasks_today = fetch_todoist(secrets, horizon_days=0)
        sections.append(format_todoist_unfinished(tasks_today))
    except Exception as e:
        log.warning(f"Todoist (today) section failed: {e}")
        sections.append("⚠️ Tasks: unavailable")

    # Todoist — upcoming horizon
    try:
        horizon = cfg.get("alert_window_days", 7)
        tasks_all = fetch_todoist(secrets, horizon_days=horizon)
        sections.append(format_todoist_horizon(tasks_all, horizon))
    except Exception as e:
        log.warning(f"Todoist (horizon) section failed: {e}")

    # Life-ledger alerts
    if paths["ledger"]:
        try:
            alerts = scan_ledger(paths["ledger"], cfg.get("alert_window_days", 7))
            alert_text = format_ledger_alerts(alerts)
            if alert_text:
                sections.append(alert_text)
        except Exception as e:
            log.warning(f"Ledger section failed: {e}")

    # v1.1 hook: prep reminders (needs calendar data)
    # sections.append(_prep_reminders(tomorrow_events))

    return "\n\n".join(sections)


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("morning", "evening"):
        print("Usage: python3 daily_brief.py [morning|evening]")
        sys.exit(1)

    edition = sys.argv[1]

    try:
        cfg = load_config()
    except Exception as e:
        print(f"ERROR: Could not load config from {CONFIG_PATH}: {e}")
        log.error(f"Config load failed: {e}")
        sys.exit(1)

    secrets = load_secrets()

    text = morning_briefing(cfg, secrets) if edition == "morning" else evening_briefing(cfg, secrets)

    print(text)
    print("\n" + "─" * 40)

    delivered = send_telegram(text, cfg, secrets)
    if delivered:
        print("✅ Sent to Telegram")
        log.info(f"{edition} briefing delivered successfully")
    else:
        print("❌ Telegram delivery failed — check daily-brief.log")
        log.error(f"{edition} briefing delivery failed")


if __name__ == "__main__":
    main()
