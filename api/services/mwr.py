import yfinance as yf
import pandas as pd
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from collections import defaultdict
from ..models import Operacion

def calcular_portfolio_sombra_spy(usuario):
    operaciones = Operacion.objects.filter(usuario=usuario).select_related('activo').order_by('fecha')
    if not operaciones.exists():
        return None

    tickers_db = set(op.activo.ticker for op in operaciones)
    tickers_descarga = list(tickers_db.union({'SPY'}))

    primera_fecha = operaciones.first().fecha
    hoy = datetime.now().date()
    inicio_str = (primera_fecha - timedelta(days=5)).strftime('%Y-%m-%d')
    fin_str = (hoy + timedelta(days=1)).strftime('%Y-%m-%d')

    logging.getLogger('yfinance').setLevel(logging.CRITICAL)
    try:
        data = yf.download(tickers_descarga, start=inicio_str, end=fin_str, progress=False)
        if data.empty: return None
        close_data = data['Close']
        if isinstance(close_data, pd.Series):
            close_data = close_data.to_frame(name='SPY')
    except Exception:
        return None

    ops_por_fecha = defaultdict(list)
    for op in operaciones:
        ops_por_fecha[op.fecha.strftime('%Y-%m-%d')].append(op)

    # LA MAGIA: Diccionarios para llevar el Costo Promedio exacto como hace tu tabla Posiciones
    inventario = {t: {'cantidad': Decimal('0.0'), 'costo_base': Decimal('0.0')} for t in tickers_db}
    inv_sombra = {'cantidad': Decimal('0.0'), 'costo_base': Decimal('0.0')}

    datos_grafico = []

    for fecha_pd in close_data.index:
        fecha_str = fecha_pd.strftime('%Y-%m-%d')

        if fecha_str in ops_por_fecha:
            for op in ops_por_fecha[fecha_str]:
                if not op.costo_accion_entera_usd: continue

                ticker = op.activo.ticker
                acciones_enteras = Decimal(str(op.nominales)) / Decimal(str(op.activo.ratio))
                monto_usd = acciones_enteras * Decimal(str(op.costo_accion_entera_usd))

                precio_spy_transaccion = float(close_data.loc[fecha_pd, 'SPY'])
                if pd.isna(precio_spy_transaccion): continue
                precio_spy_transaccion = Decimal(str(precio_spy_transaccion))

                if op.tipo_operacion == 'COMPRA':
                    # Sumamos nominales y guita real
                    inventario[ticker]['cantidad'] += acciones_enteras
                    inventario[ticker]['costo_base'] += monto_usd
                    
                    qty_sombra = monto_usd / precio_spy_transaccion
                    inv_sombra['cantidad'] += qty_sombra
                    inv_sombra['costo_base'] += monto_usd
                    
                elif op.tipo_operacion == 'VENTA':
                    # Al vender, restamos el costo PROPORCIONAL (Igual que en tus tarjetas)
                    if inventario[ticker]['cantidad'] > 0:
                        promedio_real = inventario[ticker]['costo_base'] / inventario[ticker]['cantidad']
                        inventario[ticker]['cantidad'] -= acciones_enteras
                        inventario[ticker]['costo_base'] -= (acciones_enteras * promedio_real)
                        if inventario[ticker]['cantidad'] <= 0:
                            inventario[ticker]['cantidad'] = inventario[ticker]['costo_base'] = Decimal('0.0')

                    if inv_sombra['cantidad'] > 0:
                        promedio_sombra = inv_sombra['costo_base'] / inv_sombra['cantidad']
                        qty_sombra = monto_usd / precio_spy_transaccion
                        inv_sombra['cantidad'] -= qty_sombra
                        inv_sombra['costo_base'] -= (qty_sombra * promedio_sombra)
                        if inv_sombra['cantidad'] <= 0:
                            inv_sombra['cantidad'] = inv_sombra['costo_base'] = Decimal('0.0')

        # Calculamos el costo base total del día sumando lo que nos queda en inventario
        costo_base_total_real = sum(d['costo_base'] for d in inventario.values())
        
        # Si no tenés plata invertida, no graficamos
        if costo_base_total_real <= 0 and inv_sombra['costo_base'] <= 0:
            continue

        valor_mercado_real = Decimal('0.0')
        for ticker, data_inv in inventario.items():
            if data_inv['cantidad'] > 0:
                precio_hoy = float(close_data.loc[fecha_pd, ticker])
                if not pd.isna(precio_hoy):
                    valor_mercado_real += data_inv['cantidad'] * Decimal(str(precio_hoy))

        valor_mercado_sombra = Decimal('0.0')
        precio_spy_hoy = float(close_data.loc[fecha_pd, 'SPY'])
        if not pd.isna(precio_spy_hoy) and inv_sombra['cantidad'] > 0:
            valor_mercado_sombra = inv_sombra['cantidad'] * Decimal(str(precio_spy_hoy))

        # Porcentajes calculados sobre el Costo Promedio (Igual a las tarjetas)
        rendimiento_real = Decimal('0.0')
        if costo_base_total_real > 0:
            rendimiento_real = ((valor_mercado_real / costo_base_total_real) - Decimal('1.0')) * Decimal('100.0')

        rendimiento_sombra = Decimal('0.0')
        if inv_sombra['costo_base'] > 0:
            rendimiento_sombra = ((valor_mercado_sombra / inv_sombra['costo_base']) - Decimal('1.0')) * Decimal('100.0')

        datos_grafico.append({
            "fecha": fecha_str,
            "portfolio_pct": round(rendimiento_real, 2),
            "spy_sombra_pct": round(rendimiento_sombra, 2),
            "portfolio_usd": round(valor_mercado_real, 2),
            "spy_sombra_usd": round(valor_mercado_sombra, 2),

            "costo_base_real_usd": round(costo_base_total_real, 2),
            "costo_base_sombra_usd": round(inv_sombra['costo_base'], 2),
            "precio_spy_hoy": round(precio_spy_hoy, 2) if not pd.isna(precio_spy_hoy) else 0.0
        })

    if not datos_grafico: return None
    ultimo_dato = datos_grafico[-1]
    
    # Devolvemos TODO calculado en base a la misma variable
    return {
        "resumen": {
            "capital_bolsillo_usd": round(costo_base_total_real, 2),
            "tu_portfolio_real_usd": ultimo_dato["portfolio_usd"],
            "tu_portfolio_real_porcentaje": ultimo_dato["portfolio_pct"],
            "portfolio_sombra_spy_usd": ultimo_dato["spy_sombra_usd"],
            "portfolio_sombra_spy_porcentaje": ultimo_dato["spy_sombra_pct"],
            "diferencia_alpha_usd": round(Decimal(str(ultimo_dato["portfolio_usd"])) - Decimal(str(ultimo_dato["spy_sombra_usd"])), 2)
        },
        "grafico": datos_grafico
    }