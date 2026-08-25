# PJ Job Scraper — LA / Orange County / Long Beach

Automated watchers that scrape **account-management / client & customer success, marketing / communications, project & operations coordination, sales / business development, and entertainment roles**, commit the results to the repo, and surface them in the [`triage.html`](#interactive-triage-dashboard--triagehtml) dashboard. Sources are limited to LA / Orange County / Long Beach; US-remote roles are off by default (`INCLUDE_REMOTE_US` flag in `scrape_jobs.py` — a one-line flip to widen the net).

This is a fork of [`Job_Scraper`](https://github.com/ernestod1998/Job_Scraper), operated by Ernesto for PJ.

## What It Does

### 1. LinkedIn watcher — hourly, last 1h
Hits LinkedIn's public guest endpoint for LA-metro roles posted in **the last hour** across multiple search terms, dedupes by job ID, and sorts by recency. Output goes to `linkedin_jobs.json`, `linkedin_jobs.md`, and `linkedin_jobs.html`.

Runs hourly, driven externally by cron-job.org with the in-GH watchdog as backup. A block guard preserves the previous results when LinkedIn returns zero cards across every term (rate-limited run), so the dedupe baseline and dashboard column survive.

> ⚠️ Uses the unauthenticated public guest endpoint only — **never** signs in with a user account and does not use LinkedIn cookies, tokens, or credentials.

### 2. Indeed watcher — every 1h, last 24h
Uses [`python-jobspy`](https://pypi.org/project/python-jobspy/) (Indeed's public RSS and Publisher API were both deprecated in 2026; the site sits behind Cloudflare's top-tier bot product, so stdlib `urllib` is blocked at the edge). JobSpy uses Indeed's mobile-app API internally — no proxies required, no documented rate limit. Output goes to `indeed_jobs.json`, `indeed_jobs.md`, and `indeed_jobs.html`, deduped against the previous run.

Scheduled externally by cron-job.org, offset from the LinkedIn slot to reduce contention on the shared commit-push concurrency group.

### 3. Broad sources — boards, government, and the ATS registry
ZipRecruiter + Google (twice daily), USAJOBS, NEOGOV/governmentjobs.com, CalOpps, CalCareers, and a 2,100-board direct-ATS registry (daily shard cycle) — see [Extra sources](#extra-sources--features) and the [registry section](#broad-ats-registry) below.

## Keywords Matched

A title is included if it contains any of (case-insensitive substring match), grouped by lane:

**Account management / client & customer success:** `account coordinator`, `account manager`, `client success`, `customer success`, `client services`, `client relations`, `customer onboarding`, `customer experience specialist`, …

**Marketing / communications:** `marketing coordinator/specialist/associate/assistant`, `brand coordinator`, `brand marketing`, `assistant brand manager`, `campaign coordinator`, `digital/email/growth/field marketing`, `content coordinator/marketing`, `social media coordinator/specialist/manager`, `community manager`, `creative coordinator`, `media planner`, `advertising coordinator`, `public relations`, `publicist`, `publicity`, `communications coordinator/specialist`, `event coordinator`, `experiential marketing`, `promotions coordinator`, …

**Project & operations coordination:** `project coordinator`, `junior/associate/assistant project manager`, `program coordinator/associate/specialist`, `operations coordinator/specialist/associate`, `business operations`, `implementation coordinator`, `logistics coordinator`, `vendor coordinator`, `procurement coordinator`, `purchasing coordinator`, …

**Sales / business development:** `sales coordinator`, `sales representative`, `inside sales`, `sdr`, `bdr`, `business development representative/coordinator/associate`, `partnerships coordinator`, `sponsorship coordinator`, `sales operations`, `revenue operations`, `crm coordinator/specialist`, …

**Entertainment / Hollywood:** `production coordinator`, `production assistant`, `post-production coordinator`, `development assistant/coordinator`, `talent coordinator`, `talent agency`, `distribution coordinator`, `licensing coordinator/assistant`, `consumer products coordinator`, `merchandising coordinator`, `entertainment marketing`, `studio operations`, …

**Research / insights / e-comm / admin:** `market research`, `consumer insights`, `audience insights`, `research coordinator`, `real estate research`, `transaction coordinator`, `e-commerce coordinator`, `retail marketing`, `administrative coordinator`, `executive assistant`, `recruiting coordinator`, `people operations coordinator`, `outreach coordinator`, …

Bare `coordinator` / `associate` / `specialist` / `manager`, `research associate`, bare `talent`, `trailer`, and `account executive` are deliberately excluded (flood control). The full list is `KEYWORDS` in `scrape_jobs.py`.

**Excluded seniority:** titles containing word-bounded `senior`/`sr`, `staff`, `principal`, `distinguished`, `founding`, `director`, `vice president`, `vp`/`svp`/`evp`, `chief`, `head of`, or `executive director` are dropped everywhere, as are `general|group|regional|national|district` + `manager` combinations. **Bare `manager` and `lead` are allowed** — Account Manager, Community Manager, and Junior Project Manager are target titles. Single-word role keywords are word-bounded, so `sdr` cannot match inside another word.

**Excluded stale postings:** every persisted source drops rows provably older than `MAX_POSTING_AGE_DAYS = 14` (the `"stale"` reason in `_filter_job_observations`). Workday's `"Posted N Days Ago"` strings and Lever's epoch-ms `createdAt` are parseable for this check; rows whose age can't be proven are kept.

**Excluded companies:** `EXCLUDED_COMPANIES` in `scrape_jobs.py` blocks recruiting-platform/aggregator accounts and MLM / commission-only spam (pre-seeded: Vector Marketing, Bankers Life, PHP Agency, Globe Life). Matched case-insensitively against the parsed company name in every source before any digest is written, and as a backstop before anything enters `all_jobs.json`. Add a line there to block the next one.

## Location policies

- The SoCal city-token list (`SOCAL_LOCATIONS`): greater LA, the westside/beach cities, the Valley/studios corridor (Burbank, Glendale, Universal City, Studio City…), Long Beach and the gateway cities, and all of Orange County. Inland Empire is deliberately excluded (one-line add to widen).
- City names with well-known out-of-state namesakes (Glendale AZ, Long Beach NY, Pasadena TX, Orange NJ, Norwalk CT, Hollywood FL, …) require a CA confirmation in the location string (`_SOCAL_AMBIGUOUS`).
- US-remote roles are rejected while `INCLUDE_REMOTE_US = False` (the default).

## Output Files

| File | Source | Description |
|---|---|---|
| `linkedin_jobs.json` / `.md` / `.html` | LinkedIn watcher | Roles posted in the last 1h, deduped against the previous run |
| `indeed_jobs.json` / `.md` / `.html` | Indeed watcher | Indeed-sourced roles posted in the last 24h, deduped against the previous run |
| `boards_jobs.json` / `.md` / `.html` | ZipRecruiter + Google | JobSpy-backed board results |
| `usajobs_jobs.json` / `.md` / `.html` | USAJOBS | Current federal results |
| `governmentjobs_jobs.json` / `.md` / `.html` | NEOGOV | State/local government results |
| `calopps_jobs.json` / `.md` / `.html` | CalOpps | California local-agency results |
| `calcareers_jobs.json` / `.md` / `.html` | CalCareers | California civil-service results |
| `registry_jobs.json` / `.md` / `.html` | ATS registry | Verified-board shard output from the daily registry cycle |
| `all_jobs.json` | All sources | Canonical 14-day master with `feeds` provenance |

The `.html` files are styled standalone digests; the `.md` files render nicely on GitHub. (Both are committed for history/browsing; the `triage.html` dashboard reads the `.json` files directly.)

The scraper workflows keep a GitHub history of generated digests by committing changed result files through the shared race-safe commit/push helper.

### Interactive triage dashboard — `triage.html`

A single-file dashboard hosted on GitHub Pages that merges all the latest source JSONs into one filterable cockpit: search, role/seniority/source filters, save/applied/dismiss buttons persisted in localStorage, top-companies + role-mix charts, and Export/Import buttons for backing up your triage decisions to a file.

Triage state lives in two localStorage keys, deliberately kept apart: `pjTriage:v2` holds your decisions (small, merged on every write, never dropped) and `pjTriage:cache:v1` holds a capped copy of the job list (bulky and disposable). Every decision write merges against what's already stored — newest timestamp per job wins — so a second browser window refreshing can no longer overwrite decisions it never saw. (The keys are `pjTriage:*`, not `jobTriage:*`, because this fork's dashboard shares the `ernestod1998.github.io` origin with the original — distinct keys keep the two dashboards from touching each other's state.) Open `triage.html?selftest=1` to run the merge-rule assertion suite.

#### Cross-device sync — on by default

**Your triage decisions leave your browser.** The ⇅ Sync button mirrors them to a small endpoint (`sync/`, deployed on Vercel, backed by Upstash Redis) so a phone and a laptop can share them. This is **on by default**; the dot on the button shows the current state and **Turn sync off** stops it completely, at which point nothing is uploaded and everything still works.

What's stored: the decision (`saved` / `applied` / `dismissed`) for each job URL, plus the title/company of the jobs you triaged — that's what lets a saved role display on a phone that never fetched it. Nothing else is: the bulky job cache never syncs, and there is no account, email, or profile data involved.

How it identifies you: your browser generates a random 26-character code (~130 bits) and keeps it locally. The server only ever receives `SHA-256(code)`, sent as a request header — so it cannot learn your code, and the code never appears in a URL or a server log. To add a device, hit Sync → **Copy link** and open that link there. Anyone with the link can read and change your decisions, so treat it like a password. Pasting a code **merges** both devices' decisions; it never replaces either side.

Losing the code means losing the bucket — the server only knows its hash, by design. Use **Export** for a backup file.

Dismissals older than 30 days are garbage-collected (safe: `all_jobs.json` prunes at 14 days, so such a job can't reappear). **Saved and applied are kept forever.**

The merge rule exists twice — inline in `triage.html` for the browser and in `sync/merge.js` for the server — because the dashboard is a single file with no build step. `sync/merge.test.mjs` extracts the browser's copy and asserts the two agree; CI fails on any drift.

**View it:** [`https://ernestod1998.github.io/PJ_Job_Scraper/triage.html`](https://ernestod1998.github.io/PJ_Job_Scraper/triage.html)

The dashboard fetches the source JSONs from the same repo at view time, so it always reflects the latest committed scrape. Refresh in the browser to see new data after a cron fire (Pages serves with ~1–2 min lag after each push). No bake-on-cron step in the scraper — `triage.html` is committed once and never modified by automation.

To run locally (e.g. to edit the dashboard UI):
```bash
python3 -m http.server 8765
# then visit http://localhost:8765/triage.html
```
Opening from `file://` won't work — the dashboard needs same-origin HTTP to `fetch()` the source JSONs. (Port 8765 is the localhost origin the sync endpoint's CORS allowlist accepts.)

## Extra sources & features

Beyond the two core watchers, these sources run on their own workflows (all reuse the existing `KEYWORDS` / `is_target_role` gate, so they follow whatever roles you already target):

| Flag | Source | Notes |
|---|---|---|
| `--usajobs-only` | [usajobs.gov](https://www.usajobs.gov) | Federal jobs **with salary**, no API key (public search endpoint). Nationwide query, filtered to LA / OC / Long Beach. |
| `--governmentjobs-only` | [governmentjobs.com](https://www.governmentjobs.com) (NEOGOV) | State & local government; filtered to LA / OC / Long Beach via `is_watch_location()`. |
| `--calopps-only` | [calopps.org](https://www.calopps.org) | California local agencies (cities/counties/special districts). |
| `--calcareers-only` | [calcareers.ca.gov](https://calcareers.ca.gov) | California state civil service (ASP.NET postback). |
| `--boards-only` | ZipRecruiter + Google Jobs | Via `python-jobspy` (same library as Indeed); runs twice daily via `boards_watch.yml`. |

Heavier per-term sources share `GOV_SEARCH_TERMS` (the first 8 entries of `LINKEDIN_SEARCH_TERMS`); widen it to taste. Each source has a matching workflow (`usajobs_watch.yml`, `localgov_watch.yml`, `calcareers_watch.yml`).

**Salary backfill:** the LinkedIn watcher backfills pay from each posting's public guest page (search cards omit it). The dashboard harmonizes every format (hourly / monthly / yearly / `$k` ranges / title-embedded) to an annual figure.

**Dashboard additions:**
- **🗺 Map view** — Leaflet map of roles by city (client-side geocoding, no API key), centered on the LA basin.
- **Salary distribution** chart + a salary-floor slider (filters by minimum annual pay; excludes unlisted-salary roles by default).
- **Cross-source de-duplication** — the same role cross-posted to multiple boards collapses into one card (matched on title + location + compatible company), showing all source badges; triage applies to every copy.
- **Explicit source** shown on each card (`🔗 LinkedIn`, etc.).

**📲 Pushover notifications** (`notify.py`) — get a phone push for each new role.
No-op unless `PUSHOVER_TOKEN` + `PUSHOVER_USER` are set as Actions secrets; dedupes
via `notified.json`. Optional `NOTIFY_TERMS` variable filters by title words. Test
from the **Test Pushover Notification** workflow or `python notify.py --test`.

## Setup

### Triage secrets (optional manual fit scoring)

The scraper workflows need no scoring secrets. Automated LLM scoring and evals are
paused; `triage.yml` and `evals.yml` are manual-dispatch only. If deliberately run,
they read `ANTHROPIC_API_KEY`, `CANDIDATE_PROFILE`, and `CANDIDATE_RESUME` from
**Settings → Secrets and variables → Actions**.

### Run manually

From the **Actions** tab: *LinkedIn Watcher*, *Indeed Watcher*, or any of the source workflows → Run workflow.

Or locally:
```bash
python scrape_jobs.py --linkedin-only  # general LinkedIn, last 1h
python scrape_jobs.py --indeed-only    # Indeed, last 24h (requires python-jobspy)
python scrape_jobs.py --boards-only    # ZipRecruiter + Google
python scrape_jobs.py --registry-only  # one bounded active-registry shard
python scrape_jobs.py --refilter-existing          # preview current-output cleanup
python scrape_jobs.py --refilter-existing --write  # apply cleanup after reviewing preview
python discover.py --registry-seeds --write --limit 100
python discover.py --verify-registry --write --limit 100
```

The LinkedIn pipeline uses only the standard library. Indeed/boards require `pip install -r requirements.txt` (single dep: `python-jobspy`).

## Repo Structure

```
├── scrape_jobs.py                  # All scraping logic
├── discover.py                     # Registry seed/verify helpers (portfolio modes dormant)
├── ats_registry.py                 # Bounded broad-board discovery/verification/scraping
├── ats_registry.json               # Registry state, health, baselines, and cursors
├── triage_agent.py                 # Optional manual fit-scoring agent (paused)
├── eval_triage.py                  # Golden-case evals for the triage agent (paused)
├── requirements.txt                # python-jobspy (Indeed/boards; LinkedIn is stdlib)
├── linkedin_jobs.{json,md,html}    # LinkedIn watcher output (last 1h)
├── indeed_jobs.{json,md,html}      # Indeed watcher output (last 24h, includes JD text)
├── all_jobs.json                   # Cumulative 14-day master with feed provenance
├── workflow_runs.jsonl             # Per-run job counts (scheduler observability)
├── triage.html                     # Interactive dashboard (fetches the JSONs at view time)
└── .github/workflows/
    ├── linkedin_watch.yml          # Hourly — general LinkedIn (last 1h, cron-job.org-driven)
    ├── indeed_watch.yml            # Hourly — Indeed (last 24h, cron-job.org-driven)
    ├── linkedin_watch_backup.yml   # In-GH watchdog — re-dispatches missed runs
    ├── boards_watch.yml            # Twice daily — ZipRecruiter + Google
    ├── registry_watch.yml          # Daily ATS registry seed/verify/scrape cycle
    ├── usajobs_watch.yml / localgov_watch.yml / calcareers_watch.yml
    ├── triage.yml                  # Manual-only fit scoring (paused)
    └── evals.yml                   # Manual-only scoring evals (paused)
```

## ATS Endpoints Used

| ATS | Endpoint |
|---|---|
| [Greenhouse](https://developers.greenhouse.io/job-board.html) | `https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true` |
| Workday | `https://{tenant}.wd1.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs` (POST) |
| [Ashby](https://developers.ashbyhq.com/docs/public-job-posting-api) | `https://api.ashbyhq.com/posting-api/job-board/{slug}` |
| [Lever](https://github.com/lever/postings-api) | `https://api.lever.co/v0/postings/{slug}?mode=json` |
| [Gem](https://api.gem.com/job_board/v0/reference) | `https://api.gem.com/job_board/v0/{slug}/job_posts/` |
| LinkedIn | `https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search` (public guest) |
| Indeed | `python-jobspy` library (mobile-app API; no public endpoint since 2026 deprecation) |

## Broad ATS registry

The `ats_registry.json` registry (2,100 verified company boards) expands source
discovery beyond the big boards. It supports public Greenhouse, Lever, Ashby, and Gem
board locators plus Workday URLs that can be converted to a verified CXS tenant/site
endpoint.

Seed inputs are deliberately bounded:

- [Wayback CDX](https://github.com/internetarchive/wayback/blob/master/wayback-cdx-server/README.md) prefix queries.
- The [YC hiring feed](https://yc-oss.github.io/api/companies/hiring.json).
- Direct ATS URLs from [SimplifyJobs/New-Grad-Positions](https://github.com/SimplifyJobs/New-Grad-Positions), including its [listings file](https://github.com/SimplifyJobs/New-Grad-Positions/blob/dev/.github/scripts/listings.json).
- [Common Crawl](https://index.commoncrawl.org/) only when `--common-crawl` is explicitly supplied.

Simplify data is used only to discover board locators; its job dataset is not copied
into this repository. Candidate verification is cursor-bounded. Three consecutive
failures produce a 30-day cooldown. Active boards are split into seven stable shards,
successful boards with eligible roles are temporarily promoted, and each board
establishes its own notification-free baseline (so a fresh fork's first passes are
silent). Network work is capped at 1,500 HTTP requests or 20 minutes.
`.github/workflows/registry_watch.yml` runs a daily seed → verify → scrape cycle;
manual dispatch still runs a single bounded mode. Scraped registry roles merge into
`all_jobs.json` under the `general` feed, so they appear on the triage dashboard like
any other source.
