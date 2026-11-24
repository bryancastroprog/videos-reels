"""Genera los archivos de marca de Pórtico (SVG vectorial + PNG).

Uso:  python3 marca/generar_marca.py

Todo el texto se convierte en trazos (curvas), así los SVG se ven igual
en cualquier computadora aunque no tenga las tipografías instaladas.
"""
from pathlib import Path

import cairosvg
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

RAIZ = Path(__file__).resolve().parent
FUENTES = RAIZ / "fuentes"
SALIDA = RAIZ / "logo"

# ---------------------------------------------------------------- paleta
CARBON = "#1C1B19"   # texto y logo principal
HUESO = "#F2EEE7"    # fondos claros / logo sobre oscuro
TRAVERTINO = "#B49A7A"  # acento (piedra)
GRIS = "#6E6A64"     # textos secundarios

SERIF = FUENTES / "CormorantGaramond-Medium.ttf"
SANS = FUENTES / "Inter-Regular.otf"


# ------------------------------------------------------- texto a curvas
def texto_a_path(texto, fuente, tam, x, y, tracking=0.0, ancla="start"):
    """Devuelve (d, ancho) con el texto convertido a trazo SVG.

    tracking: espaciado extra entre letras en fracción del tamaño (0.3 = 30%).
    ancla: start | middle | end
    """
    f = TTFont(fuente)
    gs = f.getGlyphSet()
    cmap = f.getBestCmap()
    upm = f["head"].unitsPerEm
    esc = tam / upm
    extra = tracking * tam

    glifos = [cmap.get(ord(c)) for c in texto]
    ancho = 0.0
    for i, g in enumerate(glifos):
        ancho += gs[g].width * esc if g else tam * 0.3
        if i < len(glifos) - 1:
            ancho += extra

    if ancla == "middle":
        x -= ancho / 2
    elif ancla == "end":
        x -= ancho

    pen = SVGPathPen(gs)
    cur = x
    for g in glifos:
        if g:
            tp = TransformPen(pen, (esc, 0, 0, -esc, cur, y))
            gs[g].draw(tp)
            cur += gs[g].width * esc + extra
        else:
            cur += tam * 0.3 + extra
    return pen.getCommands(), ancho


def alto_mayusculas(fuente, tam):
    f = TTFont(fuente)
    gs = f.getGlyphSet()
    bp = BoundsPen(gs)
    gs[f.getBestCmap()[ord("H")]].draw(bp)
    return bp.bounds[3] * tam / f["head"].unitsPerEm


# ------------------------------------------------------------- isotipo
def isotipo(x, y, ancho, color):
    """Pórtico: dintel + dos columnas. El vano entre columnas es 4:5,
    la proporción de la foto vertical de Instagram.

    Módulo base: ancho = 100 u.
      dintel      0..100  x 0..12
      separación  6 u (las piezas no se tocan: lectura constructiva)
      columnas    10..20 y 80..90, alto 75  -> vano 60 x 75 = 4:5
    """
    u = ancho / 100
    r = lambda a, b, c, d: (
        f'<rect x="{x + a * u:.2f}" y="{y + b * u:.2f}" '
        f'width="{c * u:.2f}" height="{d * u:.2f}" fill="{color}"/>'
    )
    partes = [r(0, 0, 100, 12), r(10, 18, 10, 75), r(80, 18, 10, 75)]
    return "\n  ".join(partes), 93 * u  # (svg, alto total)


# -------------------------------------------------------------- piezas
def svg(ancho, alto, cuerpo, fondo=None):
    bg = f'<rect width="100%" height="100%" fill="{fondo}"/>' if fondo else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{ancho}" height="{alto}" '
        f'viewBox="0 0 {ancho} {alto}">\n  {bg}\n  {cuerpo}\n</svg>\n'
    )


def pieza_isotipo(color, fondo=None, lado=1000):
    m = lado * 0.18
    w = lado - 2 * m
    g, h = isotipo(m, (lado - w * 0.93) / 2, w, color)
    return svg(lado, lado, g, fondo)


