"""Plantillas de post de Pórtico para Instagram (1080 x 1350, formato 4:5).

Tipos de post:
  obra        fotografía a sangre, sin texto (los créditos van en el texto del post)
  reel        portada de reel: fotografía + etiqueta discreta "REEL"
  ficha       ficha de obra tipográfica (obra, autor, lugar, año, créditos)
  manifiesto  frase de marca sobre color liso
  servicio    portada de carrusel de servicios

También genera la simulación de la cuadrícula del perfil.

Uso:  python3 marca/posts/generar_posts.py CARPETA_FOTOGRAMAS SALIDA
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).resolve().parents[2]
FUENTES = RAIZ / "marca" / "fuentes"
LOGOS = RAIZ / "marca" / "logo"

W, H = 1080, 1350          # post 4:5
M = 96                     # margen: queda dentro del recorte 3:4 de la cuadrícula

CARBON = (28, 27, 25)
HUESO = (242, 238, 231)
TRAVERTINO = (180, 154, 122)
GRIS = (110, 106, 100)
GRIS_CLARO = (169, 163, 154)


def F(nombre: str, tam: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FUENTES / nombre), tam)


SANS_EL = "Archivo-ExtraLight.ttf"
SANS_L = "Archivo-Light.ttf"
SANS = "Archivo-Regular.ttf"
MONO = "IBMPlexMono-Regular.ttf"
MONO_L = "IBMPlexMono-Light.ttf"


def espaciado(d: ImageDraw.ImageDraw, xy, texto, fuente, tracking, color, ancla="izq"):
    anchos = [d.textlength(c, font=fuente) for c in texto]
    total = sum(anchos) + tracking * (len(texto) - 1)
    x, y = xy
    if ancla == "der":
        x -= total
    for c, a in zip(texto, anchos):
        d.text((x, y), c, font=fuente, fill=color)
        x += a + tracking
    return total


# ------------------------------------------------------------- look Pórtico
def balance_hueso(a: np.ndarray) -> np.ndarray:
    """Calibra los blancos de la foto al Hueso de la paleta (#F2EEE7).

    Toma el 15 % de píxeles más claros y poco saturados (muros, techos) y ajusta
    cada canal para que su tono coincida con el Hueso. Evita dominantes rosas,
    verdes o azules que no son de la marca. No toca la luminosidad general.
    """
    lum = a.mean(axis=2)
    sat = a.max(axis=2) - a.min(axis=2)
    mask = (lum > np.percentile(lum, 85)) & (sat < np.percentile(sat, 60)) & (lum < 0.98)
    if mask.sum() < 500:
        return a
    ref = a[mask].mean(axis=0)
    objetivo = np.array(HUESO, dtype=np.float32) / 255.0
    ganancia = (objetivo / objetivo.mean()) / (ref / ref.mean())
    ganancia = np.clip(ganancia, 0.85, 1.15)  # corrección moderada
    return np.clip(a * ganancia, 0, 1)


# Pórtico usa el color original de cada foto. Cambiar a True solo si se quiere
# volver a aplicar el filtro (blancos en Hueso, negros mate, grano).
APLICAR_LOOK = False


def graduar(img: Image.Image, grano=5.0, semilla=7) -> Image.Image:
    """Devuelve la imagen con su color original (o con el look si APLICAR_LOOK)."""
    if not APLICAR_LOOK:
        return img.convert("RGB")
    a = np.asarray(img.convert("RGB")).astype(np.float32) / 255.0
    a = balance_hueso(a)
    # curva suave: negros mate, altas luces contenidas
    a = 0.055 + a * 0.915
    a = a + 0.04 * np.sin(np.pi * a) * (a - 0.5)  # leve S
    # saturación 0.86
    lum = (a * np.array([0.299, 0.587, 0.114])).sum(axis=2, keepdims=True)
    a = lum + (a - lum) * 0.86
    # grano de película sobre la luminancia
    rng = np.random.default_rng(semilla)
    ruido = rng.normal(0, grano / 255.0, a.shape[:2])[..., None]
    a = np.clip(a + ruido, 0, 1)
    return Image.fromarray((a * 255).astype(np.uint8))


def recorte_45(img: Image.Image, centro_y=0.5) -> Image.Image:
    w, h = img.size
    objetivo = w * H / W
    if objetivo <= h:
        y0 = int((h - objetivo) * centro_y)
        img = img.crop((0, y0, w, y0 + int(objetivo)))
    else:
        nuevo_w = h * W / H
        x0 = int((w - nuevo_w) / 2)
        img = img.crop((x0, 0, x0 + int(nuevo_w), h))
    return img.resize((W, H), Image.LANCZOS)


def isotipo(alto: int, color: str) -> Image.Image:
    archivo = LOGOS / f"portico_isotipo_{color}.png"
    im = Image.open(archivo).convert("RGBA")
    im = im.crop(im.getbbox())
    return im.resize((int(im.width * alto / im.height), alto), Image.LANCZOS)


# ------------------------------------------------------------------ posts
def post_obra(foto: Path, centro_y=0.5) -> Image.Image:
    return graduar(recorte_45(Image.open(foto), centro_y))


def post_reel(foto: Path, centro_y=0.5) -> Image.Image:
    im = post_obra(foto, centro_y)
    d = ImageDraw.Draw(im)
    y = H - M - 22
    d.polygon([(M, y + 3), (M, y + 23), (M + 17, y + 13)], fill=(255, 255, 255))
    espaciado(d, (M + 34, y), "REEL", F(MONO, 22), 5, (255, 255, 255))
    return im


def post_ficha(obra: str, autor: str, datos: list[str], numero: str,
               fondo=CARBON) -> Image.Image:
    claro = fondo != CARBON
    tinta = CARBON if claro else HUESO
    sec = GRIS if claro else GRIS_CLARO
    im = Image.new("RGB", (W, H), fondo)
    d = ImageDraw.Draw(im)
    espaciado(d, (M, M + 10), f"OBRA {numero}", F(MONO, 22), 5, TRAVERTINO if not claro else CARBON)
    y = 470
    d.text((M - 6, y), obra, font=F(SANS_EL, 132), fill=tinta)
    y += 168
    d.text((M - 2, y), autor, font=F(SANS_L, 44), fill=tinta)
    y += 110
    d.line([(M, y), (W - M, y)], fill=tinta, width=2)
    y += 36
    for linea in datos:
        espaciado(d, (M, y), linea.upper(), F(MONO_L, 24), 3, sec)
        y += 44
    iso = isotipo(46, "carbon" if claro else "hueso")
    im.paste(iso, (M, H - M - iso.height), iso)
    espaciado(d, (W - M, H - M - 30), "@PORTICO.FA", F(MONO_L, 22), 4, sec, ancla="der")
    return im


def post_manifiesto(lineas: list[str], etiqueta: str, fondo=HUESO) -> Image.Image:
    claro = fondo != CARBON
    tinta = CARBON if claro else HUESO
    im = Image.new("RGB", (W, H), fondo)
    d = ImageDraw.Draw(im)
    espaciado(d, (M, M + 10), etiqueta.upper(), F(MONO, 22), 5, CARBON if claro else TRAVERTINO)
    f = F(SANS_EL, 84)
    alto = 100
    y = (H - alto * len(lineas)) / 2
    for l in lineas:
        d.text((M - 4, y), l, font=f, fill=tinta)
        y += alto
    iso = isotipo(46, "carbon" if claro else "hueso")
    im.paste(iso, (M, H - M - iso.height), iso)
    return im


def post_servicio(foto: Path, titulo: list[str], etiqueta: str, centro_y=0.5) -> Image.Image:
    """Portada de carrusel: foto arriba, bloque travertino abajo."""
    im = Image.new("RGB", (W, H), TRAVERTINO)
    f = post_obra(foto, centro_y).crop((0, 0, W, 760))
    im.paste(f, (0, 0))
    d = ImageDraw.Draw(im)
    espaciado(d, (M, 820), etiqueta.upper(), F(MONO, 22), 5, CARBON)
    y = 880
    for l in titulo:
        d.text((M - 4, y), l, font=F(SANS_EL, 76), fill=CARBON)
        y += 90
    espaciado(d, (W - M, H - M - 28), "DESLIZA  →", F(MONO, 22), 4, CARBON, ancla="der")
    return im


# -------------------------------------------------------- simulación perfil
def simular_perfil(posts: list[Image.Image], foto_perfil: Path, destino: Path,
                   usuario="portico.fa", nombre="Pórtico · Fotografía arquitectónica",
                   bio=("Fotografía y video de arquitectura y obra",
                        "Ciudad de Guatemala", "Proyectos · WhatsApp 5413 1753")):
    """Pantalla de perfil de 1170 px de ancho con la cuadrícula 3:4 de Instagram."""
    AN = 1170
    celda_w = (AN - 2 * 4) // 3
    celda_h = int(celda_w * 4 / 3)
    filas = (len(posts) + 2) // 3
    cab = 610
    lienzo = Image.new("RGB", (AN, cab + filas * (celda_h + 4)), (255, 255, 255))
    d = ImageDraw.Draw(lienzo)
    fi = ImageFont.truetype("/usr/share/fonts/opentype/inter/Inter-Medium.otf", 40)
    fr = ImageFont.truetype("/usr/share/fonts/opentype/inter/Inter-Regular.otf", 34)
    fb = ImageFont.truetype("/usr/share/fonts/opentype/inter/Inter-Bold.otf", 40)
    d.text((48, 40), usuario, font=fb, fill=(0, 0, 0))
    # foto de perfil circular
    pf = Image.open(foto_perfil).convert("RGB").resize((230, 230), Image.LANCZOS)
    mask = Image.new("L", (230, 230), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, 229, 229), fill=255)
    lienzo.paste(pf, (48, 120), mask)
    for i, (n, t) in enumerate([(str(len(posts)), "publicaciones"), ("—", "seguidores"), ("—", "seguidos")]):
        x = 380 + i * 260
        d.text((x, 175), n, font=fb, fill=(0, 0, 0))
        d.text((x, 228), t, font=fr, fill=(0, 0, 0))
    y = 380
    d.text((48, y), nombre, font=fi, fill=(0, 0, 0))
    y += 52
    for l in bio:
        d.text((48, y), l, font=fr, fill=(0, 0, 0))
        y += 44
    y0 = cab
    for i, p in enumerate(posts):
        fila, col = divmod(i, 3)
        # Instagram muestra el centro 3:4 del post 4:5
        rec_w = int(H * 3 / 4)
        x0 = (W - rec_w) // 2
        c = p.crop((x0, 0, x0 + rec_w, H)).resize((celda_w, celda_h), Image.LANCZOS)
        lienzo.paste(c, (col * (celda_w + 4), y0 + fila * (celda_h + 4)))
    lienzo.save(destino, quality=92)


# ----------------------------------------------------------------- ejemplo
def main(carpeta: Path, salida: Path):
    salida.mkdir(parents=True, exist_ok=True)
    fr = lambda t: carpeta / f"f_{t}.png"
    datos_fragmento = ["Instalación — Interiorismo", "Ciudad de Guatemala", "2026", "Video — Pórtico"]

    posts = {
        # fila 1 (lo más reciente)
        "01_obra": post_obra(fr("5"), 0.45),
        "02_ficha": post_ficha("Fragmento", "Fragmento Arquitectura", datos_fragmento, "001"),
        "03_obra": post_obra(fr("19"), 0.5),
        # fila 2
        "04_reel": post_reel(fr("16"), 0.5),
        "05_obra": post_obra(fr("1.5"), 0.35),
        "06_obra": post_obra(fr("10.5"), 0.4),
        # fila 3
        "07_obra": post_obra(fr("23"), 0.45),
        "08_manifiesto": post_manifiesto(
            ["La arquitectura", "ya fue pensada.", "Nosotros la", "documentamos."], "Pórtico — 01"),
        "09_obra": post_obra(fr("13"), 0.5),
    }
    extras = {
        "x_servicio": post_servicio(fr("10.5"), ["Fotografía y reels", "de arquitectura", "y obra"],
                                    "Servicios 2027", 0.35),
        "x_ficha_clara": post_ficha("Fragmento", "Fragmento Arquitectura", datos_fragmento, "001",
                                    fondo=HUESO),
        "x_manifiesto_carbon": post_manifiesto(
            ["Luz, material", "y proporción.", "Nada más."], "Pórtico — 02", fondo=CARBON),
    }
    for nombre, im in {**posts, **extras}.items():
        im.save(salida / f"post_{nombre}.jpg", quality=93)
    simular_perfil(list(posts.values()), LOGOS / "portico_perfil_redes.png",
                   salida / "simulacion_perfil.jpg")
    print("Listo:", salida)


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
