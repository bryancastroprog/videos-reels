# PÓRTICO · Fotografía arquitectónica

Repositorio de la marca y del **motor de edición** de Pórtico.

```
marca/      logo (SVG + PNG), tipografías y paleta
motor/      portico.py → convierte clips en reels terminados
proyectos/  una carpeta por trabajo (los clips no se suben a GitHub)
```

## Marca

| Archivo (`marca/logo/`) | Uso |
|---|---|
| `portico_logo_horizontal_*` | Firma de correo, sitio web, cotizaciones |
| `portico_logo_vertical_*` | Presentaciones, cierre de videos |
| `portico_isotipo_*` | Íconos, sellos, favicon |
| `portico_perfil_redes.png` | Foto de perfil de Instagram / TikTok / WhatsApp |
| `portico_marca_agua_blanca.png` | Marca de agua sobre video o foto |
| `portico_perfil_logo_*.png` | Foto de perfil con isotipo + PÓRTICO |

**Manual de marca:** `marca/manual/Portico_Manual_de_Marca.pdf` · **Plantillas de post:** `python3 marca/posts/generar_posts.py CARPETA_FOTOGRAMAS SALIDA`
| `portico_tablero_marca.png` | Lámina con paleta y tipografías |

`*_carbon` = para fondo claro · `*_hueso` = para fondo oscuro.

**Concepto:** el isotipo es un pórtico (dintel + dos columnas). El vano entre las columnas
tiene proporción **4:5**, el formato de la foto vertical de Instagram: el marco por donde se mira la arquitectura.

**Paleta:** Carbón `#1C1B19` · Hueso `#F2EEE7` · Travertino `#B49A7A` · Gris piedra `#6E6A64`
**Tipografía:** Cormorant Garamond (títulos) + Inter (datos y etiquetas). Ambas con licencia libre OFL.

Para regenerar todos los logos: `python3 marca/generar_marca.py`

## Motor de edición

### Instalación (una vez)

Necesitas Python 3.10+ y ffmpeg.

```bash
pip install -r requirements.txt
```

### Flujo de un trabajo

```bash
python3 motor/portico.py nuevo proyectos/casa_zona14      # crea la carpeta y proyecto.yaml
# copia los clips a proyectos/casa_zona14/clips/  (01_fachada.mp4, 02_sala.mp4, ...)
python3 motor/portico.py revisar proyectos/casa_zona14    # hoja de contacto con el recorte vertical
python3 motor/portico.py armar proyectos/casa_zona14 --borrador   # versión rápida para revisar (~45 s)
python3 motor/portico.py armar proyectos/casa_zona14      # exporta final
```

En `exportados/` quedan: video(s), portada con y sin texto, y `Textos_Instagram.md`.

### Lo que hace automáticamente

- Recorta cada toma a la duración necesaria (o reparte `duracion_objetivo` entre todas)
- Antiparpadeo (exposición automática del celular) y estabilización suave/fuerte
- Reencuadre a vertical 9:16, retrato 4:5 u horizontal 16:9 con punto de encuadre por toma
- Convierte video HDR del iPhone a color normal (evita que se vea lavado en Instagram)
- Color por preset (`natural`, `calido`, `frio`, `luminoso`) o LUT propia
- Transiciones por fundido, textos con fundido, cierre a negro / logo Pórtico / logo del cliente
- Marca de agua opcional, música opcional (por defecto **sin audio**, con pista muda compatible)
- Portada con el estilo Pórtico dentro de la zona segura de la cuadrícula del perfil

### Cambios del cliente

Casi todos los cambios se resuelven editando `proyecto.yaml` y volviendo a correr `armar`:
quitar una toma, cambiar su orden, mover el encuadre, cambiar textos o duración.

### Lista de tomas estándar (para que el motor funcione bien)

Grabar cada toma **6–10 s**, movimiento lento y continuo, celular en 4K 30 fps, bloqueo de exposición (AE/AF lock).

| # | Toma | Movimiento |
|---|---|---|
| 01 | Fachada / acceso | Avance lento hacia la puerta |
| 02 | Vestíbulo | Entrada lateral |
| 03 | Sala | Paneo lento siguiendo la luz |
| 04 | Comedor / cocina | Desplazamiento lateral |
| 05 | Detalle de material | Acercamiento lento |
| 06 | Recámara principal | Avance desde la puerta |
| 07 | Baño | Fijo o paneo corto |
| 08 | Terraza / vista | Salida hacia el exterior |
| 09 | Dron o toma final | Elevación / alejamiento |

**Graba en vertical** si el entregable principal es Reel. Si también se entrega horizontal,
graba esas tomas en horizontal: recortar horizontal desde vertical pierde mucha resolución.
