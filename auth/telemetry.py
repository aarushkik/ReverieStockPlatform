"""
Browser-side telemetry probe feeding the bot detector.

The probe collects only what the model in ``features.py`` consumes: coarse
environment facts the browser already advertises to every site, plus aggregate
statistics about *how* the form was filled. It deliberately does not collect a
stable cross-site fingerprint, does not read canvas or WebGL, and does not
record what was typed - only the timing between keystrokes.

The device identifier is derived from coarse, stable-ish properties and is
salted per deployment, so it is useful for "is this the same browser as last
time" and useless for tracking a person across sites.

Signals and what they are for
-----------------------------
``webdriver``, plugin/language counts, hardware concurrency, device memory
    Environment facts. Automation frameworks leave characteristic gaps.

``screen`` vs ``viewport``
    A viewport equal to the full screen means no browser chrome, which is how
    headless rendering looks.

pointer path length vs displacement
    Humans arc toward a target; synthetic clicks jump straight to it.

pointer turn-angle entropy
    Variance in movement direction. Interpolated cursor paths are smooth in a
    way hand movement is not.

keystroke intervals
    Mean and standard deviation only. Rhythm is the signal; content is never
    read. Reported as a coefficient of variation downstream so a fast typist is
    not mistaken for a script.

honeypot
    A field that is off-screen, ``aria-hidden``, ``tabindex=-1`` and
    ``autocomplete=off``. No human can focus it and no assistive technology
    announces it, so anything that fills it is parsing the DOM rather than
    using the page.
"""

from __future__ import annotations

