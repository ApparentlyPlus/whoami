// portfolio interactions
(function () {
    'use strict';

    var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var SVGNS = 'http://www.w3.org/2000/svg';

    var scrollTasks = [];
    var scrollQueued = false;

    function runScrollTasks() {
        scrollQueued = false;
        var y = window.scrollY;
        for (var i = 0; i < scrollTasks.length; i++) { scrollTasks[i](y); }
    }
    function onScroll(fn) { scrollTasks.push(fn); }

    window.addEventListener('scroll', function () {
        if (!scrollQueued) {
            scrollQueued = true;
            requestAnimationFrame(runScrollTasks);
        }
    }, { passive: true });

    function el(name, attrs) {
        var node = document.createElementNS(SVGNS, name);
        for (var k in attrs) { node.setAttribute(k, attrs[k]); }
        return node;
    }

    // Theme
    var root = document.documentElement;
    var themeState = document.getElementById('nav-theme-state');

    function paintThemeLabel() {
        if (themeState) {
            themeState.textContent =
                root.getAttribute('data-theme') === 'light' ? 'Light' : 'Dark';
        }
    }
    function flipTheme() {
        var next = root.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
        root.setAttribute('data-theme', next);
        try { localStorage.setItem('theme', next); } catch (e) {}
        paintThemeLabel();
    }
    paintThemeLabel();
    ['theme-toggle', 'nav-theme'].forEach(function (id) {
        var el = document.getElementById(id);
        if (el) { el.addEventListener('click', flipTheme); }
    });

    // Nav
    var nav = document.getElementById('nav');
    var navPanel = document.getElementById('nav-menu');
    var navToggle = document.getElementById('nav-toggle');
    var navBubble = navPanel && navPanel.querySelector('.nav-bubble');
    var navItems = navPanel ? Array.prototype.slice.call(navPanel.querySelectorAll('a, .nav-theme')) : [];
    var narrow = window.matchMedia('(max-width: 860px)');
    var syncNavBubble = function () {};

    if (nav) {
        var isScrolled = null;
        var applyScrolled = function (y) {
            var next = y > 8;
            if (next !== isScrolled) {
                isScrolled = next;
                nav.classList.toggle('scrolled', next);
            }
        };
        onScroll(applyScrolled);
        applyScrolled(window.scrollY);
    }

    if (nav && navPanel && navBubble) {
        var here = window.location.pathname.replace(/\/$/, '') || '/';
        navItems.forEach(function (el) {
            var href = el.getAttribute && el.getAttribute('href');
            if (!href || href.indexOf('#') === 0) { return; }
            var path = href.split('#')[0].replace(/\/$/, '') || '/';
            if (path === here && path !== '/') {
                el.classList.add('active');
                el.setAttribute('aria-current', 'page');
            }
        });

        function moveBubble(el, instant) {
            if (!el) { navBubble.style.opacity = '0'; return; }
            var w = el.offsetWidth;
            var h = el.offsetHeight;
            if (!w || !h) { navBubble.style.opacity = '0'; return; }
            if (instant) {
                // Jump to the item with no transition, so the only thing that
                // animates on open is the fade.
                navBubble.classList.add('snap');
                navBubble.style.opacity = '0';
                navBubble.style.setProperty('--i', el.style.getPropertyValue('--i') || 0);
            }
            navBubble.style.width = w + 'px';
            navBubble.style.height = h + 'px';
            navBubble.style.transform =
                'translate3d(' + el.offsetLeft + 'px,' + el.offsetTop + 'px,0)';
            if (instant) {
                void navBubble.offsetWidth;
                navBubble.classList.remove('snap');
            }
            navBubble.style.opacity = '1';
        }

        var heldItem = null;

        syncNavBubble = function (instant) {
            if (heldItem) { return; }
            if (!narrow.matches || !nav.classList.contains('open')) {
                navBubble.style.opacity = '0';
                return;
            }
            moveBubble(navPanel.querySelector('.active'), instant);
        };

        navItems.forEach(function (el) {
            el.addEventListener('pointerenter', function (e) {
                if (narrow.matches && e.pointerType === 'mouse') { moveBubble(el); }
            });
            el.addEventListener('pointerdown', function () {
                if (!narrow.matches) { return; }
                heldItem = el;
                moveBubble(el);
            });
            el.addEventListener('focus', function () {
                if (narrow.matches) { moveBubble(el); }
            });
        });

        ['pointerup', 'pointercancel'].forEach(function (type) {
            document.addEventListener(type, function () { heldItem = null; }, true);
        });

        navPanel.addEventListener('pointerleave', function (e) {
            if (e.pointerType === 'mouse') { syncNavBubble(); }
        });
        navPanel.addEventListener('focusout', function (e) {
            if (!navPanel.contains(e.relatedTarget)) { syncNavBubble(); }
        });

        // Disclosure
        function setOpen(open) {
            nav.classList.toggle('open', open);
            if (navToggle) {
                navToggle.setAttribute('aria-expanded', String(open));
                navToggle.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
            }
            if (open) {
                nav.style.setProperty('--panel-h', navPanel.scrollHeight + 'px');
            }
            if (narrow.matches) { navPanel.inert = !open; }
            requestAnimationFrame(function () { syncNavBubble(open); });
        }

        function applyViewport() {
            if (narrow.matches) {
                navPanel.inert = !nav.classList.contains('open');
            } else {
                navPanel.inert = false;
                nav.classList.remove('open');
                nav.style.removeProperty('--panel-h');
            }
            requestAnimationFrame(syncNavBubble);
        }

        var openedAt = 0;
        if (navToggle) {
            navToggle.addEventListener('click', function () {
                var next = !nav.classList.contains('open');
                openedAt = window.scrollY;
                setOpen(next);
            });
        }
        onScroll(function (y) {
            if (nav.classList.contains('open') && Math.abs(y - openedAt) > 60) {
                setOpen(false);
            }
        });
        navItems.forEach(function (el) {
            if (el.tagName === 'A') {
                el.addEventListener('click', function () {
                    if (narrow.matches) { setOpen(false); }
                });
            }
        });
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && nav.classList.contains('open')) {
                setOpen(false);
                if (navToggle) { navToggle.focus(); }
            }
        });
        document.addEventListener('pointerdown', function (e) {
            if (nav.classList.contains('open') && !nav.contains(e.target)) {
                setOpen(false);
            }
        });

        if (narrow.addEventListener) {
            narrow.addEventListener('change', applyViewport);
        } else if (narrow.addListener) {
            narrow.addListener(applyViewport);   // Safari < 14
        }
        window.addEventListener('resize', function () {
            if (nav.classList.contains('open')) {
                nav.style.setProperty('--panel-h', navPanel.scrollHeight + 'px');
            }
            syncNavBubble();
        }, { passive: true });

        applyViewport();
    }

    // Shared floating popup
    var tip = document.getElementById('cal-tooltip');
    var tipLabel = document.getElementById('tip-label');
    var tipCount = document.getElementById('tip-count');
    var tipUnit = document.getElementById('tip-unit');
    var tipNote = document.getElementById('tip-note');

    function showTip(label, count, unit, x, y, note) {
        if (!tip) { return; }
        tipLabel.textContent = label;
        tipCount.textContent = count.toLocaleString();
        tipUnit.textContent = unit;
        if (tipNote) {
            tipNote.textContent = note || '';
            tipNote.hidden = !note;
        }
        tip.hidden = false;
        var half = tip.offsetWidth / 2;
        tip.style.left = Math.min(Math.max(x, half + 8), window.innerWidth - half - 8) + 'px';
        tip.style.top = y + 'px';
    }
    function hideTip() {
        if (tip && !tip.hidden) { tip.hidden = true; }
    }
    onScroll(hideTip);

    // Count up
    var counters = [];
    var countersRunning = false;
    var COUNT_MS = 1100;

    function tickCounters(now) {
        for (var i = counters.length - 1; i >= 0; i--) {
            var c = counters[i];
            var p = Math.min((now - c.start) / COUNT_MS, 1);
            var eased = p === 1 ? 1 : 1 - Math.pow(2, -10 * p);
            c.el.textContent = Math.round(c.target * eased).toLocaleString();
            if (p === 1) { counters.splice(i, 1); }
        }
        if (counters.length) {
            requestAnimationFrame(tickCounters);
        } else {
            countersRunning = false;
        }
    }

    function countUp(node) {
        var raw = (node.getAttribute('data-count') || '').replace(/[^0-9-]/g, '');
        var target = parseInt(raw, 10);
        if (isNaN(target) || reduceMotion || target === 0) { return; }
        counters.push({ el: node, target: target, start: performance.now() });
        if (!countersRunning) {
            countersRunning = true;
            requestAnimationFrame(tickCounters);
        }
    }

    // Contribution chart
    function niceCeil(n) {
        if (n <= 0) { return 1; }
        var mag = Math.pow(10, Math.floor(Math.log10(n)));
        return Math.ceil(n / (mag / 2)) * (mag / 2);
    }

    function fmtDay(iso, opts) {
        var d = new Date(iso + 'T00:00:00');
        return isNaN(d) ? iso : d.toLocaleDateString(undefined, opts);
    }

    function buildChart(host) {
        var series = (host.getAttribute('data-series') || '')
            .split(',')
            .map(function (v) { return parseInt(v, 10) || 0; });
        if (series.length < 2) { return; }

        var months = (host.getAttribute('data-months') || '')
            .split(',')
            .filter(Boolean)
            .map(function (pair) {
                var bits = pair.split(':');
                return { label: bits[0], week: parseInt(bits[1], 10) };
            });

        var weekDates = (host.getAttribute('data-weeks') || '').split(',').filter(Boolean);

        var peak = niceCeil(Math.max.apply(null, series));
        var peakValue = Math.max.apply(null, series);
        var peakIdx = series.indexOf(peakValue);
        var svg = el('svg', {
            role: 'img',
            'aria-label': 'Weekly contribution volume over the last year'
        });
        host.appendChild(svg);

        var cursor, cursorDot, geom = null, drawn = false;

        function render() {
            var W = host.clientWidth;
            var H = host.clientHeight;
            if (!W || !H) { return; }

            while (svg.firstChild) { svg.removeChild(svg.firstChild); }
            svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);

            var padR = 46, padT = 14, padB = 28;
            var plotW = W - padR;
            var plotH = H - padT - padB;

            var x = function (i) { return (i / (series.length - 1)) * plotW; };
            var y = function (v) { return padT + plotH - (v / peak) * plotH; };
            geom = { x: x, y: y, W: W, H: H, plotW: plotW };

            var defs = el('defs');
            var grad = el('linearGradient', { id: 'seriesFade', x1: '0', y1: '0', x2: '0', y2: '1' });
            grad.appendChild(el('stop', { offset: '0', 'stop-color': 'currentColor', 'stop-opacity': '.17' }));
            grad.appendChild(el('stop', { offset: '1', 'stop-color': 'currentColor', 'stop-opacity': '0' }));
            defs.appendChild(grad);
            svg.appendChild(defs);

            [0, 0.25, 0.5, 0.75, 1].forEach(function (f) {
                var v = peak * f;
                var gy = y(v);
                svg.appendChild(el('line', { class: 'grid-line', x1: 0, x2: plotW + 8, y1: gy, y2: gy }));
                var label = el('text', { class: 'axis-y', x: plotW + 16, y: gy + 3.5 });
                label.textContent = Math.round(v);
                svg.appendChild(label);
            });

            months.forEach(function (m) {
                if (m.week >= series.length) { return; }
                var label = el('text', { class: 'axis-x', x: x(m.week), y: H - 8 });
                label.textContent = m.label;
                svg.appendChild(label);
            });

            var points = series.map(function (v, i) { return x(i) + ',' + y(v); }).join(' ');
            svg.appendChild(el('polygon', {
                class: 'series-fill',
                fill: 'url(#seriesFade)',
                points: '0,' + y(0) + ' ' + points + ' ' + plotW + ',' + y(0)
            }));

            var path = el('polyline', { class: 'series-line', points: points });
            svg.appendChild(path);

            var last = series.length - 1;
            svg.appendChild(el('circle', { class: 'series-halo', cx: x(last), cy: y(series[last]), r: 4 }));

            cursor = el('line', { class: 'marker-line', y1: padT, y2: padT + plotH, opacity: '0' });
            cursorDot = el('circle', { class: 'series-cap', r: 3.5, opacity: '0' });
            svg.appendChild(cursor);
            svg.appendChild(cursorDot);

            if (!drawn && !reduceMotion && path.getTotalLength) {
                drawn = true;
                var len = path.getTotalLength();
                path.style.strokeDasharray = len;
                path.style.strokeDashoffset = len;
                path.style.transition = 'stroke-dashoffset 1.7s cubic-bezier(.2,.7,.3,1)';
                requestAnimationFrame(function () { path.style.strokeDashoffset = '0'; });
            }
        }

        render();

        if ('ResizeObserver' in window) {
            new ResizeObserver(render).observe(host);
        } else {
            window.addEventListener('resize', render);
        }

        var card = host.closest('.instrument');
        var headNum = card && card.querySelector('.instrument-readout [data-count]');
        var headUnit = card && card.querySelector('.instrument-readout .unit');
        var headNumBase = headNum ? headNum.getAttribute('data-count') : null;
        var headUnitBase = headUnit ? headUnit.textContent : '';

        function setHead(i) {
            if (!headNum) { return; }
            if (i === null) {
                headNum.textContent = parseInt(headNumBase, 10).toLocaleString();
                if (headUnit) { headUnit.textContent = headUnitBase; }
                return;
            }
            headNum.textContent = series[i].toLocaleString();
            if (headUnit) {
                headUnit.textContent = weekDates[i] ? 'week of ' + fmtDay(weekDates[i], { month: 'short', day: 'numeric' }) : 'that week';
            }
        }

        function weekLabel(i) {
            return weekDates[i] ? 'Week of ' + fmtDay(weekDates[i], { month: 'short', day: 'numeric' }) : 'Week ' + (i + 1);
        }

        var hostRect = null;
        function rect() {
            if (!hostRect) { hostRect = host.getBoundingClientRect(); }
            return hostRect;
        }
        function dropRect() { hostRect = null; }
        onScroll(dropRect);
        window.addEventListener('resize', dropRect, { passive: true });

        function indexAt(clientX) {
            var box = rect();
            if (!box.width) { return 0; }
            var vx = (clientX - box.left) * (geom.W / box.width);
            var i = Math.round((vx / geom.plotW) * (series.length - 1));
            return Math.max(0, Math.min(series.length - 1, i));
        }

        function moveCursor(clientX) {
            if (!geom || !cursor) { return; }
            var i = indexAt(clientX);
            var box = rect();
            var scale = box.width / geom.W;
            var cx = geom.x(i), cy = geom.y(series[i]);

            var isPeak = i === peakIdx && peakValue > 0;

            cursor.setAttribute('x1', cx);
            cursor.setAttribute('x2', cx);
            cursor.setAttribute('opacity', '.4');
            cursorDot.setAttribute('cx', cx);
            cursorDot.setAttribute('cy', cy);
            cursorDot.setAttribute('opacity', '1');
            cursorDot.setAttribute('class', isPeak ? 'series-cap peak' : 'series-cap');
            cursor.setAttribute('class', isPeak ? 'marker-line warn' : 'marker-line');

            setHead(i);
            showTip(weekLabel(i), series[i],
                    series[i] === 1 ? 'contribution' : 'contributions',
                    box.left + cx * scale, box.top + cy * scale,
                    isPeak ? 'busiest week of the year' : '');
        }

        function clearCursor() {
            if (cursor) { cursor.setAttribute('opacity', '0'); }
            if (cursorDot) { cursorDot.setAttribute('opacity', '0'); }
            setHead(null);
            hideTip();
        }

        var pendingX = null;
        var moveQueued = false;
        function flushMove() {
            moveQueued = false;
            if (pendingX !== null) { moveCursor(pendingX); }
        }
        function queueMove(e) {
            pendingX = e.clientX;
            if (!moveQueued) {
                moveQueued = true;
                requestAnimationFrame(flushMove);
            }
        }
        host.addEventListener('pointermove', queueMove);
        host.addEventListener('pointerdown', function (e) {
            if (e.pointerType !== 'mouse' && host.setPointerCapture) {
                try { host.setPointerCapture(e.pointerId); } catch (err) {}
            }
            queueMove(e);
        });
        function leaveChart() { pendingX = null; clearCursor(); }
        host.addEventListener('pointerleave', function (e) {
            if (e.pointerType === 'mouse') { leaveChart(); }
        });
        host.addEventListener('pointercancel', leaveChart);
        // A tap leaves the readout up until you touch elsewhere.
        document.addEventListener('pointerdown', function (e) {
            if (e.pointerType !== 'mouse' && !host.contains(e.target)) { clearCursor(); }
        });
    }

    document.querySelectorAll('.instrument-chart[data-series]').forEach(buildChart);

    // Reveal on view 
    var items = document.querySelectorAll('.reveal');
    if ('IntersectionObserver' in window && items.length) {
        var io = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (!entry.isIntersecting) { return; }
                entry.target.classList.add('in');
                entry.target.querySelectorAll('.readout [data-count]').forEach(countUp);
                io.unobserve(entry.target);
            });
        }, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });
        items.forEach(function (node) { io.observe(node); });
    } else {
        items.forEach(function (node) { node.classList.add('in'); });
    }

    // Calendar cells
    var grid = document.querySelector('.cal-grid');
    if (grid && tip) {
        function showCell(cell) {
            var n = parseInt(cell.getAttribute('data-count'), 10) || 0;
            var box = cell.getBoundingClientRect();
            showTip(fmtDay(cell.getAttribute('data-date'),
                           { weekday: 'short', month: 'short', day: 'numeric' }), n,
                    n === 1 ? 'contribution' : 'contributions',
                    box.left + box.width / 2, box.top);
        }
        grid.addEventListener('pointerover', function (e) {
            if (e.pointerType !== 'mouse') { return; }
            var cell = e.target.closest('.cell[data-date]');
            if (cell) { showCell(cell); }
        });
        grid.addEventListener('pointerout', function (e) {
            if (e.pointerType !== 'mouse') { return; }
            if (e.target.closest('.cell[data-date]')) { hideTip(); }
        });
        // Touch: tap a day to read it, and it stays until you touch elsewhere.
        grid.addEventListener('pointerdown', function (e) {
            if (e.pointerType === 'mouse') { return; }
            var cell = e.target.closest('.cell[data-date]');
            if (cell) { showCell(cell); }
        });
        document.addEventListener('pointerdown', function (e) {
            if (e.pointerType !== 'mouse' && !grid.contains(e.target)) { hideTip(); }
        });
    }

    // Scroll-spy
    var links = Array.prototype.slice.call(document.querySelectorAll('.nav-links a[href*="#"]'));
    var targets = links
        .map(function (a) {
            var id = a.getAttribute('href').split('#')[1];
            var node = id && document.getElementById(id);
            return node ? { link: a, el: node } : null;
        })
        .filter(Boolean);

    if (targets.length && 'IntersectionObserver' in window) {
        var spy = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                var match = targets.find(function (t) { return t.el === entry.target; });
                if (match && entry.isIntersecting) {
                    links.forEach(function (l) { l.classList.remove('active'); });
                    match.link.classList.add('active');
                    syncNavBubble();
                }
            });
        }, { rootMargin: '-45% 0px -50% 0px' });
        targets.forEach(function (t) { spy.observe(t.el); });
    }

    // Footer year
    var year = document.getElementById('year');
    if (year) { year.textContent = new Date().getFullYear(); }
})();
