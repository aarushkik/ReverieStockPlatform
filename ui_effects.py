"""
Motion and micro-interaction primitives for the Reverie terminal.

These are ports of effects from React Bits (https://reactbits.dev,
https://github.com/DavidHDev/react-bits, MIT + Commons Clause) rewritten as
framework-free CSS and DOM script. The upstream components are React + Framer
Motion; this app renders server-side through Streamlit, so a React runtime would
mean shipping a component bundle for every animated number on the page. Porting
the underlying techniques instead keeps everything working on markup that
Streamlit itself emits.

Effects ported here and their upstream counterparts:

    SpotlightCard   -> .rv-spotlight        cursor-tracked radial highlight
    CountUp         -> [data-rv-countup]    spring-integrated number rolls
    ShinyText       -> .rv-shiny            sweeping specular highlight
    GradientText    -> .rv-gradient-text    animated gradient fill
    DecryptedText   -> [data-rv-decrypt]    scramble-to-resolve reveal
    ClickSpark      -> document-level       canvas spark burst on click
    StarBorder      -> .rv-star-border      travelling border sheen
    AnimatedContent -> [data-rv-reveal]     staggered entrance on intersect
    Magnet          -> [data-rv-magnet]     cursor attraction
    Aurora/Particles-> rv_background()      login backdrop

Two constraints shape the implementation:

1.  Streamlit replaces DOM subtrees on every rerun, so nothing can be bound
    once at load. Every behaviour is delegated from the document root or
    re-bound by a MutationObserver, and binding is idempotent.

2.  Motion must be suppressible. Each effect checks the resolved --rv-motion
    token and the OS prefers-reduced-motion setting before doing any work, and
    degrades to a static end state rather than disappearing.
"""

from __future__ import annotations

import json
from typing import Optional

from theme import Theme, rgba

# ==============================================================================
# CSS — effects that need no script
# ==============================================================================


