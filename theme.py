"""
Design token system for the Reverie terminal.

Everything visual in the app resolves back to the tokens defined here. A token is
either a *palette* value (colour), a *scale* value (spacing / type / radius) or a
*motion* value. Nothing else in the codebase should hardcode a hex value: the CSS
custom properties emitted by :func:`build_css` are the single source of truth for
markup, and the :class:`Theme` dataclass is the single source of truth for the
Python-side renderers (Plotly, matplotlib) that cannot read CSS variables.

The practical payoff is that the whole terminal can be re-skinned - palette,
accent, density, corner radius, motion - from the Appearance panel without
touching a line of layout code.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Dict, List, Tuple

# ==============================================================================
# PALETTES
# ==============================================================================
# A palette only defines the *neutral* ladder plus the semantic data colours.
# The accent is chosen separately so any accent can ride on any palette.


@dataclass(frozen=True)
class Palette:
    """A neutral colour ladder plus semantic market colours."""

    name: str
    label: str
    # Neutral ladder, darkest surface -> brightest text.
    bg: str            # page background
    surface: str       # card background
    surface_alt: str   # inset / secondary surface (inputs, table stripes)
    surface_hi: str    # hover / raised surface
    border: str        # hairline borders
    border_hi: str     # emphasised borders
    text: str          # primary text
    text_muted: str    # secondary text
    text_faint: str    # tertiary text, axis labels
    # Semantic market colours.
    pos: str           # gains
    neg: str           # losses
    warn: str
    info: str
    is_dark: bool = True


PALETTES: Dict[str, Palette] = {
    "midnight": Palette(
        name="midnight",
        label="Midnight",
        bg="#0A0D13",
        surface="#111621",
        surface_alt="#161C29",
        surface_hi="#1C2333",
        border="#212A3B",
        border_hi="#2E3A50",
        text="#E8EDF5",
        text_muted="#93A1B8",
        text_faint="#7A88A0",
        pos="#00D68F",
        neg="#FF4D6A",
        warn="#FFB020",
        info="#4C9AFF",
    ),
    "graphite": Palette(
        name="graphite",
        label="Graphite",
        bg="#0F0F11",
        surface="#17171A",
        surface_alt="#1D1D21",
        surface_hi="#242429",
        border="#2A2A30",
        border_hi="#3A3A42",
        text="#EDEDEF",
        text_muted="#9B9BA3",
        text_faint="#82828C",
        pos="#3ECF8E",
        neg="#F5566E",
        warn="#F5A524",
        info="#7C9CF5",
    ),
    "abyss": Palette(
        name="abyss",
        label="Abyss",
        bg="#06090F",
        surface="#0C121C",
        surface_alt="#111927",
        surface_hi="#16202F",
        border="#1B2637",
        border_hi="#27364C",
        text="#DEE7F2",
        text_muted="#8798B2",
        text_faint="#6D7F9B",
        pos="#0ACF97",
        neg="#FF5C77",
        warn="#FFC542",
        info="#3E8BFF",
    ),
    "parchment": Palette(
        name="parchment",
        label="Parchment",
        bg="#F7F6F3",
        surface="#FFFFFF",
        surface_alt="#F1F0EC",
        surface_hi="#E9E8E3",
        border="#DDDBD4",
        border_hi="#C4C1B8",
        text="#1A1A18",
        text_muted="#5C5A54",
        text_faint="#716E67",
        pos="#04704A",
        neg="#B22A36",
        warn="#8A5600",
        info="#2563C7",
        is_dark=False,
    ),
}

# ==============================================================================
# ACCENTS
# ==============================================================================
# Accents are kept separate from palettes so the two can be mixed freely. Each
# accent carries a contrasting "on" colour for text sitting on top of a filled
# accent surface.

ACCENTS: Dict[str, Tuple[str, str, str]] = {
    # key: (label, colour, on-accent text colour)
    "mint": ("Mint", "#00D68F", "#04140E"),
    "azure": ("Azure", "#4C9AFF", "#06121F"),
    "violet": ("Violet", "#A78BFA", "#140D24"),
    "amber": ("Amber", "#FFB020", "#1A1200"),
    "rose": ("Rose", "#FF6B8A", "#210910"),
    "cyan": ("Cyan", "#22D3EE", "#04161A"),
}

# ==============================================================================
# SCALES
# ==============================================================================
# Density drives spacing and control heights. Type scale is driven separately so
# a user can run a compact layout with larger text (or the reverse).


@dataclass(frozen=True)
class Density:
    name: str
    label: str
    space: float       # base spacing unit in px; the scale is a multiple of this
    control_h: int     # height of inputs / buttons in px
    row_h: int         # table row height in px
    card_pad: int      # card interior padding in px
    gutter: int        # gap between grid columns in px


DENSITIES: Dict[str, Density] = {
    "compact": Density("compact", "Compact", 4.0, 32, 28, 12, 8),
    "cozy": Density("cozy", "Cozy", 5.0, 36, 32, 16, 12),
    "roomy": Density("roomy", "Roomy", 6.0, 42, 38, 20, 16),
}

RADII: Dict[str, Tuple[str, int]] = {
    # key: (label, base radius in px)
    "sharp": ("Sharp", 2),
    "soft": ("Soft", 8),
    "round": ("Round", 14),
}

# Motion presets. "off" is also force-applied whenever the OS reports
# prefers-reduced-motion, regardless of what the user picked here.
MOTION: Dict[str, Tuple[str, float]] = {
    "full": ("Full", 1.0),
    "subtle": ("Subtle", 0.55),
    "off": ("Off", 0.0),
}

# Colour-vision-deficiency safe overrides for the gain/loss pair. Red/green is
# the single worst choice for deuteranopia and it is the most load-bearing
# colour signal in the entire product, so it gets a first-class override.
CVD_PAIRS: Dict[str, Tuple[str, str, str]] = {
    # key: (label, positive, negative)
    "classic": ("Classic (red / green)", "", ""),  # empty -> use palette defaults
    "blue_orange": ("Blue / Orange", "#3B9EFF", "#FF8A3D"),
    "teal_magenta": ("Teal / Magenta", "#14B8A6", "#E255A1"),
    "mono": ("Monochrome (shape only)", "#D8DEE9", "#8A94A6"),
}


# ==============================================================================
# THEME
# ==============================================================================


@dataclass(frozen=True)
class Theme:
    """A fully resolved visual configuration."""

    palette_key: str = "midnight"
    accent_key: str = "mint"
    density_key: str = "cozy"
    radius_key: str = "soft"
    motion_key: str = "full"
    cvd_key: str = "classic"
    type_scale: float = 1.0     # multiplier on the whole type ramp
    glass: bool = True          # backdrop blur on cards
    grid_lines: bool = True     # hairline separators in tables / cards
    uppercase_labels: bool = True   # terminal-style small caps on eyebrow labels

    # ---- resolved token access -------------------------------------------
    @property
    def palette(self) -> Palette:
        return PALETTES.get(self.palette_key, PALETTES["midnight"])

    @property
    def density(self) -> Density:
        return DENSITIES.get(self.density_key, DENSITIES["cozy"])

    @property
    def accent_raw(self) -> str:
        """The accent exactly as authored - correct for large fills and glows,
        where contrast rules for text do not apply."""
        return ACCENTS.get(self.accent_key, ACCENTS["mint"])[1]

    @property
    def accent(self) -> str:
        """The accent adjusted to stay legible as text on this palette's surface."""
        return ensure_contrast(self.accent_raw, self.palette.surface, target=4.5)

    @property
    def on_accent(self) -> str:
        """Text colour for content sitting on a filled accent surface."""
        return readable_on(self.accent_raw)

    @property
    def radius(self) -> int:
        return RADII.get(self.radius_key, RADII["soft"])[1]

    @property
    def motion(self) -> float:
        return MOTION.get(self.motion_key, MOTION["full"])[1]

    @property
    def pos_raw(self) -> str:
        override = CVD_PAIRS.get(self.cvd_key, CVD_PAIRS["classic"])[1]
        return override or self.palette.pos

    @property
    def neg_raw(self) -> str:
        override = CVD_PAIRS.get(self.cvd_key, CVD_PAIRS["classic"])[2]
        return override or self.palette.neg

    @property
    def pos(self) -> str:
        """Gain colour, guaranteed legible as text on this palette."""
        return ensure_contrast(self.pos_raw, self.palette.surface, target=4.5)

    @property
    def neg(self) -> str:
        """Loss colour, guaranteed legible as text on this palette."""
        return ensure_contrast(self.neg_raw, self.palette.surface, target=4.5)

    # Convenience passthroughs so callers can write ``T.bg`` instead of
    # ``T.palette.bg`` - these are read constantly by the Plotly renderers.
    @property
    def bg(self) -> str:
        return self.palette.bg

    @property
    def surface(self) -> str:
        return self.palette.surface

    @property
    def surface_alt(self) -> str:
        return self.palette.surface_alt

    @property
    def surface_hi(self) -> str:
        return self.palette.surface_hi

    @property
    def border(self) -> str:
        return self.palette.border

    @property
    def border_hi(self) -> str:
        return self.palette.border_hi

    @property
    def text(self) -> str:
        return self.palette.text

    @property
    def text_muted(self) -> str:
        return self.palette.text_muted

    @property
    def text_faint(self) -> str:
        return self.palette.text_faint

    @property
    def warn(self) -> str:
        return self.palette.warn

    @property
    def info(self) -> str:
        return self.palette.info

    @property
    def is_dark(self) -> bool:
        return self.palette.is_dark

    # ---- type ramp --------------------------------------------------------
    @property
    def type_ramp(self) -> Dict[str, float]:
        """Named font sizes in px.

        A real ramp with meaningful jumps, rather than the flat 14px-everywhere
        the terminal used to run - hierarchy is what makes dense data scannable.
        """
        s = self.type_scale
        return {
            "micro": round(10.0 * s, 2),   # dense table sub-labels
            "eyebrow": round(11.0 * s, 2),  # uppercase section labels
            "small": round(12.0 * s, 2),   # captions, metadata
            "body": round(13.5 * s, 2),    # default reading size
            "figure": round(15.0 * s, 2),  # numbers in tables
            "h3": round(16.0 * s, 2),
            "h2": round(19.0 * s, 2),
            "h1": round(23.0 * s, 2),
            "display": round(30.0 * s, 2),  # hero readouts
            "mega": round(42.0 * s, 2),
        }

    def spacing(self, steps: float) -> float:
        """Spacing scale: ``spacing(2)`` is two base units."""
        return round(self.density.space * steps, 2)

    def with_overrides(self, **kwargs) -> "Theme":
        return replace(self, **{k: v for k, v in kwargs.items() if v is not None})


