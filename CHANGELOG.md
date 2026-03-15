# Changelog — daily-brief

## [1.0.0] — 2026-03-14

### Initial release

- Morning briefing (06:00): weather today, tasks due today + overdue, life-ledger alerts, rig status one-liner
- Evening briefing (21:00): weather tomorrow, unfinished today, 7-day task horizon, life-ledger alerts
- OpenWeatherMap `/data/2.5/forecast`, free tier — any location, configurable via setup
- Todoist REST API v1 (`api/v1/tasks`, envelope format `{"results": [...]}`)
- Life-ledger integration (optional): scans `ledger.json` for upcoming dates and keyword-flagged reminders; year-agnostic birthday support
- Pulse-board integration (optional): morning rig status one-liner from `last-delivered.md`
- Telegram delivery via **HTML parse_mode** (avoids `400 Bad Request` errors from Markdown when task content contains special characters)
- Calendar sections are v1.1 placeholders — ICS URL method planned (Microsoft Graph deprecated for personal accounts)
- All sections degrade independently — one failed API call does not prevent the rest of the briefing from sending
- Interactive `setup.py`: validates all three APIs live, asks about optional skills, writes secrets, installs cron, handles Ctrl+C cleanly
- Config-driven paths for life-ledger and pulse-board — sections omitted entirely when those skills are not installed
