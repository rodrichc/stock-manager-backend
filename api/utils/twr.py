from decimal import Decimal
from ..models import HistoricoPortfolio, Operacion

def calcular_twr_periodo(usuario, fecha_inicio, fecha_fin):
    # 1. Traemos las fotos del periodo solicitado
    fotos = HistoricoPortfolio.objects.filter(
        usuario=usuario,
        fecha__range=[fecha_inicio, fecha_fin]
    ).order_by('fecha')

    if not fotos.exists():
        return Decimal('0.0')

    # EL ARREGLO CLAVE 1: Buscar con cuánta plata EMPEZÓ el periodo (la foto del día anterior)
    foto_previa = HistoricoPortfolio.objects.filter(
        usuario=usuario,
        fecha__lt=fecha_inicio
    ).order_by('-fecha').first()
    
    # Si no hay foto previa (ej: es su primer depósito histórico), arranca en 0.0
    valor_inicio_subperiodo = foto_previa.valor_actual_usd if foto_previa else Decimal('0.0')
    
    twr_acumulado = Decimal('1.0')

    # 2. Traemos TODAS las operaciones del periodo
    flujos_fondos = Operacion.objects.filter(
        usuario=usuario, 
        fecha__range=[fecha_inicio, fecha_fin]
    ).order_by('fecha')

    fechas_con_operaciones = flujos_fondos.values_list('fecha', flat=True).distinct()

    for fecha in fechas_con_operaciones:
        foto_dia = fotos.filter(fecha=fecha).first()
        
        if foto_dia:
            operaciones_del_dia = flujos_fondos.filter(fecha=fecha)
            flujo_neto_del_dia_usd = Decimal('0.0')
            
            for op in operaciones_del_dia:
                acciones_enteras = Decimal(str(op.nominales)) / Decimal(str(op.activo.ratio))
                monto_operacion_usd = acciones_enteras * Decimal(str(op.costo_accion_entera_usd))
                
                if op.tipo_operacion == 'COMPRA':
                    flujo_neto_del_dia_usd += monto_operacion_usd
                else:
                    flujo_neto_del_dia_usd -= monto_operacion_usd

            # EL ARREGLO CLAVE 2: Fórmula de Flujo al Inicio del Día
            # (El valor de ayer + lo que metiste hoy)
            base_calculo = valor_inicio_subperiodo + flujo_neto_del_dia_usd
            
            if base_calculo > Decimal('0.0'):
                # Rendimiento = Cómo cerró hoy / Cuánta plata había en juego hoy
                rendimiento_tramo = foto_dia.valor_actual_usd / base_calculo
                twr_acumulado *= rendimiento_tramo
            
            # El inicio del próximo salto es la foto con la que cerró este día
            valor_inicio_subperiodo = foto_dia.valor_actual_usd 

    # 3. Rendimiento del último tramo "vacío" (desde la última operación hasta hoy)
    ultimo_valor = fotos.last().valor_actual_usd
    if valor_inicio_subperiodo > Decimal('0.0'):
        twr_acumulado *= (ultimo_valor / valor_inicio_subperiodo)

    # Devolvemos el porcentaje limpio
    return round((twr_acumulado - Decimal('1.0')) * Decimal('100.0'), 2)