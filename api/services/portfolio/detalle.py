from decimal import Decimal
from api.models import Posicion, HistoricoActivo, HistoricoPortfolio

def calcular_detalle_portfolio(usuario):
    posiciones = Posicion.objects.filter(
        usuario=usuario, 
        cantidad_nominales__gt=0
    ).select_related('activo')
    
    detalles = []
    
    ultima_foto = HistoricoPortfolio.objects.filter(usuario=usuario).order_by('-fecha').first()
    
    precios_historicos = {}
    if ultima_foto:
        activos_ids = [pos.activo.id for pos in posiciones]
        h_activos = HistoricoActivo.objects.filter(
            snapshot_global=ultima_foto,
            activo_id__in=activos_ids
        )
        for h in h_activos:
            precios_historicos[h.activo_id] = h.precio_usd_diario

    for pos in posiciones:
        acciones_enteras = Decimal(str(pos.cantidad_nominales)) / Decimal(str(pos.activo.ratio))
        promedio = pos.precio_promedio_usd
        actual = pos.activo.precio_actual_usd
        
        rendimiento_diario_porcentaje = Decimal('0.0')
        ganancia_diaria_usd = Decimal('0.0')

        precio_ayer = precios_historicos.get(pos.activo.id)

        if precio_ayer and precio_ayer > Decimal('0.0'):
            rendimiento_diario_porcentaje = ((actual / precio_ayer) - Decimal('1.0')) * Decimal('100.0')
            ganancia_diaria_usd = (actual - precio_ayer) * acciones_enteras

        if promedio is not None and actual is not None:
            detalles.append({
                "ticker": pos.activo.ticker,
                "nombre": pos.activo.nombre,
                "nominales": pos.cantidad_nominales,
                "precio_promedio": promedio,
                "precio_actual": actual,
                "bolsillo_usd": round(acciones_enteras * promedio, 2),
                "valor_actual_usd": round(acciones_enteras * actual, 2),
                "rendimiento_porcentaje": pos.rendimiento_porcentaje,
                "ganancia_neta_usd": round((acciones_enteras * actual) - (acciones_enteras * promedio), 2),
                "rendimiento_diario_porcentaje": round(rendimiento_diario_porcentaje, 2),
                "ganancia_diaria_usd": round(ganancia_diaria_usd, 2)
            })

    return detalles