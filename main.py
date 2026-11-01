import os
import json
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from supabase import create_client, Client

# Variables de entorno para producción
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://ggiswfomgyzmuzvaitsj.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "TU_ANON_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = FastAPI(
    title="Plataforma Express Polar - SaaS API",
    version="1.0.0",
    description="Backend B2B/B2C para distribución automatizada en San Felipe"
)

# --- MODELOS PYDANTIC ---
class ItemCarrito(BaseModel):
    nombre: str
    cantidad_bultos: int
    peso_bulto_kg: float
    precio_unitario_bulto: float

class SolicitudPedido(BaseModel):
    usuario_id: int
    items: List[ItemCarrito]
    tipo_entrega: str = "delivery"

# --- LÓGICA DE NEGOCIO ---
def calcular_flete(items: List[ItemCarrito], es_vip: bool) -> float:
    peso_total = sum(i.cantidad_bultos * i.peso_bulto_kg for i in items)
    bultos_totales = sum(i.cantidad_bultos for i in items)
    
    if peso_total <= 15 and bultos_totales <= 1:
        base = 2.50
    elif peso_total <= 100 and bultos_totales <= 5:
        base = 6.00
    else:
        base = 12.00

    if es_vip and (bultos_totales >= 5 or peso_total >= 100):
        return round(base * 0.5, 2)
    return base

# --- RUTAS DE LA INTERFAZ WEB Y API ---
@app.get("/", response_class=HTMLResponse)
def vista_tienda_web(tenant: str = "default"):
    res_prod = supabase.table("productos").select("*").execute()
    productos = res_prod.data or []
    
    res_user = supabase.table("usuarios").select("*").limit(1).execute()
    usuario = res_user.data[0] if res_user.data else {"nombre": "Comerciante VIP", "saldo_wallet_reembolso": 1.17}

    color_primario = "#059669" if tenant == "san-felipe-norte" else "#1e3a8a"
    nombre_tienda = "Distribuidora San Felipe Norte" if tenant == "san-felipe-norte" else "Plataforma Express Polar"

    tarjetas_html = ""
    for p in productos:
        precio_bulto = float(p.get('precio_regular_bulto', 0))
        desc_vip = float(p.get('descuento_vip_bulto', 0))
        precio_final = precio_bulto - desc_vip
        
        tarjetas_html += f"""
        <div style="background: white; border-radius: 12px; padding: 18px; margin-bottom: 16px; border: 1px solid #e2e8f0;">
            <div style="display: flex; justify-content: space-between;">
                <h3 style="margin:0; font-weight: bold;">{p['nombre']}</h3>
                <span style="background: #dcfce7; color: #166534; padding: 2px 8px; border-radius: 12px; font-size: 12px;">Stock: {p['stock_disponible']}</span>
            </div>
            <div style="margin-top: 10px;">
                <span style="text-decoration: line-through; color: #94a3b8; font-size: 14px;">${precio_bulto:.2f} USD</span>
                <span style="color: #2563eb; font-weight: 800; font-size: 20px; margin-left: 8px;">${precio_final:.2f} USD</span>
            </div>
            <p style="color: #16a34a; font-size: 12px; margin: 4px 0;">🏷️ Descuento VIP: -${desc_vip:.2f}</p>
            <button onclick="alert('🛒 ¡Producto agregado!')" style="width: 100%; background: {color_primario}; color: white; border: none; padding: 10px; border-radius: 8px; font-weight: bold; margin-top: 10px;">
                Añadir al Pedido Express
            </button>
        </div>
        """

    html_content = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{nombre_tienda}</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-slate-100 p-4">
        <div class="max-w-md mx-auto">
            <div style="background: linear-gradient(135deg, {color_primario}, #1e293b);" class="rounded-2xl p-6 text-white mb-6">
                <h1 class="text-2xl font-bold">{nombre_tienda}</h1>
                <p class="text-xs text-slate-200 mt-1">Av. Alberto Ravell • San Felipe</p>
                <div class="mt-4 bg-white/20 p-3 rounded-xl">
                    <p class="text-xs">Billetera Virtual (Cashback)</p>
                    <p class="text-xl font-black text-amber-300">${float(usuario['saldo_wallet_reembolso']):.2f} USD</p>
                </div>
            </div>
            <h2 class="font-bold text-slate-800 mb-4">Catálogo Disponible</h2>
            {tarjetas_html}
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/api/v1/productos")
def listar_productos():
    res = supabase.table("productos").select("*").execute()
    return res.data

@app.post("/api/v1/pedidos")
def crear_pedido(solicitud: SolicitudPedido):
    res_user = supabase.table("usuarios").select("es_suscriptor_vip").eq("id", solicitud.usuario_id).execute()
    es_vip = res_user.data[0]["es_suscriptor_vip"] if res_user.data else False
    
    subtotal = sum(i.cantidad_bultos * i.precio_unitario_bulto for i in solicitud.items)
    costo_flete = 0.0 if solicitud.tipo_entrega == "pickup" else calcular_flete(solicitud.items, es_vip)
    monto_total = round(subtotal + costo_flete, 2)
    
    pedido = supabase.table("pedidos").insert({
        "usuario_id": solicitud.usuario_id,
        "tipo_entrega": solicitud.tipo_entrega,
        "monto_total": monto_total,
        "costo_flete": costo_flete,
        "compromiso_vinculante_aceptado": True,
        "metodo_pago": "Pago Móvil",
        "referencia_bancaria": "PENDIENTE",
        "estatus": "recibido"
    }).execute()
    
    return {"estatus": "exito", "pedido": pedido.data[0]}

@app.get("/api/v1/metrics/saas")
def obtener_metricas_saas():
    pedidos = supabase.table("pedidos").select("*").execute().data or []
    usuarios = supabase.table("usuarios").select("*").execute().data or []
    total_ventas = sum(float(p["monto_total"]) for p in pedidos)
    return {
        "ventas_totales_usd": round(total_ventas, 2),
        "comision_saas_usd": round(total_ventas * 0.015, 2),
        "pedidos_totales": len(pedidos),
        "usuarios_registrados": len(usuarios)
    }