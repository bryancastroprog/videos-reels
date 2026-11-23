#!/usr/bin/env python3
"""Motor de edición de Pórtico.

Convierte una carpeta de clips + un archivo proyecto.yaml en reels terminados.

Comandos:
  python3 motor/portico.py nuevo   proyectos/NOMBRE      crea la carpeta del proyecto
  python3 motor/portico.py revisar proyectos/NOMBRE      hoja de contacto de cada toma
  python3 motor/portico.py armar   proyectos/NOMBRE      exporta los videos finales
  python3 motor/portico.py armar   proyectos/NOMBRE --borrador   versión rápida en baja

Requisitos: ffmpeg, Python 3.10+, pyyaml, pillow.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).resolve().parent.parent
FUENTES = RAIZ / "marca" / "fuentes"
LOGOS = RAIZ / "marca" / "logo"

SERIF = FUENTES / "CormorantGaramond-Regular.ttf"
SERIF_ITALICA = FUENTES / "CormorantGaramond-Italic.ttf"
SANS = FUENTES / "Inter-Regular.otf"
SANS_MEDIA = FUENTES / "Inter-Medium.otf"

FORMATOS = {
    "vertical": (1080, 1920),    # Reels, TikTok, Stories
    "retrato": (1080, 1350),     # feed de Instagram 4:5
    "horizontal": (1920, 1080),  # YouTube, portales, web
}
FPS = 30
EXT_VIDEO = {".mp4", ".mov", ".m4v", ".mkv", ".avi"}

PRESETS_COLOR = {
    # brillo, contraste, saturación, gamma
    "natural": (0.0, 1.03, 1.03, 1.0),
    "calido": (0.01, 1.04, 1.06, 0.98),
    "frio": (0.0, 1.05, 0.97, 1.0),
    "luminoso": (0.03, 1.02, 1.04, 0.94),
    "ninguno": (0.0, 1.0, 1.0, 1.0),
}
PRESETS_CALIDO = "colorbalance=rm=0.03:gm=0.0:bm=-0.03:rh=0.02:bh=-0.02"
PRESETS_FRIO = "colorbalance=rm=-0.02:bm=0.03:rh=-0.01:bh=0.02"

PLANTILLA_YAML = """\
# ============================================================
#  PÓRTICO · proyecto de video
#  1. Copia los clips a la carpeta clips/  (nombrados en orden:
#     01_fachada.mp4, 02_acceso.mp4, 03_sala.mp4 ...)
#  2. Ajusta este archivo (todo es opcional salvo lo marcado)
#  3. python3 motor/portico.py armar proyectos/{nombre}
# ============================================================

proyecto: "{nombre}"
cliente: ""

# Formatos a exportar: vertical (9:16), retrato (4:5), horizontal (16:9)
formatos: [vertical]

# Duración total aproximada en segundos. Si las tomas no traen
# 'duracion', el motor reparte este tiempo entre todas.
duracion_objetivo: 27

# Color: natural | calido | frio | luminoso | ninguno
color: natural
# Ajuste fino opcional (se suma al preset):
# ajuste_color: {{brillo: 0.0, contraste: 1.0, saturacion: 1.0}}
# lut: marca/luts/portico.cube

# Estabilización: no | suave | fuerte
estabilizar: suave
# Quita el parpadeo de exposición automática del celular
antiparpadeo: true

# Transición entre tomas (segundos). 0 = corte seco
transicion: 0.5

# Cierre: negro (fundido a negro) | logo (logo Pórtico) | logo_cliente | ninguno
cierre: negro
# logo_cliente: logo_cliente.png   (dentro de la carpeta del proyecto)

# Marca de agua discreta de Pórtico en una esquina
marca_agua: false

# Audio: sin audio por defecto (el cliente pone la música en Instagram)
# musica: musica.mp3   (dentro de la carpeta del proyecto)