def pieza_perfil(color, fondo, lado=1080):
    """Foto de perfil: isotipo al 50 % para que respire dentro del recorte circular."""
    w = lado * 0.50
    h = w * 0.93
    g, _ = isotipo((lado - w) / 2, (lado - h) / 2, w, color)
    return svg(lado, lado, g, fondo)


def pieza_vertical(color, sub_color, fondo=None):
    W, H = 1200, 1200
    iso_w = 300
    g, iso_h = isotipo((W - iso_w) / 2, 250, iso_w, color)
    y_txt = 250 + iso_h + 110 + alto_mayusculas(SERIF, 130)
    d1, _ = texto_a_path("PÓRTICO", SERIF, 130, W / 2, y_txt, tracking=0.22, ancla="middle")
    d2, _ = texto_a_path("FOTOGRAFÍA ARQUITECTÓNICA", SANS, 26, W / 2, y_txt + 80,
                         tracking=0.42, ancla="middle")
    cuerpo = (f'{g}\n  <path d="{d1}" fill="{color}"/>\n'
              f'  <path d="{d2}" fill="{sub_color}"/>')
    return svg(W, H, cuerpo, fondo)


def pieza_horizontal(color, sub_color, fondo=None):
    H = 400
    iso_w = 170
    m = 60
    g, iso_h = isotipo(m, (H - iso_w * 0.93) / 2, iso_w, color)
    x_txt = m + iso_w + 70
    cap = alto_mayusculas(SERIF, 120)
    y_txt = H / 2 + cap / 2 - 18
    d1, w1 = texto_a_path("PÓRTICO", SERIF, 120, x_txt, y_txt, tracking=0.2)
    d2, w2 = texto_a_path("FOTOGRAFÍA ARQUITECTÓNICA", SANS, 22, x_txt + 4, y_txt + 62,
                          tracking=0.4)
    W = x_txt + max(w1, w2) + m
    cuerpo = (f'{g}\n  <path d="{d1}" fill="{color}"/>\n'
              f'  <path d="{d2}" fill="{sub_color}"/>')
    return svg(round(W), H, cuerpo, fondo)


def pieza_marca_agua():
    """Para esquina de videos: isotipo + PÓRTICO en una línea, blanco."""
    H = 120
    g, _ = isotipo(10, (H - 60 * 0.93) / 2, 60, "#FFFFFF")
    cap = alto_mayusculas(SERIF, 48)
    d, w = texto_a_path("PÓRTICO", SERIF, 48, 100, H / 2 + cap / 2, tracking=0.22)
    return svg(round(100 + w + 10), H, f'{g}\n  <path d="{d}" fill="#FFFFFF"/>')


