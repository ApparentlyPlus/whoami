# whoareyou.plus

My personal site, backend is Flask, no build step, no frontend framework.

## Running locally

```bash
pip install -r requirements.txt
python github_sync.py    # once, to create data/github.json
python app.py            # http://127.0.0.1:5000
```

`python app.py` starts Flask's **development** server. It is fine for local work and wrong for production.

A GitHub token is required to start at all; the app refuses rather than serving a site with every GitHub-driven section silently empty. Set `GITHUB_TOKEN`, put it in `.env`, or be logged into `gh`. To start without one anyway:`ALLOW_NO_GITHUB_TOKEN=1`.

## GitHub sync

The Activity, Open Source and Recent Activity sections are generated from a
snapshot of the GitHub API cached at `data/github.json`. The site always renders
from that file, so a slow or rate-limited API never blocks a page load.

Refreshing needs a token, because the contribution calendar is only exposed over GitHub's GraphQL API. A classic token with `public_repo` (or a fine-grained token with public read access) is enough. `github_sync.py` looks in three places and takes the first hit:

1. `GITHUB_TOKEN` in the environment
2. a `.env` file next to the script (`GITHUB_TOKEN=ghp_...`)
3. `gh auth token`, whatever the GitHub CLI is logged in as

So on a machine with the CLI already authenticated, nothing needs setting up:

```bash
gh auth login              # once, if you haven't
python github_sync.py      # writes data/github.json
```

Shared hosting has no `gh`, so use (1) or (2) there.

Two ways to keep it auto-updating:

1. **Lazy refresh (default).** When a request comes in and the snapshot is more
   than 24h old, the app kicks off a background refresh and serves the existing
   snapshot meanwhile. Set `GITHUB_TOKEN` in the app's environment for this.
2. **Cron.** More predictable on shared hosting where the process may be
   recycled. Put the token in a `.env` file next to `sync-cron.sh` and add:

   ```
   17 4 * * *  /path/to/whoami/sync-cron.sh >> /path/to/whoami/data/sync.log 2>&1
   ```

`data/` is generated and git-ignored since it holds the snapshot plus the sync and update logs. Keeping it out of the repository is deliberate: the daily sync rewrites `github.json`, and a tracked file that changes every day would leave the working tree permanently dirty, which `autoupdate.py` treats (correctly) as a reason to refuse to update. 

Run `python github_sync.py` once after deploying; until then every GitHub-driven section simply doesn't render.

### Tuning

Both live in `github_sync.py`:

- `REPO_DENYLIST`: repos never shown, whatever the API returns.
- `REPO_PRIORITY`: ordering for the public-repo table.

Open-source contributions are separated from personal ones by repository owner,
then ranked by the repo's star count; anything at 1,000+ stars is flagged as a
major project.


## Editing the site's text

Every string lives in **`content.toml`**, including titles, paragraphs, nav labels, award entries, metadata, the 404 copy. The templates read from it and hold no copy of their own, so that file is the only place to edit words.

```toml
[home.hero]
eyebrow = "Systems & Full-Stack Engineer"
title   = "I build things close to the metal: <em>kernels, compilers,</em> ..."
```

* Inline HTML is allowed in any field and `<em>` renders as the amber accent.
* `"""triple-quoted"""` strings may span lines.
* Lists (projects, roles, awards, nav items) are `[[double-bracketed]]` blocks. Add or remove one and the page follows.
* The app re-reads the file whenever it changes, so edits show on refresh with
  no restart. If it fails to parse, the last good version keeps serving and the
  error is logged rather than 500-ing the site.

Numbers from GitHub are never in `content.toml`, only the labels around them.

## Pages

| Route       | What it is                                                |
|-------------|-----------------------------------------------------------|
| `/`         | The recruiter page: hero, work, upstream, experience       |
| `/pawstack` | Case study of the thesis toolchain                        |
| `/activity` | The full GitHub instrumentation                            |
| `/resume`   | The PDF                                                    |
| `/healthz`  | Liveness probe used by the updater's smoke test            |

## Auto-update

`autoupdate.py` pulls the latest source from GitHub once a day, verifies it, and
restarts the site. It is built to refuse rather than risk anything:

