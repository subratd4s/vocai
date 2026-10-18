"""Small inline Lucide SVGs and the application shell."""
from pathlib import Path
from base64 import b64encode
from functools import lru_cache

ICONS = {
    "home": '<path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1z"/>',
    "book": '<path d="M12 7v14m0-14C9 4 5 3 2 4v16c3-1 7 0 10 1 3-1 7-2 10-1V4c-3-1-7 0-10 3Z"/>',
    "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4m0-4h.01"/>',
    "help": '<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3m.08 4h.01"/>',
}

def icon(name: str) -> str:
    return f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICONS[name]}</svg>'

@lru_cache(maxsize=1)
def font_styles() -> str:
    rules = []
    for family, weights in (("IBM Plex Serif", (500, 600)), ("Inter", (400, 500, 600))):
        for weight in weights:
            data = (Path(__file__).parent / "fonts" / f"{family.replace(' ', '-')}-{weight}.ttf").read_bytes()
            encoded = b64encode(data).decode("ascii")
            rules.append(f"@font-face {{font-family:'{family}';font-weight:{weight};font-style:normal;font-display:swap;src:url(data:font/ttf;base64,{encoded}) format('truetype');}}")
    return "".join(rules)

def shell(configured: bool) -> str:
    links = ''.join(f'<a href="#{target}" class="{active}" aria-label="{label}" title="{label}">{icon(name)}</a>' for name, target, label, active in [
        ('home', 'reading', 'Home', 'active'), ('book', 'vocabulary', 'Vocabulary', ''), ('info', 'about', 'Information', '')])
    status = 'AI configured' if configured else 'API key required'
    return f'''<style>{font_styles()}{Path(__file__).with_name("styles.css").read_text(encoding="utf-8")}</style>
<nav class="rail" aria-label="Main navigation"><a class="monogram" href="#reading" aria-label="Vocabulary Builder home">v<span>&bull;</span></a><div class="rail-links">{links}</div><a class="rail-help" href="#about" aria-label="Help" title="Help">{icon('help')}</a></nav>
<header class="topbar"><a href="#reading">Vocabulary Builder</a><span class="ai-status {'configured' if configured else ''}"><i></i>{status}</span></header>
<div class="bottom-glow" aria-hidden="true"></div>'''
