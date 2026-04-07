from django.core.management.base import BaseCommand
from api.models import Activo, HistoricoPortfolio, HistoricoActivo, Posicion
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
import yfinance as yf

User = get_user_model()

class Command(BaseCommand):
    help = 'Actualiza los precios en BD, busca el SPY y toma una foto del portfolio para CADA usuario'

    def handle(self, *args, **options):
        # ==========================================
        # FASE 1: ACTUALIZAR EL CATÁLOGO GLOBAL
        # ==========================================
        self.stdout.write(self.style.WARNING('1. Actualizando precios desde Yahoo Finance...'))
        activos = Activo.objects.all()
        
        for activo in activos:
            if activo.actualizar_precio_desde_yahoo():
                self.stdout.write(f"   [+] {activo.ticker} actualizado a u$s{activo.precio_actual_usd}")
            else:
                self.stdout.write(self.style.ERROR(f"   [-] Error al actualizar {activo.ticker}"))

        # ==========================================
        # FASE 1.5: BUSCAR EL SPY DEL MOMENTO
        # ==========================================
        self.stdout.write(self.style.WARNING('\n1.5. Buscando cotización del SPY...'))
        precio_spy_hoy = Decimal('0.0')
        try:
            import logging
            logging.getLogger('yfinance').setLevel(logging.CRITICAL)
            spy_data = yf.download('SPY', period="1d", progress=False)
            
            if not spy_data.empty:
                close_spy = spy_data['Close'].squeeze()
                
                # BLINDAJE: Si squeeze() lo dejó como un número suelto, lo usamos directo.
                # Si lo dejó como una serie/lista de pandas, usamos .iloc[-1]
                if isinstance(close_spy, (float, int)) or type(close_spy).__name__ == 'float64':
                    valor_final = float(close_spy)
                else:
                    valor_final = float(close_spy.iloc[-1])
                    
                precio_spy_hoy = Decimal(str(round(valor_final, 2)))
                self.stdout.write(self.style.SUCCESS(f"   [+] SPY actualizado a u$s{precio_spy_hoy}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   [-] Error al actualizar SPY: {e}"))

        # ==========================================
        # FASE 2: SACAR LA FOTO POR USUARIO
        # ==========================================
        self.stdout.write(self.style.WARNING('\n2. Procesando portfolios de usuarios...'))
        usuarios = User.objects.all()
        hoy = timezone.now().date() # <--- Fecha exacta de hoy para buscar la foto

        for usuario in usuarios:
            total_bolsillo = Decimal('0.0')
            total_actual = Decimal('0.0')
            data_para_fotos_individuales = []

            posiciones = Posicion.objects.filter(usuario=usuario, cantidad_nominales__gt=0)

            if not posiciones.exists():
                self.stdout.write(f"   - {usuario.username} no tiene activos. Salteando.")
                continue

            for pos in posiciones:
                acciones_enteras = Decimal(str(pos.cantidad_nominales)) / Decimal(str(pos.activo.ratio))
                promedio = pos.precio_promedio_usd
                actual = pos.activo.precio_actual_usd 
                
                if promedio is not None and actual is not None:
                    invertido = acciones_enteras * promedio
                    valor_hoy = acciones_enteras * actual
                    
                    total_bolsillo += invertido
                    total_actual += valor_hoy
                    
                    data_para_fotos_individuales.append({
                        'activo': pos.activo,
                        'nominales': pos.cantidad_nominales,
                        'precio': actual,
                        'invertido': invertido
                    })

            # Guardamos la foto global de ESTE usuario usando update_or_create
            if total_bolsillo > 0:
                foto_global, created = HistoricoPortfolio.objects.update_or_create(
                    usuario=usuario,
                    fecha=hoy, # Clave de búsqueda 1
                    defaults={
                        'total_invertido_usd': total_bolsillo,
                        'valor_actual_usd': total_actual,
                        'precio_spy_usd': precio_spy_hoy if precio_spy_hoy > 0 else None
                    }
                )

                # Si la foto ya existía (created es False), borramos el detalle viejo de hoy 
                # para que no se dupliquen las filas en la tabla HistoricoActivo
                if not created:
                    HistoricoActivo.objects.filter(snapshot_global=foto_global).delete()

                # Guardamos los detalles individuales vinculados a esa foto limpia
                for item in data_para_fotos_individuales:
                    HistoricoActivo.objects.create(
                        snapshot_global=foto_global,
                        activo=item['activo'],
                        nominales=item['nominales'],
                        precio_usd_diario=item['precio'],
                        cantidad_invertida_usd=item['invertido']
                    )
                
                self.stdout.write(self.style.SUCCESS(f'   [OK] Foto de {usuario.username} guardada con éxito.'))

        self.stdout.write(self.style.SUCCESS('\n¡Proceso finalizado!'))