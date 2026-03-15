# Daily Brief

An [OpenClaw](https://github.com/LittleJakub) skill that posts a morning and evening personal briefing via a configurable channel (Feishu or Telegram) — weather, calendar events, tasks, life reminders, and a rig health check.

This is a **personal day planner**, not a system health monitor. For system health, see [pulse-board](https://github.com/LittleJakub/pulse-board).

---

## What's in each briefing

### Morning — 06:00

| Section | Source |
|---|---|
| Weather today | OpenWeatherMap (free tier) |
| Today's calendar | ICS feeds (Outlook, Google, iCloud, etc.) |
| Tasks due today + overdue | Todoist REST API v1 |
| Life-ledger reminders (7-day window) | [life-ledger](https://github.com/LittleJakub/life-ledger) skill |
| Rig status (one-liner) | [pulse-board](https://github.com/LittleJakub/pulse-board) |

### Evening — 21:00

| Section | Source |
|---|---|
| Tomorrow's calendar | ICS feeds |
| Weather tomorrow | OpenWeatherMap |
| Unfinished items from today | Todoist REST API v1 |
| 7-day task + date horizon | Todoist + life-ledger |
| Life-ledger reminders | life-ledger skill |

Life-ledger and pulse-board are **optional** — setup asks whether they're installed and omits their sections cleanly if not.

---

## Delivery channels

Set `"channel"` in `config.json` to route briefings to the right place:

| Value | Description |
|---|---|
| `"feishu"` | Feishu chat topic via tenant access token |
| `"telegram"` | Telegram supergroup topic (default) |

Both channel configs can coexist in `config.json` — only the active one is used. Switching channels is a one-line config change.

---

## Requirements

- Python 3.9+ (stdlib only — no pip dependencies)
- OpenWeatherMap API key (free tier — new keys take up to 2 hours to activate)
- Todoist account + API token
- **Feishu** (primary): Feishu app with `app_id` + `app_secret`, and a target chat + topic
- **Telegram** (fallback): bot token, supergroup `chat_id`, and topic `thread_id`

Optional:
- ICS calendar URLs (Outlook.com, Office 365, Google Calendar, iCloud, or any standard ICS source)
- [life-ledger](https://github.com/LittleJakub/life-ledger) — for upcoming date/reminder alerts
- [pulse-board](https://github.com/LittleJakub/pulse-board) — for the morning rig status one-liner

---

## Install

```bash
# Copy files to your skill directory
cp daily_brief.py setup.py SKILL.md CHANGELOG.md _meta.json \
  ~/.openclaw/agents/main/workspace/skills/daily-brief/

# Run interactive setup
python3 ~/.openclaw/agents/main/workspace/skills/daily-brief/setup.py
```

Setup will:
- Ask for your delivery channel and corresponding credentials
- Ask for your city name, coordinates, and OpenWeatherMap key
- Ask for your Todoist token
- Ask about calendar ICS feeds — how many, label and secret key for each
- Ask whether life-ledger and pulse-board are installed (and where)
- Offer to validate each API live before writing anything
- Write `~/.openclaw/config/daily-brief/config.json`
- Install two cron entries (06:00 and 21:00)

---

## Config structure

`~/.openclaw/config/daily-brief/config.json`:

```json
{
  "channel": "feishu",
  "feishu": {
    "chat_id": "oc_...",
    "thread_id": "omt_..."
  },
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

`channel` defaults to `"telegram"` if omitted.

---

## Required secrets

All in `~/.openclaw/shared/secrets/openclaw-secrets.env`:

| Variable | Description |
|---|---|
| `FEISHU_APP_ID` | Feishu app ID |
| `FEISHU_APP_SECRET` | Feishu app secret |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token (fallback channel) |
| `TODOIST_API_TOKEN` | Todoist REST API token |
| `OPENWEATHER_API_KEY` | OpenWeatherMap API key |
| `DAILY_BRIEF_ICS_*` | One per calendar — name is up to you |

---

## Calendar setup

daily-brief uses ICS feeds — a universal, auth-free calendar format supported by every major calendar service.

**ICS URLs are treated as secrets.** Store them in `openclaw-secrets.env`:

```bash
echo "DAILY_BRIEF_ICS_PERSONAL=https://outlook.live.com/owa/calendar/..." \
  >> ~/.openclaw/shared/secrets/openclaw-secrets.env

echo "DAILY_BRIEF_ICS_WORK=https://outlook.office365.com/owa/calendar/..." \
  >> ~/.openclaw/shared/secrets/openclaw-secrets.env
```

**How to get your ICS URL:**

| Service | Path |
|---|---|
| Outlook.com | Settings → View all Outlook settings → Calendar → Shared calendars → Publish a calendar → Can view all details → Publish → copy **ICS** link |
| Office 365 | Same flow at `outlook.office.com` (requires IT to allow external publishing) |
| Google Calendar | Calendar settings → [calendar name] → Integrate calendar → Secret address in iCal format |
| iCloud | Calendar app → share → Public Calendar → copy link (change `webcal://` to `https://`) |

---

## Manual run

```bash
python3 ~/.openclaw/agents/main/workspace/skills/daily-brief/daily_brief.py morning
python3 ~/.openclaw/agents/main/workspace/skills/daily-brief/daily_brief.py evening
```

---

## Why ICS and not Microsoft Graph?

Microsoft deprecated personal account app registration outside a directory in June 2024. Getting a directory now requires an Azure subscription — not a reasonable dependency for a home server skill. ICS export requires no auth, no app registration, and works for personal Outlook.com and (if IT allows external publishing) work/school Microsoft 365 accounts.

---

## Section degradation

Every section is independent. If weather is down, calendar and tasks still appear. Errors go to `daily-brief.log`, not into the message.

---

## Formatting

Briefs are composed in HTML internally. When delivering to **Telegram**, HTML parse_mode is used directly. When delivering to **Feishu**, HTML is converted to plain text (`<b>` → `*bold*`, remaining tags stripped) since Feishu text messages don't support HTML.

---

## License

MIT
