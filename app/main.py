from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from weasyprint import HTML
import base64, os

app = FastAPI()
OUT_DIR = os.path.join(os.path.dirname(__file__), "out")
os.makedirs(OUT_DIR, exist_ok=True)
app.mount("/files", StaticFiles(directory=OUT_DIR), name="files")

class Medida(BaseModel):
    ancho: float
    alto: float

class Payload(BaseModel):
    cliente: str
    ubicacion: str
    color: str
    cantidad_hojas: int
    medida_hoja_m: Medida
    precio_panel_m2: float = 670
    precio_instalacion_m2: float = 1300
    flete: float = 800
    moneda: str = "MXN"
    iva_porcentaje: float = 0.16
    modalidad: str = "suministro_e_instalacion"
    folio: str
    fecha_iso: str

def f2(n): return f"{n:,.2f}"

def fila(cant, desc, m2tot, punit, subtotal):
    return f"<tr><td>{cant}</td><td>{desc}</td><td>{m2tot}</td><td>{punit}</td><td>{subtotal}</td></tr>"

@app.post("/render")
def render_pdf(request: Request, p: Payload):
    m2_hoja = round(p.medida_hoja_m.ancho * p.medida_hoja_m.alto, 2)
    m2_total = round(m2_hoja * p.cantidad_hojas, 2)
    sub_panel = round(m2_total * p.precio_panel_m2, 2) if p.modalidad in ("solo_suministro","suministro_e_instalacion") else 0.0
    sub_inst = round(m2_total * p.precio_instalacion_m2, 2) if p.modalidad in ("solo_instalacion","suministro_e_instalacion") else 0.0
    sub_flete = round(p.flete, 2) if p.flete else 0.0
    subtotal = round(sub_panel + sub_inst + sub_flete, 2)
    iva = round(subtotal * p.iva_porcentaje, 2)
    total = round(subtotal + iva, 2)
    html_path = os.path.join(os.path.dirname(__file__), "templates", "base.html")
    with open(html_path, "r", encoding="utf-8") as f: html = f.read()
    logo_path = os.path.join(os.path.dirname(__file__), "static", "logo.png")
    logo_b64 = ""
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as f: logo_b64 = base64.b64encode(f.read()).decode("utf-8")
    filas = ""
    if p.modalidad in ("solo_suministro","suministro_e_instalacion"):
        filas += fila(p.cantidad_hojas, f"Panel aluminio {p.color} {p.medida_hoja_m.ancho}x{p.medida_hoja_m.alto}m", m2_total, p.precio_panel_m2, sub_panel)
    if p.modalidad in ("solo_instalacion","suministro_e_instalacion"):
        filas += fila("-", "Instalación de panel aluminio", m2_total, p.precio_instalacion_m2, sub_inst)
    if sub_flete > 0: filas += fila("-", "Flete", "-", p.flete, sub_flete)
    html = html.replace("{{LOGO_B64}}", logo_b64).replace("{{FOLIO}}", p.folio).replace("{{FECHA}}", p.fecha_iso).replace("{{CLIENTE}}", p.cliente).replace("{{UBICACION}}", p.ubicacion).replace("{{COLOR}}", p.color).replace("{{FILAS}}", filas).replace("{{SUBTOTAL}}", f2(subtotal)).replace("{{IVA}}", f2(iva)).replace("{{TOTAL}}", f2(total))
    filename = p.folio.replace("/", "_") + ".pdf"
    path = os.path.join(OUT_DIR, filename)
    HTML(string=html).write_pdf(path)
    return JSONResponse({"pdf_url": f"{request.base_url}files/{filename}"})
