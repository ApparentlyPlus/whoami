import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

USERNAME = os.environ.get('GITHUB_USER', 'ApparentlyPlus')

def _token_from_env_file():
    env_file = Path(__file__).parent / '.env'
    try:
        for line in env_file.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line.startswith('#') or '=' not in line:
                continue
            key, _, value = line.partition('=')
            if key.strip().lstrip('export').strip() == 'GITHUB_TOKEN':
                return value.strip().strip('\'"')
    except OSError:
        pass
    return ''


def _token_from_gh_cli():
    gh = shutil.which('gh')
    if not gh:
        return ''
    try:
        out = subprocess.run(
            [gh, 'auth', 'token'],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return ''
    return out.stdout.strip() if out.returncode == 0 else ''


def _resolve_token():
    for source in (
        lambda: os.environ.get('GITHUB_TOKEN', '').strip(),
        _token_from_env_file,
        _token_from_gh_cli,
    ):
        token = source()
        if token:
            return token
    return ''


TOKEN = _resolve_token()


class MissingToken(RuntimeError):
    pass


def require_token():
    if TOKEN:
        return TOKEN
    if os.environ.get('ALLOW_NO_GITHUB_TOKEN') == '1':
        print('[github_sync] WARNING: no GitHub token. Every GitHub-driven '
              'section will be empty (ALLOW_NO_GITHUB_TOKEN=1)')
        return ''
    raise MissingToken(
        'No GitHub token found, and the site needs one.\n'
        '  Provide it in any of these ways (first hit wins):\n'
        '    1. export GITHUB_TOKEN=ghp_...\n'
        '    2. GITHUB_TOKEN=ghp_... in a .env file beside github_sync.py\n'
        '    3. gh auth login          (dev machines; shared hosting has no gh)\n'
        '  A classic token with public_repo scope is enough.\n'
        '  To start without GitHub data anyway: ALLOW_NO_GITHUB_TOKEN=1'
    )

DATA_DIR = Path(__file__).parent / 'data'
CACHE_FILE = DATA_DIR / 'github.json'
CACHE_TTL = 24 * 60 * 60
RETRY_AFTER_FAILURE = 30 * 60

# Repos to keep off the site regardless of what the API returns
REPO_DENYLIST = {'Greyscale'}

# Curated ordering / framing for the repos we care about most
REPO_PRIORITY = ['GatOS', 'Gata', 'Appa', 'UniNotes', 'fdlibm_freestanding', 'Marina']

_TIMEOUT = 20
_lock = threading.Lock()
_refreshing = False
_last_attempt = 0.0

def _request(url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers=headers or {})
    req.add_header('Accept', 'application/vnd.github+json')
    req.add_header('User-Agent', f'{USERNAME}-portfolio')
    if TOKEN:
        req.add_header('Authorization', f'Bearer {TOKEN}')
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read().decode('utf-8'))


def _graphql(query, variables=None):
    if not TOKEN:
        return None
    payload = json.dumps({'query': query, 'variables': variables or {}}).encode()
    result = _request(
        'https://api.github.com/graphql',
        data=payload,
        headers={'Content-Type': 'application/json'},
    )
    if 'errors' in result:
        raise RuntimeError(f"GraphQL error: {result['errors']}")
    return result.get('data')


def _search_count(query):
    url = 'https://api.github.com/search/issues?per_page=1&q=' + urllib.parse.quote(query)
    try:
        return _request(url).get('total_count')
    except Exception:
        return None

