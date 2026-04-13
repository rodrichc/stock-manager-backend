from decimal import Decimal
from api.models import HistoricoPortfolio, Activo, HistoricoActivo

def obtener_evolucion_portfolio(usuario):
    historicos = HistoricoPortfolio.objects.filter(usuario=usuario).order_by('fecha')
        
    data = []
    for h in historicos:
        invertido = h.total_invertido_usd if h.total_invertido_usd else Decimal('0.0')
        actual = h.valor_actual_usd if h.valor_actual_usd else Decimal('0.0')
        
        data.append({
            "fecha": h.fecha.strftime('%Y-%m-%d'),
            "invertido": round(invertido, 2),
            "valor_actual": round(actual, 2),
            "ganancia": round(actual - invertido, 2)
        })
    
    return data

def obtener_evolucion_activo(usuario, ticker):
    activo = Activo.objects.filter(ticker=ticker.upper()).first()
    if not activo:
        return []

    detalles = HistoricoActivo.objects.filter(
        snapshot_global__usuario=usuario, 
        activo=activo
    ).select_related('snapshot_global').order_by('snapshot_global__fecha')
    
    data = []
    for d in detalles:
        acciones_enteras = Decimal(str(d.nominales)) / Decimal(str(activo.ratio))
        valor_posicion = acciones_enteras * d.precio_usd_diario
        
        data.append({
            "fecha": d.snapshot_global.fecha.strftime('%Y-%m-%d'),
            "nominales": d.nominales,
            "precio_usd": d.precio_usd_diario,
            "cantidad_invertida": d.cantidad_invertida_usd,
            "valor_posicion": round(valor_posicion, 2),
            "ganancia": round(valor_posicion - d.cantidad_invertida_usd, 2)
        })
    
    return data
