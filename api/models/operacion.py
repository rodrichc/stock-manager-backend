import requests
from decimal import Decimal # <-- Necesario para calcular la ganancia exacta
from django.conf import settings
from django.db import models
from django.utils import timezone
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
    
    # Dejamos un solo campo usuario
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True) 
    tipo_operacion = models.CharField(max_length=10, choices=TIPO_CHOICES, default='COMPRA')
    
    activo = models.ForeignKey(Activo, on_delete=models.CASCADE)
    fecha = models.DateField(default=timezone.now)
    nominales = models.IntegerField()
    moneda = models.CharField(max_length=3, choices=OPCIONES_MONEDA, default='ARS')
    
    precio_unitario = models.DecimalField(max_digits=15, decimal_places=2)
    dolar_ccl = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # --- NUEVO: Campo para guardar la ganancia exacta de la venta ---
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
            # MAGIA ANTI-SPLIT: Si la acción fue gratis, el costo en USD es cero directo.
            if self.precio_unitario == Decimal('0.0'):
                return Decimal('0.0')
                
            if self.dolar_ccl:
                precio_cedear_usd = Decimal(str(self.precio_unitario)) / Decimal(str(self.dolar_ccl))
                return round(precio_cedear_usd * Decimal(str(self.activo.ratio)), 2)
        return None

    def save(self, *args, **kwargs):
        # 1. Lógica del Dólar CCL
        if self.moneda == 'ARS' and not self.dolar_ccl:
            try:
                fecha_formateada = self.fecha.strftime("%Y/%m/%d")
                url = f"https://api.argentinadatos.com/v1/cotizaciones/dolares/contadoconliqui/{fecha_formateada}"
                respuesta = requests.get(url)
                if respuesta.status_code == 200:
                    datos = respuesta.json()
                    # BLINDAJE API: Guardamos el dato de la API como Decimal puro
                    self.dolar_ccl = Decimal(str(datos['venta']))
            except Exception as e:
                print(f"Error al traer el CCL: {e}")
        
        # 2. VALIDACIÓN DE VENTAS Y CÁLCULO DE GANANCIA
        if self.tipo_operacion == 'VENTA':
            pos = Posicion.objects.filter(usuario=self.usuario, activo=self.activo).first()
            
            # A. Validamos que no venda más de lo que tiene
            cantidad_actual = pos.cantidad_nominales if pos else 0
            
            # EXCEPCIÓN CSV: Si la venta viene del CSV (force_insert), no bloqueamos por si el CSV viene desordenado
            if cantidad_actual < self.nominales and not kwargs.get('force_insert', False):
                raise ValueError(f"No tenés suficientes nominales para vender. Tenés {cantidad_actual}.")
            
            # B. Calculamos la ganancia de esta operación
            if pos and pos.precio_promedio_usd and pos.precio_promedio_usd > Decimal('0.0') and self.costo_accion_entera_usd:
                acciones_enteras_vendidas = Decimal(str(self.nominales)) / Decimal(str(self.activo.ratio))
                diferencia_precio = Decimal(str(self.costo_accion_entera_usd)) - pos.precio_promedio_usd
                self.ganancia_realizada_usd = round(diferencia_precio * acciones_enteras_vendidas, 2)

        # 3. Guardamos la operación primero
        super().save(*args, **kwargs)

        # 4. ACTUALIZAR POSICIÓN (Tenencia)
        posicion, created = Posicion.objects.get_or_create(
            usuario=self.usuario,
            activo=self.activo
        )

        operaciones_del_usuario = Operacion.objects.filter(
            usuario=self.usuario, 
            activo=self.activo
        )
        
        # IMPORTANTE: Si es compra suma, si es venta resta
        total = sum(
            op.nominales if op.tipo_operacion == 'COMPRA' else -op.nominales 
            for op in operaciones_del_usuario
        )
        
        posicion.cantidad_nominales = total
        posicion.save()

        # 5. IMPACTAR GANANCIA EN LA CUENTA (Activo)
        if self.tipo_operacion == 'VENTA' and self.ganancia_realizada_usd:
            cuenta, _ = Cuenta.objects.get_or_create(usuario=self.usuario)
            
            # Sumamos al acumulador histórico
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