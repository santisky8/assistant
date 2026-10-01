# Daily plan calendar feed

Contract between this repo (writes the plan) and the Lyfe Time app (santisky8/time, reads it).

## Source

- Feed: `https://gist.githubusercontent.com/santisky8/<gist_id>/raw/plan.ics` (secret gist, refreshed daily at 9 PM by `run_daily.cmd`).
- Google Calendar subscribes to the feed as the calendar **"Daily plan"**. Lyfe Time sees it through the phone's calendar, like other Google calendars (read-only).

## Events

- Covers today plus the next 13 days, in the `TZID` from `schedule.json` (now `America/Toronto`).
- `SUMMARY`: task title, for example `3 applications`, `Outreach: 15 requests + follow-ups`, `Workout: Vertical Pull (L-sit pull-ups)`.
- `DESCRIPTION`: steps, one per line. Lines starting with `- ` are sub-tasks (job links, people to contact, LeetCode patterns).
- `TRANSP:TRANSPARENT`: a reminder that overlaps other blocks (for example `Oatmeal (Meal 3)`). Do not count it as busy time.
- `UID` is `YYYYMMDD-<index>@job-assistant`. The index changes when the routine changes, so do **not** use it as a stable key.

## Rules for consumers (checklist, progress tracking)

- Identify a task by **local date + SUMMARY**. SUMMARY is unique within a day (a repeat gets " (2)") and has no counters or timestamps, so it stays the same across refreshes.
- Every full refresh replaces all future events; keep completion state in the app, keyed as above.
- Treat the feed as read-only. Changes to the routine go in `schedule.json` in this repo.
