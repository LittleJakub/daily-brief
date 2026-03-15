# daily-brief

An [OpenClaw](https://github.com/LittleJakub) skill that posts a morning and evening personal briefing to a Telegram topic — weather, calendar events, tasks, life reminders, and a rig health check.

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

## Requirements

- Python 3.9+ (stdlib only — no pip dependencies)
- A Telegram bot and a supergroup with a dedicated topic
  - Two IDs required: the supergroup's `chat_id` and the topic's `thread_id` (setup explains how to find both)
- OpenWeatherMap API key (free tier — new keys take up to 2 hours to activate)
- Todoist account + API token

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
- Ask for your Telegram chat_id, thread_id, and bot token (with how-to instructions)
- Ask for your city name, coordinates, and OpenWeatherMap key
- Ask for your Todoist token
- Ask about calendar ICS feeds — how many, label and secret key for each
- Ask whether life-ledger and pulse-board are installed (and where)
- Offer to validate each API live before writing anything
- Write `~/.openclaw/config/daily-brief/config.json`
- Install two cron entries (06:00 and 21:00)

---

## Calendar setup

daily-brief uses ICS feeds — a universal, auth-free calendar format supported by every major calendar service.

**ICS URLs are treated as secrets.** They give read access to your calendar to anyone who has them. Store them in `openclaw-secrets.env`:

```bash
echo "DAILY_BRIEF_ICS_PERSONAL=https://outlook.live.com/owa/calendar/..." \
  >> ~/.openclaw/shared/secrets/openclaw-secrets.env

echo "DAILY_BRIEF_ICS_WORK=https://outlook.office365.com/owa/calendar/..." \
  >> ~/.openclaw/shared/secrets/openclaw-secrets.env
```

Then run setup and provide the key names (`DAILY_BRIEF_ICS_PERSONAL`, `DAILY_BRIEF_ICS_WORK`, etc.) when prompted. You can add as many calendars as you like.

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

## Required secrets

All in `~/.openclaw/shared/secrets/openclaw-secrets.env`:

| Variable | Description |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Telegram bot token |
| `TODOIST_API_TOKEN` | Todoist REST API token |
| `OPENWEATHER_API_KEY` | OpenWeatherMap API key |
| `DAILY_BRIEF_ICS_*` | One per calendar — name is up to you |

---

## Why ICS and not Microsoft Graph?

Microsoft deprecated personal account app registration outside a directory in June 2024. Getting a directory now requires an Azure subscription — not a reasonable dependency for a home server skill. ICS export requires no auth, no app registration, and works for personal Outlook.com and (if IT allows external publishing) work/school Microsoft 365 accounts. Staleness of a few hours is completely acceptable for a morning/evening briefing.

---

## Section degradation

Every section is independent. If weather is down, calendar and tasks still appear. Errors go to `daily-brief.log`, not into the Telegram message.

---

## Telegram formatting

Uses **HTML parse_mode** throughout. Markdown parse_mode produces `400 Bad Request` errors when content contains underscores, asterisks, or other special characters — a lesson learned from pulse-board.

---

## License

MIT
