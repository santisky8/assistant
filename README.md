# Remote Job Assistant

A command-line assistant that helps you:

1. **Find** the latest remote jobs open to people in Europe (or worldwide).
2. **Rank** them against your CV, so you apply where you have the best chance.
3. **Apply** with a tailored CV, cover letter, answers and interview prep for each job.
4. **Find people** to contact (recruiters, hiring managers, future teammates) and get ready-to-send LinkedIn notes to ask for advice or a referral.

Job data comes from free public APIs: Remotive, RemoteOK, Arbeitnow, Jobicy and Himalayas.
Ranking, application packs and contact research use Claude (`claude-opus-5-5`) with web search.

## Setup

1. Install [uv](https://docs.astral.sh/uv/).
2. Get an Anthropic API key and set it:
   - PowerShell: `$env:ANTHROPIC_API_KEY = "sk-ant-..."`
   - Bash: `export ANTHROPIC_API_KEY=sk-ant-...`
3. Copy `profile.example.json` to `profile.json` and fill in your target roles, skills and regions.
4. Copy `cv.example.md` to `cv.md` and paste your real CV.

`profile.json`, `cv.md`, `jobs.json` and `out/` are git-ignored, so your personal data stays local.

## Use

```bash
uv run assistant.py find --days 14     # fetch and filter jobs, saves jobs.json
uv run assistant.py rank --top 30      # Claude scores the top 30 against your CV
uv run assistant.py apply <job-id>     # application pack + referral contacts, saved in out/
uv run assistant.py contacts <job-id>  # only the people to contact and messages
```

## Profile fields

| Field | Meaning |
|---|---|
| `target_roles` | Job titles to search for. A job must match one in its title or tags. |
| `skills` | Your skills. More matches rank a job higher. |
| `exclude` | Words in titles you want to skip, for example `director`. |
| `regions` | `europe`/`emea` keeps jobs open to European countries; `worldwide` keeps "anywhere" jobs. You can add country names. |
| `based_in` | Where you live. Claude checks if the company can hire you there. |

## Good practice

- The assistant never invents experience. It rewrites what is really in your CV.
- It uses only public information and does not scrape LinkedIn. It gives you LinkedIn search links to open yourself.
- Send connection notes personally and keep follow-ups polite: no more than 2 follow-ups per person.

## Daily plan in Google Calendar

`plan.py` builds the next 14 days from `schedule.json` (your fixed routine, git-ignored), the job tracker spreadsheet and `jobs.json`. Placeholders in the schedule (`{outreach}`, `{apply:N}`, `{leetcode:N}`) become real tasks: open jobs with links, follow-ups due and people to find.

1. Create a secret gist at gist.github.com with one file named `plan.ics`. Put its id in `schedule.json` (`gist_id`).
2. Run `uv run plan.py --publish` and subscribe in Google Calendar: Other calendars, +, From URL, with the printed URL.
3. Schedule `run_daily.cmd` in Windows Task Scheduler to refresh jobs and the plan every evening.

### Planning around real events

Put your Google Calendar's private iCal address (Settings, your calendar, Integrate calendar, "Secret address in iCal format") in `schedule.json` under `busy_ics`. Each evening the plan moves job-search blocks off in-person events (online ones such as webinars only add a note, since you can follow them while working) into the next free slot between 07:00 and 22:00, may take the time of soft routine blocks (walks, wind down), drops free-time blocks that clash, and never moves work, meals or sleep. Keep that address private: anyone with it can read your calendar.

### Carry-over and metrics

Lyfe Time writes what you did (`done=k/N at=HH:MM`) onto its busy copies of the plan in your Google calendar. Each night plan.py reads them: missed applications, LeetCode, requests and referral asks move to the next block of the same kind that week, and anything left goes to Sunday's catch-up block. It also rewrites the tracker's **Metrics** tab: done vs planned per task, the hours you actually get things done, applications by weekday vs responses, and sleep against the 22:00-07:00 goal.