# Portada: toma y segundo de donde sale la imagen
portada:
  toma: 1
  segundo: 1.0
  categoria: "INTERIORISMO"
  titulo: "El arte de"
  titulo_italica: "habitar la luz"

# Textos para Instagram (se generan en un .md junto al video)
instagram:
  titulo: ""
  descripcion: ""
  hashtags: "#arquitectura #interiorismo #bienesraices #guatemala"

# ------------------------------------------------------------
# Tomas. Si borras esta lista, el motor usa todos los clips de
# clips/ en orden alfabético con valores automáticos.
#
#  archivo:   nombre del clip dentro de clips/
#  inicio:    segundo donde empieza (auto = centro del clip)
#  duracion:  segundos que dura la toma
#  encuadre:  0.0 = izquierda · 0.5 = centro · 1.0 = derecha
#             (sólo aplica cuando hay que recortar el clip)
#  encuadre_v: igual pero vertical (0 arriba, 1 abajo)
#  zoom:      1.0 = normal, 1.15 = 15 % más cerca
#  velocidad: 1.0 normal · 0.5 cámara lenta
#  texto:     {{titulo: "...", subtitulo: "..."}} sobre la toma
# ------------------------------------------------------------
tomas:
{tomas}
"""


# ============================================================ utilidades
def run(cmd: list[str], silencioso=True):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("\n".join(r.stderr.strip().splitlines()[-25:]), file=sys.stderr)
        raise SystemExit(f"ffmpeg falló: {' '.join(cmd[:6])} ...")
    return r


def ruta_proyecto(p: "Proyecto", valor) -> Path:
    """Rutas en proyecto.yaml: primero relativas a la carpeta del proyecto, luego al repo."""
    v = Path(str(valor))
    for c in (v, p.carpeta / v, RAIZ / v):
        if c.exists():
            return c.resolve()
    raise SystemExit(f"No encuentro el archivo {valor}")


def n_entradas(args: list[str]) -> int:
    return sum(1 for x in args if x == "-i")


def info(msg):
    print(f"  · {msg}", flush=True)


@dataclass
class InfoClip:
    ancho: int
    alto: int
    duracion: float
    hdr: bool
    fps: float


def analizar(ruta: Path) -> InfoClip:
    r = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-print_format", "json",
             "-show_streams", "-show_format", str(ruta)])
    d = json.loads(r.stdout)
    s = d["streams"][0]
    w, h = int(s["width"]), int(s["height"])
    rot = 0
    for sd in s.get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = int(float(sd["rotation"]))
    rot = int(s.get("tags", {}).get("rotate", rot))
    if abs(rot) % 180 == 90:
        w, h = h, w
    dur = float(s.get("duration") or d["format"]["duration"])
    hdr = s.get("color_transfer") in ("arib-std-b67", "smpte2084")
    num, den = (s.get("avg_frame_rate") or "30/1").split("/")
    fps = float(num) / float(den) if float(den) else 30.0
    return InfoClip(w, h, dur, hdr, fps)


# ============================================================ proyecto
@dataclass
class Toma:
    archivo: Path
    info: InfoClip
    inicio: float
    duracion: float
    encuadre: float = 0.5
    encuadre_v: float = 0.5
    zoom: float = 1.0
    velocidad: float = 1.0
    texto: dict | None = None


@dataclass
class Proyecto:
    carpeta: Path
    cfg: dict
    tomas: list[Toma] = field(default_factory=list)

    def get(self, clave, defecto=None):
        v = self.cfg.get(clave, defecto)
        return defecto if v is None else v


def clips_en(carpeta: Path) -> list[Path]:
    return sorted(p for p in (carpeta / "clips").iterdir()
                  if p.suffix.lower() in EXT_VIDEO and not p.name.startswith("."))


def cargar(carpeta: Path) -> Proyecto:
    archivo = carpeta / "proyecto.yaml"
    if not archivo.exists():
        raise SystemExit(f"No existe {archivo}. Usa: portico.py nuevo {carpeta}")
    cfg = yaml.safe_load(archivo.read_text(encoding="utf-8")) or {}
    p = Proyecto(carpeta, cfg)

    lista = cfg.get("tomas") or [{"archivo": c.name} for c in clips_en(carpeta)]
    if not lista:
        raise SystemExit("No hay clips en clips/ ni tomas en proyecto.yaml")

    infos = []
    for t in lista:
        ruta = carpeta / "clips" / t["archivo"]
        if not ruta.exists():
            raise SystemExit(f"No encuentro el clip {ruta}")
        infos.append((t, ruta, analizar(ruta)))

    # reparto de duración entre tomas sin duración fija
    trans = float(p.get("transicion", 0.5))
    objetivo = float(p.get("duracion_objetivo", 0) or 0)
    fijas = sum(float(t["duracion"]) for t, _, _ in infos if t.get("duracion"))
    libres = [x for x in infos if not x[0].get("duracion")]
    if libres:
        n = len(infos)
        total_bruto = (objetivo + trans * (n - 1)) if objetivo else 0
        por_toma = max(1.5, (total_bruto - fijas) / len(libres)) if objetivo else 3.0
    for t, ruta, inf in infos:
        vel = float(t.get("velocidad", 1.0))
        dur = float(t.get("duracion") or por_toma)
        fuente_necesaria = dur * vel
        if fuente_necesaria > inf.duracion - 0.05:
            dur = (inf.duracion - 0.05) / vel
            fuente_necesaria = dur * vel
        if t.get("inicio") is not None:
            ini = min(float(t["inicio"]), max(0.0, inf.duracion - fuente_necesaria))
        else:  # automático: centro del clip, evitando el arranque movido
            ini = max(0.0, (inf.duracion - fuente_necesaria) / 2)
        p.tomas.append(Toma(
            archivo=ruta, info=inf, inicio=round(ini, 3), duracion=round(dur, 3),
            encuadre=float(t.get("encuadre", 0.5)), encuadre_v=float(t.get("encuadre_v", 0.5)),
            zoom=float(t.get("zoom", 1.0)), velocidad=vel, texto=t.get("texto"),
        ))
    return p


# ============================================================ filtros
def filtro_hdr():
    return ("zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,"
            "tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p")


def filtro_color(p: Proyecto) -> str:
    preset = str(p.get("color", "natural"))
    b, c, s, g = PRESETS_COLOR.get(preset, PRESETS_COLOR["natural"])
    aj = p.get("ajuste_color", {}) or {}
    b += float(aj.get("brillo", 0))
    c *= float(aj.get("contraste", 1))
    s *= float(aj.get("saturacion", 1))
    partes = []
    if p.get("lut"):
        partes.append(f"lut3d='{esc_ruta(ruta_proyecto(p, p.get('lut')))}'")
    if (b, c, s, g) != (0.0, 1.0, 1.0, 1.0):
        partes.append(f"eq=brightness={b:.3f}:contrast={c:.3f}:saturation={s:.3f}:gamma={g:.3f}")
    if preset == "calido":
        partes.append(PRESETS_CALIDO)
    elif preset == "frio":
        partes.append(PRESETS_FRIO)
    return ",".join(partes)


def filtro_encuadre(t: Toma, W: int, H: int, extra_zoom: float) -> str:
    """Recorta al formato de salida respetando el punto de encuadre."""
    R = W / H
    z = t.zoom * extra_zoom
    ax, ay = t.encuadre, t.encuadre_v
    cw = f"if(gt(iw/ih\\,{R:.6f})\\,ih*{R:.6f}\\,iw)/{z:.4f}"
    ch = f"if(gt(iw/ih\\,{R:.6f})\\,ih\\,iw/{R:.6f})/{z:.4f}"
    return (f"crop=w='trunc({cw}/2)*2':h='trunc({ch}/2)*2':"
            f"x='(iw-ow)*{ax:.3f}':y='(ih-oh)*{ay:.3f}',"
            f"scale={W}:{H}:flags=lanczos,setsar=1")


def esc_ruta(p: Path) -> str:
    return p.as_posix().replace(":", "\\:").replace("'", "\\'")


def filtro_texto(texto: dict, W: int, H: int, dur: float, tmp: Path, idx: int) -> str:
    """Título serif + subtítulo sans espaciado, con fundido, en el tercio inferior."""
    filtros = []
    base = min(W, H)
    t_in, t_out = 0.35, max(0.6, dur - 0.45)
    alfa = (f"if(lt(t\\,{t_in})\\,0\\,if(lt(t\\,{t_in + 0.5})\\,(t-{t_in})/0.5\\,"
            f"if(lt(t\\,{t_out})\\,1\\,max(0\\,1-(t-{t_out})/0.4))))")
    y_base = H * (0.72 if H > W else 0.70)
    sombra = "shadowcolor=black@0.35:shadowx=0:shadowy=2"
    if texto.get("subtitulo"):
        f = tmp / f"sub_{idx}.txt"
        f.write_text(" ".join(str(texto["subtitulo"]).upper()), encoding="utf-8")
        filtros.append(
            f"drawtext=fontfile='{esc_ruta(SANS_MEDIA)}':textfile='{esc_ruta(f)}':"
            f"fontsize={int(base * 0.026)}:fontcolor=white:alpha='{alfa}':{sombra}:"
            f"x=(w-text_w)/2:y={int(y_base - base * 0.07)}")
    if texto.get("titulo"):
        f = tmp / f"tit_{idx}.txt"
        f.write_text(str(texto["titulo"]), encoding="utf-8")
        filtros.append(
            f"drawtext=fontfile='{esc_ruta(SERIF)}':textfile='{esc_ruta(f)}':"
            f"fontsize={int(base * 0.085)}:fontcolor=white:alpha='{alfa}':{sombra}:"
            f"x=(w-text_w)/2:y={int(y_base)}")
    return ",".join(filtros)


def cadena_toma(p: Proyecto, t: Toma, W: int, H: int, tmp: Path, idx: int) -> str:
    f = []
    if t.info.hdr:
        f.append(filtro_hdr())
    if t.velocidad != 1.0:
        f.append(f"setpts=PTS/{t.velocidad}")
    f.append(f"fps={FPS}")
    if p.get("antiparpadeo", True):
        f.append("deflicker=mode=pm:size=10")
    est = str(p.get("estabilizar", "suave"))
    extra_zoom = 1.0
    if est in ("suave", "fuerte"):
        r = 16 if est == "suave" else 48
        f.append(f"deshake=rx={r}:ry={r}:edge=mirror:blocksize=8:contrast=125")
        extra_zoom = 1.04 if est == "suave" else 1.08
    f.append(filtro_encuadre(t, W, H, extra_zoom))
    col = filtro_color(p)
    if col:
        f.append(col)
    if t.texto:
        tx = filtro_texto(t.texto, W, H, t.duracion, tmp, idx)
        if tx:
            f.append(tx)
    f.append("format=yuv420p,settb=AVTB")
    return ",".join(f)


# ============================================================ armado
def codificador(borrador: bool, intermedio=False):
    if intermedio and not borrador:  # casi sin pérdida: se vuelve a codificar al unir
        return ["-c:v", "libx264", "-preset", "fast", "-crf", "12", "-pix_fmt", "yuv420p"]
    if borrador:
        return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-pix_fmt", "yuv420p"]
    return ["-c:v", "libx264", "-preset", "slow", "-crf", "17", "-profile:v", "high",
            "-pix_fmt", "yuv420p"]


def render_toma(p, t, i, W, H, tmp, borrador):
    salida = tmp / f"toma_{i:02d}.mp4"
    vf = cadena_toma(p, t, W, H, tmp, i)
    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t.inicio}", "-t", f"{t.duracion * t.velocidad + 0.1}",
         "-i", str(t.archivo), "-an", "-vf", vf, "-t", f"{t.duracion}",
         *codificador(borrador, intermedio=True), str(salida)])
    return salida


def render_cierre_logo(logo: Path, W, H, dur, tmp, fondo="0x1C1B19"):
    salida = tmp / "cierre.mp4"
    im = Image.open(logo).convert("RGBA")
    im = im.crop(im.getbbox())
    recortado = tmp / "logo_cierre.png"
    im.save(recortado)
    logo = recortado
    ancho_logo = int(min(W, H) * 0.46)
    vf = (f"[1:v]scale={ancho_logo}:-1[l];[0:v][l]overlay=(W-w)/2:(H-h)/2,"
          f"fade=t=in:st=0.2:d=0.6:alpha=0,format=yuv420p,settb=AVTB")
    run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
         f"color=c={fondo}:s={W}x{H}:r={FPS}:d={dur}", "-loop", "1", "-t", f"{dur}",
         "-i", str(logo), "-filter_complex", vf, "-t", f"{dur}", "-r", f"{FPS}",
         *codificador(False), str(salida)])
    return salida


def unir(p: Proyecto, segmentos: list[Path], duraciones: list[float], W, H,
         salida: Path, borrador: bool, cierre: Path | None, dur_cierre: float):
    T = float(p.get("transicion", 0.5))
    entradas, partes = [], []
    for s in segmentos + ([cierre] if cierre else []):
        entradas += ["-i", str(s)]
    durs = duraciones + ([dur_cierre] if cierre else [])
    n = len(durs)

    if n == 1 or T <= 0:
        partes.append("".join(f"[{i}:v]" for i in range(n)) + f"concat=n={n}:v=1:a=0[v0]")
        total = sum(durs)
    else:
        prev, acumulado = "[0:v]", durs[0]
        for i in range(1, n):
            T_i = min(T, durs[i - 1] * 0.45, durs[i] * 0.45)
            off = acumulado - T_i
            etiqueta = f"[x{i}]"
            tipo = "fade"
            partes.append(f"{prev}[{i}:v]xfade=transition={tipo}:duration={T_i:.3f}:offset={off:.3f}{etiqueta}")
            prev = etiqueta
            acumulado = off + durs[i]
        partes.append(f"{prev}null[v0]")
        total = acumulado

    ult = "[v0]"
    tipo_cierre = str(p.get("cierre", "negro"))
    if tipo_cierre == "negro":
        partes.append(f"{ult}fade=t=out:st={total - 0.8:.3f}:d=0.8[v1]")
        ult = "[v1]"
    if p.get("marca_agua"):
        wm = LOGOS / "portico_marca_agua_blanca.png"
        entradas += ["-i", str(wm)]
        idx = n_entradas(entradas) - 1
        ancho_wm = int(W * 0.16)
        partes.append(f"[{idx}:v]scale={ancho_wm}:-1,format=rgba,colorchannelmixer=aa=0.7[wm]")
        hasta = total - (dur_cierre if cierre else 0) + 0.1
        partes.append(f"{ult}[wm]overlay=W-w-{int(W*0.05)}:H-h-{int(H*0.04)}:"
                      f"enable='lt(t\\,{hasta:.3f})'[v2]")
        ult = "[v2]"

    audio = []
    musica = p.get("musica")
    if musica:
        entradas += ["-i", str(ruta_proyecto(p, musica))]
        ai = n_entradas(entradas) - 1
        partes.append(f"[{ai}:a]atrim=0:{total:.3f},afade=t=in:d=0.5,"
                      f"afade=t=out:st={total - 1.5:.3f}:d=1.5[a0]")
        audio = ["-map", "[a0]", "-c:a", "aac", "-b:a", "192k"]
    else:
        # pista de audio muda: Instagram/TikTok la aceptan y el cliente agrega su música
        entradas += ["-f", "lavfi", "-t", f"{total:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
        audio = ["-map", f"{n_entradas(entradas) - 1}:a", "-c:a", "aac", "-b:a", "128k"]

    run(["ffmpeg", "-y", "-v", "error", *entradas, "-filter_complex", ";".join(partes),
         "-map", ult, *audio, "-r", f"{FPS}", *codificador(borrador),
         "-t", f"{total:.3f}", "-movflags", "+faststart", str(salida)])
    return total


# ============================================================ portada
def _texto_espaciado(draw, xy_centro, texto, fuente, tracking, color):
    anchos = [draw.textlength(c, font=fuente) for c in texto]
    total = sum(anchos) + tracking * (len(texto) - 1)
    x = xy_centro[0] - total / 2
    for c, a in zip(texto, anchos):
        draw.text((x, xy_centro[1]), c, font=fuente, fill=color)
        x += a + tracking


def portada(p: Proyecto, W, H, tmp, destino: Path, nombre_base: str):
    cfg = p.get("portada", {}) or {}
    idx = max(1, int(cfg.get("toma", 1))) - 1
    t = p.tomas[min(idx, len(p.tomas) - 1)]
    seg = float(cfg.get("segundo", 1.0))
    crudo = tmp / f"portada_{W}x{H}.png"
    vf = cadena_toma(p, Toma(**{**t.__dict__, "texto": None}), W, H, tmp, 99)
    vf = vf.replace("deflicker=mode=pm:size=10,", "")
    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t.inicio + seg}", "-i", str(t.archivo),
         "-vf", vf, "-frames:v", "1", str(crudo)])
    img = Image.open(crudo).convert("RGB")
    img.save(destino / f"Portada_{nombre_base}_sin_texto.png")

    if not (cfg.get("titulo") or cfg.get("titulo_italica")):
        return
    # degradado inferior color hueso
    grad = Image.new("L", (1, H))
    inicio = int(H * 0.48)
    for y in range(H):
        v = 0 if y < inicio else int(240 * min(1, (y - inicio) / (H * 0.24)) ** 1.2)
        grad.putpixel((0, y), v)
    capa = Image.new("RGB", (W, H), (246, 242, 236))
    img = Image.composite(capa, img, grad.resize((W, H)))
    d = ImageDraw.Draw(img)
    base = min(W, H)
    cx = W / 2
    # zona segura de la cuadrícula 3:4 del perfil de Instagram
    y = H * 0.64 if H > W else H * 0.58
    if cfg.get("categoria"):
        f = ImageFont.truetype(str(SANS_MEDIA), int(base * 0.022))
        _texto_espaciado(d, (cx, y), str(cfg["categoria"]).upper(), f, base * 0.012, (40, 38, 35))
        y += base * 0.05
    if cfg.get("titulo"):
        f = ImageFont.truetype(str(SERIF), int(base * 0.10))
        d.text((cx, y), str(cfg["titulo"]), font=f, fill=(28, 27, 25), anchor="ma")
        y += base * 0.105
    if cfg.get("titulo_italica"):
        f = ImageFont.truetype(str(SERIF_ITALICA), int(base * 0.10))
        d.text((cx, y), str(cfg["titulo_italica"]), font=f, fill=(28, 27, 25), anchor="ma")
    img.save(destino / f"Portada_{nombre_base}.png")


# ============================================================ textos IG
def textos_instagram(p: Proyecto, destino: Path, archivos: list[str]):
    ig = p.get("instagram", {}) or {}
    lineas = [f"# {p.get('proyecto', p.carpeta.name)}", ""]
    if p.get("cliente"):
        lineas += [f"Cliente: {p.get('cliente')}", ""]
    if ig.get("titulo"):
        lineas += ["## Título", f"**{ig['titulo']}**", ""]
    if ig.get("descripcion"):
        lineas += ["## Descripción", str(ig["descripcion"]).strip(), ""]
    if ig.get("hashtags"):
        lineas += ["## Hashtags", str(ig["hashtags"]), ""]
    lineas += ["## Archivos"] + [f"- {a}" for a in archivos] + [""]
    if not p.get("musica"):
        lineas += ["## Audio",
                   "El video va sin música: agrégala desde la biblioteca de Instagram/TikTok "
                   "al publicar (sugerencia: piano ambiental o lo-fi suave, 60–90 BPM).", ""]
    (destino / "Textos_Instagram.md").write_text("\n".join(lineas), encoding="utf-8")


# ============================================================ comandos
def cmd_nuevo(carpeta: Path):
    (carpeta / "clips").mkdir(parents=True, exist_ok=True)
    archivo = carpeta / "proyecto.yaml"
    if archivo.exists():
        print(f"{archivo} ya existe; no lo sobrescribo.")
        return
    clips = clips_en(carpeta) if (carpeta / "clips").exists() else []
    if clips:
        tomas = "\n".join(f"  - archivo: {c.name}" for c in clips)
    else:
        tomas = "  - archivo: 01_fachada.mp4\n  - archivo: 02_acceso.mp4\n  - archivo: 03_sala.mp4"
    archivo.write_text(PLANTILLA_YAML.format(nombre=carpeta.name, tomas=tomas), encoding="utf-8")
    print(f"Proyecto creado en {carpeta}\n  1) copia los clips a {carpeta/'clips'}\n"
          f"  2) edita {archivo}\n  3) python3 motor/portico.py armar {carpeta}")


def cmd_revisar(carpeta: Path):
    """Hoja de contacto: 4 fotogramas por toma + guía del recorte vertical."""
    p = cargar(carpeta)
    destino = carpeta / "revision"
    destino.mkdir(exist_ok=True)
    filas = []
    with tempfile.TemporaryDirectory() as tmpd:
        tmp = Path(tmpd)
        for i, t in enumerate(p.tomas, 1):
            cuadros = []
            for k in range(4):
                s = t.inicio + t.duracion * t.velocidad * (k + 0.5) / 4
                f = tmp / f"{i}_{k}.png"
                vf = (filtro_hdr() + "," if t.info.hdr else "") + "scale=-2:360"
                run(["ffmpeg", "-y", "-v", "error", "-ss", f"{s}", "-i", str(t.archivo),
                     "-vf", vf, "-frames:v", "1", str(f)])
                im = Image.open(f).convert("RGB")
                # guía de recorte 9:16
                R = 9 / 16
                w, h = im.size
                if w / h > R:
                    cw = h * R / t.zoom
                    x0 = (w - cw) * t.encuadre
                    ov = Image.new("RGBA", im.size, (0, 0, 0, 0))
                    od = ImageDraw.Draw(ov)
                    od.rectangle([0, 0, x0, h], fill=(0, 0, 0, 140))
                    od.rectangle([x0 + cw, 0, w, h], fill=(0, 0, 0, 140))
                    im = Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB")
                cuadros.append(im)
            ancho = sum(c.width for c in cuadros) + 10 * 3
            fila = Image.new("RGB", (ancho + 340, 400), (28, 27, 25))
            x = 330
            for c in cuadros:
                fila.paste(c, (x, 20)); x += c.width + 10
            d = ImageDraw.Draw(fila)
            f1 = ImageFont.truetype(str(SANS_MEDIA), 26)
            f2 = ImageFont.truetype(str(SANS), 20)
            d.text((20, 30), f"{i:02d}  {t.archivo.name}", font=f1, fill=(242, 238, 231))
            datos = [f"{t.info.ancho}x{t.info.alto}  {t.info.fps:.0f} fps",
                     f"clip: {t.info.duracion:.1f} s" + ("  HDR" if t.info.hdr else ""),
                     f"usa: {t.inicio:.1f} → {t.inicio + t.duracion * t.velocidad:.1f} s",
                     f"encuadre: {t.encuadre:.2f}  zoom: {t.zoom:.2f}"]
            for j, txt in enumerate(datos):
                d.text((20, 90 + j * 34), txt, font=f2, fill=(180, 154, 122))
            filas.append(fila)
    ancho = max(f.width for f in filas)
    hoja = Image.new("RGB", (ancho, sum(f.height for f in filas)), (28, 27, 25))
    y = 0
    for f in filas:
        hoja.paste(f, (0, y)); y += f.height
    salida = destino / "hoja_de_contacto.jpg"
    hoja.save(salida, quality=88)
    print(f"Hoja de contacto: {salida}")
    print("La zona clara es lo que se ve en vertical; mueve 'encuadre' si queda mal.")


def cmd_armar(carpeta: Path, borrador: bool, solo: list[str] | None):
    t0 = time.time()
    p = cargar(carpeta)
    formatos = solo or p.get("formatos", ["vertical"])
    if isinstance(formatos, str):
        formatos = [formatos]
    destino = carpeta / ("borrador" if borrador else "exportados")
    destino.mkdir(exist_ok=True)
    nombre = "".join(ch if ch.isalnum() else "_" for ch in str(p.get("proyecto", carpeta.name))).strip("_")
    print(f"PÓRTICO · {p.get('proyecto', carpeta.name)} · {len(p.tomas)} tomas")
    archivos = []
    with tempfile.TemporaryDirectory() as tmpd:
        tmp = Path(tmpd)
        for fmt in formatos:
            if fmt not in FORMATOS:
                raise SystemExit(f"Formato desconocido: {fmt}. Usa {list(FORMATOS)}")
            W, H = FORMATOS[fmt]
            if borrador:
                W, H = W // 2, H // 2
            sub = tmp / fmt
            sub.mkdir()
            segs = []
            for i, t in enumerate(p.tomas, 1):
                info(f"{fmt}: toma {i}/{len(p.tomas)} {t.archivo.name} ({t.duracion:.1f}s)")
                segs.append(render_toma(p, t, i, W, H, sub, borrador))
            cierre, dur_cierre = None, 0.0
            tipo = str(p.get("cierre", "negro"))
            if tipo in ("logo", "logo_cliente"):
                if tipo == "logo":
                    logo = LOGOS / "portico_logo_vertical_hueso.png"
                else:
                    logo = ruta_proyecto(p, p.get("logo_cliente"))
                dur_cierre = 2.2
                cierre = render_cierre_logo(logo, W, H, dur_cierre, sub)
            salida = destino / f"{nombre}_{W}x{H}.mp4"
            info(f"{fmt}: uniendo y exportando…")
            total = unir(p, segs, [t.duracion for t in p.tomas], W, H, salida,
                         borrador, cierre, dur_cierre)
            archivos.append(salida.name)
            info(f"{fmt}: {salida.name}  ({total:.1f} s)")
            if not borrador:
                portada(p, W, H, sub, destino, f"{nombre}_{fmt}")
    if not borrador:
        textos_instagram(p, destino, archivos)
    print(f"Listo en {time.time() - t0:.0f} s → {destino}")


def main():
    ap = argparse.ArgumentParser(description="Motor de edición de Pórtico")
    sp = ap.add_subparsers(dest="cmd", required=True)
    a = sp.add_parser("nuevo"); a.add_argument("carpeta", type=Path)
    a = sp.add_parser("revisar"); a.add_argument("carpeta", type=Path)
    a = sp.add_parser("armar"); a.add_argument("carpeta", type=Path)
    a.add_argument("--borrador", action="store_true", help="versión rápida a media resolución")
    a.add_argument("--solo", nargs="+", help="exportar sólo estos formatos")
    args = ap.parse_args()
    if not shutil.which("ffmpeg"):
        raise SystemExit("Necesitas ffmpeg instalado.")
    if args.cmd == "nuevo":
        cmd_nuevo(args.carpeta)
    elif args.cmd == "revisar":
        cmd_revisar(args.carpeta)
    else:
        cmd_armar(args.carpeta, args.borrador, args.solo)


if __name__ == "__main__":
    main()
