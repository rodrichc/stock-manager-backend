from decimal import Decimal

def calcular_twr_periodo(usuario, fecha_inicio, fecha_fin):
    from api.models import HistoricoPortfolio, Operacion
    
    # 1. EL ESCUDO ANTI-FECHAS ROTAS (Busca la foto real, salvando fines de semana)
    foto_ini = HistoricoPortfolio.objects.filter(usuario=usuario, fecha__lte=fecha_inicio).order_by('-fecha').first()
    foto_fin = HistoricoPortfolio.objects.filter(usuario=usuario, fecha__lte=fecha_fin).order_by('-fecha').first()
    
    # Si es el mismo día, o si el usuario pide fechas del futuro, cortamos por lo sano: 0%
    if not foto_ini or not foto_fin or foto_ini.id == foto_fin.id:
        return Decimal('0.0')

    # 2. Buscamos SOLO las operaciones que pasaron ESTRICTAMENTE en el medio
    flujos_fondos = Operacion.objects.filter(
        usuario=usuario, 
        fecha__gt=foto_ini.fecha,
        fecha__lte=foto_fin.fecha
    ).order_by('fecha')

    fechas_con_operaciones = flujos_fondos.values_list('fecha', flat=True).distinct()

    twr_acumulado = Decimal('1.0')
    valor_inicio_subperiodo = foto_ini.valor_actual_usd 

    # 3. TU MAGIA: Calculamos los saltos ajustando por flujos de caja (compras/ventas)
    for fecha in fechas_con_operaciones:
        foto_dia = HistoricoPortfolio.objects.filter(usuario=usuario, fecha=fecha).first()
        
        if foto_dia:
            operaciones_del_dia = flujos_fondos.filter(fecha=fecha)
            flujo_neto_del_dia_usd = Decimal('0.0')
            
            for op in operaciones_del_dia:
                if op.costo_accion_entera_usd is None:
                    continue
                    
                acciones_enteras = Decimal(str(op.nominales)) / Decimal(str(op.activo.ratio))
                monto_operacion_usd = acciones_enteras * Decimal(str(op.costo_accion_entera_usd))
                
                if op.tipo_operacion == 'COMPRA':
                    flujo_neto_del_dia_usd += monto_operacion_usd
                else:
                    flujo_neto_del_dia_usd -= monto_operacion_usd

            # Base = Lo que traíamos de rentabilidad + la plata fresca de hoy
            base_calculo = valor_inicio_subperiodo + flujo_neto_del_dia_usd
            
            if base_calculo > Decimal('0.0'):
                rendimiento_tramo = foto_dia.valor_actual_usd / base_calculo
                twr_acumulado *= rendimiento_tramo
            
            # El piso para el próximo salto es cómo cerró la billetera este día
            valor_inicio_subperiodo = foto_dia.valor_actual_usd 

    # 4. EL TRAMO FINAL: De la última operación hasta la foto final solicitada
    # (Esto arregla el bug de que te daba 0% si no habías operado nada en esos días)
    if valor_inicio_subperiodo > Decimal('0.0'):
        twr_acumulado *= (foto_fin.valor_actual_usd / valor_inicio_subperiodo)

    # Devolvemos el porcentaje limpio
    return round((twr_acumulado - Decimal('1.0')) * Decimal('100.0'), 2)