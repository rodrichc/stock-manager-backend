import requests
from decimal import Decimal
from datetime import timedelta
from django.conf import settings
from django.db import models
from django.utils import timezone

from api.utils.errors import AppError
from .activo import Activo
from .posicion import Posicion
from .cuenta import Cuenta 

class Operacion(models.Model):
    OPCIONES_MONEDA = [
        ('ARS', 'Pesos Argentinos'),
        ('USD', 'Dólares'),
    ]

    TIPO_CHOICES = [
        ('COMPRA', 'Compra'),
        ('VENTA', 'Venta'),
    ]
    
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True) 
    tipo_operacion = models.CharField(max_length=10, choices=TIPO_CHOICES, default='COMPRA')
    
    activo = models.ForeignKey(Activo, on_delete=models.CASCADE)
    fecha = models.DateField(default=timezone.now)
    nominales = models.IntegerField()
    moneda = models.CharField(max_length=3, choices=OPCIONES_MONEDA, default='ARS')
    
    precio_unitario = models.DecimalField(max_digits=15, decimal_places=2)
    dolar_ccl = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    ganancia_realizada_usd = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)

    class Meta:
        app_label = 'api'



    @property
    def precio_total_gastado(self):
        return self.precio_unitario * self.nominales
        


    @property
    def costo_accion_entera_usd(self):
        if self.moneda == 'USD':
            return round(self.precio_unitario * Decimal(str(self.activo.ratio)), 2)
        elif self.moneda == 'ARS':
            # PARA LOS SPLITS: Si la acción fue gratis, el costo en USD es cero directo.
            if self.precio_unitario == Decimal('0.0'):
                return Decimal('0.0')
                
            if self.dolar_ccl:
                precio_cedear_usd = Decimal(str(self.precio_unitario)) / Decimal(str(self.dolar_ccl))
                return round(precio_cedear_usd * Decimal(str(self.activo.ratio)), 2)
        return None



    def save(self, *args, **kwargs):
        cantidad_accion_entera_operada = Decimal(str(self.nominales)) / Decimal(str(self.activo.ratio))

        # Dolar CLL
        if self.moneda == 'ARS' and not self.dolar_ccl:
            try:
                dias = 0
                fecha_busqueda = self.fecha
                while dias < 6:
                    fecha_formateada = fecha_busqueda.strftime("%Y/%m/%d")
                    url = f"https://api.argentinadatos.com/v1/cotizaciones/dolares/contadoconliqui/{fecha_formateada}"
                    respuesta = requests.get(url)
                    if respuesta.status_code == 200:
                        datos = respuesta.json()
                        self.dolar_ccl = Decimal(str(datos['venta']))
                        break
                    else:
                        fecha_busqueda = fecha_busqueda - timedelta(days=1)
                        dias +=1

            except Exception as e:
                print(f"Error al traer el CCL: {e}")
                raise AppError(
                    "Error al obtener la cotización del CCL",
                    503
                )
                
        
        # 2. VALIDACIÓN DE VENTAS Y CÁLCULO DE GANANCIA
        # Buscamos la posición ANTES de guardar la operación
        pos = Posicion.objects.filter(usuario=self.usuario, activo=self.activo).first()

        if self.tipo_operacion == 'VENTA':
            cantidad_actual = pos.cantidad_nominales if pos else 0
            
            # A. Validamos que no venda más de lo que tiene
            if cantidad_actual < self.nominales and not kwargs.get('force_insert', False):
                raise ValueError(f"No tenés suficientes nominales para vender. Tenés {cantidad_actual}.")
            
            # B. Calculamos la ganancia leyendo el precio guardado fijo en la base de datos
            if pos and pos.precio_promedio_usd and pos.precio_promedio_usd > Decimal('0.0') and self.costo_accion_entera_usd:
                cantidad_accion_entera_operada = Decimal(str(self.nominales)) / Decimal(str(self.activo.ratio))
                diferencia_precio = Decimal(str(self.costo_accion_entera_usd)) - pos.precio_promedio_usd
                self.ganancia_realizada_usd = round(diferencia_precio * cantidad_accion_entera_operada, 2)

        # 3. GUARDAMOS LA OPERACIÓN 
        # Se guarda en la BD para que se pueda encontrar en el siguiente paso
        super().save(*args, **kwargs)

        # 4. ACTUALIZAR POSICIÓN
        posicion, _ = Posicion.objects.get_or_create(
            usuario=self.usuario,
            activo=self.activo
        )

        posicion.recalcular_estado_completo()

        # 5. IMPACTAR GANANCIA EN LA CUENTA (Activo)
        if self.tipo_operacion == 'VENTA' and self.ganancia_realizada_usd:
            cuenta, _ = Cuenta.objects.get_or_create(usuario=self.usuario)
            cuenta.ganancia_realizada_historica_usd += self.ganancia_realizada_usd
            cuenta.save()


        # # 6. ACTUALIZAR CUENTA (Saldos líquidos) - Apagado temporalmente
        # # Usamos get_or_create por si el usuario no tiene cuenta aún
        # cuenta, _ = Cuenta.objects.get_or_create(usuario=self.usuario)
        # total_monto = self.precio_total_gastado
        
        # if self.tipo_operacion == 'COMPRA':
        #     # Si compro, gasto plata
        #     if self.moneda == 'ARS': cuenta.saldo_ars -= total_monto
        #     else: cuenta.saldo_usd -= total_monto
        # else:
        #     # Si vendo, entra plata
        #     if self.moneda == 'ARS': cuenta.saldo_ars += total_monto
        #     else: cuenta.saldo_usd += total_monto
            
        # cuenta.save()



    def __str__(self):
        # Hacemos el string dinámico para que no diga siempre "Compra"
        return f"{self.tipo_operacion} {self.nominales} {self.activo.ticker} ({self.moneda})"
    