# daily-brief

**Version:** 1.1.0
**Location:** `~/.openclaw/agents/main/workspace/skills/daily-brief/`

---

## What it does

`daily-brief` posts two personal briefings to a dedicated Telegram topic each day — a morning edition to start the day, and an evening edition to close it out. Personal day planner, not a system health monitor (that's pulse-board).

---

## Morning briefing — 06:00

| Section | Source | Required |
|---|---|---|
| Weather today | OpenWeatherMap | `OPENWEATHER_API_KEY` |
| Today's calendar | ICS feeds | configured in setup |
| Tasks due today + overdue | Todoist REST API v1 | `TODOIST_API_TOKEN` |
| Life-ledger reminders (7-day window) | `ledger.json` | configured in setup |
| Rig status (one-liner) | pulse-board `last-delivered.md` | configured in setup |

## Evening briefing — 21:00

| Section | Source | Required |
|---|---|---|
| Tomorrow's calendar | ICS feeds | configured in setup |
| Weather tomorrow | OpenWeatherMap | `OPENWEATHER_API_KEY` |
| Unfinished items from today | Todoist REST API v1 | `TODOIST_API_TOKEN` |
| 7-day task + date horizon | Todoist + life-ledger | — |
| Life-ledger reminders | `ledger.json` | configured in setup |

---

## Manual run

```bash
python3 ~/.openclaw/agents/main/workspace/skills/daily-brief/daily_brief.py morning
python3 ~/.openclaw/agents/main/workspace/skills/daily-brief/daily_brief.py evening
```

---

## Required secrets

All stored in `~/.openclaw/shared/secrets/openclaw-secrets.env`:

| Variable | Description |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Telegram bot token |
| `TODOIST_API_TOKEN` | Todoist REST API token (shared with task-bridge) |
| `OPENWEATHER_API_KEY` | OpenWeatherMap API key (free tier — new keys take up to 2h to activate) |
| `DAILY_BRIEF_ICS_*` | One entry per calendar, key name is up to you |

---

## Calendar — ICS feeds

daily-brief fetches calendar events from standard ICS (iCalendar) URLs. These work with any calendar service that can publish a shareable ICS link:

- **Outlook.com (personal):** Settings → View all Outlook settings → Calendar → Shared calendars → Publish a calendar → Can view all details → Publish → copy **ICS** link
- **Office 365 (work/school):** Same flow at `outlook.office.com` (requires IT to have external publishing enabled)
- **Google Calendar:** Calendar settings → [calendar name] → Integrate calendar → Secret address in iCal format
- **iCloud:** Calendar → share → Public Calendar → copy link (change `webcal://` to `https://`)

**ICS URLs are treated as secrets** — they give read access to your calendar to anyone who has them. They are stored in `openclaw-secrets.env`, never in `config.json`. Config only stores the secret key name.

---

## Config file

`~/.openclaw/config/daily-brief/config.json` — written by `setup.py`.

```json
{
  "telegram": {
    "chat_id": -1001234567890,
    "thread_id": 99
  },
  "weather": {
    "lat": 0.0000,
    "lon": 0.0000,
    "city_name": "Your City"
  },
  "calendar": {
    "enabled": true,
    "calendars": [
      {"label": "Personal", "ics_secret_key": "DAILY_BRIEF_ICS_PERSONAL"},
      {"label": "Work",     "ics_secret_key": "DAILY_BRIEF_ICS_WORK"}
    ]
  },
  "life_ledger": {
    "enabled": true,
    "path": "/home/USER/.openclaw/shared/life-ledger/ledger.json"
  },
  "pulse_board": {
    "enabled": true,
    "last_delivered_path": "/home/USER/.openclaw/agents/main/workspace/skills/pulse-board/last-delivered.md"
  },
  "alert_window_days": 7
}
```

**Field notes:**

- `telegram.thread_id` — the `message_thread_id` of the daily-brief topic. Messages go to main group chat if null.
- `calendar.calendars` — list of calendars. Add as many as needed. Each entry needs a `label` (display name) and an `ics_secret_key` (the variable name to look up in `openclaw-secrets.env`).
- `life_ledger.enabled` — set false if life-ledger not installed; section omitted entirely.
- `pulse_board.enabled` — set false if pulse-board not installed; section omitted entirely.
- `alert_window_days` — how many days ahead to scan for life-ledger dates and Todoist horizon tasks.

---

## Life-ledger scanning

daily-brief reads `ledger.json` but **never writes to it**. Scans all entries for:
- Keys named `birthday`, `born`, `anniversary`, `contract_end`, `appointment`, `deadline`, `expires`, `renewal`, `reminder`, `date`, or any key containing "date"
- Notes containing `reminder:`, `remind:`, `birthday:`, or `due:` followed by a date

Dates without a year (e.g. `"09-15"`) are interpreted as the current or next occurrence.

---

## Section degradation

Every section is wrapped in an independent try/except. If one data source fails, the rest of the briefing still sends. Errors go to `daily-brief.log`, not into the Telegram message.

---

## Logs

`~/.openclaw/agents/main/workspace/skills/daily-brief/daily-brief.log`

---

## Cron

```bash
crontab -l | grep daily-brief
```

The crontab includes a `PATH=` line with `~/.npm-global/bin` so `openclaw` resolves correctly in cron context.

---

## Related skills

| Skill | Relationship |
|---|---|
| `pulse-board` | Separate skill — system health. daily-brief reads `last-delivered.md` for the rig one-liner only. |
| `task-bridge` | Shares `TODOIST_API_TOKEN` |
| `life-ledger` | daily-brief reads `ledger.json` — read-only |