PROFILE_QUERY = """
query($login: String!) {
  user(login: $login) {
    name login url avatarUrl bio location
    followers { totalCount }
    following { totalCount }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      totalPullRequestReviewContributions
      restrictedContributionsCount
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays { date contributionCount weekday }
        }
      }
    }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false,
                 orderBy: {field: STARGAZERS, direction: DESC}) {
      totalCount
      nodes {
        name description url stargazerCount forkCount isPrivate isArchived
        pushedAt
        defaultBranchRef { target { ... on Commit { history { totalCount } } } }
        primaryLanguage { name color }
        languages(first: 6, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
          totalSize
        }
      }
    }
    pullRequests(first: 30, orderBy: {field: CREATED_AT, direction: DESC}) {
      totalCount
      nodes {
        title url number state createdAt mergedAt additions deletions
        repository { nameWithOwner owner { login } stargazerCount }
      }
    }
    issues(first: 20, orderBy: {field: CREATED_AT, direction: DESC}) {
      totalCount
      nodes {
        title url number state createdAt
        repository { nameWithOwner stargazerCount owner { login } }
      }
    }
  }
}
"""


COMMENTS_QUERY = """
query($q: String!) {
  search(query: $q, type: ISSUE, first: 40) {
    nodes {
      __typename
      ... on Issue {
        title url number state createdAt
        repository { nameWithOwner stargazerCount owner { login } }
      }
      ... on PullRequest {
        title url number state createdAt merged
        repository { nameWithOwner stargazerCount owner { login } }
      }
    }
  }
}
"""


HIGHLIGHT_TIERS = [(10000, 'major'), (1000, 'notable'), (100, 'active'), (0, 'small')]
_KIND_WEIGHT = {'pr': 1.0, 'issue': 0.5, 'comment': 0.3}
_KIND_WORD = {'pr': 'pull request', 'issue': 'issue', 'comment': 'review thread'}


def _contributor_count(full_name):
    url = (f'https://api.github.com/repos/{full_name}/contributors'
           f'?per_page=1&anon=true')
    req = urllib.request.Request(url)
    req.add_header('Accept', 'application/vnd.github+json')
    req.add_header('User-Agent', f'{USERNAME}-portfolio')
    if TOKEN:
        req.add_header('Authorization', f'Bearer {TOKEN}')
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            link = resp.headers.get('Link', '')
    except Exception:
        return None
    match = re.search(r'[?&]page=(\d+)>;\s*rel="last"', link)
    if match:
        return int(match.group(1))
    return None


def _tier_for(stars):
    for threshold, name in HIGHLIGHT_TIERS:
        if stars >= threshold:
            return name
    return 'small'


def _highlight(external):
    if not external:
        return None

    now = datetime.now(timezone.utc)
    best, best_score = None, -1.0

    for item in external:
        reach = math.log10(max(item.get('repo_stars') or 0, 0) + 10)
        kind = _KIND_WEIGHT.get(item['kind'], 0.3)
        if item.get('merged'):
            state = 1.0
        elif item.get('state') == 'OPEN':
            state = 0.75
        else:
            state = 0.55

        recency = 1.0
        if item.get('date'):
            try:
                age = (now - datetime.fromisoformat(
                    item['date'].replace('Z', '+00:00'))).days
                recency = 0.5 ** (max(age, 0) / 730.0)
            except ValueError:
                pass

        score = reach * kind * state * (0.7 + 0.3 * recency)
        if score > best_score:
            best, best_score = item, score

    if not best:
        return None

    stars = best.get('repo_stars') or 0
    state_word = ('merged' if best.get('merged')
                  else 'open' if best.get('state') == 'OPEN' else 'closed')
    return {
        'repo': best['repo'],
        'owner': best['repo'].split('/')[0],
        'name': best['repo'].split('/')[-1],
        'repo_url': best['repo_url'],
        'url': best['url'],
        'title': best['title'],
        'number': best['number'],
        'kind': best['kind'],
        'kind_word': _KIND_WORD.get(best['kind'], 'contribution'),
        'state_word': state_word,
        'stars': stars,
        'tier': _tier_for(stars),
        'contributors': _contributor_count(best['repo']),
        'score': round(best_score, 3),
    }


