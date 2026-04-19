"""
hunter/theme.py
===============
Central store for every visual constant used across the application.

Importing from here (rather than scattering hex strings through the code)
means you can restyle the entire app by editing this one file.

Sections
--------
THEME           – background colours, accent tints, text shades, special
                  colours for APT modules (red-tinted) and MITRE chips (purple).
PRIORITY_COLORS – maps "Critical / High / Medium / Low" to a hex colour used
                  on priority stripes and badges.
CATEGORY_ICONS  – one Unicode emoji per module category shown in card titles.
CATEGORIES      – ordered list of valid category strings (used in editor dropdown).
PRIORITIES      – ordered list of valid priority strings (used in editor dropdown).
FILTER_CATS     – category list prepended with "All" for the library filter bar.
"""

# ── Main colour palette ───────────────────────────────────────────────────────
THEME = {
    # Backgrounds — dark theme layered from darkest (page) to lightest (card)
    "bg_dark":        "#0d1117",   # root window / canvas background
    "bg_panel":       "#161b22",   # side-panel and header backgrounds
    "bg_card":        "#1c2230",   # individual module cards
    "bg_card_hover":  "#242d3f",   # card hover state
    "bg_selected":    "#1a3a5c",   # card is already in the plan (blue tint)

    # Accent colours used for highlights, borders, and interactive elements
    "accent":         "#00b4d8",   # primary cyan accent (buttons, headings)
    "accent_dim":     "#0077a8",   # dimmed accent (question number badges)
    "accent_glow":    "#48cae4",   # lighter variant for hunt action titles

    # Semantic colours
    "success":        "#3dd68c",   # green — steps count, positive indicators
    "warning":        "#f4a261",   # orange — High priority, prerequisites
    "danger":         "#e76f51",   # red-orange — remove buttons, High priority alt
    "critical":       "#c1121f",   # deep red — Critical priority, the H logo

    # Text hierarchy
    "text_primary":   "#e6edf3",   # main readable text
    "text_secondary": "#8b949e",   # meta labels, timestamps
    "text_muted":     "#4a5568",   # hint text, disabled states

    # Structural / border colours
    "border":         "#21262d",   # default card and input borders
    "border_accent":  "#264f73",   # plan card border (blue tint)

    # Tag chips in library cards
    "tag_bg":         "#1e3a5f",
    "tag_text":       "#7ec8e3",

    # MITRE ATT&CK technique chips (purple tint)
    "mitre_bg":       "#2d1b69",
    "mitre_text":     "#c084fc",

    # APT module overrides — dark red tint to visually separate nation-state modules
    "apt_bg":         "#2a0a0a",
    "apt_text":       "#ff6b6b",
    "apt_border":     "#7a1a1a",
}

# ── Priority → colour mapping ─────────────────────────────────────────────────
# Used on priority stripe, step-number badge, and plan subtitle text.
PRIORITY_COLORS = {
    "Critical": "#c1121f",   # deep red
    "High":     "#e76f51",   # red-orange
    "Medium":   "#f4a261",   # amber
    "Low":      "#3dd68c",   # green
}

# ── Category → emoji icon ─────────────────────────────────────────────────────
# Shown at the left of every module card title.
CATEGORY_ICONS = {
    "Cloud":    "☁",
    "Identity": "🔑",
    "Endpoint": "💻",
    "Network":  "🌐",
    "APT":      "🎯",   # Nation-state threat actor modules
    "Other":    "🔍",
}

# ── Dropdown / filter lists ───────────────────────────────────────────────────
CATEGORIES  = ["Cloud", "Identity", "Endpoint", "Network", "APT", "Other"]
PRIORITIES  = ["Critical", "High", "Medium", "Low"]
FILTER_CATS = ["All"] + CATEGORIES   # "All" is prepended for the library filter bar
