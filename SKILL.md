# daily-brief

**Version:** 1.2.0
**Location:** `~/.openclaw/agents/main/workspace/skills/daily-brief/`

---

## What it does

`daily-brief` posts two personal briefings to a configurable channel (Feishu or Telegram) each day — a morning edition and an evening edition. Personal day planner, not a system health monitor (that's pulse-board).

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

All in `~/.openclaw/shared/secrets/openclaw-secrets.env`:

| Variable | Description |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Telegram bot token (when channel = telegram) |
| `TODOIST_API_TOKEN` | Todoist REST API token (shared with task-bridge) |
| `OPENWEATHER_API_KEY` | OpenWeatherMap API key (free — new keys take up to 2h to activate) |
| `FEISHU_APP_ID` | Feishu app ID (when channel = feishu) |
| `FEISHU_APP_SECRET` | Feishu app secret (when channel = feishu) |
| `FEISHU_HORIZON_ROOT_MSG` | Root `om_xxx` message ID of the target Feishu topic |
| `DAILY_BRIEF_ICS_*` | One per calendar — name is up to you |

---

## Config file

`~/.openclaw/config/daily-brief/config.json` — written by `setup.py`.

```json
{
  "channel": "feishu",
  "feishu": {
    "chat_id": "oc_..."
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

**Notes:**
- `channel` — `"feishu"` or `"telegram"`. Defaults to `"telegram"` if omitted.
- `feishu.thread_id` — not used. Topic routing is via `FEISHU_HORIZON_ROOT_MSG` secret (reply API).
- `calendar.calendars` — add as many calendars as needed.
- `life_ledger.enabled` / `pulse_board.enabled` — set false to omit those sections entirely.

---

## Feishu topic routing

Feishu rejects `receive_id_type=thread_id` with a field validation error. The only working method to post into an existing topic is the reply API, using the root `om_xxx` message ID of that thread.

To get the root message ID of a topic:

```bash
source ~/.openclaw/shared/secrets/openclaw-secrets.env

TOKEN=$(curl -s https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal \
  -H "Content-Type: application/json" \
  -d "{\"app_id\":\"$FEISHU_APP_ID\",\"app_secret\":\"$FEISHU_APP_SECRET\"}" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["tenant_access_token"])')

curl -s "https://open.feishu.cn/open-apis/im/v1/messages?container_id_type=thread&container_id=$FEISHU_TOPIC_HORIZON&page_size=1" \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["data"]["items"][0]["message_id"])'
```

Store the result as `FEISHU_HORIZON_ROOT_MSG` in `openclaw-secrets.env`.

---

## Calendar — ICS feeds

Works with any calendar that provides an ICS URL. URLs stored in secrets, never in config.

| Service | Path |
|---|---|
| Outlook.com | Settings → Calendar → Shared calendars → Publish → copy ICS link |
| Office 365 | Same flow at `outlook.office.com` (requires IT to allow external publishing) |
| Google Calendar | Calendar settings → Integrate calendar → Secret address in iCal format |
| iCloud | Share → Public Calendar → copy link (change `webcal://` to `https://`) |

---

## Logs

`~/.openclaw/agents/main/workspace/skills/daily-brief/daily-brief.log`

---

## Cron

```bash
crontab -l | grep daily-brief
```

Includes a `PATH=` line with `~/.npm-global/bin` so `openclaw` resolves in cron context.

---

## Related skills

| Skill | Relationship |
|---|---|
| `pulse-board` | daily-brief reads `last-delivered.md` for the morning rig one-liner |
| `task-bridge` | Shares `TODOIST_API_TOKEN` |
| `life-ledger` | daily-brief reads `ledger.json` — read-only |
