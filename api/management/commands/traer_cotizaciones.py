from django.core.management.base import BaseCommand
from api.models import Activo
from django.contrib.auth import get_user_model
from decimal import Decimal

User = get_user_model()

class Command(BaseCommand):
    help = 'Actualiza los precios en BD y toma una foto del portfolio para CADA usuario'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('1. Actualizando precios desde Yahoo Finance...'))
        activos = Activo.objects.all()
        
        for activo in activos:
            # Usamos el método nuevo que le agregaste al modelo Activo
            if activo.actualizar_precio_desde_yahoo():
                self.stdout.write(f"   [+] {activo.ticker} actualizado a u$s{activo.precio_actual_usd}")
            else:
                self.stdout.write(self.style.ERROR(f"   [-] Error al actualizar {activo.ticker}"))