# Changelog — daily-brief

## [1.3.0] — 2026-03-15

### Added
- **Prep reminders in evening briefing** — keyword-matches tomorrow's calendar events and suggests what to pack/prepare
  - Runs after the calendar section; omitted entirely if no events or no matches
  - Keyword → action table has sensible defaults (gym, flight, meeting, doctor, exam, hike, etc.)
  - Fully configurable via `config.json` under `"prep_reminders": {"keywords": {...}}` — add, remove, or override any keyword without touching code
  - Degrades independently — if it fails, the rest of the evening briefing is unaffected
  - `tomorrow_events` hoisted out of the calendar try/except so prep reminders work even if calendar formatting fails

---

## [1.2.0] — 2026-03-15

### Added
- **Configurable delivery channel** — `"channel": "feishu"` or `"channel": "telegram"` in `config.json`
- `send_feishu()` — delivers briefs to a Feishu topic via tenant access token flow (stdlib only)
  - Step 1: POST to `/auth/v3/tenant_access_token/internal` with `app_id` + `app_secret`
  - Step 2: POST to `/im/v1/messages/{root_msg_id}/reply` — the only working method for posting into an existing Feishu topic (`receive_id_type=thread_id` is rejected by the API; reply to root `om_xxx` is the correct pattern)
  - `FEISHU_HORIZON_ROOT_MSG` in secrets holds the root message ID of the target topic
  - Fallback: posts to group `chat_id` directly if root msg ID is absent
- `strip_html()` — strips all HTML tags for plain-text delivery to Feishu
- `send_brief()` — dispatcher routing to `send_feishu()` or `send_telegram()` based on `cfg["channel"]`

### Changed
- All delivery now goes through `send_brief()` — `send_telegram()` still used when `channel = "telegram"` (default)
- Morning greeting no longer hardcodes a name
- Docstring updated to reflect multi-channel support

### Config shape (new fields)
```json
{
  "channel": "feishu",
  "feishu": {
    "chat_id": "oc_..."
  },
  "telegram": {
    "chat_id": -1001234567890,
    "thread_id": 99
  }
}
```
`channel` defaults to `"telegram"` if omitted. `feishu.thread_id` is not used — topic routing is via `FEISHU_HORIZON_ROOT_MSG` secret.

### Secrets (new)
- `FEISHU_APP_ID`
- `FEISHU_APP_SECRET`
- `FEISHU_HORIZON_ROOT_MSG` — root `om_xxx` message ID of the target Feishu topic

---

## [1.1.0] — 2026-03-15

### Added
- **Calendar integration via ICS feeds** — replaces v1.0 placeholder
  - Fetches and parses iCalendar (`.ics`) feeds using stdlib only
  - Supports any number of calendars (personal, work, shared, etc.)
  - ICS URLs stored in `openclaw-secrets.env` only — never in `config.json`
  - Works with Outlook.com, Office 365, Google Calendar, iCloud, and any standard ICS source
- **iCal parser** — RFC 5545 line unfolding, all-day and timed events, multi-day events, recurring events (DAILY/WEEKLY/MONTHLY/YEARLY + INTERVAL), CANCELLED filtering, LOCATION display, multi-calendar source tagging
- **`setup.py` calendar section** — interactive, validates each ICS URL live, supports multiple calendars

### Changed
- Config `calendar` block: `enabled` + `calendars: [{label, ics_secret_key}]`
- `setup_weather()` always prompts for city/coordinates — no hardcoded defaults

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
