from decimal import Decimal
from api.models.historico import HistoricoPortfolio
from api.services.metrics.twr import calcular_twr_periodo
from api.utils.errors import AppError

def calcular_rendimiento_real(usuario, fecha_inicio, fecha_fin):
    foto_inicio = HistoricoPortfolio.obtener_foto_con_fecha(usuario, fecha_inicio)
    foto_fin = HistoricoPortfolio.obtener_foto_con_fecha(usuario, fecha_fin)

    if not foto_inicio or not foto_fin:
        raise AppError("No hay fotos del portfolio guardadas cerca de esas fechas.", 400)

    fecha_inicio_real = foto_inicio.fecha
    fecha_fin_real = foto_fin.fecha

    resultado_twr = calcular_twr_periodo(usuario, fecha_inicio_real, fecha_fin_real)

    rendimiento_spy = Decimal('0.0')
    precio_spy_ini = foto_inicio.precio_spy_usd
    precio_spy_fin = foto_fin.precio_spy_usd

    if precio_spy_ini and precio_spy_fin and precio_spy_ini > Decimal('0.0'):
        rendimiento_spy = round(((precio_spy_fin / precio_spy_ini) - Decimal('1.0')) * Decimal('100.0'), 2)


    diferencia_vs_spy = resultado_twr - rendimiento_spy

    return {
        "periodo_solicitado": f"{fecha_inicio} al {fecha_fin}",
        "periodo_real_evaluado": f"{fecha_inicio_real} al {fecha_fin_real}",
        "tu_rendimiento_twr": resultado_twr,
        "rendimiento_spy": rendimiento_spy,
        "alpha_diferencia": diferencia_vs_spy
    }