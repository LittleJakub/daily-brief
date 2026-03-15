# daily-brief

An [OpenClaw](https://github.com/LittleJakub) skill that posts a morning and evening personal briefing to a Telegram topic — weather, tasks, life reminders, and a rig health check.

This is a **personal day planner**, not a system health monitor. For system health, see [pulse-board](https://github.com/LittleJakub/pulse-board).

---

## What's in each briefing

### Morning — 06:00

| Section | Source |
|---|---|
| Weather today | OpenWeatherMap (free tier) |
| Today's calendar | 📅 *v1.1 — coming* |
| Tasks due today + overdue | Todoist REST API v1 |
| Life-ledger reminders (7-day window) | [life-ledger](https://github.com/LittleJakub/life-ledger) skill |
| Rig status (one-liner) | [pulse-board](https://github.com/LittleJakub/pulse-board) last-delivered.md |

### Evening — 21:00

| Section | Source |
|---|---|
| Tomorrow's calendar | 📅 *v1.1 — coming* |
| Weather tomorrow | OpenWeatherMap |
| Unfinished items from today | Todoist REST API v1 |
| 7-day task + date horizon | Todoist + life-ledger |
| Life-ledger reminders | life-ledger skill |

Life-ledger and pulse-board are **optional** — setup asks whether they're installed and omits their sections cleanly if not.

---

## Requirements

- Python 3.9+ (stdlib only — no pip dependencies)
- A Telegram bot and a supergroup with a dedicated topic
  - Two IDs required: the supergroup's `chat_id` and the topic's `thread_id` (see setup for how to find both)
- OpenWeatherMap API key (free tier — 1000 calls/day)
- Todoist account + API token
- OpenClaw gateway (for the agent integration context, though the script runs standalone via cron)

Optional:
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
- Ask for your Telegram chat_id, thread_id, and bot token
- Ask for your OpenWeatherMap API key and weather location
- Ask for your Todoist token
- Ask whether life-ledger and pulse-board are installed (and where)
- Offer to validate each API live before writing anything
- Write `~/.openclaw/config/daily-brief/config.json`
- Install two cron entries (06:00 and 21:00)

---

## Manual run

```bash
python3 ~/.openclaw/agents/main/workspace/skills/daily-brief/daily_brief.py morning
python3 ~/.openclaw/agents/main/workspace/skills/daily-brief/daily_brief.py evening
```

Prints the briefing to stdout and sends it to Telegram. Good for testing.

---

## Required secrets

All stored in `~/.openclaw/shared/secrets/openclaw-secrets.env`:

| Variable | Description |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Telegram bot token |
| `TODOIST_API_TOKEN` | Todoist REST API token |
| `OPENWEATHER_API_KEY` | OpenWeatherMap API key. **New keys take up to 2 hours to activate.** |

Setup offers to write missing secrets for you.

---

## Calendar — v1.1

Calendar sections are placeholders in v1.0. The hook exists in the code.

**Why not Microsoft Graph?** Microsoft deprecated personal account app registration outside a directory in June 2024. Getting a directory now requires an Azure subscription or the M365 Developer Program — neither is a reasonable ask for a personal home server skill.

**v1.1 plan:** ICS URL export from Outlook.com. No auth, no app registration — just a stable HTTPS URL you generate in Outlook settings. Works for personal accounts and (if IT allows external publishing) for work/school Microsoft 365 accounts too.

---

## Section degradation

Every section is wrapped in an independent try/except. If one data source is down, the rest of the briefing still sends. Errors go to `daily-brief.log`, not into the Telegram message.

---

## Logs

```
~/.openclaw/agents/main/workspace/skills/daily-brief/daily-brief.log
```

---

## Telegram formatting note

Uses **HTML parse_mode** throughout — not Markdown. This avoids the `400 Bad Request` errors that Markdown parse_mode produces when task content contains underscores, asterisks, or other special characters (a lesson learned from pulse-board).

---

## License

MIT
