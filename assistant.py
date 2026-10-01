"""Remote job assistant: find Europe-friendly remote jobs, rank them against your CV,
build an application pack and find people to ask for a referral.

Usage:
  uv run assistant.py find [--days 14] [--top 30]
  uv run assistant.py rank [--top 30]
  uv run assistant.py apply <job-id>
  uv run assistant.py contacts <job-id>
"""
import argparse
import html
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).parent
JOBS = ROOT / "jobs.json"
OUT = ROOT / "out"
MODEL = "claude-opus-5-5"
UA = {"User-Agent": "Mozilla/5.0 (job-assistant)"}

EUROPE = [
    "europe", "emea", "eu", "eea", "cet", "cest", "uk", "united kingdom", "ireland",
    "germany", "france", "spain", "portugal", "italy", "netherlands", "belgium", "luxembourg",
    "switzerland", "austria", "poland", "czech", "slovakia", "hungary", "romania", "bulgaria",
    "greece", "croatia", "slovenia", "serbia", "estonia", "latvia", "lithuania", "finland",
    "sweden", "norway", "denmark", "iceland", "ukraine", "cyprus", "malta",
]
ANYWHERE = ["worldwide", "anywhere", "global"]


# ---------- helpers ----------

def get_json(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return json.load(r)


def clean(text, limit=None):
    text = re.sub(r"<[^>]+>", " ", html.unescape(text or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit] if limit else text


def to_date(value):
    if isinstance(value, (int, float)) or str(value).isdigit():
        return datetime.fromtimestamp(int(value), timezone.utc)
    try:
        d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        return datetime.now(timezone.utc)


def job(source, id, title, company, location, url, date, description, tags=()):
    return {
        "id": f"{source}-{id}", "source": source, "title": clean(title), "company": clean(company),
        "location": clean(location) or "Not stated", "url": url, "date": to_date(date).date().isoformat(),
        "tags": [str(t) for t in tags], "description": clean(description, 6000),
    }


def load(path, example):
    if not path.exists():
        sys.exit(f"Missing {path.name}. Copy {example} to {path.name} and fill it in.")
    return path.read_text(encoding="utf-8")


def profile():
    return json.loads(load(ROOT / "profile.json", "profile.example.json"))


def saved_jobs():
    if not JOBS.exists():
        sys.exit("No jobs yet. Run: uv run assistant.py find")
    return json.loads(JOBS.read_text(encoding="utf-8"))


def find_job(job_id):
    for j in saved_jobs():
        if j["id"] == job_id:
            return j
    sys.exit(f"Job {job_id} not in jobs.json. Run find again or check the id.")


# ---------- job sources (free public APIs) ----------

def remotive(p):
    out = []
    for term in p["target_roles"]:
        data = get_json("https://remotive.com/api/remote-jobs?search=" + urllib.parse.quote(term))
        out += [job("remotive", j["id"], j["title"], j["company_name"], j["candidate_required_location"],
                    j["url"], j["publication_date"], j["description"], j.get("tags", [])) for j in data["jobs"]]
    return out


def remoteok(p):
    data = get_json("https://remoteok.com/api")[1:]
    return [job("remoteok", j["id"], j.get("position"), j.get("company"), j.get("location"),
                j.get("url"), j.get("date"), j.get("description"), j.get("tags", [])) for j in data]


def arbeitnow(p):
    data = get_json("https://www.arbeitnow.com/api/job-board-api")["data"]
    return [job("arbeitnow", j["slug"], j["title"], j["company_name"], j["location"] + " (Europe)",
                j["url"], j["created_at"], j["description"], j.get("tags", [])) for j in data if j.get("remote")]


def jobicy(p):
    out = []
    for geo in ("europe", "emea", "uk"):
        data = get_json(f"https://jobicy.com/api/v2/remote-jobs?count=100&geo={geo}")
        out += [job("jobicy", j["id"], j["jobTitle"], j["companyName"], j.get("jobGeo", geo), j["url"],
                    j["pubDate"], j.get("jobDescription"), j.get("jobIndustry", [])) for j in data.get("jobs", [])]
    return out


def himalayas(p):
    out = []
    for offset in range(0, 500, 100):
        data = get_json(f"https://himalayas.app/jobs/api?limit=100&offset={offset}")
        for j in data.get("jobs", []):
            where = ", ".join(j.get("locationRestrictions") or []) or "Worldwide"
            out.append(job("himalayas", j["guid"].rstrip("/").split("/")[-1], j["title"], j["companyName"],
                           where, j["applicationLink"], j["pubDate"], j.get("description"), j.get("categories", [])))
    return out


SOURCES = [remotive, remoteok, arbeitnow, jobicy, himalayas]


def europe_ok(location, regions):
    loc = location.lower()
    if loc == "not stated":
        return False
    words = set(re.findall(r"[a-z]+", loc))
    wanted = EUROPE if "europe" in regions or "emea" in regions else []
    wanted += ANYWHERE if "worldwide" in regions else []
    wanted += [r.lower() for r in regions]
    return any((w in words) if " " not in w else (w in loc) for w in wanted)


def score(j, p):
    text = f"{j['title']} {' '.join(j['tags'])} {j['description']}".lower()
    title = j["title"].lower()
    if any(x.lower() in title for x in p.get("exclude", [])):
        return -1
    if not any(r.lower() in title for r in p["target_roles"]):
        return -1
    hits = lambda words: sum(1 for w in words if re.search(rf"\b{re.escape(w.lower())}\b", text))
    # boost: async, flexible hours, hires in Spain. penalty: US-hours overlap, seniority too high.
    return 10 + hits(p["skills"]) + 3 * hits(p.get("boost", [])) - 3 * hits(p.get("penalty", []))


def cmd_find(args):
    p = profile()
    jobs, seen = [], set()
    for source in SOURCES:
        try:
            got = source(p)
            print(f"  {source.__name__}: {len(got)} jobs")
            jobs += got
        except Exception as e:
            print(f"  {source.__name__}: failed ({e})")
    cutoff = (datetime.now(timezone.utc) - timedelta(days=args.days)).date().isoformat()
    keep = []
    for j in jobs:
        key = (j["title"].lower(), j["company"].lower())
        if key in seen or j["date"] < cutoff or not europe_ok(j["location"], p["regions"]):
            continue
        seen.add(key)
        j["score"] = score(j, p)
        if j["score"] >= 0:
            keep.append(j)
    keep.sort(key=lambda j: (j["score"], j["date"]), reverse=True)
    JOBS.write_text(json.dumps(keep, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\n{len(keep)} matching Europe-friendly remote jobs saved to jobs.json\n")
    show(keep[: args.top])


def show(jobs):
    for j in jobs:
        extra = f"  fit {j['fit']}/10: {j['why']}" if "fit" in j else ""
        print(f"[{j['id']}] {j['title']} at {j['company']}\n    {j['location']} | {j['date']} | {j['url']}{extra}\n")


# ---------- Claude ----------

def claude(system, prompt, web=False, effort="high"):
    import anthropic

    client = anthropic.Anthropic()
    messages = [{"role": "user", "content": prompt}]
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 15}] if web else []
    while True:
        r = client.beta.messages.create(
            model=MODEL, max_tokens=16000, system=system, messages=messages, tools=tools,
            output_config={"effort": effort},
            betas=["server-side-fallback-2026-07-01"], fallbacks="default",
        )
        if r.stop_reason != "pause_turn":
            break
        messages.append({"role": "assistant", "content": r.content})
    if r.stop_reason == "refusal":
        sys.exit("Claude declined this request.")
    return "".join(b.text for b in r.content if b.type == "text").strip()


SYSTEM = """You are a career coach and recruiter helping one candidate win remote jobs, ideally with
European companies. Be specific, practical and honest. Never invent experience the candidate does
not have: improve how real experience is described, and name real gaps with a fast way to close them.
Only use contact details that are publicly published. Mark anything you could not verify as
"unverified". Do not guess personal email addresses."""


def cmd_rank(args):
    p, cv = profile(), load(ROOT / "cv.md", "cv.example.md")
    jobs = saved_jobs()
    batch = jobs[: args.top]
    listing = "\n\n".join(f"ID: {j['id']}\n{j['title']} at {j['company']} ({j['location']})\n{j['description'][:1200]}"
                          for j in batch)
    text = claude(SYSTEM, f"""Candidate profile: {json.dumps(p)}

CV:
{cv}

Score each job from 1 to 10 for how likely this candidate is to get an interview, considering
skills, seniority, location eligibility from {p['based_in']}, language needs and the candidate's
preferences: {p.get('preferences', 'none')}. Lower the score for fixed hours far from the candidate's time zone.
Answer ONLY with a JSON array: [{{"id": "...", "fit": 7, "why": "one short sentence"}}]

Jobs:
{listing}""", effort="medium")
    ranks = {r["id"]: r for r in json.loads(text[text.find("["): text.rfind("]") + 1])}
    for j in batch:
        if j["id"] in ranks:
            j["fit"], j["why"] = ranks[j["id"]]["fit"], ranks[j["id"]]["why"]
    jobs.sort(key=lambda j: (j.get("fit", 0), j["score"]), reverse=True)
    JOBS.write_text(json.dumps(jobs, indent=1, ensure_ascii=False), encoding="utf-8")
    show([j for j in jobs if "fit" in j])


def linkedin_links(company, roles):
    people = "https://www.linkedin.com/search/results/people/?keywords="
    google = "https://www.google.com/search?q="
    titles = ["recruiter", "talent acquisition", "hiring manager", "engineering manager", "head of"]
    lines = [f"- {t.title()} at {company}: {people}{urllib.parse.quote(f'{t} {company}')}" for t in titles]
    lines += [f"- {r.title()} at {company} (future teammates): {people}{urllib.parse.quote(f'{r} {company}')}"
              for r in roles[:2]]
    lines.append(f"- Google search of public profiles: {google}"
                 + urllib.parse.quote(f'site:linkedin.com/in "{company}" (recruiter OR "talent acquisition" OR manager) Europe'))
    return "\n".join(lines)


def contacts_prompt(j, p):
    return f"""Find the people this candidate should contact about this job, to ask for advice or a referral.
Use web search. Look at the company website, careers page, team page, blog, GitHub, conference talks
and public LinkedIn profiles that appear in search results.

Give:
1. The best 5 to 8 people to contact: name, role, why them, public profile link, and the best
   channel (LinkedIn note, public work email from the company site, X, GitHub). Prefer people in Spain, then Europe,
   people in the hiring team, and recruiters who post about this role.
2. The company's public hiring contact or careers email, if published.
3. A LinkedIn connection note under 300 characters for each type of person (recruiter, hiring manager,
   peer engineer), signed by {p['name']}. Friendly, specific to the job, no begging.
4. A short follow-up message to send after they accept, asking for a referral or a 15-minute chat.
5. A follow-up plan with days (day 0, day 4, day 10).

Job: {j['title']} at {j['company']} ({j['location']})
Link: {j['url']}
Description: {j['description'][:4000]}"""


def cmd_contacts(args):
    j, p = find_job(args.id), profile()
    report = claude(SYSTEM, contacts_prompt(j, p), web=True)
    save(j, "contacts", report + "\n\n## LinkedIn search links\n\n" + linkedin_links(j["company"], p["target_roles"]))


def cmd_apply(args):
    j, p, cv = find_job(args.id), profile(), load(ROOT / "cv.md", "cv.example.md")
    pack = claude(SYSTEM, f"""Build a complete application pack for this candidate and this job.
Research the company with web search first (product, stack, culture, recent news, remote policy,
whether they hire from {p['based_in']} as an employee or contractor).

Give, with clear Markdown headings:
1. Company brief (5 bullets) and what this team most needs.
2. Fit check: score out of 10, strongest matches, gaps, and how to close each gap in under 2 weeks.
3. Tailored CV: rewritten summary and 6 to 10 bullets using the job's keywords (ATS friendly),
   only from real experience in the CV.
4. Cover letter under 250 words.
5. Answers to likely application questions.
6. Interview prep: 8 likely questions with short answer outlines from the CV, and 3 smart questions to ask.
7. One small portfolio project or demo that would make this candidate stand out for this role.

Candidate profile: {json.dumps(p)}

CV:
{cv}

Job: {j['title']} at {j['company']} ({j['location']})
Link: {j['url']}
Description: {j['description']}""", web=True)
    save(j, "application", pack)
    if not args.no_contacts:
        cmd_contacts(args)


def save(j, kind, text):
    OUT.mkdir(exist_ok=True)
    name = re.sub(r"[^a-z0-9]+", "-", f"{j['company']}-{j['title']}".lower()).strip("-")[:60]
    path = OUT / f"{name}-{kind}.md"
    path.write_text(f"# {j['title']} at {j['company']}\n\n{j['url']}\n\n{text}\n", encoding="utf-8")
    print(f"Saved {path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("find", help="fetch latest Europe-friendly remote jobs")
    f.add_argument("--days", type=int, default=14)
    f.add_argument("--top", type=int, default=30)
    r = sub.add_parser("rank", help="score saved jobs against your CV with Claude")
    r.add_argument("--top", type=int, default=30)
    a = sub.add_parser("apply", help="application pack + referral contacts for one job")
    a.add_argument("id")
    a.add_argument("--no-contacts", action="store_true")
    c = sub.add_parser("contacts", help="people to contact for a referral for one job")
    c.add_argument("id")
    args = ap.parse_args()
    {"find": cmd_find, "rank": cmd_rank, "apply": cmd_apply, "contacts": cmd_contacts}[args.cmd](args)


if __name__ == "__main__":
    main()
