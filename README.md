# Pearl of Trades — Autonomous Agents (GitHub Actions)

Two self-running agents for **pearloftrades.com**, scheduled free on GitHub Actions (no Pipedream, no quotas).

| Agent | What it does | Schedule | Runs |
|---|---|---|---|
| **News Desk** | Pulls futures-news RSS, Claude Haiku tags + rewrites in plain English, files to the Economic Calendar, deep-links, pings Slack | every 3 hours | `news_desk.js` (Node) |
| **Daily Bias** | Pulls free OHLCV → desk read (6 contracts) + "Markets now" strip + event radar (FRED-live) + archive, writes the Daily Brief | 4×/day, weekdays | `daily_bias.py` (Python) |
| **Watcher** | Health-checks every prop-firm & software review page's outbound link → flags dead/closed/broken/moved links to Slack (read-only) | weekly (Mon) | `watcher.py` (Python) |

---

## One-time setup (≈10 minutes, all in the browser)

### 1. Create the repo & upload these files
- github.com → **New repository** → name it e.g. `pearl-agents` → **Private** → Create.
- On the repo page → **Add file → Upload files** → drag in **everything in this folder** (including the `.github` folder) → **Commit**.

### 2. Add the secrets
Repo → **Settings → Secrets and variables → Actions → New repository secret**. Add each (same values you used in Pipedream):

| Secret name | Value |
|---|---|
| `WP_BASE` | `https://pearloftrades.com` |
| `WP_USER` | your WordPress login email |
| `WP_APP_PASS` | your WordPress application password |
| `ANTHROPIC_API_KEY` | your Anthropic key |
| `ANTHROPIC_MODEL` | `claude-haiku-4-5-20251001` |
| `SLACK_WEBHOOK_URL` | the #news-desk Slack incoming webhook (News Desk only) |
| `FRED_API_KEY` | your FRED key (Daily Bias only) |

### 3. Turn on Actions & test
- Repo → **Actions** tab → if prompted, **enable workflows**.
- Click **News Desk** → **Run workflow** (the manual button) → watch it run green.
- Same for **Daily Bias**.
- After that they run on their own schedule. Done.

---

## How it's wired
- `news_desk.js` runs the four original Pipedream steps (`pd_A1`–`pd_A4`) unchanged, in sequence — it just emulates Pipedream's `steps`/`$` so the proven code didn't have to be rewritten.
- `daily_bias.py` is the Pipedream handler with a `__main__` entry; pure Python standard library, no pip installs.
- Schedules live in `.github/workflows/*.yml` (cron is **UTC**). Change a `cron:` line to re-time an agent.
- **Manual run** anytime: Actions tab → pick the workflow → **Run workflow**.

## Notes
- GitHub Actions cron can be delayed a few minutes under load — fine for this use.
- Scheduled workflows pause after 60 days of **zero repo activity**; any commit re-arms them.
- Free tier: public repos = unlimited Actions minutes; private repos = 2,000 min/month (these jobs use seconds).