* Aborts if the working tree has uncommitted changes to tracked files.
* Aborts if the branch has no upstream, has unpushed commits, or has diverged.
* Only ever **fast-forwards**, never merges, rebases, stashes or force-resets onto a remote.
* After updating it runs a smoke test (imports the app in a fresh interpreter
  and renders `/`, `/pawstack`, `/activity`, `/healthz`). If anything fails it
  **rolls back** to the previous commit, re-verifies, and restarts.
* A commit that fails verification is **quarantined**, so a bad push isn't
  re-applied and rolled back every night. A newer commit clears it.
* `flock` prevents overlapping runs.

```bash
python autoupdate.py --check     # is an update available and safe? changes nothing
python autoupdate.py --dry-run   # show exactly what would happen
python autoupdate.py             # do it
```

Configure with environment variables (or a `.env` beside the script):

| Variable             | Default  | Meaning                                    |
|----------------------|----------|--------------------------------------------|
| `UPDATE_REMOTE`      | `origin` | Remote to fetch from                       |
| `UPDATE_BRANCH`      | current  | Branch to track; refuses if you're on another |
| `UPDATE_RESTART_CMD` | *(none)* | Shell command that restarts the app        |
| `UPDATE_PIP`         | `1`      | Reinstall deps when `requirements.txt` changes |
| `UPDATE_SYNC`        | `1`      | Refresh the GitHub snapshot afterwards     |

`UPDATE_RESTART_CMD` is empty by default, which means the code updates but
nothing is restarted and the log says so. Set it to whatever runs the site:

```bash
UPDATE_RESTART_CMD="systemctl --user restart whoami"      # systemd
UPDATE_RESTART_CMD="mkdir -p tmp && touch tmp/restart.txt" # Passenger / cPanel
UPDATE_RESTART_CMD="docker compose up -d --build"          # Docker
```

Then schedule it:

```
17 4 * * *  /path/to/whoami/update-cron.sh
```


## Deployment

Run the readiness check first since it verifies the interpreter, dependencies, token, content file, data snapshot, every route, and auto-update wiring:

```bash
python preflight.py      # exits non-zero if anything is blocking
```

### What actually runs what

`app.py` is **not** an orchestrator. It serves pages and, when the cached
snapshot is over a day old, kicks off one background refresh. Everything else
is scheduled outside it:

| Piece | Started by | Job |
|---|---|---|
| `wsgi.py` / `passenger_wsgi.py` | your WSGI server | serves the site |
| `github_sync.py` | `sync-cron.sh`, daily | refreshes `data/github.json` |
| `autoupdate.py` | `update-cron.sh`, daily | pulls new code, verifies, restarts |
| `app.py` (lazy refresh) | first request after 24h | backstop if cron is missing |

So a complete deployment is: a process manager keeping a WSGI server alive, plus two cron entries. Nothing supervises the process itself. That is the process manager's job, not this codebase's.

### 1. Install

```bash
pip install -r requirements.txt
echo 'GITHUB_TOKEN=ghp_...' > .env      # chmod 600
python github_sync.py                   # data/ is gitignored, create it once
python preflight.py
```

### 2. Serve

**VPS with systemd** `/etc/systemd/system/whoami.service`:

```ini
[Unit]
Description=whoareyou.plus
After=network.target

[Service]
WorkingDirectory=/srv/whoami
EnvironmentFile=/srv/whoami/.env
ExecStart=/srv/whoami/venv/bin/gunicorn --bind 127.0.0.1:8000 --workers 3 wsgi:application
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
systemctl enable --now whoami
```

Then put nginx or Caddy in front for TLS and to serve `/static` directly.

**cPanel / Passenger**: point the app at `passenger_wsgi.py`. Passenger runs it for you, so gunicorn is unused there. Set `GITHUB_TOKEN` in the panel's environment variables (there is no `gh` on shared hosting), and restart by touching `tmp/restart.txt`.

### 3. Schedule

```
17 4 * * *  /srv/whoami/update-cron.sh    # pull + verify + restart
47 4 * * *  /srv/whoami/sync-cron.sh      # refresh GitHub data
```

Set the restart hook so updates take effect. In `.env`:

```bash
UPDATE_RESTART_CMD="systemctl restart whoami"               # systemd
UPDATE_RESTART_CMD="mkdir -p tmp && touch tmp/restart.txt"  # Passenger
```

Cron runs with a minimal environment, so `gh` is usually not on its `PATH`.
Both cron scripts source `.env`, which is why the token belongs there rather
than in your shell profile.
