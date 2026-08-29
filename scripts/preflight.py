#!/usr/bin/env python3

import importlib.util
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

GREEN, YELLOW, RED, DIM, RESET = '\033[32m', '\033[33m', '\033[31m', '\033[2m', '\033[0m'
if not sys.stdout.isatty():
    GREEN = YELLOW = RED = DIM = RESET = ''

results = []

def check(name, state, detail='', fix=''):
    results.append((name, state, detail, fix))

def ok(name, detail=''):    check(name, 'OK', detail)
def warn(name, detail, fix=''): check(name, 'WARN', detail, fix)
def fail(name, detail, fix=''): check(name, 'FAIL', detail, fix)

v = sys.version_info
if v >= (3, 11):
    ok('Python version', f'{v.major}.{v.minor}.{v.micro}')
else:
    fail('Python version', f'{v.major}.{v.minor}, need 3.11+',
         'content.toml is parsed with the stdlib tomllib, added in 3.11.')
try:
    import importlib.metadata
    import flask
    ok('Flask', importlib.metadata.version('flask'))
except ImportError:
    fail('Flask', 'not installed', 'pip install -r requirements.txt')

server = next((m for m in ('gunicorn', 'waitress', 'uwsgi')
               if importlib.util.find_spec(m)), None)
if server:
    ok('Production WSGI server', server)
elif (ROOT / 'passenger_wsgi.py').exists() and os.environ.get('PASSENGER_BASE_URI'):
    ok('Production WSGI server', 'Passenger (supplied by the host)')
else:
    warn('Production WSGI server', 'none installed',
         'pip install -r requirements.txt, do NOT serve with `python app.py`, '
         'that is the Flask development server.')
try:
    import github_sync
    if github_sync.TOKEN:
        source = ('GITHUB_TOKEN' if os.environ.get('GITHUB_TOKEN', '').strip()
                  else '.env file' if github_sync._token_from_env_file()
                  else 'gh CLI')
        ok('GitHub token', f'found via {source}')
        if source == 'gh CLI':
            warn('Token portability', 'only the gh CLI has a token here',
                 'Shared hosting has no gh. Set GITHUB_TOKEN or a .env on the server.')
    elif os.environ.get('ALLOW_NO_GITHUB_TOKEN') == '1':
        warn('GitHub token', 'absent, running degraded via ALLOW_NO_GITHUB_TOKEN',
             'Every GitHub-driven section will be empty.')
    else:
        fail('GitHub token', 'none found — the app refuses to start',
             'export GITHUB_TOKEN=ghp_... or add it to .env, or `gh auth login`')
except Exception as exc:
    fail('GitHub token', f'{exc.__class__.__name__}', str(exc).splitlines()[0])

try:
    import tomllib
    with open(ROOT / 'content.toml', 'rb') as fh:
        content = tomllib.load(fh)
    ok('content.toml', f'{len(content)} sections')
except FileNotFoundError:
    fail('content.toml', 'missing', 'Every string on the site lives here.')
except Exception as exc:
    fail('content.toml', f'does not parse: {exc}')

snapshot = ROOT / 'data' / 'github.json'
if not snapshot.exists():
    fail('GitHub snapshot', 'data/github.json missing',
         'Run:  python github_sync.py    (data/ is gitignored, so a fresh '
         'deploy has none until you do)')
else:
    try:
        import json
        fetched = json.loads(snapshot.read_text())['fetched_at']
        age_h = (datetime.now(timezone.utc)
                 - datetime.fromisoformat(fetched)).total_seconds() / 3600
        if age_h > 72:
            warn('GitHub snapshot', f'{age_h/24:.1f} days old',
                 'Schedule sync-cron.sh, or check the last run in data/sync.log')
        else:
            ok('GitHub snapshot', f'{age_h:.1f}h old')
    except Exception as exc:
        fail('GitHub snapshot', f'unreadable: {exc}')

missing = [str(p) for p in (
    'static/resume/Chatzikallias_Panagiotis.pdf',
    'static/assets/avatar-632.jpg',
    'static/css/styles.css',
    'static/js/main.js',
) if not (ROOT / p).exists()]
if missing:
    warn('Static assets', f'{len(missing)} missing', ', '.join(missing))
else:
    ok('Static assets', 'resume, avatar, css, js present')

try:
    import app as flask_app
    client = flask_app.app.test_client()
    broken = []
    for route in ('/', '/pawstack', '/activity', '/healthz', '/resume'):
        code = client.get(route).status_code
        if code != 200:
            broken.append(f'{route} -> {code}')
    if broken:
        fail('Routes render', ', '.join(broken))
    else:
        ok('Routes render', '/, /pawstack, /activity, /healthz, /resume')
except Exception as exc:
    fail('Routes render', f'{exc.__class__.__name__}: {exc}')

if os.environ.get('FLASK_DEBUG'):
    fail('Debug mode', 'FLASK_DEBUG is set',
         'Never set this in production; it exposes an interactive debugger.')
else:
    ok('Debug mode', 'off')

if not (ROOT / '.git').exists():
    warn('Auto-update', 'not a git repository', 'autoupdate.py cannot run here.')
elif not shutil.which('git'):
    warn('Auto-update', 'git not on PATH')
else:
    def g(*a):
        return subprocess.run(['git', '-C', str(ROOT), *a],
                              capture_output=True, text=True).stdout.rstrip('\n')
    branch = g('rev-parse', '--abbrev-ref', 'HEAD')
    upstream = g('rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{upstream}')
    dirty = g('status', '--porcelain', '--untracked-files=no')
    if not upstream:
        warn('Auto-update', f"branch '{branch}' has no upstream",
             f'git push -u origin {branch}')
    elif dirty:
        n = len(dirty.splitlines())
        warn('Auto-update', f'{n} uncommitted change(s); updater will refuse',
             'Commit or stash them.')
    else:
        ok('Auto-update', f'{branch} -> {upstream}, tree clean')

    if not os.environ.get('UPDATE_RESTART_CMD', '').strip():
        warn('Restart hook', 'UPDATE_RESTART_CMD not set',
             'Updates will apply but nothing restarts. See README.')
    else:
        ok('Restart hook', os.environ['UPDATE_RESTART_CMD'])

COLOURS = {'OK': GREEN, 'WARN': YELLOW, 'FAIL': RED}
width = max(len(n) for n, *_ in results)
print()
for name, state, detail, fix in results:
    print(f'  {COLOURS[state]}{state:<4}{RESET}  {name:<{width}}  {DIM}{detail}{RESET}')
    if fix and state != 'OK':
        print(f'        {" " * width}  {DIM}-> {fix}{RESET}')

fails = sum(1 for _, s, *_ in results if s == 'FAIL')
warns = sum(1 for _, s, *_ in results if s == 'WARN')
print()
if fails:
    print(f'  {RED}{fails} blocking issue(s){RESET}, {warns} warning(s). Not ready.')
else:
    print(f'  {GREEN}Ready to deploy{RESET}' + (f', {warns} warning(s).' if warns else '.'))
print()
sys.exit(1 if fails else 0)
