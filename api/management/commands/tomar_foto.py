from django.core.management.base import BaseCommand
from api.models import Activo, HistoricoPortfolio, HistoricoActivo, Posicion
from django.contrib.auth import get_user_model
from decimal import Decimal

User = get_user_model()

class Command(BaseCommand):
    help = 'Actualiza los precios en BD y toma una foto del portfolio para CADA usuario'

    def handle(self, *args, **options):
        # ==========================================
        # FASE 1: ACTUALIZAR EL CATÁLOGO GLOBAL
        # ==========================================
        self.stdout.write(self.style.WARNING('1. Actualizando precios desde Yahoo Finance...'))
        activos = Activo.objects.all()
        
        for activo in activos:
            # Usamos el método nuevo que le agregaste al modelo Activo
            if activo.actualizar_precio_desde_yahoo():
                self.stdout.write(f"   [+] {activo.ticker} actualizado a u$s{activo.precio_actual_usd}")
            else:
                self.stdout.write(self.style.ERROR(f"   [-] Error al actualizar {activo.ticker}"))

        # ==========================================
        # FASE 2: SACAR LA FOTO POR USUARIO
        # ==========================================
        self.stdout.write(self.style.WARNING('\n2. Procesando portfolios de usuarios...'))
        usuarios = User.objects.all()

        for usuario in usuarios:
            total_bolsillo = Decimal('0.0')
            total_actual = Decimal('0.0')
            data_para_fotos_individuales = []

            # Buscamos SOLO las posiciones de este usuario que tengan saldo
            posiciones = Posicion.objects.filter(usuario=usuario, cantidad_nominales__gt=0)

            if not posiciones.exists():
                self.stdout.write(f"   - {usuario.username} no tiene activos. Salteando.")
                continue

            for pos in posiciones:
                acciones_enteras = Decimal(str(pos.cantidad_nominales)) / Decimal(str(pos.activo.ratio))
                promedio = pos.precio_promedio_usd
                actual = pos.activo.precio_actual_usd # Usamos el precio fresco que guardamos en la Fase 1
                
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

            # Guardamos la foto global de ESTE usuario
            if total_bolsillo > 0:
                foto_global = HistoricoPortfolio.objects.create(
                    usuario=usuario,  # ¡IMPORTANTE! Lee la nota abajo sobre esto
                    total_invertido_usd=total_bolsillo,
                    valor_actual_usd=total_actual
                )

                # Guardamos los detalles individuales vinculados a esa foto
                for item in data_para_fotos_individuales:
                    HistoricoActivo.objects.create(
                        snapshot_global=foto_global,
                        activo=item['activo'],
                        nominales=item['nominales'],
                        precio_usd_diario=item['precio'],
                        cantidad_invertida_usd=item['invertido']
                    )
                
                self.stdout.write(self.style.SUCCESS(f'   [OK] Foto de {usuario.username} guardada con éxito.'))