def effects_css(theme: Optional[Theme] = None) -> str:
    """Stylesheet for the purely declarative effects.

    Entirely token-driven: every colour resolves through a CSS variable that
    theme.py emits, so this string is identical for every theme. That is what
    allows it to be registered once as static component CSS rather than being
    re-injected per run. The *theme* argument is accepted and ignored so
    callers need not care.
    """
    return f"""<style>
    /* ---------------------------------------------------------------
       SpotlightCard - React Bits Components/SpotlightCard
       Upstream sets --mouse-x/--mouse-y from React's onMouseMove; here the
       document-level pointer handler in the runtime does it instead.
       --------------------------------------------------------------- */
    .rv-spotlight {{
        position: relative;
        overflow: hidden;
        --rv-mx: 50%;
        --rv-my: 50%;
        --rv-spot: var(--rv-spotlight, rgba(0, 214, 143, 0.16));
    }}
    .rv-spotlight::before {{
        content: '';
        position: absolute;
        inset: 0;
        background: radial-gradient(
            circle at var(--rv-mx) var(--rv-my),
            var(--rv-spot),
            transparent 70%);
        opacity: 0;
        transition: opacity var(--rv-dur-slow) var(--rv-ease);
        pointer-events: none;
        z-index: 0;
    }}
    .rv-spotlight:hover::before,
    .rv-spotlight:focus-within::before {{ opacity: 1; }}
    .rv-spotlight > * {{ position: relative; z-index: 1; }}

    /* ---------------------------------------------------------------
       ShinyText - React Bits TextAnimations/ShinyText
       --------------------------------------------------------------- */
    .rv-shiny {{
        display: inline-block;
        color: var(--rv-text-muted);
        background: linear-gradient(
            120deg,
            transparent 35%,
            var(--rv-text) 50%,
            transparent 65%);
        background-size: 220% 100%;
        -webkit-background-clip: text;
        background-clip: text;
        -webkit-text-fill-color: transparent;
        animation: rv-shine calc(4s / max(var(--rv-motion), 0.01)) linear infinite;
    }}
    @keyframes rv-shine {{
        0%   {{ background-position: 220% 0; }}
        100% {{ background-position: -220% 0; }}
    }}

    /* ---------------------------------------------------------------
       GradientText - React Bits TextAnimations/GradientText
       --------------------------------------------------------------- */
    .rv-gradient-text {{
        background: linear-gradient(
            92deg,
            var(--rv-accent-fill),
            var(--rv-info),
            var(--rv-accent-fill));
        background-size: 250% 100%;
        -webkit-background-clip: text;
        background-clip: text;
        -webkit-text-fill-color: transparent;
        animation: rv-gradient-pan calc(7s / max(var(--rv-motion), 0.01)) linear infinite;
    }}
    @keyframes rv-gradient-pan {{
        0%   {{ background-position: 0% 50%; }}
        100% {{ background-position: 250% 50%; }}
    }}

    /* ---------------------------------------------------------------
       StarBorder - React Bits Animations/StarBorder
       Upstream rotates a conic gradient behind the element. That needs an
       @property-registered <angle> to be animatable, and Streamlit sanitises
       any <style> block containing an @property at-rule - it drops the whole
       stylesheet, not just the rule. Rotating the masked pseudo-element with
       transform instead would rotate its mask along with it and break the
       border shape, so this uses a linear sheen swept by background-position,
       which animates natively and needs no registered property.
       --------------------------------------------------------------- */
    .rv-star-border {{
        position: relative;
        border-radius: var(--rv-radius);
        isolation: isolate;
    }}
    .rv-star-border::before {{
        content: '';
        position: absolute;
        inset: -1px;
        border-radius: inherit;
        padding: 1px;
        background: linear-gradient(
            100deg,
            transparent 20%,
            var(--rv-accent-fill) 45%,
            var(--rv-info) 55%,
            transparent 80%);
        background-size: 300% 100%;
        -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
        -webkit-mask-composite: xor;
        mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
        mask-composite: exclude;
        animation: rv-border-sweep calc(4s / max(var(--rv-motion), 0.01)) linear infinite;
        pointer-events: none;
    }}
    @keyframes rv-border-sweep {{
        0%   {{ background-position: 300% 0; }}
        100% {{ background-position: -300% 0; }}
    }}

    /* ---------------------------------------------------------------
       AnimatedContent / FadeContent - React Bits Animations
       Entrance is opt-in per element; the runtime adds .rv-in on intersect.
       The un-animated state is the *visible* one so that a failure to bind
       never leaves content permanently invisible.
       --------------------------------------------------------------- */
    [data-rv-reveal] {{
        opacity: 1;
        transform: none;
    }}
    [data-rv-reveal].rv-armed {{
        opacity: 0;
        transform: translateY(calc(10px * var(--rv-motion)));
    }}
    [data-rv-reveal].rv-armed.rv-in {{
        opacity: 1;
        transform: none;
        transition: opacity var(--rv-dur-slow) var(--rv-ease-out),
                    transform var(--rv-dur-slow) var(--rv-ease-out);
        transition-delay: var(--rv-delay, 0ms);
    }}

    /* Numbers that just changed get a brief tint, so a moving figure is
       noticeable without the whole row flashing. */
    .rv-tick-up   {{ animation: rv-tick-up   calc(0.9s / max(var(--rv-motion), 0.01)) var(--rv-ease) 1; }}
    .rv-tick-down {{ animation: rv-tick-down calc(0.9s / max(var(--rv-motion), 0.01)) var(--rv-ease) 1; }}
    @keyframes rv-tick-up {{
        0%   {{ background-color: var(--rv-pos-soft); }}
        100% {{ background-color: transparent; }}
    }}
    @keyframes rv-tick-down {{
        0%   {{ background-color: var(--rv-neg-soft); }}
        100% {{ background-color: transparent; }}
    }}

    /* Live pulse dot for streaming/connected indicators. */
    .rv-pulse {{
        display: inline-block;
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: var(--rv-pos-fill);
        position: relative;
    }}
    .rv-pulse::after {{
        content: '';
        position: absolute;
        inset: 0;
        border-radius: 50%;
        background: inherit;
        animation: rv-pulse-ring calc(2s / max(var(--rv-motion), 0.01)) var(--rv-ease-out) infinite;
    }}
    @keyframes rv-pulse-ring {{
        0%   {{ transform: scale(1);   opacity: 0.7; }}
        100% {{ transform: scale(3.2); opacity: 0; }}
    }}

    /* Cursor-spark canvas sits above everything but never intercepts input. */
    #rv-spark-canvas {{
        position: fixed;
        inset: 0;
        width: 100vw;
        height: 100vh;
        pointer-events: none;
        z-index: 2147483000;
    }}

    /* ---------------------------------------------------------------
       Aurora + Particles backdrop - React Bits Backgrounds
       Blurred drifting blobs in CSS; the particle field is canvas.
       --------------------------------------------------------------- */
    .rv-aurora {{
        position: fixed;
        inset: 0;
        overflow: hidden;
        pointer-events: none;
        z-index: 0;
    }}
    .rv-aurora-blob {{
        position: absolute;
        border-radius: 50%;
        filter: blur(70px);
        opacity: 0.34;
        will-change: transform;
    }}
    .rv-aurora-blob:nth-child(1) {{
        width: 46vw; height: 46vw; left: -8vw; top: -12vw;
        background: var(--rv-accent-fill);
        animation: rv-drift-a calc(26s / max(var(--rv-motion), 0.01)) ease-in-out infinite alternate;
    }}
    .rv-aurora-blob:nth-child(2) {{
        width: 38vw; height: 38vw; right: -6vw; top: 8vh;
        background: var(--rv-info);
        animation: rv-drift-b calc(32s / max(var(--rv-motion), 0.01)) ease-in-out infinite alternate;
    }}
    .rv-aurora-blob:nth-child(3) {{
        width: 42vw; height: 42vw; left: 22vw; bottom: -18vw;
        background: var(--rv-accent-fill);
        opacity: 0.2;
        animation: rv-drift-c calc(38s / max(var(--rv-motion), 0.01)) ease-in-out infinite alternate;
    }}
    @keyframes rv-drift-a {{ to {{ transform: translate3d(14vw, 10vh, 0) scale(1.18); }} }}
    @keyframes rv-drift-b {{ to {{ transform: translate3d(-16vw, 14vh, 0) scale(0.85); }} }}
    @keyframes rv-drift-c {{ to {{ transform: translate3d(10vw, -12vh, 0) scale(1.12); }} }}

    #rv-particles {{
        position: fixed;
        inset: 0;
        width: 100vw;
        height: 100vh;
        pointer-events: none;
        z-index: 1;
        opacity: 0.55;
    }}

    /* A faint grain layer stops the large gradient fields from banding on
       8-bit displays. */
    .rv-grain::after {{
        content: '';
        position: fixed;
        inset: 0;
        pointer-events: none;
        z-index: 2;
        opacity: 0.035;
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='140' height='140'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
    }}

    @media (prefers-reduced-motion: reduce) {{
        .rv-aurora-blob, .rv-shiny, .rv-gradient-text,
        .rv-star-border::before, .rv-pulse::after {{
            animation: none !important;
        }}
        [data-rv-reveal].rv-armed {{ opacity: 1 !important; transform: none !important; }}
    }}
</style>"""


