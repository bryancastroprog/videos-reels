"""Genera el portafolio de Pórtico (HTML + PDF horizontal A4) desde portafolio.yaml.

Uso:  python3 portafolio/generar_portafolio.py
Requiere: pyyaml, qrcode, node + playwright (para el PDF).
"""
from __future__ import annotations

import html
import subprocess
from pathlib import Path

import qrcode
import qrcode.image.svg
import yaml

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent

e = html.escape


def qr_svg(url: str) -> str:
    img = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, border=0, box_size=10)
    return img.to_string(encoding="unicode")


def pie(medio: str) -> str:
    return "Fotograma de video" if medio == "video" else "Fotografía"


CSS = """
@font-face { font-family: "Archivo"; src: url("../marca/fuentes/Archivo-Variable.ttf"); font-weight: 100 900; font-stretch: 62% 125%; }
@font-face { font-family: "Plex Mono"; src: url("../marca/fuentes/IBMPlexMono-Light.ttf"); font-weight: 300; }
@font-face { font-family: "Plex Mono"; src: url("../marca/fuentes/IBMPlexMono-Regular.ttf"); font-weight: 400; }
:root { --carbon:#1C1B19; --hueso:#F2EEE7; --travertino:#B49A7A; --gris:#6E6A64; --gris2:#A9A39A; --linea:#D9D3C9; }
@page { size: 297mm 210mm; margin: 0; }
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: "Archivo", sans-serif; color: var(--carbon); font-size: 9.4pt; line-height: 1.5; background: var(--hueso);
  -webkit-print-color-adjust: exact; print-color-adjust: exact; }
.page { width: 297mm; height: 210mm; position: relative; overflow: hidden; background: var(--hueso); page-break-after: always; }
.page:last-child { page-break-after: auto; }
.oscura { background: var(--carbon); color: var(--hueso); }
.mono { font-family: "Plex Mono", monospace; letter-spacing: .14em; text-transform: uppercase; font-size: 7pt; }
.light { font-weight: 300; } .trav { color: var(--travertino); } .gris { color: var(--gris); }
.oscura .gris { color: var(--gris2); }
.cab { position: absolute; top: 11mm; left: 18mm; right: 18mm; display: flex; justify-content: space-between; z-index: 2; }
.pie { position: absolute; bottom: 9mm; left: 18mm; right: 18mm; display: flex; justify-content: space-between; }
h1 { font-weight: 200; font-size: 54pt; line-height: .98; letter-spacing: -.03em; }
h2 { font-weight: 200; font-size: 34pt; line-height: 1.02; letter-spacing: -.02em; }
.lead { font-weight: 300; font-size: 12pt; line-height: 1.45; }
.img { background-size: cover; background-position: center; }
.ficha .f { display: grid; grid-template-columns: 30mm 1fr; padding: 2.4mm 0; border-bottom: .2mm solid var(--linea); }
.ficha .f .mono { color: var(--travertino); padding-top: .7mm; }
"""


def pagina_portada(d) -> str:
    p = d["proyectos"][0]
    if d.get("portada"):  # imagen propia para la portada del portafolio
        p = {**p, "id": d["portada"]["proyecto"], "portada": d["portada"]["imagen"],
             "encuadre_portada": d["portada"].get("encuadre", "center")}
    return f"""
<section class="page oscura">
  <div class="img" style="position:absolute; right:0; top:0; bottom:0; width:118mm; background-position:{p.get('encuadre_portada', 'center')}; background-image:url('proyectos/{p['id']}/{p['portada']}')"></div>
  <div style="position:absolute; left:18mm; top:16mm; bottom:16mm; width:150mm; display:flex; flex-direction:column; justify-content:space-between">
    <img src="../marca/logo/portico_logo_horizontal_hueso.svg" style="height:11mm; align-self:flex-start">
    <div>
      <span class="mono trav">{e(d['edicion'])}</span>
      <h1 style="margin-top:4mm">Fotografía y video<br>de arquitectura</h1>
    </div>
    <span class="mono gris">Ciudad de Guatemala — @{e(d['contacto']['instagram'])}</span>
  </div>
</section>"""


def pagina_estudio(d) -> str:
    est = d["estudio"]
    servicios = "".join(
        f'<div style="padding:3mm 0; border-bottom:.2mm solid var(--linea)"><span class="mono trav">{i:02d}</span>'
        f'<div style="font-size:14pt; font-weight:300; margin:1mm 0">{e(s["nombre"])}</div>'
        f'<div style="font-size:9pt">{e(s["detalle"])}</div></div>'
        for i, s in enumerate(est["servicios"], 1))
    indice = "".join(
        f'<div style="display:flex; justify-content:space-between; padding:2.2mm 0; border-bottom:.2mm solid var(--linea)">'
        f'<span><span class="mono trav" style="margin-right:4mm">{i:02d}</span>{e(p["obra"])}</span>'
        f'<span class="mono gris">{e(p["autor"])} — {p["anio"]}</span></div>'
        for i, p in enumerate(d["proyectos"], 1))
    return f"""
<section class="page" style="padding:26mm 18mm 20mm">
  <div class="cab"><span class="mono">Pórtico</span><span class="mono gris">Estudio</span></div>
  <div style="display:grid; grid-template-columns: 1fr 1fr; gap:18mm; height:100%">
    <div style="display:flex; flex-direction:column; justify-content:space-between">
      <h2>{e(est['frase'])}</h2>
      <p class="lead" style="max-width:115mm">{e(est['texto'])}</p>
    </div>
    <div>
      <span class="mono gris">Servicios</span>
      <div style="border-top:.3mm solid var(--carbon); margin-top:2mm">{servicios}</div>
      <span class="mono gris" style="display:block; margin-top:9mm">Proyectos</span>
      <div style="border-top:.3mm solid var(--carbon); margin-top:2mm">{indice}</div>
    </div>
  </div>
</section>"""


