from decimal import Decimal
from django.db import models
from api.models.activo import Activo
from stockmanager import settings

class Posicion(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    activo = models.ForeignKey(Activo, on_delete=models.CASCADE)
    # Guardamos la cantidad actual para no tener que sumar mil operaciones cada vez
    cantidad_nominales = models.IntegerField(default=0) 
    
    class Meta:
        unique_together = ('usuario', 'activo')

    @property
    def precio_promedio_usd(self):
        from .operacion import Operacion 
        
        operaciones = Operacion.objects.filter(
            usuario=self.usuario, 
            activo=self.activo
        ).order_by('fecha', 'id')
        
        cantidad_actual = Decimal('0.0')
        ppc = Decimal('0.0') 
        
        for op in operaciones:
            # EL ARREGLO: Solo ignoramos si literalmente dice 'None' (sin precio).
            # Si el costo es 0.00 (un split), ¡ahora sí lo dejamos pasar!
            if op.costo_accion_entera_usd is None: 
                continue
                
            acciones_enteras = Decimal(str(op.nominales)) / Decimal(str(self.activo.ratio))
            costo_op_usd = Decimal(str(op.costo_accion_entera_usd))
            
            if op.tipo_operacion == 'COMPRA':
                costo_total_previo = cantidad_actual * ppc
                costo_nueva_compra = acciones_enteras * costo_op_usd
                
                cantidad_actual += acciones_enteras
                
                if cantidad_actual > Decimal('0.0'):
                    ppc = (costo_total_previo + costo_nueva_compra) / cantidad_actual
                    
            elif op.tipo_operacion == 'VENTA':
                cantidad_actual -= acciones_enteras
                if cantidad_actual <= Decimal('0.0'):
                    cantidad_actual = Decimal('0.0')
                    ppc = Decimal('0.0')
                    
        return round(ppc, 2)

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