# ==============================================================================
# RUNTIME — the delegated script that drives the interactive effects
# ==============================================================================

_RUNTIME_JS = r"""
(function () {
  var W = window;
  // Streamlit reruns re-execute this block; everything below must be safe to
  // call repeatedly, so the runtime installs exactly once and later calls only
  // refresh the parts that depend on new DOM.
  if (W.__rvRuntime) { W.__rvRuntime.rescan(); return; }

  var doc = document;
  var reduce = W.matchMedia && W.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function motion() {
    if (reduce) return 0;
    var v = getComputedStyle(doc.documentElement).getPropertyValue('--rv-motion');
    var n = parseFloat(v);
    return isNaN(n) ? 1 : n;
  }

  // ---------------------------------------------------------------- Spotlight
  // React Bits binds onMouseMove per card. Streamlit swaps card nodes on every
  // rerun, so we delegate from the document and walk up to the nearest card.
  doc.addEventListener('pointermove', function (e) {
    if (motion() === 0) return;
    var el = e.target && e.target.closest && e.target.closest('.rv-spotlight');
    if (!el) return;
    var r = el.getBoundingClientRect();
    el.style.setProperty('--rv-mx', (e.clientX - r.left) + 'px');
    el.style.setProperty('--rv-my', (e.clientY - r.top) + 'px');
  }, { passive: true });

  // ------------------------------------------------------------------- Magnet
  var magnetState = new WeakMap();
  doc.addEventListener('pointermove', function (e) {
    var m = motion();
    if (m === 0) return;
    var nodes = doc.querySelectorAll('[data-rv-magnet]');
    for (var i = 0; i < nodes.length; i++) {
      var el = nodes[i];
      var r = el.getBoundingClientRect();
      var cx = r.left + r.width / 2;
      var cy = r.top + r.height / 2;
      var dx = e.clientX - cx;
      var dy = e.clientY - cy;
      var radius = parseFloat(el.getAttribute('data-rv-magnet')) || 90;
      var dist = Math.hypot(dx, dy);
      if (dist < radius) {
        var pull = (1 - dist / radius) * 0.32 * m;
        el.style.transform = 'translate(' + dx * pull + 'px,' + dy * pull + 'px)';
        magnetState.set(el, true);
      } else if (magnetState.get(el)) {
        el.style.transform = '';
        magnetState.set(el, false);
      }
    }
  }, { passive: true });

  // --------------------------------------------------------------- ClickSpark
  // Port of React Bits Animations/ClickSpark. Upstream mounts a canvas sized to
  // its parent; a single document-level canvas covers the whole terminal.
  var sparks = [];
  var canvas = null;
  var ctx = null;
  var rafId = null;

  function ensureCanvas() {
    if (canvas && canvas.isConnected) return;
    canvas = doc.getElementById('rv-spark-canvas');
    if (!canvas) {
      canvas = doc.createElement('canvas');
      canvas.id = 'rv-spark-canvas';
      doc.body.appendChild(canvas);
    }
    ctx = canvas.getContext('2d');
    sizeCanvas();
  }

  function sizeCanvas() {
    if (!canvas) return;
    var dpr = W.devicePixelRatio || 1;
    canvas.width = W.innerWidth * dpr;
    canvas.height = W.innerHeight * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  W.addEventListener('resize', sizeCanvas, { passive: true });

  // Upstream default easing is ease-out: t * (2 - t).
  function easeOut(t) { return t * (2 - t); }

  function drawSparks(ts) {
    if (!ctx) { rafId = null; return; }
    ctx.clearRect(0, 0, W.innerWidth, W.innerHeight);
    var alive = [];
    for (var i = 0; i < sparks.length; i++) {
      var s = sparks[i];
      var elapsed = ts - s.t0;
      if (elapsed >= s.duration) continue;
      var eased = easeOut(elapsed / s.duration);
      var dist = eased * s.radius;
      var len = s.size * (1 - eased);
      var x1 = s.x + dist * Math.cos(s.angle);
      var y1 = s.y + dist * Math.sin(s.angle);
      var x2 = s.x + (dist + len) * Math.cos(s.angle);
      var y2 = s.y + (dist + len) * Math.sin(s.angle);
      ctx.strokeStyle = s.color;
      ctx.globalAlpha = 1 - eased;
      ctx.lineWidth = 2;
      ctx.lineCap = 'round';
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.stroke();
      alive.push(s);
    }
    ctx.globalAlpha = 1;
    sparks = alive;
    rafId = sparks.length ? requestAnimationFrame(drawSparks) : null;
  }

  doc.addEventListener('pointerdown', function (e) {
    var m = motion();
    if (m === 0) return;
    // Only fire on genuine controls, otherwise every stray click on text
    // throws sparks and the effect turns into noise.
    var hit = e.target && e.target.closest &&
      e.target.closest('button, [role="button"], .rv-sparkable, a');
    if (!hit) return;
    ensureCanvas();
    var accent = getComputedStyle(doc.documentElement)
      .getPropertyValue('--rv-accent-fill').trim() || '#00D68F';
    var count = 8;
    var now = performance.now();
    for (var i = 0; i < count; i++) {
      sparks.push({
        x: e.clientX, y: e.clientY,
        angle: (2 * Math.PI * i) / count,
        t0: now,
        duration: 420 / Math.max(m, 0.25),
        radius: 16,
        size: 9,
        color: accent
      });
    }
    if (!rafId) rafId = requestAnimationFrame(drawSparks);
  }, { passive: true });

  // ------------------------------------------------------------------ CountUp
  // Port of React Bits TextAnimations/CountUp, which drives a Framer Motion
  // spring. Same spring constants, integrated here with a semi-implicit Euler
  // step so the easing curve matches upstream.
  function runCountUp(el) {
    if (el.__rvCounted) return;
    el.__rvCounted = true;

    var to = parseFloat(el.getAttribute('data-to'));
    if (isNaN(to)) return;
    var from = parseFloat(el.getAttribute('data-from'));
    if (isNaN(from)) from = 0;
    var duration = parseFloat(el.getAttribute('data-duration')) || 1.4;
    var decimals = parseInt(el.getAttribute('data-decimals') || '0', 10);
    var prefix = el.getAttribute('data-prefix') || '';
    var suffix = el.getAttribute('data-suffix') || '';
    var group = el.getAttribute('data-separator') || '';

    function fmt(v) {
      var s = v.toLocaleString('en-US', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
        useGrouping: !!group
      });
      if (group && group !== ',') s = s.replace(/,/g, group);
      return prefix + s + suffix;
    }

    if (motion() === 0) { el.textContent = fmt(to); return; }

    // Upstream: damping = 20 + 40 * (1 / duration), stiffness = 100 * (1 / duration).
    var stiffness = 100 * (1 / duration);
    var damping = 20 + 40 * (1 / duration);
    var x = from, v = 0, last = null;

    function step(ts) {
      if (last === null) last = ts;
      var dt = Math.min((ts - last) / 1000, 0.064);
      last = ts;
      var a = (-stiffness * (x - to) - damping * v);
      v += a * dt;
      x += v * dt;
      if (Math.abs(x - to) < Math.pow(10, -decimals) / 2 && Math.abs(v) < 0.5) {
        el.textContent = fmt(to);
        return;
      }
      el.textContent = fmt(x);
      requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  // ------------------------------------------------------------ DecryptedText
  // Port of React Bits TextAnimations/DecryptedText.
  var GLYPHS = '!<>-_\\/[]{}=+*^?#01';
  function runDecrypt(el) {
    if (el.__rvDecrypted) return;
    el.__rvDecrypted = true;
    var target = el.getAttribute('data-rv-decrypt') || el.textContent || '';
    if (motion() === 0) { el.textContent = target; return; }
    var speed = parseFloat(el.getAttribute('data-speed')) || 34;
    var revealed = 0;
    var timer = setInterval(function () {
      var out = '';
      for (var i = 0; i < target.length; i++) {
        if (i < revealed || target[i] === ' ') out += target[i];
        else out += GLYPHS[Math.floor(Math.random() * GLYPHS.length)];
      }
      el.textContent = out;
      revealed += 1 / 2;
      if (revealed >= target.length) {
        clearInterval(timer);
        el.textContent = target;
      }
    }, speed);
  }

  // ------------------------------------------------- AnimatedContent / reveal
  var io = ('IntersectionObserver' in W) ? new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (!entry.isIntersecting) return;
      var el = entry.target;
      io.unobserve(el);
      if (el.hasAttribute('data-rv-countup')) runCountUp(el);
      else if (el.hasAttribute('data-rv-decrypt')) runDecrypt(el);
      else el.classList.add('rv-in');
    });
  }, { threshold: 0.15, rootMargin: '0px 0px -5% 0px' }) : null;

  function rescan() {
    var m = motion();
    var reveals = doc.querySelectorAll('[data-rv-reveal]:not([data-rv-bound])');
    for (var i = 0; i < reveals.length; i++) {
      var el = reveals[i];
      el.setAttribute('data-rv-bound', '1');
      if (m === 0) continue;
      // Arm only once observed, so content is never left hidden if the
      // observer is unavailable or the element never intersects.
      el.classList.add('rv-armed');
      var delay = parseFloat(el.getAttribute('data-rv-reveal')) || 0;
      el.style.setProperty('--rv-delay', (delay * 55) + 'ms');
      if (io) io.observe(el); else el.classList.add('rv-in');
    }

    var counters = doc.querySelectorAll('[data-rv-countup]:not([data-rv-bound])');
    for (var j = 0; j < counters.length; j++) {
      counters[j].setAttribute('data-rv-bound', '1');
      if (io) io.observe(counters[j]); else runCountUp(counters[j]);
    }

    var decrypts = doc.querySelectorAll('[data-rv-decrypt]:not([data-rv-bound])');
    for (var k = 0; k < decrypts.length; k++) {
      decrypts[k].setAttribute('data-rv-bound', '1');
      if (io) io.observe(decrypts[k]); else runDecrypt(decrypts[k]);
    }
  }

  // Streamlit mutates the tree well after this script runs, so watch for it.
  // Coalesced with rAF because a rerun produces a burst of mutations.
  var pending = false;
  new MutationObserver(function () {
    if (pending) return;
    pending = true;
    requestAnimationFrame(function () { pending = false; rescan(); });
  }).observe(doc.body, { childList: true, subtree: true });

  W.__rvRuntime = { rescan: rescan };
  rescan();
})();
"""