# The collector. Kept as one self-contained expression so it can be dropped
# into a component without a build step.
TELEMETRY_JS = r"""
function createTelemetry(root) {
  var t0 = performance.now();
  var firstInteraction = null;

  var pointer = {
    samples: 0,
    pathLength: 0,
    lastX: null, lastY: null,
    firstX: null, firstY: null,
    lastAngle: null,
    turnAngles: []
  };

  var keys = { count: 0, lastTs: null, intervals: [], pasted: false };

  function markInteraction() {
    if (firstInteraction === null) firstInteraction = performance.now();
  }

  function onPointerMove(e) {
    markInteraction();
    var x = e.clientX, y = e.clientY;
    if (pointer.lastX !== null) {
      var dx = x - pointer.lastX, dy = y - pointer.lastY;
      var step = Math.hypot(dx, dy);
      // Ignore sub-pixel jitter; it inflates the sample count without
      // carrying any information about how the pointer actually travelled.
      if (step >= 1) {
        pointer.pathLength += step;
        var angle = Math.atan2(dy, dx);
        if (pointer.lastAngle !== null) {
          var turn = angle - pointer.lastAngle;
          // Wrap to [-pi, pi] so a direction reversal is not recorded as a
          // near-2pi turn.
          while (turn > Math.PI) turn -= 2 * Math.PI;
          while (turn < -Math.PI) turn += 2 * Math.PI;
          pointer.turnAngles.push(turn);
        }
        pointer.lastAngle = angle;
        pointer.samples++;
        pointer.lastX = x; pointer.lastY = y;
      }
    } else {
      pointer.firstX = x; pointer.firstY = y;
      pointer.lastX = x; pointer.lastY = y;
      pointer.samples++;
    }
  }

  function onKeyDown(e) {
    markInteraction();
    // Modifier-only presses are not typing.
    if (e.key && e.key.length > 1 && e.key !== 'Backspace') return;
    var now = performance.now();
    if (keys.lastTs !== null) {
      var gap = now - keys.lastTs;
      // Held-key auto-repeat and multi-second pauses are both noise.
      if (gap > 5 && gap < 5000) keys.intervals.push(gap);
    }
    keys.lastTs = now;
    keys.count++;
  }

  function onPaste() { markInteraction(); keys.pasted = true; }

  root.addEventListener('pointermove', onPointerMove, { passive: true });
  root.addEventListener('keydown', onKeyDown, true);
  root.addEventListener('paste', onPaste, true);

  function stdev(xs) {
    if (xs.length < 2) return 0;
    var m = xs.reduce(function (a, b) { return a + b; }, 0) / xs.length;
    var v = xs.reduce(function (a, b) { return a + (b - m) * (b - m); }, 0) / (xs.length - 1);
    return Math.sqrt(v);
  }

  function mean(xs) {
    if (!xs.length) return 0;
    return xs.reduce(function (a, b) { return a + b; }, 0) / xs.length;
  }

  return {
    destroy: function () {
      root.removeEventListener('pointermove', onPointerMove);
      root.removeEventListener('keydown', onKeyDown, true);
      root.removeEventListener('paste', onPaste, true);
    },
    snapshot: function (honeypotValue) {
      var nav = window.navigator || {};
      var displacement = 0;
      if (pointer.firstX !== null && pointer.lastX !== null) {
        displacement = Math.hypot(
          pointer.lastX - pointer.firstX,
          pointer.lastY - pointer.firstY
        );
      }
      // Time from the user's first interaction to submit. Measuring from page
      // load instead would just record how long the tab sat open.
      var fill = firstInteraction === null
        ? 0
        : Math.max(0, performance.now() - firstInteraction);

      return {
        user_agent: nav.userAgent || '',
        webdriver: !!nav.webdriver,
        plugin_count: (nav.plugins && nav.plugins.length) || 0,
        language_count: (nav.languages && nav.languages.length) || 0,
        hardware_concurrency: nav.hardwareConcurrency || 0,
        device_memory: nav.deviceMemory || 0,
        screen_width: (window.screen && window.screen.width) || 0,
        screen_height: (window.screen && window.screen.height) || 0,
        viewport_width: window.innerWidth || 0,
        viewport_height: window.innerHeight || 0,
        touch_points: nav.maxTouchPoints || 0,
        fill_time_ms: fill,
        pointer_samples: pointer.samples,
        pointer_entropy: stdev(pointer.turnAngles),
        pointer_path_length: pointer.pathLength,
        pointer_displacement: displacement,
        keystroke_count: keys.count,
        keystroke_iki_mean: mean(keys.intervals),
        keystroke_iki_std: stdev(keys.intervals),
        paste_used: keys.pasted,
        honeypot_filled: !!(honeypotValue && String(honeypotValue).trim().length),
        timezone: (Intl.DateTimeFormat().resolvedOptions().timeZone) || '',
        timezone_offset: new Date().getTimezoneOffset()
      };
    }
  };
}
"""


# Derives a per-browser identifier from coarse properties. Deliberately weak as
# a fingerprint: it uses only values the browser already broadcasts, avoids
# canvas/WebGL/font probing, and is salted per deployment so it cannot be
# correlated with the same browser on another site.
DEVICE_ID_JS = r"""
function deriveDeviceId(salt) {
  var nav = window.navigator || {};
  var parts = [
    salt,
    nav.userAgent || '',
    nav.platform || '',
    (nav.languages || []).join(','),
    nav.hardwareConcurrency || 0,
    nav.deviceMemory || 0,
    (window.screen && window.screen.width) || 0,
    (window.screen && window.screen.height) || 0,
    (window.screen && window.screen.colorDepth) || 0,
    (Intl.DateTimeFormat().resolvedOptions().timeZone) || ''
  ].join('|');

  // FNV-1a. Not a security hash - this only needs to be stable and cheap, and
  // the value never leaves this deployment.
  var h = 0x811c9dc5;
  for (var i = 0; i < parts.length; i++) {
    h ^= parts.charCodeAt(i);
    h = (h + ((h << 1) + (h << 4) + (h << 7) + (h << 8) + (h << 24))) >>> 0;
  }
  return 'dev-' + h.toString(16);
}
"""
