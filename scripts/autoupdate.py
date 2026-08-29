#!/usr/bin/env python3

import fcntl
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG_FILE = ROOT / 'data' / 'update.log'
LOCK_FILE = ROOT / 'data' / '.update.lock'
QUARANTINE = ROOT / 'data' / '.update-quarantine'

SMOKE_ROUTES = ['/', '/pawstack', '/activity', '/healthz']
SMOKE_TIMEOUT = 60
GIT_TIMEOUT = 120

class Abort(Exception):
    pass


def _load_env_file():
    env_file = ROOT / '.env'
    try:
        for line in env_file.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line.startswith('#') or '=' not in line:
                continue
            key, _, value = line.partition('=')
            key = key.strip().removeprefix('export').strip()
            os.environ.setdefault(key, value.strip().strip('\'"'))
    except OSError:
        pass


def log(message, level='info'):
    stamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ')
    line = f'[{stamp}] {level.upper():5} {message}'
    print(line, flush=True)
    try:
        LOG_FILE.parent.mkdir(exist_ok=True)
        with open(LOG_FILE, 'a', encoding='utf-8') as fh:
            fh.write(line + '\n')
    except OSError:
        pass


def quarantined():
    try:
        return QUARANTINE.read_text(encoding='utf-8').strip()
    except OSError:
        return ''


def quarantine(sha):
    try:
        QUARANTINE.parent.mkdir(exist_ok=True)
        QUARANTINE.write_text(sha, encoding='utf-8')
    except OSError:
        pass


def clear_quarantine():
    try:
        QUARANTINE.unlink()
    except OSError:
        pass