def runtime(theme: Theme) -> str:
    """The script tag that installs the interactive-effect runtime."""
    return f"<script>{_RUNTIME_JS}</script>"


# ==============================================================================
# MOUNTING
# ==============================================================================
#
# Effects have to be delivered through st.components.v2, not st.html.
#
# st.html sanitises with DOMPurify, which strips <script> unless
# unsafe_allow_javascript is set, and - less obviously - discards an entire
# <style> block if it contains an at-rule it does not recognise. That silently
# removed the whole effects stylesheet, leaving the aurora and spotlight
# elements in the DOM with no styling at all and no error anywhere.
#
# Component css/js are explicitly documented as trusted and unsanitised, which
# is what these need: the CSS uses modern at-rules and the runtime is real
# script. Everything is authored in this repository; no user input reaches it.

_chrome_component = None


def _get_chrome_component():
    """Register the chrome component once.

    Streamlit warns and keeps only the last registration if a component name is
    declared twice, so this must not be re-registered per rerun.
    """
    global _chrome_component
    if _chrome_component is None:
        import streamlit as st

        # Strip the <style> wrapper: the component takes bare CSS.
        css = effects_css().replace("<style>", "").replace("</style>", "")

        _chrome_component = st.components.v2.component(
            "reverie_chrome",
            html='<div class="rv-chrome-anchor" aria-hidden="true"></div>',
            css=css,
            js=f"""
            export default function (component) {{
                {_RUNTIME_JS}
            }}
            """,
            # The effects must style the whole app, not just this component's
            # subtree, so style isolation is off by design.
            isolate_styles=False,
        )
    return _chrome_component