def tablero_marca():
    """Lámina de presentación con logo, paleta y tipografías."""
    W, H = 2400, 1500
    p = []
    p.append(f'<rect width="{W}" height="{H}" fill="{HUESO}"/>')
    p.append(f'<rect x="{W/2}" width="{W/2}" height="{H*0.62}" fill="{CARBON}"/>')
    # logo claro y oscuro
    g, ih = isotipo(W / 4 - 110, 230, 220, CARBON)
    p.append(g)
    cap = alto_mayusculas(SERIF, 110)
    yt = 230 + ih + 90 + cap
    d, _ = texto_a_path("PÓRTICO", SERIF, 110, W / 4, yt, 0.22, "middle"); p.append(f'<path d="{d}" fill="{CARBON}"/>')
    d, _ = texto_a_path("FOTOGRAFÍA ARQUITECTÓNICA", SANS, 22, W / 4, yt + 66, 0.42, "middle"); p.append(f'<path d="{d}" fill="{GRIS}"/>')
    g, _ = isotipo(3 * W / 4 - 110, 230, 220, HUESO); p.append(g)
    d, _ = texto_a_path("PÓRTICO", SERIF, 110, 3 * W / 4, yt, 0.22, "middle"); p.append(f'<path d="{d}" fill="{HUESO}"/>')
    d, _ = texto_a_path("FOTOGRAFÍA ARQUITECTÓNICA", SANS, 22, 3 * W / 4, yt + 66, 0.42, "middle"); p.append(f'<path d="{d}" fill="{TRAVERTINO}"/>')

    # paleta
    y0 = H * 0.62 + 110
    d, _ = texto_a_path("PALETA", SANS, 20, 120, y0, 0.4); p.append(f'<path d="{d}" fill="{GRIS}"/>')
    for i, (nom, hexa) in enumerate([("Carbón", CARBON), ("Hueso", HUESO), ("Travertino", TRAVERTINO), ("Gris piedra", GRIS)]):
        x = 120 + i * 250
        borde = f' stroke="{GRIS}" stroke-width="2"' if hexa == HUESO else ""
        p.append(f'<rect x="{x}" y="{y0 + 40}" width="200" height="200" fill="{hexa}"{borde}/>')
        d, _ = texto_a_path(nom, SANS, 24, x, y0 + 290, 0.02); p.append(f'<path d="{d}" fill="{CARBON}"/>')
        d, _ = texto_a_path(hexa, SANS, 20, x, y0 + 325, 0.08); p.append(f'<path d="{d}" fill="{GRIS}"/>')

    # tipografías
    x0 = W / 2 + 120
    d, _ = texto_a_path("TIPOGRAFÍA", SANS, 20, x0, y0, 0.4); p.append(f'<path d="{d}" fill="{GRIS}"/>')
    d, _ = texto_a_path("El arte de habitar la luz", FUENTES / "CormorantGaramond-Regular.ttf", 76, x0, y0 + 115); p.append(f'<path d="{d}" fill="{CARBON}"/>')
    d, _ = texto_a_path("Cormorant Garamond · títulos", SANS, 22, x0, y0 + 160, 0.02); p.append(f'<path d="{d}" fill="{GRIS}"/>')
    d, _ = texto_a_path("INTERIORISMO · ZONA 14 · 240 M²", SANS, 30, x0, y0 + 250, 0.3); p.append(f'<path d="{d}" fill="{CARBON}"/>')
    d, _ = texto_a_path("Inter · datos, etiquetas y subtítulos", SANS, 22, x0, y0 + 295, 0.02); p.append(f'<path d="{d}" fill="{GRIS}"/>')
    return svg(W, H, "\n  ".join(p))


# --------------------------------------------------------------- salida
def guardar(nombre, contenido, ancho_png):
    SALIDA.mkdir(exist_ok=True)
    (SALIDA / f"{nombre}.svg").write_text(contenido, encoding="utf-8")
    cairosvg.svg2png(bytestring=contenido.encode(), write_to=str(SALIDA / f"{nombre}.png"),
                     output_width=ancho_png)


def main():
    guardar("portico_isotipo_carbon", pieza_isotipo(CARBON), 1000)
    guardar("portico_isotipo_hueso", pieza_isotipo(HUESO), 1000)
    guardar("portico_perfil_redes", pieza_perfil(HUESO, CARBON), 1080)
    guardar("portico_perfil_redes_claro", pieza_perfil(CARBON, HUESO), 1080)
    guardar("portico_perfil_redes_travertino", pieza_perfil(CARBON, TRAVERTINO), 1080)
    guardar("portico_logo_vertical_carbon", pieza_vertical(CARBON, GRIS), 2400)
    guardar("portico_logo_vertical_hueso", pieza_vertical(HUESO, TRAVERTINO), 2400)
    guardar("portico_logo_horizontal_carbon", pieza_horizontal(CARBON, GRIS), 2400)
    guardar("portico_logo_horizontal_hueso", pieza_horizontal(HUESO, TRAVERTINO), 2400)
    guardar("portico_marca_agua_blanca", pieza_marca_agua(), 800)
    guardar("portico_tablero_marca", tablero_marca(), 2400)
    print("Listo:", SALIDA)


if __name__ == "__main__":
    main()
