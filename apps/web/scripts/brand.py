#!/usr/bin/env python3
"""Genera los SVG de la marca Cáterin (T14, ADR-008) en `public/brand/` y el favicon `public/icon.svg`.

El logotipo usa IBM Plex Serif 500 (OFL; T16, ADR-010) convertida a trazos, para que el SVG se vea igual sin la fuente instalada.
Necesita fontTools (no es dependencia de la app; solo se usa al rediseñar la marca):

    pip install --target /tmp/pylib "fonttools==4.60.1" "brotli==1.1.0"
    PYTHONPATH=/tmp/pylib python3 scripts/brand.py
    npm run icons   # PNG de la PWA y del PDF desde estos SVG

Colores: laurel (semilla del tema, `scripts/theme.mjs`), la superficie clara del tema y el vapor cobre claro.
"""

from __future__ import annotations

from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

WEB = Path(__file__).resolve().parent.parent
FONT = WEB / "node_modules/@fontsource/ibm-plex-serif/files/ibm-plex-serif-latin-500-normal.woff2"
OUT = WEB / "public/brand"

LAUREL = "#1f4d3f"  # semilla (token brand)
CREAM = "#faf9f7"  # surface del tema (on-brand): casi blanco, sin crema
STEAM = "#ffdbcd"  # tertiary-container (brand-steam): vapor cobre, "comida caliente"
WORD = "Cáterin"
TRACKING = -14  # unidades de la fuente (1000 por em): la serif grande se ve mejor un poco más junta
RADIUS = 96  # esquina del cuadrado del isotipo (de 512): casi recta, como el resto de la interfaz (T16)

# --------------------------------------------------------------------------- isotipo (caja de 512)

# Cloche (cúpula de servir) con vapor: "comida caliente, lista para servir". Centrada en la caja.
GLYPH = """
  <g transform="translate(0 20)">
    <path d="M216 164c-14-12 14-24 0-36s14-24 0-36M296 164c-14-12 14-24 0-36s14-24 0-36" fill="none" stroke="{steam}"
      stroke-width="18" stroke-linecap="round"/>
    <circle cx="256" cy="190" r="20" fill="{fg}"/>
    <path d="M126 336a130 130 0 0 1 260 0z" fill="{fg}"/>
    <rect x="96" y="350" width="320" height="30" rx="15" fill="{fg}"/>
    <path d="M182 304a92 92 0 0 1 52-62" fill="none" stroke="{shine}" stroke-width="16" stroke-linecap="round"/>
  </g>"""


def glyph(fg: str = CREAM, steam: str = STEAM, shine: str = LAUREL) -> str:
    return GLYPH.format(fg=fg, steam=steam, shine=shine)


def isotipo() -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">'
        f'<title>Cáterin</title><rect width="512" height="512" rx="{RADIUS}" fill="{LAUREL}"/>{glyph()}</svg>\n'
    )


def maskable() -> str:
    """Fondo completo y el dibujo dentro de la zona segura (círculo del 80 %): Android recorta la forma."""
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><title>Cáterin</title>'
        f'<rect width="512" height="512" fill="{LAUREL}"/>'
        f'<g transform="translate(256 256) scale(0.72) translate(-256 -256)">{glyph()}</g></svg>\n'
    )


def mono(ink: str = "#000000") -> str:
    """Una sola tinta: el cuadrado con el dibujo calado. Sirve para el PDF en blanco y negro y fondos de color."""
    cut = glyph(fg="#000", steam="#000", shine="#fff")
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><title>Cáterin</title>'
        f'<mask id="m"><rect width="512" height="512" fill="#fff"/>{cut}</mask>'
        f'<rect width="512" height="512" rx="{RADIUS}" fill="{ink}" mask="url(#m)"/></svg>\n'
    )


# --------------------------------------------------------------------------- logotipo (palabra en trazos)


def wordmark() -> tuple[str, float, float, float]:
    """Devuelve (path d, ancho, alto de mayúscula, descendente) en unidades de la fuente, con la línea base en y=0."""
    font = TTFont(FONT)
    gs = font.getGlyphSet()
    cmap = font.getBestCmap()
    pen = SVGPathPen(gs)
    x = 0.0
    for ch in WORD:
        name = cmap[ord(ch)]
        # La fuente dibuja con y hacia arriba; el SVG, hacia abajo.
        gs[name].draw(TransformPen(pen, (1, 0, 0, -1, x, 0)))
        x += gs[name].width + TRACKING
    cap = float(font["OS/2"].sCapHeight or 700)
    return pen.getCommands(), x - TRACKING, cap, float(-font["hhea"].descent)


def horizontal(word: tuple[str, float, float, float], color: str = LAUREL, iso: bool = True) -> str:
    d, width, cap, _ = word
    # El isotipo mide 512; la palabra se escala para que su mayúscula mida ~46 % del isotipo.
    scale = 512 * 0.46 / cap
    gap = 72
    w_word = width * scale
    total = 512 + gap + w_word
    baseline = 256 + cap * scale / 2
    iso_svg = f'<rect width="512" height="512" rx="{RADIUS}" fill="{LAUREL}"/>{glyph()}' if iso else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total:.0f} 512"><title>Cáterin</title>{iso_svg}'
        f'<path transform="translate({512 + gap} {baseline:.1f}) scale({scale:.4f})" fill="{color}" d="{d}"/></svg>\n'
    )


def stacked(word: tuple[str, float, float, float]) -> str:
    d, width, cap, desc = word
    scale = 512 * 0.40 / cap
    w_word = width * scale
    total_w = max(512, w_word)
    gap = 64
    baseline = 512 + gap + cap * scale
    height = baseline + desc * scale * 0.4
    ix = (total_w - 512) / 2
    wx = (total_w - w_word) / 2
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total_w:.0f} {height:.0f}"><title>Cáterin</title>'
        f'<g transform="translate({ix:.1f} 0)"><rect width="512" height="512" rx="{RADIUS}" fill="{LAUREL}"/>{glyph()}</g>'
        f'<path transform="translate({wx:.1f} {baseline:.1f}) scale({scale:.4f})" fill="{LAUREL}" d="{d}"/></svg>\n'
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    word = wordmark()
    files = {
        OUT / "isotipo.svg": isotipo(),
        OUT / "isotipo-maskable.svg": maskable(),
        OUT / "isotipo-mono.svg": mono(),
        OUT / "logotipo-horizontal.svg": horizontal(word),
        OUT / "logotipo-horizontal-blanco.svg": horizontal(word, color="#ffffff"),
        OUT / "logotipo-apilado.svg": stacked(word),
        OUT / "palabra.svg": horizontal(word, iso=False),
        WEB / "public/icon.svg": isotipo(),
    }
    for path, svg in files.items():
        path.write_text(svg, encoding="utf-8")
        print(f"{path.relative_to(WEB)}  {len(svg) / 1024:.1f} KB")


if __name__ == "__main__":
    main()