DEFAULT_THEME = Theme()


# ==============================================================================
# COLOUR UTILITIES
# ==============================================================================


def hex_to_rgb(value: str) -> Tuple[int, int, int]:
    value = value.lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def rgba(value: str, alpha: float) -> str:
    """``rgba('#00D68F', .15)`` -> ``'rgba(0, 214, 143, 0.15)'``."""
    r, g, b = hex_to_rgb(value)
    return f"rgba({r}, {g}, {b}, {round(alpha, 4)})"


def mix(a: str, b: str, t: float) -> str:
    """Linear blend of two hex colours; ``t=0`` returns *a*, ``t=1`` returns *b*."""
    ar, ag, ab = hex_to_rgb(a)
    br, bg_, bb = hex_to_rgb(b)
    return "#{:02X}{:02X}{:02X}".format(
        int(round(ar + (br - ar) * t)),
        int(round(ag + (bg_ - ag) * t)),
        int(round(ab + (bb - ab) * t)),
    )


def relative_luminance(value: str) -> float:
    """WCAG relative luminance, used to pick readable text on arbitrary fills."""
    def channel(c: float) -> float:
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = hex_to_rgb(value)
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast_ratio(fg: str, bg: str) -> float:
    """WCAG contrast ratio between two hex colours (1.0 - 21.0)."""
    l1, l2 = relative_luminance(fg), relative_luminance(bg)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def readable_on(background: str, dark: str = "#0A0D13", light: str = "#FFFFFF") -> str:
    """Pick whichever of *dark* / *light* has more contrast against *background*."""
    return dark if contrast_ratio(dark, background) >= contrast_ratio(light, background) else light