def _iso_now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _build_calendar(cal):
    if not cal:
        return None
    weeks = []
    counts = []
    for week in cal.get('weeks', []):
        days = [None] * 7
        for day in week.get('contributionDays', []):
            days[day['weekday']] = {'date': day['date'], 'count': day['contributionCount']}
            counts.append(day['contributionCount'])
        weeks.append(days)

    active = sorted(c for c in counts if c > 0)
    if active:
        def q(p):
            return max(1, active[min(len(active) - 1, int(len(active) * p))])
        thresholds = [q(0.25), q(0.55), q(0.80)]
    else:
        thresholds = [1, 2, 3]

    for week in weeks:
        for day in week:
            if day is None:
                continue
            c = day['count']
            if c <= 0:
                day['level'] = 0
            elif c <= thresholds[0]:
                day['level'] = 1
            elif c <= thresholds[1]:
                day['level'] = 2
            elif c <= thresholds[2]:
                day['level'] = 3
            else:
                day['level'] = 4

    months = []
    seen = set()
    for i, week in enumerate(weeks):
        first = next((d for d in week if d), None)
        if not first:
            continue
        dt = datetime.strptime(first['date'], '%Y-%m-%d')
        key = (dt.year, dt.month)
        if key not in seen and dt.day <= 14:
            seen.add(key)
            months.append({'label': dt.strftime('%b'), 'week': i})

    return {
        'total': cal.get('totalContributions', 0),
        'weeks': weeks,
        'months': months,
        'max': max(counts) if counts else 0,
    }


LANGUAGE_HALF_LIFE_DAYS = 550


def _commit_count(repo):
    ref = repo.get('defaultBranchRef') or {}
    target = ref.get('target') or {}
    return (target.get('history') or {}).get('totalCount') or 0


def _language_stats(repos):
    now = datetime.now(timezone.utc)
    totals = {}
    colors = {}

    for repo in repos:
        langs = (repo.get('languages') or {}).get('edges', [])
        repo_bytes = sum(e['size'] for e in langs)
        if not repo_bytes:
            continue

        commits = _commit_count(repo)
        weight = float(commits or 1)

        pushed = repo.get('pushedAt')
        if pushed:
            try:
                age_days = (now - datetime.fromisoformat(
                    pushed.replace('Z', '+00:00'))).days
                weight *= 0.5 ** (max(age_days, 0) / LANGUAGE_HALF_LIFE_DAYS)
            except ValueError:
                pass

        if repo.get('isArchived'):
            weight *= 0.35

        if weight <= 0:
            continue

        for edge in langs:
            node = edge['node']
            share = edge['size'] / repo_bytes
            totals[node['name']] = totals.get(node['name'], 0.0) + share * weight
            colors[node['name']] = node.get('color') or '#888'

    grand = sum(totals.values()) or 1.0
    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:8]
    return [
        {'name': name, 'pct': round(score * 100.0 / grand, 1), 'color': colors[name]}
        for name, score in ranked
    ]