def paginas_proyecto(p, n: int) -> str:
    carpeta = f"proyectos/{p['id']}"
    servicio = p["servicio"] + (f" · {p['duracion']}" if p.get("duracion") else "")
    filas = [("Obra", p["obra"]), ("Autor", p["autor"]), ("Tipo", p["tipo"]),
             ("Ubicación", p["ubicacion"]), ("Año", str(p["anio"])), ("Servicio", servicio),
             ("Imagen", f"{'Video' if p['medio'] == 'video' else 'Fotografía'}: Pórtico")]
    ficha = "".join(f'<div class="f"><span class="mono">{e(a)}</span><span>{e(b)}</span></div>' for a, b in filas)
    a = f"""
<section class="page">
  <div class="img" style="position:absolute; left:0; top:0; bottom:0; width:118mm; background-position:{p.get('encuadre_portada', 'center')}; background-image:url('{carpeta}/{p['portada']}')"></div>
  <span class="mono" style="position:absolute; left:8mm; bottom:8mm; color:#fff">{pie(p['medio'])}</span>
  <div style="position:absolute; left:136mm; right:18mm; top:18mm; bottom:16mm; display:flex; flex-direction:column; justify-content:space-between">
    <div style="display:flex; justify-content:space-between"><span class="mono trav">Proyecto {n:02d}</span><span class="mono gris">Pórtico</span></div>
    <div>
      <h1 style="font-size:58pt">{e(p['obra'])}</h1>
      <div style="font-size:16pt; font-weight:300; margin:3mm 0 7mm">{e(p['autor'])}</div>
      <p style="font-size:10.5pt; max-width:115mm; margin-bottom:7mm">{e(p['descripcion'])}</p>
      <div class="ficha" style="border-top:.3mm solid var(--carbon)">{ficha}</div>
    </div>
  </div>
</section>"""
    gal = p.get("galeria", [])
    paginas = [a]
    for i in range(0, len(gal), 3):
        grupo = gal[i:i + 3]
        celdas = "".join(
            f'<div class="img" style="background-image:url(\'{carpeta}/{g}\')"></div>' for g in grupo)
        paginas.append(f"""
<section class="page" style="padding:18mm 18mm 20mm">
  <div style="display:grid; grid-template-columns: repeat({len(grupo)}, 1fr); gap:5mm; height:160mm">{celdas}</div>
  <div class="pie"><span class="mono gris">{e(p['obra'])} — {e(p['autor'])} — {'Fotogramas de video' if p['medio'] == 'video' else 'Fotografía'}: Pórtico</span>
  <span class="mono gris">{n:02d}.{i // 3 + 1}</span></div>
</section>""")
    for j, img in enumerate(p.get("plena", []), 1):
        paginas.append(f"""
<section class="page">
  <div class="img" style="position:absolute; left:0; right:0; top:0; bottom:20mm; background-image:url('{carpeta}/{img}')"></div>
  <div class="pie" style="bottom:7.5mm"><span class="mono gris">{e(p['obra'])} — {e(p['autor'])} — {'Fotograma de video' if p['medio'] == 'video' else 'Fotografía'}: Pórtico</span>
  <span class="mono gris">{n:02d}.{len(gal) // 3 + j + (1 if len(gal) % 3 else 0)}</span></div>
</section>""")
    return "".join(paginas)


def pagina_contacto(d) -> str:
    c = d["contacto"]
    return f"""
<section class="page oscura" style="padding:20mm 18mm">
  <div style="display:flex; flex-direction:column; justify-content:space-between; height:100%">
    <span class="mono trav">Contacto</span>
    <div style="display:flex; justify-content:space-between; align-items:flex-end">
      <div>
        <h1>Agendemos<br>20 minutos.</h1>
        <div class="mono" style="margin-top:9mm; line-height:2.1; font-size:8pt">
          {e(c['nombre'])}<br>WhatsApp {e(c['whatsapp'])}<br>
          <span style="text-transform:none">{e(c['correo'])}</span><br><span style="text-transform:none">@{e(c['instagram'])}</span>
        </div>
      </div>
      <div style="text-align:right">
        <div style="width:34mm; height:34mm; background:var(--hueso); padding:3mm; margin-left:auto">{qr_svg('https://instagram.com/' + c['instagram'])}</div>
        <span class="mono gris" style="display:block; margin-top:3mm">Ver el trabajo en Instagram</span>
      </div>
    </div>
    <img src="../marca/logo/portico_isotipo_hueso.svg" style="height:14mm; align-self:flex-start">
  </div>
</section>"""


def main():
    d = yaml.safe_load((AQUI / "portafolio.yaml").read_text(encoding="utf-8"))
    cuerpo = pagina_portada(d) + pagina_estudio(d)
    for n, p in enumerate(d["proyectos"], 1):
        cuerpo += paginas_proyecto(p, n)
    cuerpo += pagina_contacto(d)
    doc = (f'<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Pórtico · {e(d["edicion"])}</title>'
           f'<style>{CSS} svg {{ width:100%; height:100%; display:block; }}</style></head><body>{cuerpo}</body></html>')
    salida_html = AQUI / "portafolio.html"
    salida_html.write_text(doc, encoding="utf-8")
    pdf = AQUI / f"Portico_{d['edicion'].replace(' ', '_')}.pdf"
    subprocess.run(["node", str(RAIZ / "herramientas" / "a_pdf.js"), str(salida_html), str(pdf),
                    str(AQUI / ".vista")], check=True)
    print("Listo:", pdf)


if __name__ == "__main__":
    main()
