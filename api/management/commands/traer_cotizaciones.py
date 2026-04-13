from django.core.management.base import BaseCommand
from api.services.market import actualizar_cotizaciones

class Command(BaseCommand):
    help = 'Actualiza los precios en BD'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('1. Descargando precios desde Yahoo Finance...'))
        
        cantidad, mensaje = actualizar_cotizaciones()
        
        if cantidad > 0:
            self.stdout.write(self.style.SUCCESS(f'[+] Se actualizaron {cantidad} activos.'))
        else:
            self.stdout.write(self.style.ERROR(f'[-] Ocurrió un problema: {mensaje}'))