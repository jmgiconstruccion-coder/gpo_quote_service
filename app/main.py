from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from jinja2 import Environment, FileSystemLoader
from datetime import date
from weasyprint import HTML
import os, random

app = FastAPI(title="GPOICONSTRUCCION Cotizador")

# Montar carpeta estática (para el logo)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Configurar plantillas
templates_dir = os.path.join("app", "templates")
env = Environment(loader=FileSystemLoader(templates_dir))

# Carpeta para PDFs generados
output_dir = os.path.join(os.getcwd(), "files")
os.makedirs(output_dir, exist_ok=True)

# Modelo de entrada
class Cotizacion(BaseModel):
    cliente: str
    ubicacion: str
    color: str
    modalidad: str
    cantidad_hojas: int
    medida_hoja_m: dict
    precio_panel_m2: float
    precio_instalacion_m2: float
    flete: float
    iva_porcentaje: float = 0.16
    fecha_iso: str = str(date.today())

@app.post("/render")
async def render_pdf(payload: Cotizacion):
    try:
        # Calcular totales
        m2_totales = payload.cantidad_hojas * payload.medida_hoja_m["ancho"] * payload.medida_hoja_m["alto"]
        subtotal_panel = m2_totales * payload.precio_panel_m2
        subtotal_instalacion = m2_totales * payload.precio_instalacion_m2
        subtotal = subtotal_panel + subtotal_instalacion + payload.flete
        iva = subtotal * payload.iva_porcentaje
        total = subtotal + iva

        # Crear filas HTML
        filas_html = f"""
        <tr>
            <td class="center">{payload.cantidad_hojas}</td>
            <td>Panel aluminio {payload.color} {payload.medida_hoja_m["ancho"]}x{payload.medida_hoja_m["alto"]}m</td>
            <td class="center">{m2_totales:.2f}</td>
            <td class="right">{payload.precio_panel_m2:.2f}</td>
            <td class="right">{subtotal_panel:.2f}</td>
        </tr>
        <tr>
            <td>-</td>
            <td>Instalación de panel aluminio</td>
            <td class="center">{m2_totales:.2f}</td>
            <td class="right">{payload.precio_instalacion_m2:.2f}</td>
            <td class="right">{subtotal_instalacion:.2f}</td>
        </tr>
        <tr>
            <td>-</td>
            <td>Flete</td>
            <td></td>
            <td class="right">{payload.flete:.2f}</td>
            <td class="right">{payload.flete:.2f}</td>
        </tr>
        """

        # Folio aleatorio
        folio = f"GPO-COT/{random.randint(10000, 99999)}"

        # Renderizar HTML
        template = env.get_template("base.html")
        html_content = template.render(
            CLIENTE=payload.cliente,
            UBICACION=payload.ubicacion,
            FECHA=payload.fecha_iso,
            FILAS=filas_html,
            SUBTOTAL=f"{subtotal:,.2f}",
            IVA=f"{iva:,.2f}",
            TOTAL=f"{total:,.2f}",
            FOLIO=folio
        )

        # Insertar CSS adicional (para agrandar el TOTAL)
        html_content = html_content.replace(
            "TOTAL:</td>",
            'TOTAL:</td><style>.total-row td:last-child{font-size:12pt;font-weight:900;}</style>'
        )

        # Guardar PDF
        pdf_filename = f"{folio.replace('/', '_')}.pdf"
        pdf_path = os.path.join(output_dir, pdf_filename)
        HTML(string=html_content, base_url=".").write_pdf(pdf_path)

        pdf_url = f"http://gpoquoteservice-production.up.railway.app/files/{pdf_filename}"
        return JSONResponse(content={"pdf_url": pdf_url})

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# Servir archivos PDF generados
@app.get("/files/{filename}")
async def get_file(filename: str):
    path = os.path.join(output_dir, filename)
    if os.path.exists(path):
        return FileResponse(path, media_type="application/pdf", filename=filename)
    return JSONResponse(status_code=404, content={"detail": "Archivo no encontrado"})
