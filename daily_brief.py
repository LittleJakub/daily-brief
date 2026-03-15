#!/usr/bin/env python3
"""
daily-brief v1.3.0
Morning and evening personal briefings via configurable channel (Feishu or Telegram).
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
import re

# ── Paths ──────────────────────────────────────────────────────────────────────
HOME        = Path.home()
SKILL_DIR   = HOME / ".openclaw/agents/main/workspace/skills/daily-brief"
CONFIG_PATH = HOME / ".openclaw/config/daily-brief/config.json"
SECRETS_PATH = HOME / ".openclaw/shared/secrets/openclaw-secrets.env"
LOG_PATH    = SKILL_DIR / "daily-brief.log"

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


# ── HTTP helpers ───────────────────────────────────────────────────────────────

def http_get_json(url: str, headers: Optional[dict] = None) -> dict:
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())

def http_get_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "daily-brief/1.3.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8", errors="replace")


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


# ── ICS calendar ───────────────────────────────────────────────────────────────

def _ics_unescape(val: str) -> str:
    """Unescape iCalendar text values."""
    return val.replace("\\n", "\n").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")

def _unfold_ics(text: str) -> list:
    """
    Unfold iCalendar lines (RFC 5545 §3.1):
    a CRLF followed by a whitespace character is a line continuation.
    Returns a list of unfolded lines.
    """
    lines = []
    for raw in text.splitlines():
        if raw and raw[0] in (" ", "\t") and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    return lines

def _parse_ics_datetime(val: str, tzid: Optional[str] = None) -> Optional[date]:
    """
    Parse an iCal DTSTART/DTEND value to a Python date.
    Handles:
      - DATE-only:      19970714          → date(1997,7,14)
      - DATE-TIME:      19980118T230000   → naive datetime → .date()
      - DATE-TIME UTC:  19980119T070000Z  → strip Z, use as-is
    We do not do full tz conversion — we work in local wall time since
    the machine runs in the correct timezone already.
    """
    val = val.strip().rstrip("Z")
    if "T" in val:
        try:
            return datetime.strptime(val[:15], "%Y%m%dT%H%M%S").date()
        except ValueError:
            return None
    else:
        try:
            return datetime.strptime(val[:8], "%Y%m%d").date()
        except ValueError:
            return None

def _parse_ics_datetime_full(val: str) -> Optional[datetime]:
    """Parse to full datetime for time display."""
    val = val.strip().rstrip("Z")
    if "T" in val:
        try:
            return datetime.strptime(val[:15], "%Y%m%dT%H%M%S")
        except ValueError:
            return None
    return None

def _rrule_matches(rrule: str, dtstart_date: date, check_date: date) -> bool:
    """
    Check if an RRULE causes an event to recur on check_date.
    Supports FREQ=DAILY/WEEKLY/MONTHLY/YEARLY with optional INTERVAL.
    Does not implement UNTIL/COUNT/BYDAY etc — good enough for personal calendars.
    """
    if check_date < dtstart_date:
        return False
    params = {}
    for part in rrule.split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            params[k.strip().upper()] = v.strip()

    freq     = params.get("FREQ", "")
    interval = int(params.get("INTERVAL", "1"))
    delta    = check_date - dtstart_date

    if freq == "DAILY":
        return delta.days % interval == 0
    elif freq == "WEEKLY":
        return delta.days % (7 * interval) == 0
    elif freq == "MONTHLY":
        months = (check_date.year - dtstart_date.year) * 12 + (check_date.month - dtstart_date.month)
        return months % interval == 0 and check_date.day == dtstart_date.day
    elif freq == "YEARLY":
        years = check_date.year - dtstart_date.year
        return years % interval == 0 and check_date.month == dtstart_date.month and check_date.day == dtstart_date.day
    return False

def _is_all_day(dtstart_raw: str) -> bool:
    """Return True if the DTSTART value is a DATE (not DATE-TIME)."""
    return "T" not in dtstart_raw.strip()

def parse_ics(text: str, target_date: date) -> list:
    """
    Parse an iCalendar string and return events occurring on target_date.
    Each event is a dict:
      summary   str
      location  str | None
      all_day   bool
      start_dt  datetime | None  (None for all-day)
      end_dt    datetime | None
    """
    lines    = _unfold_ics(text)
    events   = []
    in_event = False
    current  = {}

    for line in lines:
        if line.strip() == "BEGIN:VEVENT":
            in_event = True
            current  = {}
            continue
        if line.strip() == "END:VEVENT":
            in_event = False
            if current:
                events.append(current)
            current = {}
            continue
        if not in_event:
            continue

        # Split property name (and params) from value
        if ":" not in line:
            continue
        prop, _, val = line.partition(":")
        prop_name = prop.split(";")[0].upper()

        # Extract TZID param if present
        tzid = None
        for param in prop.split(";")[1:]:
            if param.upper().startswith("TZID="):
                tzid = param[5:]

        if prop_name == "SUMMARY":
            current["summary"] = _ics_unescape(val.strip())
        elif prop_name == "LOCATION":
            current["location"] = _ics_unescape(val.strip())
        elif prop_name == "DTSTART":
            current["dtstart_raw"] = val.strip()
            current["dtstart_date"] = _parse_ics_datetime(val, tzid)
            current["dtstart_dt"]   = _parse_ics_datetime_full(val)
        elif prop_name == "DTEND":
            current["dtend_date"] = _parse_ics_datetime(val, tzid)
            current["dtend_dt"]   = _parse_ics_datetime_full(val)
        elif prop_name == "RRULE":
            current["rrule"] = val.strip()
        elif prop_name == "STATUS":
            current["status"] = val.strip().upper()

    # Filter to target_date
    result = []
    for ev in events:
        # Skip cancelled events
        if ev.get("status") == "CANCELLED":
            continue

        dtstart_d = ev.get("dtstart_date")
        dtend_d   = ev.get("dtend_date")
        rrule     = ev.get("rrule")

        if not dtstart_d:
            continue

        # Check if event falls on target_date
        occurs = False
        if rrule:
            occurs = _rrule_matches(rrule, dtstart_d, target_date)
        elif dtend_d and dtend_d > dtstart_d + timedelta(days=1):
            # Multi-day event: spans target_date?
            occurs = dtstart_d <= target_date < dtend_d
        else:
            occurs = dtstart_d == target_date

        if occurs:
            all_day  = _is_all_day(ev.get("dtstart_raw", ""))
            start_dt = None if all_day else ev.get("dtstart_dt")
            end_dt   = None if all_day else ev.get("dtend_dt")
            result.append({
                "summary":  ev.get("summary", "(no title)"),
                "location": ev.get("location"),
                "all_day":  all_day,
                "start_dt": start_dt,
                "end_dt":   end_dt,
            })

    # Sort: all-day first, then by start time
    result.sort(key=lambda e: (
        0 if e["all_day"] else 1,
        e["start_dt"] or datetime.min,
    ))
    return result


def fetch_calendar_events(cfg: dict, secrets: dict, target_date: date) -> list:
    """
    Fetch events from all configured ICS calendars for target_date.
    Returns list of dicts with added 'calendar_label' key.
    Each calendar entry in config has:
      label           – display name
      ics_secret_key  – key to look up in secrets for the URL
    """
    cal_cfg = cfg.get("calendar", {})
    if not cal_cfg.get("enabled", False):
        return []

    calendars = cal_cfg.get("calendars", [])
    all_events = []

    for cal in calendars:
        label     = cal.get("label", "Calendar")
        secret_key = cal.get("ics_secret_key", "")
        url       = secrets.get(secret_key, "")

        if not url:
            log.warning(f"ICS URL not found in secrets for key '{secret_key}' (calendar: {label})")
            continue

        try:
            text   = http_get_text(url)
            events = parse_ics(text, target_date)
            for ev in events:
                ev["calendar_label"] = label
            all_events.extend(events)
            log.info(f"Calendar '{label}': {len(events)} event(s) on {target_date}")
        except Exception as e:
            log.warning(f"Calendar '{label}' fetch/parse failed: {e}")

    # Re-sort across all calendars: all-day first, then by time
    all_events.sort(key=lambda e: (
        0 if e["all_day"] else 1,
        e["start_dt"] or datetime.min,
    ))
    return all_events


def format_calendar(events: list, day: str = "today") -> str:
    """
    Format calendar events for a briefing section.
    day: 'today' | 'tomorrow'
    """
    label = "Today" if day == "today" else "Tomorrow"

    if not events:
        return f"📅 <b>{label}'s calendar:</b> Nothing scheduled."

    lines = [f"📅 <b>{label}'s calendar:</b>"]
    for ev in events:
        cal_tag = f" <i>[{ev['calendar_label']}]</i>" if ev.get("calendar_label") else ""
        loc     = f" 📍 {ev['location']}" if ev.get("location") else ""

        if ev["all_day"]:
            lines.append(f"   🗓️ {ev['summary']}{loc}{cal_tag}")
        else:
            start = ev["start_dt"].strftime("%H:%M") if ev["start_dt"] else "?"
            end   = ev["end_dt"].strftime("%H:%M")   if ev["end_dt"]   else ""
            time_str = f"{start}–{end}" if end else start
            lines.append(f"   🕐 {time_str}  {ev['summary']}{loc}{cal_tag}")

    return "\n".join(lines)


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

    raw    = data.get("results", data) if isinstance(data, dict) else data
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
    today   = date.today()
    overdue = [t for t in tasks if t["due_date"] < today  and not t["is_completed"]]
    due_now = [t for t in tasks if t["due_date"] == today and not t["is_completed"]]

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
    Parse a date string. Supports YYYY-MM-DD and MM-DD.
    Year-agnostic dates map to the current or next occurrence.
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
        label = entry.get("name") or entry.get("title") or entry.get("label") or "Entry"
        for key, val in entry.items():
            if not isinstance(val, str):
                continue
            if key.lower() in _DATE_KEYS or "date" in key.lower():
                d = _parse_date(val)
                if d and today <= d <= cutoff:
                    alerts.append({"label": label, "key": key, "date": d, "delta": (d - today).days})
        for note in entry.get("notes", []):
            if not isinstance(note, dict):
                continue
            text = note.get("text", "")
            if any(kw in text.lower() for kw in ("reminder:", "remind:", "birthday:", "due:")):
                for word in text.split():
                    d = _parse_date(word)
                    if d and today <= d <= cutoff:
                        alerts.append({"label": label, "key": "note", "date": d,
                                       "delta": (d - today).days, "text": text})

    alerts.sort(key=lambda x: x["date"])
    return alerts


def format_ledger_alerts(alerts: list) -> str:
    if not alerts:
        return ""
    lines = ["🗂️ <b>Life-ledger reminders:</b>"]
    for a in alerts:
        when     = "today" if a["delta"] == 0 else ("tomorrow" if a["delta"] == 1 else f"in {a['delta']} days")
        date_str = a["date"].strftime("%-d %b")
        if "text" in a:
            lines.append(f"   📌 {a['label']}: {a['text'][:60]} ({when})")
        else:
            lines.append(f"   📌 {a['label']} — {a['key'].replace('_', ' ')} {when} ({date_str})")
    return "\n".join(lines)


# ── Pulse-board rig status ─────────────────────────────────────────────────────

def rig_status_line(pulse_delivered_path: Path) -> str:
    if not pulse_delivered_path:
        return ""
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


# ── Delivery ──────────────────────────────────────────────────────────────────

def strip_html(text: str) -> str:
    """Strip all HTML tags for plain-text delivery (e.g. Feishu)."""
    return re.sub(r"<[^>]+>", "", text)


def send_telegram(text: str, cfg: dict, secrets: dict) -> bool:
    token = secrets.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        log.error("TELEGRAM_BOT_TOKEN not set in secrets")
        return False

    chat_id   = cfg["telegram"]["chat_id"]
    thread_id = cfg["telegram"].get("thread_id")

    payload = {
        "chat_id":                  chat_id,
        "text":                     text,
        "parse_mode":               "HTML",
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


def send_feishu(text: str, cfg: dict, secrets: dict) -> bool:
    """
    Deliver a brief to a Feishu chat topic.
    Auth: tenant_access_token via app_id + app_secret (2-step flow).
    HTML formatting is stripped/converted before sending.
    """
    app_id     = secrets.get("FEISHU_APP_ID", "")
    app_secret = secrets.get("FEISHU_APP_SECRET", "")
    if not app_id or not app_secret:
        log.error("FEISHU_APP_ID or FEISHU_APP_SECRET not set in secrets")
        return False

    chat_id      = cfg["feishu"]["chat_id"]
    root_msg_id  = secrets.get("FEISHU_HORIZON_ROOT_MSG", "")

    # Step 1 — get tenant access token
    token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    token_req = urllib.request.Request(
        token_url,
        data=json.dumps({"app_id": app_id, "app_secret": app_secret}).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(token_req, timeout=10) as resp:
            token_data = json.loads(resp.read())
        access_token = token_data.get("tenant_access_token", "")
        if not access_token:
            log.error(f"Feishu token fetch failed: {token_data}")
            return False
    except Exception as e:
        log.error(f"Feishu token fetch failed: {e}")
        return False

    # Step 2 — deliver message
    # Feishu does not support receive_id_type=thread_id (field rejected by API).
    # The only way to post into an existing topic is via the reply API,
    # using the root message ID (om_xxx) of that thread as the target.
    # root_msg_id is stored in secrets as FEISHU_HORIZON_ROOT_MSG.
    # Fallback: send to the group chat_id directly if root_msg_id is absent.
    plain = strip_html(text)

    if root_msg_id:
        # Reply into the hOrizon topic thread
        reply_url = f"https://open.feishu.cn/open-apis/im/v1/messages/{root_msg_id}/reply"
        payload = {
            "msg_type": "text",
            "content":  json.dumps({"text": plain}),
            "uuid":     datetime.now().strftime("%Y%m%d%H%M%S"),
        }
        msg_url = reply_url
    else:
        # Fallback: post to group chat (no topic)
        log.warning("FEISHU_HORIZON_ROOT_MSG not set — posting to group chat, not topic")
        payload = {
            "receive_id": chat_id,
            "msg_type":   "text",
            "content":    json.dumps({"text": plain}),
        }
        msg_url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id"

    msg_req = urllib.request.Request(
        msg_url,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {access_token}",
        },
    )
    try:
        with urllib.request.urlopen(msg_req, timeout=15) as resp:
            result = json.loads(resp.read())
        if result.get("code", -1) != 0:
            log.error(f"Feishu API error: {result}")
            return False
        return True
    except urllib.error.HTTPError as e:
        log.error(f"Feishu HTTP {e.code}: {e.read().decode()}")
        return False
    except Exception as e:
        log.error(f"Feishu send failed: {e}")
        return False


def send_brief(text: str, cfg: dict, secrets: dict) -> bool:
    """Route delivery to the configured channel (feishu or telegram)."""
    channel = cfg.get("channel", "telegram")
    if channel == "feishu":
        return send_feishu(text, cfg, secrets)
    return send_telegram(text, cfg, secrets)


# ── Path resolution ────────────────────────────────────────────────────────────

def _resolve_paths(cfg: dict) -> dict:
    ledger_raw = cfg.get("life_ledger", {}).get("path")
    ledger_path = Path(ledger_raw).expanduser() if ledger_raw else None

    pulse_raw  = cfg.get("pulse_board", {}).get("last_delivered_path")
    pulse_path = Path(pulse_raw).expanduser() if pulse_raw else None

    return {"ledger": ledger_path, "pulse": pulse_path}


# ── Briefing builders ──────────────────────────────────────────────────────────

def morning_briefing(cfg: dict, secrets: dict) -> str:
    paths    = _resolve_paths(cfg)
    now      = datetime.now()
    date_str = now.strftime("%A, %-d %B %Y")
    today    = date.today()
    sections = [f"🌅 <b>Good morning!</b>\n{date_str}\n"]

    # Weather — today
    try:
        sections.append(fetch_weather(cfg, secrets, "today"))
    except Exception as e:
        log.warning(f"Weather section failed: {e}")
        sections.append("⚠️ Weather: unavailable")

    # Calendar — today
    try:
        events = fetch_calendar_events(cfg, secrets, today)
        sections.append(format_calendar(events, "today"))
    except Exception as e:
        log.warning(f"Calendar section failed: {e}")
        sections.append("⚠️ Calendar: unavailable")

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

    # Rig status
    if paths["pulse"]:
        line = rig_status_line(paths["pulse"])
        if line:
            sections.append(line)

    return "\n\n".join(sections)


def _prep_reminders(events: list, cfg: dict) -> str:
    """
    Scan tomorrow's calendar events for keywords and suggest prep actions.
    Keyword → action mapping is read from cfg["prep_reminders"]["keywords"].
    Falls back to built-in defaults if not configured.
    Returns a formatted section string, or "" if nothing to suggest.
    """
    if not events:
        return ""

    # Default keyword → reminder mapping.
    # Keys are lowercased substrings to match against event title + location.
    # Override or extend via config.json: "prep_reminders": {"keywords": {...}}
    defaults = {
        "gym":        "🏋️ Pack gym bag",
        "swim":       "🏊 Pack swimwear and towel",
        "pool":       "🏊 Pack swimwear and towel",
        "flight":     "✈️ Pack passport and check-in online",
        "airport":    "✈️ Pack passport and check-in online",
        "travel":     "🧳 Pack luggage",
        "interview":  "👔 Check dress code and prep documents",
        "meeting":    "📋 Review agenda and prep notes",
        "doctor":     "🏥 Bring ID and insurance card",
        "hospital":   "🏥 Bring ID and insurance card",
        "dentist":    "🦷 Bring ID and insurance card",
        "school":     "🎒 Pack school bag",
        "class":      "📚 Pack notebook and materials",
        "exam":       "📝 Bring ID and stationery",
        "hike":       "🥾 Pack water, snacks, and sunscreen",
        "run":        "👟 Pack running gear",
        "yoga":       "🧘 Pack mat and water bottle",
        "dinner":     "🍽️ Check reservation and dress code",
        "restaurant": "🍽️ Check reservation",
        "date":       "💐 Check reservation and dress code",
        "concert":    "🎵 Check venue and bring tickets",
        "cinema":     "🎬 Bring tickets",
        "church":     "⛪ Check dress code",
    }

    keyword_map = cfg.get("prep_reminders", {}).get("keywords", defaults)

    suggestions = []
    seen = set()

    for ev in events:
        searchable = (
            (ev.get("summary", "") + " " + (ev.get("location") or "")).lower()
        )
        for keyword, action in keyword_map.items():
            if keyword.lower() in searchable and action not in seen:
                suggestions.append(action)
                seen.add(action)

    if not suggestions:
        return ""

    lines = ["🎒 <b>Tomorrow — prep reminders:</b>"]
    for s in suggestions:
        lines.append(f"   • {s}")
    return "\n".join(lines)


def evening_briefing(cfg: dict, secrets: dict) -> str:
    paths     = _resolve_paths(cfg)
    now       = datetime.now()
    date_str  = now.strftime("%A, %-d %B %Y")
    tomorrow  = date.today() + timedelta(days=1)
    sections  = [f"🌆 <b>Evening briefing</b>\n{date_str}\n"]

    # Calendar — tomorrow
    # events hoisted so prep_reminders can use it even if format_calendar fails
    tomorrow_events = []
    try:
        tomorrow_events = fetch_calendar_events(cfg, secrets, tomorrow)
        sections.append(format_calendar(tomorrow_events, "tomorrow"))
    except Exception as e:
        log.warning(f"Calendar section failed: {e}")
        sections.append("⚠️ Calendar: unavailable")

    # Prep reminders — keyword-match tomorrow's events
    try:
        prep = _prep_reminders(tomorrow_events, cfg)
        if prep:
            sections.append(prep)
    except Exception as e:
        log.warning(f"Prep reminders section failed: {e}")

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
        horizon   = cfg.get("alert_window_days", 7)
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

    channel = cfg.get("channel", "telegram")
    delivered = send_brief(text, cfg, secrets)
    if delivered:
        print(f"✅ Sent via {channel}")
        log.info(f"{edition} briefing delivered successfully via {channel}")
    else:
        print(f"❌ Delivery failed ({channel}) — check daily-brief.log")
        log.error(f"{edition} briefing delivery failed via {channel}")


if __name__ == "__main__":
    main()