def mount(theme: Theme) -> None:
    """Install the effects stylesheet and interactive runtime for this page.

    Call once per run, after the theme stylesheet.
    """
    _get_chrome_component()(data={})


_backdrop_component = None


def mount_backdrop(theme: Theme, particles: bool = True, grain: bool = True) -> None:
    """Install the full-viewport aurora backdrop for the sign-in screen."""
    global _backdrop_component
    import streamlit as st

    if _backdrop_component is None:
        canvas = '<canvas id="rv-particles"></canvas>' if particles else ""
        grain_cls = " rv-grain" if grain else ""
        _backdrop_component = st.components.v2.component(
            "reverie_backdrop",
            html=(
                f'<div class="rv-aurora{grain_cls}">'
                '<div class="rv-aurora-blob"></div>'
                '<div class="rv-aurora-blob"></div>'
                '<div class="rv-aurora-blob"></div>'
                f"</div>{canvas}"
            ),
            js=f"export default function (component) {{ {_PARTICLES_JS} }}",
            isolate_styles=False,
        )
    _backdrop_component(data={})


# ==============================================================================
# BACKDROP — particle field for the login screen
# ==============================================================================

_PARTICLES_JS = r"""
(function () {
  var W = window, doc = document;
  var host = doc.getElementById('rv-particles');
  if (!host) return;
  if (host.__rvStarted) return;
  host.__rvStarted = true;

  var reduce = W.matchMedia && W.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var motionVar = parseFloat(
    getComputedStyle(doc.documentElement).getPropertyValue('--rv-motion'));
  if (isNaN(motionVar)) motionVar = 1;
  if (reduce) motionVar = 0;

  var ctx = host.getContext('2d');
  var dpr = W.devicePixelRatio || 1;
  var pts = [];
  var running = true;

  function resize() {
    host.width = W.innerWidth * dpr;
    host.height = W.innerHeight * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    seed();
  }

  function seed() {
    // Density scaled to viewport area, capped so a large monitor does not turn
    // the login screen into a space heater.
    var count = Math.min(90, Math.round((W.innerWidth * W.innerHeight) / 19000));
    pts = [];
    for (var i = 0; i < count; i++) {
      pts.push({
        x: Math.random() * W.innerWidth,
        y: Math.random() * W.innerHeight,
        vx: (Math.random() - 0.5) * 0.22,
        vy: (Math.random() - 0.5) * 0.22,
        r: Math.random() * 1.5 + 0.6
      });
    }
  }

  function frame() {
    if (!running) return;
    var w = W.innerWidth, h = W.innerHeight;
    ctx.clearRect(0, 0, w, h);
    var styles = getComputedStyle(doc.documentElement);
    var accent = styles.getPropertyValue('--rv-accent-fill').trim() || '#00D68F';
    var faint = styles.getPropertyValue('--rv-text-faint').trim() || '#7A88A0';

    for (var i = 0; i < pts.length; i++) {
      var p = pts[i];
      p.x += p.vx * motionVar;
      p.y += p.vy * motionVar;
      if (p.x < 0) p.x = w; else if (p.x > w) p.x = 0;
      if (p.y < 0) p.y = h; else if (p.y > h) p.y = 0;

      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fillStyle = accent;
      ctx.globalAlpha = 0.55;
      ctx.fill();
    }

    // Link nearby points. O(n^2) is fine at n<=90 and the constant factor is
    // dominated by the stroke calls, not the distance test.
    ctx.lineWidth = 1;
    for (var a = 0; a < pts.length; a++) {
      for (var b = a + 1; b < pts.length; b++) {
        var dx = pts[a].x - pts[b].x, dy = pts[a].y - pts[b].y;
        var d2 = dx * dx + dy * dy;
        if (d2 > 15000) continue;
        ctx.globalAlpha = (1 - d2 / 15000) * 0.22;
        ctx.strokeStyle = faint;
        ctx.beginPath();
        ctx.moveTo(pts[a].x, pts[a].y);
        ctx.lineTo(pts[b].x, pts[b].y);
        ctx.stroke();
      }
    }
    ctx.globalAlpha = 1;
    requestAnimationFrame(frame);
  }

  // Stop burning frames while the tab is in the background.
  doc.addEventListener('visibilitychange', function () {
    if (doc.hidden) { running = false; }
    else if (!running) { running = true; requestAnimationFrame(frame); }
  });

  W.addEventListener('resize', resize, { passive: true });
  resize();
  if (motionVar === 0) {
    // Draw a single static frame so the backdrop still has texture.
    running = true; frame(); running = false;
  } else {
    requestAnimationFrame(frame);
  }
})();
"""


