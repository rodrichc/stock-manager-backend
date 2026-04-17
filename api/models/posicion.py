from decimal import Decimal
from django.db import models
from api.models.activo import Activo
from stockmanager import settings

class Posicion(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    activo = models.ForeignKey(Activo, on_delete=models.CASCADE)
    cantidad_nominales = models.IntegerField(default=0) 
    precio_promedio_usd = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    class Meta:
        unique_together = ('usuario', 'activo')


    @property
    def rendimiento_porcentaje(self):
        # ARREGLO 2: Si ya no tenés nominales de esto porque vendiste todo, el rendimiento latente es 0
        if self.cantidad_nominales <= 0:
            return Decimal('0.0')

        promedio = self.precio_promedio_usd
        # El precio actual sigue siendo algo "global" que le pedimos al Activo
        actual = self.activo.precio_actual_usd

        if actual is not None and promedio > Decimal('0.0'):
            rendimiento = ((actual / promedio) - Decimal('1.0')) * Decimal('100.0')
            return round(rendimiento, 2)
        return None
    
    
    
    def recalcular_estado_completo(self):
        from .operacion import Operacion # Evita importación circular
        
        operaciones = Operacion.objects.filter(
            usuario=self.usuario, 
            activo=self.activo
        ).order_by('fecha', 'id')
        
        cantidad_enteras = Decimal('0.0')
        nominales_totales = 0  # Agregamos esto para saber tu tenencia real
        ppc = Decimal('0.0') 
        
        for op in operaciones:
            if op.costo_accion_entera_usd is None: 
                continue
                
            acciones_enteras = Decimal(str(op.nominales)) / Decimal(str(self.activo.ratio))
            costo_op_usd = Decimal(str(op.costo_accion_entera_usd))
            
            if op.tipo_operacion == 'COMPRA':
                costo_total_previo = cantidad_enteras * ppc
                costo_nueva_compra = acciones_enteras * costo_op_usd
                
                cantidad_enteras += acciones_enteras
                nominales_totales += op.nominales # Sumamos nominales
                
                if cantidad_enteras > Decimal('0.0'):
                    ppc = (costo_total_previo + costo_nueva_compra) / cantidad_enteras
                    
            elif op.tipo_operacion == 'VENTA':
                cantidad_enteras -= acciones_enteras
                nominales_totales -= op.nominales # Restamos nominales
                
                if cantidad_enteras <= Decimal('0.0'):
                    cantidad_enteras = Decimal('0.0')
                    nominales_totales = 0
                    ppc = Decimal('0.0')
                    
        # ¡LA MAGIA FINAL! En vez de retornar, pisamos los campos de la BD y guardamos.
        self.precio_promedio_usd = round(ppc, 2)
        self.cantidad_nominales = nominales_totales
        self.save()
