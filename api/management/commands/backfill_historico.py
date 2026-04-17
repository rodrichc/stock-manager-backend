from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from api.models import HistoricoPortfolio
from api.services.metrics.mwr import calcular_portfolio_sombra_spy
from datetime import datetime

User = get_user_model()

class Command(BaseCommand):
    help = 'Rellena el historial usando la función MWR oficial'

    def handle(self, *args, **options):
        for usuario in User.objects.all():
            self.stdout.write(f"Calculando MWR histórico para: {usuario.username}...")
            
            resultado = calcular_portfolio_sombra_spy(usuario)
            
            if not resultado:
                continue

            self.stdout.write("Guardando fotos en la base de datos...")
            
            for dia in resultado['grafico']:
                HistoricoPortfolio.objects.get_or_create(
                    usuario=usuario,
                    fecha=datetime.strptime(dia['fecha'], '%Y-%m-%d').date(),
                    defaults={
                        'total_invertido_usd': dia['costo_base_real_usd'],
                        'valor_actual_usd': dia['portfolio_usd'],
                        'precio_spy_usd': dia['precio_spy_hoy'],
                        'valor_sombra_spy_usd': dia['spy_sombra_usd'],
                        'costo_base_sombra_usd': dia['costo_base_sombra_usd']
                    }
                )
                
            self.stdout.write(self.style.SUCCESS(f"¡Historial listo para {usuario.username}!"))