def git(*args, check=True, timeout=GIT_TIMEOUT):
    """Run git in the project root and return stripped stdout."""
    proc = subprocess.run(
        ['git', '-C', str(ROOT), *args],
        capture_output=True, text=True, timeout=timeout,
    )
    if check and proc.returncode != 0:
        raise Abort(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.rstrip('\n')

def preflight():
    if not (ROOT / '.git').exists():
        raise Abort(f'{ROOT} is not a git repository; nothing to update from.')

    remote = os.environ.get('UPDATE_REMOTE', 'origin')
    if remote not in git('remote').splitlines():
        raise Abort(f"remote '{remote}' is not configured.")

    branch = git('rev-parse', '--abbrev-ref', 'HEAD')
    if branch == 'HEAD':
        raise Abort('HEAD is detached; check out a branch before updating.')

    wanted = os.environ.get('UPDATE_BRANCH', '').strip()
    if wanted and wanted != branch:
        raise Abort(
            f"configured to track '{wanted}' but currently on '{branch}'. "
            f"Check out {wanted} first, or unset UPDATE_BRANCH."
        )

    upstream = git('rev-parse', '--abbrev-ref', '--symbolic-full-name',
                   '@{upstream}', check=False)
    if not upstream:
        raise Abort(
            f"branch '{branch}' has no upstream, so there is nothing to pull. "
            f"Push it first:  git push -u {remote} {branch}"
        )

    dirty = git('status', '--porcelain', '--untracked-files=no')
    if dirty:
        files = [ln[3:] for ln in dirty.splitlines()]
        raise Abort(
            'the working tree has uncommitted changes, which an update would '
            'overwrite. Commit or stash them first.\n         modified: '
            + ', '.join(files[:12])
            + (f' (+{len(files) - 12} more)' if len(files) > 12 else '')
        )

    return remote, branch, upstream


def compare(remote, branch, upstream):
    git('fetch', '--quiet', remote, branch)

    local_sha = git('rev-parse', 'HEAD')
    remote_sha = git('rev-parse', upstream)

    if local_sha == remote_sha:
        return local_sha, remote_sha, 'current'

    ahead_behind = git('rev-list', '--left-right', '--count',
                       f'{local_sha}...{remote_sha}')
    behind, ahead = (int(x) for x in ahead_behind.split())

    if behind and ahead:
        raise Abort(
            f'local and {upstream} have diverged ({behind} local commit(s), '
            f'{ahead} remote). Resolve by hand; this script will not merge or '
            f'rebase.'
        )
    if behind and not ahead:
        raise Abort(
            f'local is {behind} commit(s) ahead of {upstream} and would be '
            f'discarded by an update. Push first:  git push'
        )
    return local_sha, remote_sha, 'behind'

def smoke_test():
    script = (
        'import sys;'
        'sys.path.insert(0, %r);'
        'import app;'
        'c = app.app.test_client();'
        'bad = [(p, c.get(p).status_code) for p in %r '
        '       if c.get(p).status_code != 200];'
        'sys.exit("failing routes: %%s" %% bad if bad else 0)'
    ) % (str(ROOT), SMOKE_ROUTES)

    proc = subprocess.run(
        [sys.executable, '-c', script],
        capture_output=True, text=True, timeout=SMOKE_TIMEOUT, cwd=str(ROOT),
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip().splitlines()
        return False, (detail[-1] if detail else 'unknown failure')
    return True, 'all routes 200'


def install_deps(changed_files):
    if os.environ.get('UPDATE_PIP', '1') != '1':
        return
    if 'requirements.txt' not in changed_files:
        log('requirements.txt unchanged; skipping dependency install')
        return
    log('requirements.txt changed; installing')
    proc = subprocess.run(
        [sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'],
        capture_output=True, text=True, timeout=600, cwd=str(ROOT),
    )
    if proc.returncode != 0:
        raise Abort(f'dependency install failed: {proc.stderr.strip()[-400:]}')


def restart():
    cmd = os.environ.get('UPDATE_RESTART_CMD', '').strip()
    if not cmd:
        log('no UPDATE_RESTART_CMD set — code is updated, but nothing was '
            'restarted. Set it once the site is deployed.', 'warn')
        return True
    log(f'restarting: {cmd}')
    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                          timeout=180, cwd=str(ROOT))
    if proc.returncode != 0:
        log(f'restart failed: {proc.stderr.strip()[-400:]}', 'error')
        return False
    log('restart ok')
    return True


def refresh_data():
    if os.environ.get('UPDATE_SYNC', '1') != '1':
        return
    log('refreshing GitHub snapshot')
    proc = subprocess.run([sys.executable, 'github_sync.py'],
                          capture_output=True, text=True, timeout=300,
                          cwd=str(ROOT))
    if proc.returncode != 0:
        log(f'snapshot refresh failed (site keeps the old one): '
            f'{proc.stderr.strip()[-200:]}', 'warn')
    else:
        log(proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else 'sync ok')

def run(dry_run=False, check_only=False):
    remote, branch, upstream = preflight()
    log(f'on {branch}, tracking {upstream}')

    local_sha, remote_sha, state = compare(remote, branch, upstream)

    if state == 'current':
        log(f'already up to date at {local_sha[:8]}')
        return 0

    if remote_sha == quarantined():
        log(f'{remote_sha[:8]} already failed verification and was rolled back; '
            f'skipping until a newer commit is pushed. Delete '
            f'{QUARANTINE.name} to retry.', 'warn')
        return 0

    changed = git('diff', '--name-only', local_sha, remote_sha).splitlines()
    log(f'{local_sha[:8]} -> {remote_sha[:8]} ({len(changed)} file(s) changed)')

    if check_only:
        log('check mode: an update is available and safe to apply')
        return 0
    if dry_run:
        log('dry run: would fast-forward, verify, and restart. Nothing changed.')
        for f in changed[:20]:
            log(f'  would update {f}')
        return 0

    git('merge', '--ff-only', remote_sha)
    log(f'fast-forwarded to {remote_sha[:8]}')

    try:
        install_deps(changed)
        ok, detail = smoke_test()
        if not ok:
            raise Abort(f'smoke test failed after update: {detail}')
        log(f'smoke test passed ({detail})')
    except Abort as exc:
        log(str(exc), 'error')
        quarantine(remote_sha)
        log(f'rolling back to {local_sha[:8]}', 'warn')
        git('reset', '--hard', local_sha)
        ok, detail = smoke_test()
        log(f'rollback verified ({detail})' if ok else
            f'ROLLBACK ALSO FAILING ({detail}) — needs a human', 'warn' if ok else 'error')
        restart()
        return 1

    clear_quarantine()
    if not restart():
        return 1
    refresh_data()
    log('update complete')
    return 0


def main():
    _load_env_file()
    args = sys.argv[1:]
    dry_run = '--dry-run' in args
    check_only = '--check' in args

    LOCK_FILE.parent.mkdir(exist_ok=True)
    with open(LOCK_FILE, 'w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            log('another update is already running; exiting', 'warn')
            return 0
        started = time.time()
        try:
            code = run(dry_run=dry_run, check_only=check_only)
        except Abort as exc:
            log(f'refused: {exc}', 'error')
            code = 2
        except subprocess.TimeoutExpired as exc:
            log(f'timed out: {exc}', 'error')
            code = 3
        except Exception as exc:  # never leave the cron job without a reason
            log(f'unexpected failure: {exc!r}', 'error')
            code = 4
        log(f'finished in {time.time() - started:.1f}s (exit {code})')
        return code


if __name__ == '__main__':
    sys.exit(main())