def ensure_contrast(color: str, background: str, target: float = 4.5, steps: int = 40) -> str:
    """Darken or lighten *color* just enough to clear *target* against *background*.

    The accent palette is tuned for dark surfaces; dropped onto the light
    "Parchment" palette every one of them lands around 2:1, which is unreadable
    for text and barely visible for icons. Rather than maintaining a parallel
    accent table per palette, we walk the colour toward black or white - whichever
    direction actually increases contrast - and stop at the first step that
    clears the threshold. This keeps the accent recognisably itself while
    guaranteeing the floor.
    """
    if contrast_ratio(color, background) >= target:
        return color

    # Move away from the background: toward black on light backgrounds,
    # toward white on dark ones.
    destination = "#000000" if relative_luminance(background) > 0.5 else "#FFFFFF"

    best = color
    for i in range(1, steps + 1):
        candidate = mix(color, destination, i / steps)
        best = candidate
        if contrast_ratio(candidate, background) >= target:
            return candidate
    return best


def value_color(theme: Theme, value: float, neutral_band: float = 0.0) -> str:
    """Semantic colour for a signed market figure."""
    if value > neutral_band:
        return theme.pos
    if value < -neutral_band:
        return theme.neg
    return theme.text_muted


# ==============================================================================
# CSS GENERATION
# ==============================================================================

FONT_IMPORT = (
    "@import url('https://fonts.googleapis.com/css2?"
    "family=Inter:wght@400;500;600;700;800&"
    "family=JetBrains+Mono:wght@400;500;600;700&display=swap');"
)


