import yfinance as yf
from datetime import datetime, timedelta
from decimal import Decimal
from ..models import Operacion

def calcular_portfolio_sombra_spy(usuario):
    # 1. Traemos TODAS las operaciones del usuario ordenadas desde la más vieja a la más nueva
    operaciones = Operacion.objects.filter(usuario=usuario).order_by('fecha')
    
    if not operaciones.exists():
        return None

    # 2. Buscamos el rango de fechas total
    primera_fecha = operaciones.first().fecha
    hoy = datetime.now().date()
    
    # Colchón de 5 días para atrás por si la primera compra fue un lunes post-feriado
    inicio_str = (primera_fecha - timedelta(days=5)).strftime('%Y-%m-%d')
    fin_str = (hoy + timedelta(days=1)).strftime('%Y-%m-%d')
    
    # 3. Descargamos TODA la data del SPY de ese periodo de un solo golpe (¡Súper rápido!)
    import logging
    logging.getLogger('yfinance').setLevel(logging.CRITICAL)
    spy_data = yf.download('SPY', start=inicio_str, end=fin_str, progress=False)
    
    if spy_data.empty:
        return None
        
    close_data = spy_data['Close'].squeeze()
    
    # 4. El cofre virtual
    nominales_spy_sombra = Decimal('0.0')
    capital_bolsillo_usd = Decimal('0.0')

    # 5. Iteramos operación por operación simulando que compramos/vendimos SPY
    for op in operaciones:
        fecha_op = op.fecha.strftime('%Y-%m-%d')
        
        # Filtramos la data del SPY hasta la fecha de la operación
        data_hasta_fecha = close_data[close_data.index <= fecha_op]
        if data_hasta_fecha.empty:
            continue
            
        precio_spy_ese_dia = Decimal(str(float(data_hasta_fecha.iloc[-1])))
        
        # Cuántos dólares reales moviste en esta operación
        acciones_enteras = Decimal(str(op.nominales)) / Decimal(str(op.activo.ratio))
        monto_operacion_usd = acciones_enteras * Decimal(str(op.costo_accion_entera_usd))
        
        if op.tipo_operacion == 'COMPRA':
            # Compraste CEDEARs -> Simulamos que comprabas SPY
            nominales_spy_sombra += (monto_operacion_usd / precio_spy_ese_dia)
            capital_bolsillo_usd += monto_operacion_usd
        else:
            # Vendiste CEDEARs -> Simulamos que vendías SPY
            nominales_spy_sombra -= (monto_operacion_usd / precio_spy_ese_dia)
            capital_bolsillo_usd -= monto_operacion_usd

    # 6. ¿Cuánto vale ese cofre virtual HOY?
    precio_spy_hoy = Decimal(str(float(close_data.iloc[-1])))
    valor_actual_sombra_usd = nominales_spy_sombra * precio_spy_hoy
    
    return {
        "capital_invertido_usd": round(capital_bolsillo_usd, 2),
        "valor_sombra_spy_usd": round(valor_actual_sombra_usd, 2),
        "ganancia_sombra_usd": round(valor_actual_sombra_usd - capital_bolsillo_usd, 2)
    }