def fetch():
    data = _graphql(PROFILE_QUERY, {'login': USERNAME})
    if not data:
        raise RuntimeError(
            'No GitHub token found; cannot reach the GraphQL API. Set GITHUB_TOKEN, '
            'put it in a .env next to github_sync.py, or run `gh auth login`.'
        )

    user = data['user']
    contrib = user['contributionsCollection']

    repos = [
        r for r in user['repositories']['nodes']
        if not r['isPrivate'] and r['name'] not in REPO_DENYLIST
    ]

    def repo_rank(r):
        try:
            return (0, REPO_PRIORITY.index(r['name']))
        except ValueError:
            return (1, -r['stargazerCount'])

    repos_sorted = sorted(repos, key=repo_rank)

    def owner_of(full_name):
        return full_name.split('/')[0]

    def is_external(full_name):
        return owner_of(full_name).lower() != USERNAME.lower()

    prs = []
    for p in user['pullRequests']['nodes']:
        repo = p['repository']
        if repo['nameWithOwner'].split('/')[-1] in REPO_DENYLIST:
            continue
        prs.append({
            'kind': 'pr',
            'title': p['title'],
            'url': p['url'],
            'number': p['number'],
            'repo': repo['nameWithOwner'],
            'repo_url': 'https://github.com/' + repo['nameWithOwner'],
            'repo_stars': repo['stargazerCount'],
            'external': is_external(repo['nameWithOwner']),
            'state': p['state'],
            'merged': p['state'] == 'MERGED',
            'additions': p['additions'],
            'deletions': p['deletions'],
            'date': p['mergedAt'] or p['createdAt'],
        })

    issues = []
    for i in user['issues']['nodes']:
        repo = i['repository']
        if repo['nameWithOwner'].split('/')[-1] in REPO_DENYLIST:
            continue
        issues.append({
            'kind': 'issue',
            'title': i['title'],
            'url': i['url'],
            'number': i['number'],
            'repo': repo['nameWithOwner'],
            'repo_url': 'https://github.com/' + repo['nameWithOwner'],
            'repo_stars': repo['stargazerCount'],
            'external': is_external(repo['nameWithOwner']),
            'state': i['state'],
            'date': i['createdAt'],
        })

    comments = []
    try:
        cdata = _graphql(COMMENTS_QUERY, {'q': f'commenter:{USERNAME}'})
        seen_threads = set()
        for n in (cdata or {}).get('search', {}).get('nodes', []):
            if not n:
                continue
            repo = n['repository']
            key = (repo['nameWithOwner'], n['number'])
            if key in seen_threads or repo['nameWithOwner'].split('/')[-1] in REPO_DENYLIST:
                continue
            seen_threads.add(key)
            comments.append({
                'kind': 'comment',
                'on': 'pull request' if n['__typename'] == 'PullRequest' else 'issue',
                'title': n['title'],
                'url': n['url'],
                'number': n['number'],
                'repo': repo['nameWithOwner'],
                'repo_url': 'https://github.com/' + repo['nameWithOwner'],
                'repo_stars': repo['stargazerCount'],
                'external': is_external(repo['nameWithOwner']),
                'state': n['state'],
                'date': n['createdAt'],
            })
    except Exception as exc:
        print(f'[github_sync] comment search failed: {exc}')

    authored = {(x['repo'], x['number']) for x in prs + issues}
    timeline = prs + issues + [
        c for c in comments if (c['repo'], c['number']) not in authored
    ]
    timeline.sort(key=lambda x: x['date'] or '', reverse=True)
    timeline = timeline[:14]

    external = sorted(
        [x for x in prs + issues + comments if x['external']],
        key=lambda x: (-x['repo_stars'], x['date'] or ''),
    )

    rank = {'pr': 0, 'issue': 1, 'comment': 2}
    best = {}
    for item in sorted(external, key=lambda x: rank[x['kind']]):
        best.setdefault((item['repo'], item['number']), item)
    external = sorted(best.values(), key=lambda x: (-x['repo_stars'], x['date'] or ''))

    groups = {}
    for item in external:
        g = groups.setdefault(item['repo'], {
            'repo': item['repo'],
            'repo_url': item['repo_url'],
            'stars': item['repo_stars'],
            'contributions': [],
        })
        g['contributions'].append(item)
    for g in groups.values():
        g['contributions'].sort(key=lambda x: x['date'] or '', reverse=True)
        g['major'] = g['stars'] >= 1000
    external_groups = sorted(groups.values(), key=lambda g: -g['stars'])

    merged_count = _search_count(f'is:pr author:{USERNAME} is:merged')
    open_pr_count = _search_count(f'is:pr author:{USERNAME} is:open')
    comment_count = _search_count(f'commenter:{USERNAME}')
    issues_opened = _search_count(f'is:issue author:{USERNAME}')

    snapshot = {
        'fetched_at': _iso_now(),
        'user': {
            'name': user['name'],
            'login': user['login'],
            'url': user['url'],
            'location': user.get('location'),
            'followers': user['followers']['totalCount'],
            'following': user['following']['totalCount'],
        },
        'totals': {
            'stars': sum(r['stargazerCount'] for r in repos),
            'forks': sum(r['forkCount'] for r in repos),
            'public_repos': len(repos),
            'commits_year': contrib['totalCommitContributions'],
            'prs_year': contrib['totalPullRequestContributions'],
            'issues_year': contrib['totalIssueContributions'],
            'reviews_year': contrib['totalPullRequestReviewContributions'],
            'private_year': contrib['restrictedContributionsCount'],
            'contributions_year': contrib['contributionCalendar']['totalContributions'],
            'prs_merged': merged_count,
            'prs_open': open_pr_count,
            'issues_opened': issues_opened,
            'comments': comment_count,
            'external_repos': len({x['repo'] for x in external}),
            'external_reach': sum({x['repo']: x['repo_stars'] for x in external}.values()),
        },
        'calendar': _build_calendar(contrib['contributionCalendar']),
        'languages': _language_stats(repos),
        'repos': [
            {
                'name': r['name'],
                'description': r['description'],
                'url': r['url'],
                'stars': r['stargazerCount'],
                'forks': r['forkCount'],
                'pushed_at': r['pushedAt'],
                'archived': r['isArchived'],
                'language': (r['primaryLanguage'] or {}).get('name'),
                'language_color': (r['primaryLanguage'] or {}).get('color') or '#888',
            }
            for r in repos_sorted
        ],
        'highlight': _highlight(external),
        'timeline': timeline,
        'external': external,
        'external_groups': external_groups,
        'pull_requests': prs,
        'issues': issues,
        'comments': comments,
    }
    return snapshot