def css_variables(theme: Theme) -> str:
    """Emit every token as a CSS custom property on ``:root``."""
    p = theme.palette
    t = theme.type_ramp
    d = theme.density
    r = theme.radius
    m = theme.motion

    lines: List[str] = [
        # --- colour -------------------------------------------------------
        f"--rv-bg: {p.bg};",
        f"--rv-surface: {p.surface};",
        f"--rv-surface-alt: {p.surface_alt};",
        f"--rv-surface-hi: {p.surface_hi};",
        f"--rv-border: {p.border};",
        f"--rv-border-hi: {p.border_hi};",
        f"--rv-text: {p.text};",
        f"--rv-text-muted: {p.text_muted};",
        f"--rv-text-faint: {p.text_faint};",
        # `--rv-accent` is contrast-corrected for text; `--rv-accent-fill` is the
        # authored hue, for large fills, glows and chart series where the text
        # contrast floor does not apply.
        f"--rv-accent: {theme.accent};",
        f"--rv-accent-fill: {theme.accent_raw};",
        f"--rv-on-accent: {theme.on_accent};",
        f"--rv-accent-soft: {rgba(theme.accent_raw, 0.14)};",
        f"--rv-accent-line: {rgba(theme.accent_raw, 0.42)};",
        f"--rv-pos: {theme.pos};",
        f"--rv-neg: {theme.neg};",
        f"--rv-pos-fill: {theme.pos_raw};",
        f"--rv-neg-fill: {theme.neg_raw};",
        f"--rv-pos-soft: {rgba(theme.pos_raw, 0.14)};",
        f"--rv-neg-soft: {rgba(theme.neg_raw, 0.14)};",
        f"--rv-warn: {p.warn};",
        f"--rv-info: {p.info};",
        f"--rv-warn-soft: {rgba(p.warn, 0.14)};",
        f"--rv-info-soft: {rgba(p.info, 0.14)};",
        # --- type ---------------------------------------------------------
        "--rv-font: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;",
        "--rv-mono: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace;",
        f"--rv-fs-micro: {t['micro']}px;",
        f"--rv-fs-eyebrow: {t['eyebrow']}px;",
        f"--rv-fs-small: {t['small']}px;",
        f"--rv-fs-body: {t['body']}px;",
        f"--rv-fs-figure: {t['figure']}px;",
        f"--rv-fs-h3: {t['h3']}px;",
        f"--rv-fs-h2: {t['h2']}px;",
        f"--rv-fs-h1: {t['h1']}px;",
        f"--rv-fs-display: {t['display']}px;",
        f"--rv-fs-mega: {t['mega']}px;",
        # --- space --------------------------------------------------------
        f"--rv-space-1: {theme.spacing(1)}px;",
        f"--rv-space-2: {theme.spacing(2)}px;",
        f"--rv-space-3: {theme.spacing(3)}px;",
        f"--rv-space-4: {theme.spacing(4)}px;",
        f"--rv-space-6: {theme.spacing(6)}px;",
        f"--rv-space-8: {theme.spacing(8)}px;",
        f"--rv-control-h: {d.control_h}px;",
        f"--rv-row-h: {d.row_h}px;",
        f"--rv-card-pad: {d.card_pad}px;",
        f"--rv-gutter: {d.gutter}px;",
        # --- shape --------------------------------------------------------
        f"--rv-radius: {r}px;",
        f"--rv-radius-sm: {max(2, r - 4)}px;",
        f"--rv-radius-lg: {r + 6}px;",
        f"--rv-radius-pill: 999px;",
        # --- elevation ----------------------------------------------------
        f"--rv-shadow-1: 0 1px 2px {rgba('#000000', 0.28 if p.is_dark else 0.06)};",
        f"--rv-shadow-2: 0 4px 16px {rgba('#000000', 0.34 if p.is_dark else 0.09)};",
        f"--rv-shadow-3: 0 12px 40px {rgba('#000000', 0.45 if p.is_dark else 0.14)};",
        f"--rv-glow: 0 0 0 1px {rgba(theme.accent_raw, 0.30)}, 0 6px 24px {rgba(theme.accent_raw, 0.16)};",
        # --- motion -------------------------------------------------------
        f"--rv-motion: {m};",
        f"--rv-dur-fast: {round(0.12 * m, 4)}s;",
        f"--rv-dur: {round(0.22 * m, 4)}s;",
        f"--rv-dur-slow: {round(0.42 * m, 4)}s;",
        "--rv-ease: cubic-bezier(0.16, 1, 0.3, 1);",
        "--rv-ease-out: cubic-bezier(0.22, 0.61, 0.36, 1);",
        # --- misc ---------------------------------------------------------
        f"--rv-blur: {'12px' if theme.glass else '0px'};",
        f"--rv-hairline: {p.border if theme.grid_lines else 'transparent'};",
        f"--rv-label-transform: {'uppercase' if theme.uppercase_labels else 'none'};",
        f"--rv-label-spacing: {'0.07em' if theme.uppercase_labels else '0'};",
        f"--rv-nav-h: 52px;",
    ]
    body = "\n        ".join(lines)
    return ":root {\n        " + body + "\n    }"


