import csv
from datetime import datetime
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from api.models import Operacion, Activo 

User = get_user_model()

class Command(BaseCommand):
    help = 'Importa un archivo CSV del bróker y genera las operaciones cronológicamente'

    def add_arguments(self, parser):
        parser.add_argument('ruta_csv', type=str, help='Ruta exacta al archivo CSV')
        parser.add_argument('username', type=str, help='Usuario al que se le asignarán las operaciones')

    def handle(self, *args, **options):
        ruta = options['ruta_csv']
        username = options['username']

        try:
            usuario = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'No existe el usuario: {username}'))
            return

        operaciones_creadas = 0
        errores_activos = set()

        self.stdout.write(self.style.WARNING('Iniciando lectura y ordenamiento del CSV...'))

        with open(ruta, mode='r', encoding='latin-1') as archivo:
            lector = csv.DictReader(archivo)
            
            # 1. Metemos todas las filas válidas en una lista temporal
            filas_validas = []
            for fila in lector:
                descripcion = fila.get('Descripcion', '')
                tipo_instrumento = fila.get('Tipo de Instrumento', '')
                
                if tipo_instrumento.strip().lower() != 'cedears':
                    continue
                
                desc_upper = descripcion.upper()
                
                # FILTRO 2 ACTUALIZADO: Aceptamos "BOLETO" y también "DIVIDENDO EN ACCIONES"
                if not (desc_upper.startswith('BOLETO') or 'DIVIDENDO EN ACCIONES' in desc_upper):
                    continue
                    
                filas_validas.append(fila)
            
            # 2. Ordenamos la lista cronológicamente
            filas_validas.sort(key=lambda x: datetime.strptime(x.get('Concertacion', '').strip(), '%Y-%m-%d'))
            
            # 3. Ahora sí, procesamos en el orden correcto
            for fila in filas_validas:
                descripcion = fila.get('Descripcion', '')
                desc_upper = descripcion.upper()
                
                # ACTUALIZADO: Si es "Dividendo en acciones", suma nominales, así que es COMPRA
                tipo_operacion = 'COMPRA' if ('COMPRA' in desc_upper or 'DIVIDENDO EN ACCIONES' in desc_upper) else 'VENTA'
                
                ticker_csv = fila.get('Ticker', '').strip()
                fecha_str = fila.get('Concertacion', '').strip()
                cantidad = int(fila.get('Cantidad', 0))
                precio_unitario = fila.get('Precio', '0')
                moneda_csv = fila.get('Moneda', '').strip()

                activo = Activo.objects.filter(ticker=ticker_csv).first()
                if not activo:
                    errores_activos.add(ticker_csv)
                    continue

                fecha_obj = datetime.strptime(fecha_str, '%Y-%m-%d').date()
                moneda_nuestra = 'ARS' if moneda_csv.lower() == 'pesos' else 'USD'
                
                cantidad_real = abs(cantidad)
                
                # ==========================================
                # MAGIA ANTI-SPLIT
                # ==========================================
                # Si el broker nos mandó un split, forzamos el precio a 0 absoluto.
                # Si es un boleto normal, tomamos el precio que dice el CSV.
                if 'DIVIDENDO EN ACCIONES' in desc_upper:
                    precio_real = Decimal('0.0')
                else:
                    precio_real = abs(Decimal(str(precio_unitario)))

                # Creamos la operación
                Operacion.objects.create(
                    usuario=usuario,
                    activo=activo,
                    tipo_operacion=tipo_operacion,
                    fecha=fecha_obj,
                    nominales=cantidad_real,
                    moneda=moneda_nuestra,
                    precio_unitario=precio_real
                )
                
                operaciones_creadas += 1
                
                # Un log especial para que veas cuando detecta el split
                if 'DIVIDENDO EN ACCIONES' in desc_upper:
                    self.stdout.write(self.style.SUCCESS(f'OK: SPLIT DETECTADO de {cantidad_real} {ticker_csv} a costo $0'))
                else:
                    self.stdout.write(self.style.SUCCESS(f'OK: {fecha_str} - {tipo_operacion} de {cantidad_real} {ticker_csv}'))

        # Resumen final
        self.stdout.write(self.style.SUCCESS(f'\n¡Proceso terminado! Se importaron {operaciones_creadas} operaciones.'))
        
        if errores_activos:
            self.stdout.write(self.style.WARNING('\nOJO: No se importaron estos tickers porque no existen en tu modelo Activo:'))
            for t in errores_activos:
                self.stdout.write(self.style.ERROR(f'- {t}'))