def save(snapshot):
    DATA_DIR.mkdir(exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(DATA_DIR), suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as fh:
            json.dump(snapshot, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, CACHE_FILE)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


_snapshot_cache = {'mtime': None, 'data': None}


def load():
    try:
        mtime = os.stat(CACHE_FILE).st_mtime
    except OSError:
        _snapshot_cache['mtime'] = None
        _snapshot_cache['data'] = None
        return None

    if _snapshot_cache['mtime'] != mtime:
        try:
            with open(CACHE_FILE, encoding='utf-8') as fh:
                _snapshot_cache['data'] = json.load(fh)
            _snapshot_cache['mtime'] = mtime
        except (OSError, ValueError):
            return None
    return _snapshot_cache['data']


def is_stale(snapshot):
    if not snapshot:
        return True
    try:
        fetched = datetime.fromisoformat(snapshot['fetched_at'])
    except (KeyError, ValueError):
        return True
    age = (datetime.now(timezone.utc) - fetched).total_seconds()
    return age > CACHE_TTL


def refresh_in_background():
    global _refreshing, _last_attempt
    with _lock:
        if _refreshing or (time.time() - _last_attempt) < RETRY_AFTER_FAILURE:
            return
        _refreshing = True
        _last_attempt = time.time()

    def worker():
        global _refreshing
        try:
            save(fetch())
        except Exception as exc:  # never let a refresh take the site down
            print(f'[github_sync] refresh failed: {exc}')
        finally:
            with _lock:
                _refreshing = False

    threading.Thread(target=worker, daemon=True, name='github-sync').start()


def get(auto_refresh=True):
    snapshot = load()
    if auto_refresh and is_stale(snapshot):
        refresh_in_background()
    return snapshot


if __name__ == '__main__':
    import sys
    try:
        require_token()
        snap = fetch()
        save(snap)
        t = snap['totals']
        print(f"[github_sync] ok — {t['contributions_year']} contributions, "
              f"{t['stars']} stars, {len(snap['repos'])} repos, "
              f"{t['prs_merged']} merged PRs -> {CACHE_FILE}")
    except Exception as exc:
        print(f'[github_sync] FAILED: {exc}', file=sys.stderr)
        sys.exit(1)