def backdrop(particles: bool = True, grain: bool = True) -> str:
    """Full-viewport aurora backdrop, optionally with a linked particle field."""
    canvas = '<canvas id="rv-particles"></canvas>' if particles else ""
    script = f"<script>{_PARTICLES_JS}</script>" if particles else ""
    grain_cls = " rv-grain" if grain else ""
    return f"""<div class="rv-aurora{grain_cls}">
        <div class="rv-aurora-blob"></div>
        <div class="rv-aurora-blob"></div>
        <div class="rv-aurora-blob"></div>
    </div>{canvas}{script}"""


# ==============================================================================
# MARKUP HELPERS
# ==============================================================================


def count_up(
    value: float,
    decimals: int = 2,
    prefix: str = "",
    suffix: str = "",
    duration: float = 1.4,
    separator: str = ",",
    cls: str = "",
    start: Optional[float] = None,
) -> str:
    """A number that springs from *start* to *value* when scrolled into view."""
    from_val = 0.0 if start is None else start
    # Rendered with the final value as its text content, so the figure is
    # correct even if script never runs.
    text = f"{prefix}{value:,.{decimals}f}{suffix}"
    if separator != ",":
        text = text.replace(",", separator)
    return (
        f'<span class="rv-num {cls}" data-rv-countup data-to="{value}" '
        f'data-from="{from_val}" data-duration="{duration}" data-decimals="{decimals}" '
        f'data-prefix="{prefix}" data-suffix="{suffix}" data-separator="{separator}">'
        f"{text}</span>"
    )


