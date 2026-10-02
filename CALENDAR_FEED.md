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

## Progress back from Lyfe Time

- Each [daily-plan] busy copy in the primary calendar carries, under its key line, `done=k/N at=HH:MM`.
  N is the leading number of SUMMARY when it starts with one (`3 applications`, `15 connection requests + follow-ups`, `2 LeetCode + 1 git commit`, `5 referral asks (warm contacts)`), else 1. `at` is when he actually did it.
- The `Sleep (9 h)` copy carries `done=1/1 bed=HH:MM wake=HH:MM` from the morning check.
- No done line means not reviewed (unknown, not missed). Past copies are kept so plan.py can read them.
- plan.py runs at 21:50 (after the 21:00 evening review) and at logon. Units missed from Monday to today move to the next block of the same kind this week; what is left lands in Sunday's `Catch-up` block. Counts reset each Monday.
- Every day ends with `Wind down + magnesium & omega-3` 21:30-22:00 and `Sleep (9 h)` 22:00-07:00 (DTEND on the next day). Both are fixed: never flagged or moved.

## Rules for consumers (checklist, progress tracking)

- Identify a task by **local date + SUMMARY**. SUMMARY is unique within a day (a repeat gets " (2)") and has no counters or timestamps, so it stays the same across refreshes.
- Every full refresh replaces all future events; keep completion state in the app, keyed as above.
- Lyfe Time copies plan blocks into his primary Google calendar so others see him as busy. Each copy carries the marker `[daily-plan]` in its DESCRIPTION; plan.py and conflict checks ignore events with that marker.
- Blocks that clashed with an in-person event when the plan was built are already moved; their DESCRIPTION starts with "Moved from HH:MM: clashes with <event>."
- Online events (SUMMARY, LOCATION or DESCRIPTION mentions a link, Zoom, Meet, Teams, YouTube, webinar, livestream, "live with", online, virtual or watch) do not block time. A block that overlaps one keeps its time and gets the line "Online at the same time: <event>. Watch it while you do this."
- Treat the feed as read-only. Changes to the routine go in `schedule.json` in this repo.
