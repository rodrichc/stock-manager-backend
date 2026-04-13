from decimal import Decimal
from api.models import HistoricoPortfolio

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