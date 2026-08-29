import gzip
import io
import os
import tomllib
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Flask, g, jsonify, render_template, request, send_from_directory

import github_sync

github_sync.require_token()

app = Flask(__name__)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = timedelta(days=365)

CONTENT_FILE = Path(__file__).parent / 'content.toml'
STATIC_DIR = Path(__file__).parent / 'static'

_GZIP_CACHE = {}
_GZIP_TYPES = (
    'text/html', 'text/css', 'application/javascript', 'text/javascript',
    'application/json', 'image/svg+xml', 'text/plain',
)
_GZIP_MIN_BYTES = 600

_asset_versions = {}


def _asset_version(filename):
    try:
        mtime = (STATIC_DIR / filename).stat().st_mtime
    except OSError:
        return None
    cached = _asset_versions.get(filename)
    if not cached or cached[0] != mtime:
        _asset_versions[filename] = (mtime, format(int(mtime), 'x')[-8:])
    return _asset_versions[filename][1]


@app.url_defaults
def add_static_version(endpoint, values):
    if endpoint == 'static' and 'filename' in values and 'v' not in values:
        version = _asset_version(values['filename'])
        if version:
            values['v'] = version


@app.after_request
def compress(response):
    accepts = request.headers.get('Accept-Encoding', '')
    if ('gzip' not in accepts
            or not (200 <= response.status_code < 300)
            or response.headers.get('Content-Encoding')
            or response.mimetype not in _GZIP_TYPES):
        response.headers.setdefault('Vary', 'Accept-Encoding')
        return response

    etag = response.headers.get('ETag')
    if etag and etag in _GZIP_CACHE:
        blob = _GZIP_CACHE[etag]
    else:
        response.direct_passthrough = False
        raw = response.get_data()
        if len(raw) < _GZIP_MIN_BYTES:
            response.headers.setdefault('Vary', 'Accept-Encoding')
            return response
        buf = io.BytesIO()
        level = 9 if etag else 6
        with gzip.GzipFile(fileobj=buf, mode='wb', compresslevel=level, mtime=0) as fh:
            fh.write(raw)
        blob = buf.getvalue()
        if etag:
            _GZIP_CACHE[etag] = blob

    response.set_data(blob)
    response.headers['Content-Encoding'] = 'gzip'
    response.headers['Content-Length'] = str(len(blob))
    response.headers['Vary'] = 'Accept-Encoding'
    return response


@app.after_request
def cache_policy(response):
    """Immutable for versioned assets, always-revalidate for pages."""
    if request.endpoint == 'static' and request.args.get('v'):
        response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    elif response.mimetype == 'text/html':
        response.headers['Cache-Control'] = 'no-cache'
    return response

_content_cache = {'mtime': None, 'data': {}}


def load_content():
    try:
        mtime = CONTENT_FILE.stat().st_mtime
    except OSError:
        return _content_cache['data']

    if _content_cache['mtime'] != mtime:
        try:
            with open(CONTENT_FILE, 'rb') as fh:
                _content_cache['data'] = tomllib.load(fh)
            _content_cache['mtime'] = mtime
        except (OSError, tomllib.TOMLDecodeError) as exc:
            print(f'[content] {CONTENT_FILE.name} failed to parse: {exc}')
    return _content_cache['data']


@app.context_processor
def inject_content():
    content = load_content()
    gh, _ = _github()
    highlight = resolve_highlight(content, gh)
    return {
        'c': content,
        'site': content.get('site', {}),
        'nav': content.get('nav', []),
        'nav_resume': content.get('nav_resume', {}),
        'footer': content.get('footer', {}),
        'highlight': highlight,
        'available': {'highlight': bool(highlight), 'github': bool(gh)},
    }


@app.template_filter('humandate')
def humandate(value):
    if not value:
        return ''
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return value
    return dt.strftime('%b %Y')


@app.template_filter('ago')
def ago(value):
    if not value:
        return 'never'
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return value
    secs = (datetime.now(timezone.utc) - dt).total_seconds()
    if secs < 3600:
        return f'{int(secs // 60)}m ago'
    if secs < 86400:
        return f'{int(secs // 3600)}h ago'
    return f'{int(secs // 86400)}d ago'


@app.template_filter('commas')
def commas(value):
    try:
        return f'{int(value):,}'
    except (TypeError, ValueError):
        return value


def resolve_highlight(content, gh):
    highlight = (gh or {}).get('highlight')
    if not highlight:
        return None

    upstream = content.get('home', {}).get('upstream', {})
    facts = dict(highlight)
    facts['stars'] = f"{highlight.get('stars') or 0:,}"
    contributors = highlight.get('contributors')
    facts['contributors'] = f'{contributors:,}' if contributors else ''
    facts['state'] = highlight.get('state_word', '')
    facts['kind'] = highlight.get('kind_word', 'contribution')
    lead = (facts['state'] or facts['kind'] or '').lstrip()
    facts['article'] = 'An' if lead[:1].lower() in 'aeiou' else 'A'

    override = (upstream.get('overrides') or {}).get(highlight['repo'], {})
    body = (override.get('body') or '').strip()

    if not body:
        tiers = upstream.get('tiers') or {}
        template = tiers.get(highlight.get('tier')) or tiers.get('small') or ''
        try:
            body = template.format(**facts)
        except (KeyError, IndexError, ValueError):
            body = template

    return dict(highlight, body=body, overridden=bool(override.get('body')))


def _github():
    """Cached GitHub snapshot plus a name->repo lookup for the templates."""
    if 'github' not in g:
        gh = github_sync.get()
        g.github = (gh, {r['name']: r for r in (gh or {}).get('repos', [])})
    return g.github


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.route('/')
def index():
    gh, repos = _github()
    return render_template('index.html', gh=gh, repos=repos, page='home')


@app.route('/activity')
def activity():
    gh, repos = _github()
    return render_template('activity.html', gh=gh, repos=repos, page='activity')


@app.route('/pawstack')
def pawstack():
    gh, repos = _github()
    return render_template('pawstack.html', gh=gh, repos=repos, page='pawstack')


@app.route('/api/github.json')
def github_json():
    snapshot = github_sync.get()
    if not snapshot:
        return jsonify({'error': 'no snapshot available'}), 503
    return jsonify(snapshot)


@app.route('/resume')
def resume():
    return send_from_directory('static/resume', 'Chatzikallias_Panagiotis.pdf')


@app.route('/healthz')
def healthz():
    """Cheap liveness probe — used by the auto-updater's smoke test."""
    return {'ok': True, 'content': bool(load_content())}


if __name__ == '__main__':
    app.run(debug=bool(os.environ.get('FLASK_DEBUG')))
