"""Presentation assets for the Vocabulary Builder Streamlit interface."""
from base64 import b64encode
from functools import lru_cache
from pathlib import Path

ICONS = {
    "home": '<path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1z"/>',
    "book": '<path d="M12 7v14m0-14C9 4 5 3 2 4v16c3-1 7 0 10 1 3-1 7-2 10-1V4c-3-1-7 0-10 3Z"/>',
    "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4m0-4h.01"/>',
    "help": '<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3m.08 4h.01"/>',
    "spark": '<path d="m12 3 1.9 5.8L20 11l-6.1 2.2L12 19l-1.9-5.8L4 11l6.1-2.2L12 3Z"/><path d="m19 14 1 2.5 2 1-2 1L19 21l-1-2.5-2-1 2-1 1-2.5Z"/>',
    "chat": '<path d="M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.4 8.4 0 0 1 3.8-.9h.5a8.5 8.5 0 0 1 8 8v.5Z"/>',
    "cap": '<path d="m2 10 10-5 10 5-10 5-10-5Z"/><path d="M6 12v5c3.5 3 8.5 3 12 0v-5m4-2v6"/>',
    "arrow": '<path d="M12 19V5m-7 7 7-7 7 7"/>',
    "file": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M8 13h8m-8 4h8"/>',
}


def icon(name: str, size: int = 18) -> str:
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
            f'stroke="currentColor" stroke-width="1.7" stroke-linecap="round" '
            f'stroke-linejoin="round" aria-hidden="true">{ICONS[name]}</svg>')


@lru_cache(maxsize=1)
def font_styles() -> str:
    rules = []
    for family, weights in (("IBM Plex Serif", (500, 600)), ("Inter", (400, 500, 600))):
        for weight in weights:
            path = Path(__file__).parent / "fonts" / f"{family.replace(' ', '-')}-{weight}.ttf"
            encoded = b64encode(path.read_bytes()).decode("ascii")
            rules.append(f"@font-face {{font-family:'{family}';font-weight:{weight};font-style:normal;"
                         f"font-display:swap;src:url(data:font/ttf;base64,{encoded}) format('truetype');}}")
    return "".join(rules)


@lru_cache(maxsize=1)
def orb_markup() -> str:
    """Load the decorative vector orb used above the landing heading."""
    return Path(__file__).with_name("orb.svg").read_text(encoding="utf-8")


def shell(configured: bool, expanded: bool = False) -> str:
    """Build the minimal frosted sidebar and shared styles."""
    del configured  # The reference design does not show API configuration status.
    del expanded  # Kept for compatibility with earlier callers.
    nav_items = (("home", "Home", "home"), ("book", "Vocabulary", "vocabulary"))
    side_links = "".join(
        f'<a href="#{target}" class="side-link" title="{label}" aria-label="{label}">'
        f'{icon(name)}<span>{label}</span></a>' for name, label, target in nav_items
    )
    return f'''<style>{font_styles()}{Path(__file__).with_name("styles.css").read_text(encoding="utf-8")}</style>
<nav class="rail" aria-label="Primary navigation">
  <a class="brand-name" href="#home" aria-label="Vocai home">Vocai</a>
  <div class="rail-links">{side_links}</div>
</nav>
<div class="bottom-bars" aria-hidden="true"></div>'''