def decrypt_text(text: str, speed: int = 34, cls: str = "") -> str:
    """Text that resolves out of a character scramble."""
    safe = text.replace('"', "&quot;")
    return f'<span class="{cls}" data-rv-decrypt="{safe}" data-speed="{speed}">{text}</span>'


def shiny(text: str, cls: str = "") -> str:
    return f'<span class="rv-shiny {cls}">{text}</span>'


def gradient_text(text: str, cls: str = "") -> str:
    return f'<span class="rv-gradient-text {cls}">{text}</span>'


def reveal(html: str, index: int = 0, tag: str = "div", cls: str = "") -> str:
    """Wrap markup so it fades up on entry; *index* staggers sibling delays."""
    return f'<{tag} class="{cls}" data-rv-reveal="{index}">{html}</{tag}>'


def card(
    body: str,
    spotlight: bool = True,
    flush: bool = False,
    accent: bool = False,
    reveal_index: Optional[int] = None,
    extra_class: str = "",
    style: str = "",
) -> str:
    """The standard surface: a themed card with an optional cursor spotlight."""
    classes = ["rv-card"]
    if spotlight:
        classes.append("rv-spotlight")
    if flush:
        classes.append("rv-card--flush")
    if accent:
        classes.append("rv-card--accent")
    if extra_class:
        classes.append(extra_class)
    attrs = f' data-rv-reveal="{reveal_index}"' if reveal_index is not None else ""
    style_attr = f' style="{style}"' if style else ""
    return f'<div class="{" ".join(classes)}"{attrs}{style_attr}>{body}</div>'