def build_css(theme: Theme) -> str:
    """The complete stylesheet for the terminal, derived entirely from tokens."""
    p = theme.palette
    glass_rule = (
        "backdrop-filter: blur(var(--rv-blur)); -webkit-backdrop-filter: blur(var(--rv-blur));"
        if theme.glass
        else ""
    )
    card_bg = rgba(p.surface, 0.82) if theme.glass else p.surface
    scrim = rgba(p.bg, 0.72)

    return f"""<style>
    {FONT_IMPORT}

    {css_variables(theme)}

    /* =====================================================================
       1. RESET & CHROME
       Streamlit ships a lot of chrome we do not want in a terminal layout.
       ===================================================================== */
    header[data-testid="stHeader"], footer, #MainMenu {{
        display: none !important;
        height: 0 !important;
    }}
    .stApp {{
        background: var(--rv-bg) !important;
        color: var(--rv-text) !important;
    }}
    .stAppViewContainer, .stMain {{ background: var(--rv-bg) !important; }}

    .block-container {{
        max-width: 100% !important;
        padding: calc(var(--rv-nav-h) + var(--rv-space-3)) var(--rv-space-4) var(--rv-space-6) !important;
        background: transparent !important;
    }}

    html, body, [class*="css"], .stApp {{
        font-family: var(--rv-font) !important;
        font-size: var(--rv-fs-body);
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
    }}

    /* Vertical rhythm. Streamlit's default is a uniform 1rem gap between every
       element, which reads as noise in a dense layout. We tighten it and let
       cards own their own spacing instead. */
    [data-testid="stVerticalBlock"] {{ gap: var(--rv-space-2) !important; }}
    [data-testid="stHorizontalBlock"] {{
        gap: var(--rv-gutter) !important;
        align-items: stretch !important;
    }}
    [data-testid="stElementContainer"] {{ margin: 0 !important; }}

    /* =====================================================================
       2. TYPOGRAPHY
       A real ramp. Previously every p/span/div was forced to 14px/600, which
       flattened all hierarchy - headings, body and captions looked identical.
       ===================================================================== */
    h1, h2, h3, h4, h5, h6 {{
        font-family: var(--rv-font) !important;
        color: var(--rv-text) !important;
        letter-spacing: -0.011em;
        margin: 0 0 var(--rv-space-2) 0 !important;
        padding: 0 !important;
        border: none !important;
        text-transform: none !important;
    }}
    h1 {{ font-size: var(--rv-fs-h1) !important; font-weight: 700 !important; }}
    h2 {{ font-size: var(--rv-fs-h2) !important; font-weight: 650 !important; }}
    h3 {{ font-size: var(--rv-fs-h3) !important; font-weight: 650 !important; }}
    h4, h5, h6 {{ font-size: var(--rv-fs-body) !important; font-weight: 650 !important; }}

    p, li {{
        font-size: var(--rv-fs-body) !important;
        font-weight: 400 !important;
        line-height: 1.55 !important;
        color: var(--rv-text) !important;
    }}
    small, .rv-caption {{
        font-size: var(--rv-fs-small) !important;
        color: var(--rv-text-muted) !important;
        font-weight: 400 !important;
    }}
    [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {{
        font-size: var(--rv-fs-small) !important;
        color: var(--rv-text-muted) !important;
    }}

    /* Every figure in the product is tabular so columns of numbers align on the
       decimal point instead of shimmying as digits change. */
    .rv-num, .rv-figure, td.rv-num, .rv-mono {{
        font-family: var(--rv-mono) !important;
        font-variant-numeric: tabular-nums;
        font-feature-settings: "tnum" 1, "zero" 1;
    }}

    /* Eyebrow: the small uppercase label above a section or metric. This is the
       only place uppercase is used - it reads as deliberate rather than shouty. */
    .rv-eyebrow {{
        font-size: var(--rv-fs-eyebrow) !important;
        font-weight: 600 !important;
        color: var(--rv-text-muted) !important;
        text-transform: var(--rv-label-transform);
        letter-spacing: var(--rv-label-spacing);
        line-height: 1.2;
    }}

    /* Section header: a title with an optional trailing rule. */
    .rv-section {{
        display: flex;
        align-items: baseline;
        gap: var(--rv-space-2);
        margin: var(--rv-space-4) 0 var(--rv-space-2);
    }}
    .rv-section-title {{
        font-size: var(--rv-fs-h3);
        font-weight: 650;
        color: var(--rv-text);
        letter-spacing: -0.01em;
        white-space: nowrap;
    }}
    .rv-section-note {{
        font-size: var(--rv-fs-small);
        color: var(--rv-text-faint);
        white-space: nowrap;
    }}
    .rv-section-rule {{
        flex: 1;
        height: 1px;
        background: var(--rv-hairline);
    }}

    /* =====================================================================
       3. SURFACES
       ===================================================================== */
    .rv-card, .fintech-card {{
        background: {card_bg};
        {glass_rule}
        border: 1px solid var(--rv-border);
        border-radius: var(--rv-radius);
        padding: var(--rv-card-pad);
        box-shadow: var(--rv-shadow-1);
        display: flex;
        flex-direction: column;
        width: 100%;
        height: 100%;
        box-sizing: border-box;
        overflow: hidden;
        transition: border-color var(--rv-dur) var(--rv-ease),
                    box-shadow var(--rv-dur) var(--rv-ease),
                    transform var(--rv-dur) var(--rv-ease);
    }}
    .rv-card:hover, .fintech-card:hover {{
        border-color: var(--rv-border-hi);
        box-shadow: var(--rv-shadow-2);
    }}
    .rv-card--flush {{ padding: 0; }}
    .rv-card--accent {{ border-color: var(--rv-accent-line); }}
    .card-highlighted {{
        border-color: var(--rv-accent) !important;
        box-shadow: var(--rv-glow) !important;
    }}

    div[data-testid="stVerticalBlockBorderContainer"] {{
        background: var(--rv-surface) !important;
        border: 1px solid var(--rv-border) !important;
        border-radius: var(--rv-radius) !important;
        padding: var(--rv-card-pad) !important;
    }}

    /* =====================================================================
       4. TABLES
       ===================================================================== */
    table {{
        width: 100%;
        border-collapse: collapse !important;
        background: transparent !important;
    }}
    th {{
        font-family: var(--rv-font) !important;
        font-size: var(--rv-fs-eyebrow) !important;
        font-weight: 600 !important;
        color: var(--rv-text-faint) !important;
        text-transform: var(--rv-label-transform) !important;
        letter-spacing: var(--rv-label-spacing);
        text-align: left !important;
        padding: var(--rv-space-1) var(--rv-space-2) !important;
        border: none !important;
        border-bottom: 1px solid var(--rv-border) !important;
        background: transparent !important;
        white-space: nowrap;
    }}
    td {{
        font-family: var(--rv-mono) !important;
        font-variant-numeric: tabular-nums;
        font-size: var(--rv-fs-body) !important;
        font-weight: 450 !important;
        color: var(--rv-text) !important;
        padding: 0 var(--rv-space-2) !important;
        height: var(--rv-row-h);
        line-height: var(--rv-row-h);
        border: none !important;
        border-bottom: 1px solid var(--rv-hairline) !important;
        background: transparent !important;
    }}
    tbody tr {{ transition: background var(--rv-dur-fast) linear; }}
    tbody tr:hover {{ background: var(--rv-surface-alt) !important; }}
    tbody tr:last-child td {{ border-bottom: none !important; }}
    th.rv-right, td.rv-right {{ text-align: right !important; }}
    /* Ticker symbols read as identifiers, not prose. */
    td.rv-sym {{ font-weight: 600 !important; color: var(--rv-text) !important; }}

    /* =====================================================================
       5. METRICS
       ===================================================================== */
    .rv-metric {{
        display: flex;
        flex-direction: column;
        gap: 2px;
        padding: var(--rv-space-2);
        background: var(--rv-surface-alt);
        border: 1px solid var(--rv-border);
        border-radius: var(--rv-radius-sm);
        min-width: 0;
    }}
    .rv-metric-label {{
        font-size: var(--rv-fs-eyebrow);
        font-weight: 600;
        color: var(--rv-text-faint);
        text-transform: var(--rv-label-transform);
        letter-spacing: var(--rv-label-spacing);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }}
    .rv-metric-value {{
        font-family: var(--rv-mono);
        font-variant-numeric: tabular-nums;
        font-size: var(--rv-fs-figure);
        font-weight: 600;
        color: var(--rv-text);
        line-height: 1.25;
    }}
    .rv-metric-delta {{
        font-family: var(--rv-mono);
        font-variant-numeric: tabular-nums;
        font-size: var(--rv-fs-small);
        font-weight: 600;
    }}
    .rv-readout {{
        font-family: var(--rv-mono);
        font-variant-numeric: tabular-nums;
        font-size: var(--rv-fs-display);
        font-weight: 600;
        letter-spacing: -0.02em;
        color: var(--rv-text);
        line-height: 1.1;
    }}

    /* legacy aliases retained so older markup keeps rendering correctly */
    .metric-box {{
        background: var(--rv-surface-alt) !important;
        border: 1px solid var(--rv-border) !important;
        border-radius: var(--rv-radius-sm) !important;
        padding: var(--rv-space-2) !important;
    }}
    .metric-label {{
        font-size: var(--rv-fs-eyebrow) !important;
        color: var(--rv-text-faint) !important;
        font-weight: 600 !important;
        text-transform: var(--rv-label-transform);
        letter-spacing: var(--rv-label-spacing);
    }}
    .metric-val, .fin-readout {{
        font-family: var(--rv-mono) !important;
        font-variant-numeric: tabular-nums;
        font-weight: 600 !important;
        color: var(--rv-text) !important;
    }}
    .metric-val {{ font-size: var(--rv-fs-figure) !important; }}
    .fin-readout {{ font-size: var(--rv-fs-display) !important; letter-spacing: -0.02em; }}

    /* =====================================================================
       6. SEMANTIC COLOUR
       ===================================================================== */
    .rv-pos, .color-green {{ color: var(--rv-pos) !important; }}
    .rv-neg, .color-red {{ color: var(--rv-neg) !important; }}
    .rv-muted, .color-gray {{ color: var(--rv-text-muted) !important; }}
    .rv-accent {{ color: var(--rv-accent) !important; }}

    .rv-pill, .pill-pos, .pill-neg, .pill-neut {{
        display: inline-flex;
        align-items: center;
        gap: 4px;
        font-family: var(--rv-mono);
        font-variant-numeric: tabular-nums;
        font-size: var(--rv-fs-micro);
        font-weight: 600;
        padding: 2px 7px;
        border-radius: var(--rv-radius-pill);
        line-height: 1.5;
        white-space: nowrap;
    }}
    .pill-pos {{ background: var(--rv-pos-soft); color: var(--rv-pos); }}
    .pill-neg {{ background: var(--rv-neg-soft); color: var(--rv-neg); }}
    .pill-neut {{ background: var(--rv-surface-hi); color: var(--rv-text-muted); }}

    .rv-badge, .badge-strong-buy, .badge-buy, .badge-hold, .badge-sell {{
        display: inline-flex;
        align-items: center;
        font-size: var(--rv-fs-eyebrow);
        font-weight: 650;
        padding: 3px 9px;
        border-radius: var(--rv-radius-pill);
        text-transform: var(--rv-label-transform);
        letter-spacing: var(--rv-label-spacing);
        border: 1px solid transparent;
        white-space: nowrap;
    }}
    .badge-strong-buy {{
        background: var(--rv-pos-fill); color: {readable_on(theme.pos_raw)};
    }}
    .badge-buy {{
        background: var(--rv-pos-soft); color: var(--rv-pos); border-color: var(--rv-pos);
    }}
    .badge-hold {{
        background: var(--rv-surface-hi); color: var(--rv-text-muted); border-color: var(--rv-border-hi);
    }}
    .badge-sell {{
        background: var(--rv-neg-soft); color: var(--rv-neg); border-color: var(--rv-neg);
    }}

    .sent-bullish {{ color: var(--rv-pos); font-weight: 600; font-size: var(--rv-fs-small); }}
    .sent-bearish {{ color: var(--rv-neg); font-weight: 600; font-size: var(--rv-fs-small); }}
    .sent-neutral {{ color: var(--rv-text-muted); font-weight: 600; font-size: var(--rv-fs-small); }}

    /* =====================================================================
       7. FORM CONTROLS
       ===================================================================== */
    div[data-baseweb="input"], div[data-baseweb="textarea"], div[data-baseweb="select"] > div {{
        background: var(--rv-surface-alt) !important;
        border: 1px solid var(--rv-border) !important;
        border-radius: var(--rv-radius-sm) !important;
        color: var(--rv-text) !important;
        transition: border-color var(--rv-dur) var(--rv-ease),
                    box-shadow var(--rv-dur) var(--rv-ease);
    }}
    div[data-baseweb="input"]:focus-within,
    div[data-baseweb="textarea"]:focus-within,
    div[data-baseweb="select"] > div:focus-within {{
        border-color: var(--rv-accent) !important;
        box-shadow: 0 0 0 3px var(--rv-accent-soft) !important;
    }}
    .stTextInput input, .stNumberInput input, .stTextArea textarea {{
        background: transparent !important;
        color: var(--rv-text) !important;
        font-size: var(--rv-fs-body) !important;
        border: none !important;
    }}
    .stTextInput input::placeholder, .stTextArea textarea::placeholder {{
        color: var(--rv-text-faint) !important;
    }}
    .stNumberInput button {{
        background: var(--rv-surface-hi) !important;
        color: var(--rv-text-muted) !important;
        border-color: var(--rv-border) !important;
    }}
    label, .stSelectbox label, .stTextInput label, .stSlider label {{
        font-size: var(--rv-fs-small) !important;
        font-weight: 550 !important;
        color: var(--rv-text-muted) !important;
    }}

    /* =====================================================================
       8. BUTTONS
       ===================================================================== */
    div.stButton > button, div.stDownloadButton > button, div.stFormSubmitButton > button {{
        background: var(--rv-surface-alt) !important;
        color: var(--rv-text) !important;
        border: 1px solid var(--rv-border) !important;
        border-radius: var(--rv-radius-sm) !important;
        font-family: var(--rv-font) !important;
        font-size: var(--rv-fs-small) !important;
        font-weight: 600 !important;
        min-height: var(--rv-control-h) !important;
        padding: 0 var(--rv-space-3) !important;
        transition: background var(--rv-dur) var(--rv-ease),
                    border-color var(--rv-dur) var(--rv-ease),
                    color var(--rv-dur) var(--rv-ease),
                    transform var(--rv-dur-fast) var(--rv-ease);
    }}
    div.stButton > button:hover, div.stDownloadButton > button:hover,
    div.stFormSubmitButton > button:hover {{
        background: var(--rv-surface-hi) !important;
        border-color: var(--rv-border-hi) !important;
        color: var(--rv-text) !important;
        transform: translateY(calc(-1px * var(--rv-motion)));
    }}
    div.stButton > button:active {{ transform: translateY(0); }}
    div.stButton > button[kind="primary"], div.stFormSubmitButton > button {{
        background: var(--rv-accent-fill) !important;
        color: var(--rv-on-accent) !important;
        border-color: var(--rv-accent-fill) !important;
    }}
    div.stButton > button[kind="primary"]:hover, div.stFormSubmitButton > button:hover {{
        filter: brightness(1.08);
        background: var(--rv-accent-fill) !important;
        color: var(--rv-on-accent) !important;
    }}

    /* Focus ring. The previous stylesheet removed focus outlines entirely,
       which made the terminal unusable by keyboard. */
    *:focus-visible {{
        outline: 2px solid var(--rv-accent) !important;
        outline-offset: 2px !important;
        border-radius: var(--rv-radius-sm);
    }}

    /* =====================================================================
       9. TABS, SIDEBAR, MISC STREAMLIT WIDGETS
       ===================================================================== */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 2px !important;
        background: var(--rv-surface-alt);
        border: 1px solid var(--rv-border);
        border-radius: var(--rv-radius-sm);
        padding: 3px !important;
        display: inline-flex;
    }}
    .stTabs [data-baseweb="tab"] {{
        background: transparent !important;
        color: var(--rv-text-muted) !important;
        border: none !important;
        border-radius: calc(var(--rv-radius-sm) - 1px) !important;
        padding: 6px 14px !important;
        font-size: var(--rv-fs-small) !important;
        font-weight: 600 !important;
        text-transform: none !important;
        transition: background var(--rv-dur) var(--rv-ease), color var(--rv-dur) var(--rv-ease);
    }}
    .stTabs [data-baseweb="tab"]:hover {{ color: var(--rv-text) !important; }}
    .stTabs [aria-selected="true"] {{
        background: var(--rv-surface-hi) !important;
        color: var(--rv-text) !important;
        box-shadow: var(--rv-shadow-1);
    }}
    .stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] {{
        display: none !important;
    }}

    section[data-testid="stSidebar"] {{
        background: var(--rv-surface) !important;
        border-right: 1px solid var(--rv-border) !important;
    }}
    section[data-testid="stSidebar"] .block-container {{ padding-top: var(--rv-space-3) !important; }}

    [data-testid="stExpander"] details {{
        background: var(--rv-surface) !important;
        border: 1px solid var(--rv-border) !important;
        border-radius: var(--rv-radius-sm) !important;
    }}
    [data-testid="stExpander"] summary {{
        font-size: var(--rv-fs-small) !important;
        font-weight: 600 !important;
        color: var(--rv-text-muted) !important;
    }}

    [data-testid="stChatMessage"] {{
        background: var(--rv-surface-alt) !important;
        border: 1px solid var(--rv-border) !important;
        border-radius: var(--rv-radius) !important;
        padding: var(--rv-space-2) var(--rv-space-3) !important;
    }}

    hr {{ border-color: var(--rv-border) !important; margin: var(--rv-space-3) 0 !important; }}

    a {{ color: var(--rv-accent); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}

    .news-link {{
        color: var(--rv-text);
        text-decoration: none;
        font-size: var(--rv-fs-body);
        font-weight: 550;
        transition: color var(--rv-dur-fast) linear;
    }}
    .news-link:hover {{ color: var(--rv-accent) !important; text-decoration: none; }}
    .tl-item {{ padding: var(--rv-space-2) 0; border-bottom: 1px solid var(--rv-hairline); }}
    .tl-item:last-child {{ border-bottom: none; }}

    .scan-row {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 1px solid var(--rv-hairline);
        padding: 0 var(--rv-space-2);
        height: var(--rv-row-h);
        font-size: var(--rv-fs-body);
        transition: background var(--rv-dur-fast) linear;
    }}
    .scan-row:hover {{ background: var(--rv-surface-alt); }}
    .scan-row:last-child {{ border-bottom: none; }}

    .vol-track {{
        background: var(--rv-surface-hi);
        border-radius: var(--rv-radius-pill);
        height: 6px;
        width: 100%;
        position: relative;
        margin: var(--rv-space-1) 0;
        overflow: hidden;
    }}
    .vol-fill {{
        height: 100%;
        border-radius: var(--rv-radius-pill);
        position: absolute;
        left: 0;
        top: 0;
        transition: width var(--rv-dur-slow) var(--rv-ease);
    }}
    .vol-marker {{
        width: 2px;
        height: 12px;
        background: var(--rv-text);
        border-radius: 1px;
        position: absolute;
        top: -3px;
    }}

    /* Charts sit on the card surface, not on a separate white plate. */
    .stPlotlyChart, [data-testid="stPlotlyChart"] {{
        background: transparent !important;
        border-radius: var(--rv-radius-sm);
        overflow: hidden;
    }}
    .js-plotly-plot .plotly .modebar {{ background: transparent !important; }}

    /* Scrollbars */
    ::-webkit-scrollbar {{ width: 10px; height: 10px; }}
    ::-webkit-scrollbar-track {{ background: transparent; }}
    ::-webkit-scrollbar-thumb {{
        background: var(--rv-border-hi);
        border-radius: var(--rv-radius-pill);
        border: 2px solid var(--rv-bg);
    }}
    ::-webkit-scrollbar-thumb:hover {{ background: var(--rv-text-faint); }}

    /* =====================================================================
       10. LAYOUT PRIMITIVES
       ===================================================================== */
    .rv-row {{ display: flex; align-items: center; gap: var(--rv-space-2); }}
    .rv-row--between {{ justify-content: space-between; }}
    .rv-col {{ display: flex; flex-direction: column; gap: var(--rv-space-1); }}
    .rv-grid {{ display: grid; gap: var(--rv-gutter); }}
    .rv-spacer {{ flex: 1; }}
    .rv-truncate {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .rv-scroll-y {{ overflow-y: auto; }}

    /* Empty states should look intentional rather than broken. */
    .rv-empty {{
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: var(--rv-space-1);
        padding: var(--rv-space-6) var(--rv-space-3);
        color: var(--rv-text-faint);
        font-size: var(--rv-fs-small);
        text-align: center;
    }}
    .rv-empty-icon {{ font-size: 20px; opacity: 0.5; }}

    /* Skeleton shimmer for content that is still loading. */
    .rv-skeleton {{
        background: linear-gradient(90deg,
            var(--rv-surface-alt) 25%,
            var(--rv-surface-hi) 50%,
            var(--rv-surface-alt) 75%);
        background-size: 200% 100%;
        animation: rv-shimmer calc(1.4s / max(var(--rv-motion), 0.01)) linear infinite;
        border-radius: var(--rv-radius-sm);
    }}
    @keyframes rv-shimmer {{
        from {{ background-position: 200% 0; }}
        to {{ background-position: -200% 0; }}
    }}

    .rv-scrim {{ background: {scrim}; }}

    /* =====================================================================
       11. MOTION
       A user choosing "Off", or an OS-level reduced-motion preference, must
       win over every animation in the app.
       ===================================================================== */
    @media (prefers-reduced-motion: reduce) {{
        *, *::before, *::after {{
            animation-duration: 0.001ms !important;
            animation-iteration-count: 1 !important;
            transition-duration: 0.001ms !important;
            scroll-behavior: auto !important;
        }}
    }}
</style>"""


def plotly_layout(theme: Theme) -> dict:
    """Shared Plotly layout so every chart inherits the active theme."""
    return dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(
            family="JetBrains Mono, ui-monospace, monospace",
            size=11,
            color=theme.text_muted,
        ),
        xaxis=dict(
            gridcolor=theme.border,
            zerolinecolor=theme.border,
            linecolor=theme.border,
            tickfont=dict(color=theme.text_faint, size=10),
        ),
        yaxis=dict(
            gridcolor=theme.border,
            zerolinecolor=theme.border,
            linecolor=theme.border,
            tickfont=dict(color=theme.text_faint, size=10),
        ),
        hoverlabel=dict(
            bgcolor=theme.surface_hi,
            bordercolor=theme.border_hi,
            font=dict(color=theme.text, family="JetBrains Mono, monospace", size=11),
        ),
        margin=dict(l=8, r=8, t=8, b=8),
        showlegend=False,
    )
