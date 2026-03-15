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

Set `"channel"` in `config.json`:

| Value | Description |
|---|---|
| `"feishu"` | Feishu chat topic via tenant access token + reply API |
| `"telegram"` | Telegram supergroup topic (default) |

Both configs can coexist — switching channels is a one-line change.

---

## Requirements

- Python 3.9+ (stdlib only — no pip dependencies)
- OpenWeatherMap API key (free tier — new keys take up to 2 hours to activate)
- Todoist account + API token
- **Feishu** (primary): app with `app_id` + `app_secret`, target chat, and root message ID of the topic
- **Telegram** (fallback): bot token, supergroup `chat_id`, topic `thread_id`

Optional:
- ICS calendar URLs (Outlook.com, Office 365, Google Calendar, iCloud, or any standard ICS source)
- [life-ledger](https://github.com/LittleJakub/life-ledger) — for upcoming date/reminder alerts
- [pulse-board](https://github.com/LittleJakub/pulse-board) — for the morning rig status one-liner

---

## Install

```bash
cp daily_brief.py setup.py SKILL.md CHANGELOG.md _meta.json \
  ~/.openclaw/agents/main/workspace/skills/daily-brief/

python3 ~/.openclaw/agents/main/workspace/skills/daily-brief/setup.py
```

Setup will:
- Ask for your delivery channel and credentials
- Ask for city name, coordinates, and OpenWeatherMap key
- Ask for Todoist token
- Ask about ICS calendar feeds
- Ask whether life-ledger and pulse-board are installed
- Validate each API live before writing anything
- Write `~/.openclaw/config/daily-brief/config.json`
- Install cron entries (06:00 and 21:00)

---

## Feishu topic routing

Feishu rejects `receive_id_type=thread_id`. The only working method to post into an existing topic is the reply API, targeting the root `om_xxx` message ID of the thread.

Get the root message ID of your target topic:

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

Store the result:
```bash
echo "FEISHU_HORIZON_ROOT_MSG=om_xxx..." \
  >> ~/.openclaw/shared/secrets/openclaw-secrets.env
```

---

## Calendar setup

ICS URLs are treated as secrets — store them in `openclaw-secrets.env`:

```bash
echo "DAILY_BRIEF_ICS_PERSONAL=https://..." \
  >> ~/.openclaw/shared/secrets/openclaw-secrets.env
```

| Service | Path |
|---|---|
| Outlook.com | Settings → Calendar → Shared calendars → Publish → copy ICS link |
| Office 365 | Same flow at `outlook.office.com` (requires IT to allow external publishing) |
| Google Calendar | Calendar settings → Integrate calendar → Secret address in iCal format |
| iCloud | Share → Public Calendar → copy link (change `webcal://` to `https://`) |

---

## Required secrets

All in `~/.openclaw/shared/secrets/openclaw-secrets.env`:

| Variable | Description |
|---|---|
| `FEISHU_APP_ID` | Feishu app ID |
| `FEISHU_APP_SECRET` | Feishu app secret |
| `FEISHU_HORIZON_ROOT_MSG` | Root `om_xxx` message ID of the target Feishu topic |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token (fallback channel) |
| `TODOIST_API_TOKEN` | Todoist REST API token |
| `OPENWEATHER_API_KEY` | OpenWeatherMap API key |
| `DAILY_BRIEF_ICS_*` | One per calendar — name is up to you |

---

## Manual run

```bash
python3 ~/.openclaw/agents/main/workspace/skills/daily-brief/daily_brief.py morning
python3 ~/.openclaw/agents/main/workspace/skills/daily-brief/daily_brief.py evening
```

---

## Why ICS and not Microsoft Graph?

Microsoft deprecated personal account app registration outside a directory in June 2024. ICS export requires no auth, no app registration, and works for personal Outlook.com and (if IT allows external publishing) work/school Microsoft 365 accounts.

---

## Formatting note

Briefs are composed in HTML internally. Telegram receives them with `parse_mode: HTML`. Feishu receives plain text — all HTML tags are stripped before delivery.

---

## License

MIT