def section_header(title: str, note: str = "", rule: bool = True) -> str:
    """A section title with an optional trailing note and hairline rule."""
    note_html = f'<span class="rv-section-note">{note}</span>' if note else ""
    rule_html = '<span class="rv-section-rule"></span>' if rule else ""
    return (
        f'<div class="rv-section">'
        f'<span class="rv-section-title">{title}</span>'
        f"{rule_html}{note_html}</div>"
    )


def metric(
    label: str,
    value: str,
    delta: Optional[str] = None,
    delta_kind: str = "neutral",
    animate_to: Optional[float] = None,
    decimals: int = 2,
    prefix: str = "",
) -> str:
    """A labelled figure with an optional signed delta beneath it."""
    if animate_to is not None:
        value_html = count_up(animate_to, decimals=decimals, prefix=prefix)
    else:
        value_html = value
    kind_cls = {"pos": "rv-pos", "neg": "rv-neg"}.get(delta_kind, "rv-muted")
    delta_html = (
        f'<span class="rv-metric-delta {kind_cls}">{delta}</span>' if delta else ""
    )
    return (
        f'<div class="rv-metric">'
        f'<span class="rv-metric-label">{label}</span>'
        f'<span class="rv-metric-value">{value_html}</span>'
        f"{delta_html}</div>"
    )


def empty_state(message: str, icon: str = "—", hint: str = "") -> str:
    """A deliberate-looking placeholder for a panel with no data."""
    hint_html = f'<span style="opacity:.7">{hint}</span>' if hint else ""
    return (
        f'<div class="rv-empty"><span class="rv-empty-icon">{icon}</span>'
        f"<span>{message}</span>{hint_html}</div>"
    )


def pulse_dot(label: str = "", kind: str = "pos") -> str:
    """A live-status indicator with an expanding ring."""
    color = {"pos": "var(--rv-pos-fill)", "neg": "var(--rv-neg-fill)",
             "warn": "var(--rv-warn)"}.get(kind, "var(--rv-accent-fill)")
    text = f'<span class="rv-eyebrow">{label}</span>' if label else ""
    return (
        f'<span class="rv-row" style="gap:7px">'
        f'<span class="rv-pulse" style="background:{color}"></span>{text}</span>'
    )
