# daily-brief

**Version:** 1.0.0
**Location:** `~/.openclaw/agents/main/workspace/skills/daily-brief/`

---

## What it does

`daily-brief` posts two personal briefings to a dedicated Telegram topic each day — a morning edition to start the day, and an evening edition to close it out. This is a **personal day planner**, entirely separate from pulse-board (which handles system health in the exOskeleton thread).

---

## Morning briefing — 06:00 Asia/Shanghai

| Section | Source | Required |
|---|---|---|
| Weather today | OpenWeatherMap | `OPENWEATHER_API_KEY` |
| Today's calendar | 📅 *v1.1 placeholder* | — |
| Tasks due today + overdue | Todoist REST API v1 | `TODOIST_API_TOKEN` |
| Life-ledger reminders (7-day window) | `ledger.json` | configured in setup |
| Rig status (one-liner) | pulse-board `last-delivered.md` | configured in setup |

---

## Evening briefing — 21:00 Asia/Shanghai

| Section | Source | Required |
|---|---|---|
| Tomorrow's calendar | 📅 *v1.1 placeholder* | — |
| Weather tomorrow | OpenWeatherMap | `OPENWEATHER_API_KEY` |
| Unfinished items from today | Todoist REST API v1 | `TODOIST_API_TOKEN` |
| 7-day horizon (tasks + dates) | Todoist + life-ledger | — |
| Life-ledger reminders | `ledger.json` | configured in setup |

---

## Manual run

```bash
python3 ~/.openclaw/agents/main/workspace/skills/daily-brief/daily_brief.py morning
python3 ~/.openclaw/agents/main/workspace/skills/daily-brief/daily_brief.py evening
```

Prints the briefing to stdout and sends to Telegram. Use for testing before the first cron run.

---

## Required environment variables

All stored in `~/.openclaw/shared/secrets/openclaw-secrets.env`:

| Variable | Description |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Telegram bot token (shared with other skills) |
| `TODOIST_API_TOKEN` | Todoist REST API token (shared with task-bridge) |
| `OPENWEATHER_API_KEY` | OpenWeatherMap API key — free tier at openweathermap.org (1000 calls/day). **Note: new keys can take up to 2 hours to activate after signup.** |

---

## Config file

`~/.openclaw/config/daily-brief/config.json` — written by `setup.py`.

```json
{
  "telegram": {
    "chat_id": -1001234567890,
    "thread_id": 123
  },
  "weather": {
    "lat": 0.0000,
    "lon": 0.0000,
    "city_name": "Your City"
  },
  "life_ledger": {
    "enabled": true,
    "path": "/home/USER/.openclaw/shared/life-ledger/ledger.json"
  },
  "pulse_board": {
    "enabled": true,
    "last_delivered_path": "/home/USER/.openclaw/agents/main/workspace/skills/pulse-board/last-delivered.md"
  },
  "calendar": {
    "enabled": false,
    "note": "v1.1 — ICS URL method planned",
    "ics_url": null
  },
  "alert_window_days": 7
}
```

**Field notes:**

- `telegram.thread_id` — the `message_thread_id` of the daily-brief topic. Set after creating the topic in Telegram. Messages go to the main group chat if null.
- `life_ledger.enabled` — set to `false` if life-ledger is not installed; reminders section is omitted entirely.
- `pulse_board.enabled` — set to `false` if pulse-board is not installed; rig status line is omitted entirely.
- `calendar.ics_url` — null in v1.0. v1.1 will read an ICS URL published from Outlook.com or your work calendar.
- `alert_window_days` — how many days ahead to scan for life-ledger dates and Todoist horizon tasks.

---

## Life-ledger scanning

daily-brief reads `ledger.json` but **never writes to it**. It scans all entries for:

- Keys named `birthday`, `born`, `anniversary`, `contract_end`, `appointment`, `deadline`, `expires`, `renewal`, `reminder`, `date`, or any key containing "date"
- Notes containing `reminder:`, `remind:`, `birthday:`, or `due:` followed by a date

Dates without a year (e.g. `"09-15"` for a birthday) are interpreted as the current or next occurrence.

---

## Calendar (v1.1 roadmap)

Calendar sections are placeholders in v1.0. The hook exists in the code (`calendar_placeholder()`).

**v1.1 plan:** ICS URL export from Outlook.com.

- Microsoft Graph API is not viable for personal accounts — app registration outside a directory was deprecated in June 2024 and now requires an Azure subscription.
- ICS export requires no auth, no app registration, and works for both personal Outlook.com and work Microsoft 365 calendars (subject to IT publishing policy for the latter).

**To prepare for v1.1:**
1. In Outlook.com → Settings → View all Outlook settings → Calendar → Shared calendars → Publish a calendar
2. Select the calendar, choose "Can view all details", click Publish
3. Copy the ICS link
4. Set `calendar.ics_url` in config.json
5. Set `calendar.enabled` to `true`

---

## Section degradation

Every section is wrapped in independent try/except. If weather is down, tasks and reminders still appear. If Todoist is unreachable, the rest of the briefing still sends. Errors are written to `daily-brief.log`, not surfaced in the Telegram message.

---

## Logs

`~/.openclaw/agents/main/workspace/skills/daily-brief/daily-brief.log`

---

## Cron

Installed by `setup.py`. Verify with:

```bash
crontab -l | grep daily-brief
```

The crontab includes a `PATH=` line with `~/.npm-global/bin` so `openclaw` resolves correctly in the cron environment (same pattern as pulse-board v1.1.4).

---

## Related skills

| Skill | Relationship |
|---|---|
| `pulse-board` | Separate skill — system health. daily-brief reads its `last-delivered.md` for the rig status one-liner only. |
| `task-bridge` | Shares `TODOIST_API_TOKEN` |
| `life-ledger` | daily-brief reads `ledger.json` — read-only |
