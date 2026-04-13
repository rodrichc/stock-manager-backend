from decimal import Decimal
from api.models import Posicion, HistoricoPortfolio, Cuenta
from ..market import asegurar_precios_actualizados


def calcular_resumen_portfolio(usuario):
    cantidad_actualizada, mensaje = asegurar_precios_actualizados()

    posiciones = Posicion.objects.filter(
        usuario=usuario,
        cantidad_nominales__gt=0
    )

    total_bolsillo = Decimal('0.0')
    total_actual = Decimal('0.0')

    for pos in posiciones:
        acciones = Decimal(pos.cantidad_nominales) / Decimal(pos.activo.ratio)
        promedio = pos.precio_promedio_usd
        actual = pos.activo.precio_actual_usd

        if promedio is not None and actual is not None:
            total_bolsillo += acciones * promedio
            total_actual += acciones * actual

    rendimiento_global = Decimal('0.0')
    if total_bolsillo > 0:
        rendimiento_global = ((total_actual / total_bolsillo) - 1) * 100

    # =========================
    # Rendimiento diario
    # =========================
    ultima_foto = (
        HistoricoPortfolio.objects
        .filter(usuario=usuario)
        .order_by('-fecha')
        .first()
    )

    ganancia_diaria = Decimal('0.0')
    rendimiento_diario = Decimal('0.0')

    if ultima_foto and ultima_foto.valor_actual_usd > 0:
        ganancia_diaria = total_actual - ultima_foto.valor_actual_usd
        rendimiento_diario = (ganancia_diaria / ultima_foto.valor_actual_usd) * 100

    # =========================
    # Cuenta
    # =========================
    cuenta = Cuenta.objects.get(usuario=usuario)
    ganancia_realizada = cuenta.ganancia_realizada_historica_usd if cuenta else Decimal('0.0')

    return {
        "capital_invertido_usd": round(total_bolsillo, 2),
        "valor_actual_usd": round(total_actual, 2),
        "ganancia_neta_usd": round(total_actual - total_bolsillo, 2),
        "rendimiento_global_porcentaje": round(rendimiento_global, 2),
        "ganancia_diaria_usd": round(ganancia_diaria, 2),
        "rendimiento_diario_porcentaje": round(rendimiento_diario, 2),
        "ganancia_realizada": round(ganancia_realizada, 2),
    }