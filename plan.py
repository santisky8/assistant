"""Build the next 14 days as a calendar (.ics) from schedule.json, the job tracker and jobs.json,
then publish it to a secret GitHub Gist that Google Calendar subscribes to.

Placeholders in schedule titles:
  {outreach}    connection requests + follow-ups due, from the tracker's Contacts tab
  {apply:N}     N real open jobs from jobs.json not yet in the tracker's Applications tab
  {leetcode:N}  N LeetCode problems, rotating through the 5 core patterns

Usage:
  uv run plan.py            # write out/plan.ics
  uv run plan.py --publish  # also push it to the gist in schedule.json
"""
import argparse
import json
import re
import subprocess
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).parent
OUT = ROOT / "out"
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
PATTERNS = ["Two pointers / sliding window", "Hash map / set", "BFS / DFS", "Fast & slow pointers", "Binary search"]


def rows(wb, name):
    ws = wb[name]
    head = [c.value for c in ws[1]]
    return [dict(zip(head, r)) for r in ws.iter_rows(min_row=2, values_only=True) if any(r)]


def as_date(v):
    return v.date() if isinstance(v, datetime) else v if isinstance(v, date) else None


class Planner:
    def __init__(self, cfg):
        wb = load_workbook(cfg["tracker"], data_only=True)
        self.contacts = rows(wb, "Contacts")
        applied = {(r["Company"] or "").lower() for r in rows(wb, "Applications") if r["Status"] != "To apply"}
        jobs = json.loads((ROOT / "jobs.json").read_text(encoding="utf-8")) if (ROOT / "jobs.json").exists() else []
        # roles at your level first, senior roles after
        self.jobs = sorted((j for j in jobs if j["company"].lower() not in applied),
                           key=lambda j: "senior" in j["title"].lower())
        self.next_job = 0
        self.next_pattern = 0

    def apply(self, n, day):
        picks = self.jobs[self.next_job:self.next_job + n]
        self.next_job += n
        lines = [f"- {j['title']} at {j['company']}: {j['url']}" for j in picks]
        if len(picks) < n:
            lines.append(f"- {n - len(picks)} more from the Targets tab (priority A) or Applications 'To apply'")
        lines.append("After each one: log it in Applications, then connect with 2 people there.")
        return f"{n} application{'s' * (n != 1)}", lines

    def leetcode(self, n, day):
        picks = [PATTERNS[(self.next_pattern + i) % len(PATTERNS)] for i in range(n)]
        self.next_pattern += n
        return f"{n} LeetCode", [f"- Pattern: {p} (20-minute rule)" for p in picks] + ["Log each in the Learning tab."]

    def outreach(self, n, day):
        due = [c for c in self.contacts if as_date(c.get("Next date")) and as_date(c["Next date"]) <= day
               and c["Status"] not in ("Referred (written)", "Referred (call)", "Not a fit")]
        find = [c for c in self.contacts if c["Status"] == "Find person"]
        lines = ["Follow-ups due:"] + [f"- {c['Person'] or '?'} ({c['Company']}): {c['Next action']}" for c in due] \
            if due else ["No follow-ups due (check Contacts for new replies)."]
        lines += ["", "15 new connection requests with a note (Messages tab). Start with:"]
        lines += [f"- Find someone at {c['Company']} ({c['Job / role']})" for c in find[:5]]
        lines.append("- Then priority A companies in Targets. Log each person in Contacts.")
        return "Outreach: 15 requests + follow-ups", lines

    def expand(self, title, day):
        notes = []

        def sub(m):
            label, lines = getattr(self, m.group(1))(int(m.group(2) or 0), day)
            notes.extend(lines)
            return label

        return re.sub(r"\{(\w+)(?::(\d+))?\}", sub, title), notes


def esc(text):
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def build(cfg, start, days=14):
    p = Planner(cfg)
    tz = cfg["tz"]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//santisky8//job-assistant//EN",
           "X-WR-CALNAME:Daily plan", f"X-WR-TIMEZONE:{tz}", "REFRESH-INTERVAL;VALUE=DURATION:PT6H"]
    for i in range(days):
        day = start + timedelta(days=i)
        for n, (s, e, title, *extra) in enumerate(cfg["days"][DAYS[day.weekday()]]):
            summary, notes = p.expand(title, day)
            notes = extra + notes
            d = day.strftime("%Y%m%d")
            out += ["BEGIN:VEVENT", f"UID:{d}-{n}@job-assistant", f"DTSTAMP:{stamp}",
                    f"DTSTART;TZID={tz}:{d}T{s.replace(':', '')}00", f"DTEND;TZID={tz}:{d}T{e.replace(':', '')}00",
                    f"SUMMARY:{esc(summary)}"]
            if notes:
                out.append(f"DESCRIPTION:{esc(chr(10).join(notes))}")
            out += ["BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{esc(summary)}", "TRIGGER:-PT5M", "END:VALARM",
                    "END:VEVENT"]
    out.append("END:VCALENDAR")
    return "\r\n".join(out) + "\r\n"


def publish(cfg, ics):
    if not cfg.get("gist_id"):
        raise SystemExit("Set gist_id in schedule.json first.")
    repo = OUT / "gist"
    if not repo.exists():
        subprocess.run(["git", "clone", "-q", f"https://gist.github.com/{cfg['gist_id']}.git", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "pull", "-q"], check=True)
    (repo / "plan.ics").write_text(ics, encoding="utf-8", newline="")
    subprocess.run(["git", "-C", str(repo), "add", "plan.ics"], check=True)
    if subprocess.run(["git", "-C", str(repo), "diff", "--cached", "--quiet"]).returncode:
        subprocess.run(["git", "-C", str(repo), "commit", "-qm", f"plan {date.today()}"], check=True)
        subprocess.run(["git", "-C", str(repo), "push", "-q"], check=True)
    print(f"Published. Subscribe URL: https://gist.githubusercontent.com/{cfg['github_user']}/{cfg['gist_id']}/raw/plan.ics")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--publish", action="store_true")
    ap.add_argument("--days", type=int, default=14)
    args = ap.parse_args()
    cfg = json.loads((ROOT / "schedule.json").read_text(encoding="utf-8"))
    ics = build(cfg, date.today(), args.days)
    OUT.mkdir(exist_ok=True)
    (OUT / "plan.ics").write_text(ics, encoding="utf-8", newline="")
    print(f"Wrote {OUT / 'plan.ics'}")
    if args.publish:
        publish(cfg, ics)


if __name__ == "__main__":
    main()
