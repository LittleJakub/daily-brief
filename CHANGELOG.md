# Changelog — daily-brief

## [1.2.0] — 2026-03-15

### Added
- **Configurable delivery channel** — set `"channel": "feishu"` or `"channel": "telegram"` in `config.json`
- `send_feishu()` — delivers briefs to a Feishu chat topic via tenant access token flow (stdlib `urllib` only)
  - Step 1: POST to `/auth/v3/tenant_access_token/internal` with `app_id` + `app_secret`
  - Step 2: POST to `/im/v1/messages` with `receive_id_type=chat_id` and optional `thread_id`
  - Reads `FEISHU_APP_ID`, `FEISHU_APP_SECRET` from secrets
  - Reads `cfg["feishu"]["chat_id"]` and `cfg["feishu"].get("thread_id")`
- `strip_html()` — converts HTML-formatted brief text to Feishu-compatible plain text: `<b>` → `*bold*`, remaining tags stripped
- `send_brief()` — dispatcher that reads `cfg["channel"]` and routes to `send_feishu()` or `send_telegram()`

### Changed
- All delivery now goes through `send_brief()` — `send_telegram()` still exists and is called when `channel = "telegram"` (default)
- `_meta.json` description updated; `FEISHU_APP_ID` and `FEISHU_APP_SECRET` added to secrets list

### Config shape (new fields)
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
  }
}
```
Existing `telegram` block unchanged. `channel` defaults to `"telegram"` if omitted.

## [1.1.0] — 2026-03-15

### Added
- **Calendar integration via ICS feeds** — replaces v1.0 placeholder
  - Fetches and parses iCalendar (`.ics`) feeds using stdlib only
  - Supports any number of calendars (personal, work, shared, etc.)
  - ICS URLs stored in `openclaw-secrets.env` only — never in `config.json`
  - Config references calendars by secret key, not by URL
  - Works with Outlook.com, Office 365, Google Calendar, iCloud, and any standard ICS source
- **iCal parser** (`parse_ics`) — full RFC 5545 line unfolding, handles:
  - All-day events (DATE) and timed events (DATE-TIME)
  - UTC and local-time values
  - Multi-day events (spans via DTEND)
  - Recurring events via RRULE: DAILY, WEEKLY, MONTHLY, YEARLY with INTERVAL
  - CANCELLED event filtering
  - LOCATION display
  - Multi-calendar source tagging per event
- **`setup.py` calendar section** — interactive, asks for label + secret key per calendar, validates each ICS URL, supports adding multiple calendars in one run

### Changed
- Config `calendar` block restructured:
  - `enabled` + `calendars: [{label, ics_secret_key}]` (replaces single `ics_url` field)
  - ICS URLs never stored in config — only the secret key name is stored
- `setup_weather()` now always prompts for city/coordinates — no hardcoded defaults

---

## [1.0.0] — 2026-03-14

### Initial release

- Morning briefing (06:00): weather today, tasks due today + overdue, life-ledger alerts, rig status one-liner
- Evening briefing (21:00): weather tomorrow, unfinished today, 7-day task horizon, life-ledger alerts
- OpenWeatherMap `/data/2.5/forecast`, free tier
- Todoist REST API v1 (`api/v1/tasks`, envelope format `{"results": [...]}`)
- Life-ledger integration (optional): scans `ledger.json` for upcoming dates and keyword-flagged reminders
- Pulse-board integration (optional): morning rig status one-liner from `last-delivered.md`
- Telegram delivery via HTML parse_mode
- Interactive `setup.py`: validates all APIs live, asks about optional skills, writes secrets, installs cron
- Config-driven paths for life-ledger and pulse-board — sections omitted when skills not installed
