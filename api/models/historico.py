from django.conf import settings 
from django.db import models
from django.utils import timezone 
from .activo import Activo

class HistoricoPortfolio(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True) 
    
    # Cambiamos auto_now_add para tener flexibilidad de guardar fechas pasadas
    fecha = models.DateField(default=timezone.now)
    total_invertido_usd = models.DecimalField(max_digits=15, decimal_places=2)
    valor_actual_usd = models.DecimalField(max_digits=15, decimal_places=2)

    # --- NUEVO: La foto del SPY de ese exacto día ---
    precio_spy_usd = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        app_label = 'api'
        ordering = ['-fecha']
        # ESCUDO: Evita que se creen 5 fotos el mismo día si el usuario aprieta mucho el botón
        unique_together = ('usuario', 'fecha') 

    def __str__(self):
        username = self.usuario.username if self.usuario else "Sin Usuario"
        return f"Portfolio de {username} - {self.fecha}"


class HistoricoActivo(models.Model):
    # Relacionamos cada detalle con la "foto" global del día
    snapshot_global = models.ForeignKey(HistoricoPortfolio, related_name='detalles', on_delete=models.CASCADE)
    activo = models.ForeignKey(Activo, on_delete=models.CASCADE)
    nominales = models.IntegerField()
    precio_usd_diario = models.DecimalField(max_digits=15, decimal_places=2)
    cantidad_invertida_usd = models.DecimalField(max_digits=15, decimal_places=2, default=0.0)

    class Meta:
        app_label = 'api'
        
    def __str__(self):
        return f"{self.nominales} {self.activo.ticker} a u$s{self.precio_usd_diario}"