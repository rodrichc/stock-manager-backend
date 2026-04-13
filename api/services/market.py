import yfinance as yf
import pandas as pd
from decimal import Decimal
from datetime import time
from django.utils import timezone
from api.models import Activo

def actualizar_cotizaciones():
    activos = list(Activo.objects.all())
    
    if not activos:
        return 0, "No hay activos en la base de datos."

    tickers = [activo.ticker for activo in activos]
    
    try:
        data = yf.download(tickers, period="1d", progress=False)
        
        if data.empty:
            return 0, "Yahoo Finance no devolvió datos."
            
        cierres = data['Close']
        
    except Exception as e:
        return 0, f"Error de conexión con Yahoo: {str(e)}"

    activos_a_actualizar = []
    ahora = timezone.now()

    for activo in activos:
        try:
            # yfinance cambia el formato si le pedís 1 solo ticker o varios
            if len(tickers) == 1:
                precio_float = float(cierres.iloc[-1])
            else:
                precio_float = float(cierres[activo.ticker].iloc[-1])
                
            # Si Yahoo devuelve "NaN" (Not a Number) porque el ticker no cotizó hoy
            if pd.isna(precio_float):
                continue
                
            activo.precio_actual_usd = Decimal(str(round(precio_float, 2)))
            activo.ultima_actualizacion = ahora
            activos_a_actualizar.append(activo)
            
        except Exception:
            continue

    if activos_a_actualizar:
        Activo.objects.bulk_update(activos_a_actualizar, ['precio_actual_usd', 'ultima_actualizacion'])

    return len(activos_a_actualizar), "Éxito"


def asegurar_precios_actualizados():
    ahora = timezone.now()
    hora_actual = ahora.time()
    
    #Horario en UTC (argentina UTC-3 | 14UTC == 11ARG)
    inicio_mercado = time(14, 0)
    fin_mercado = time(21, 0)
    es_horario_mercado = inicio_mercado <= hora_actual <= fin_mercado
    es_dia_laboral = ahora.weekday() < 5 

    if not es_horario_mercado or not es_dia_laboral:
        return False, "Mercado cerrado"

    ultimo_refresco = Activo.objects.order_by('-ultima_actualizacion').first()
    
    if ultimo_refresco and ultimo_refresco.ultima_actualizacion:
        tiempo_pasado = ahora - ultimo_refresco.ultima_actualizacion
        if tiempo_pasado.total_seconds() < 1200: # 1200 seg = 20 min
            return False, "Usando datos cacheados"

    print(">>> Ejecutando actualización de precios...")
    cantidad, mensaje = actualizar_cotizaciones()
    return True, f"Actualizados {cantidad} activos"
