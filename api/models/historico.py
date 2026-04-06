from django.conf import settings 
from django.db import models
from .activo import Activo

class HistoricoPortfolio(models.Model):
    # <-- NUEVO: Le decimos a quién le pertenece esta foto del portfolio
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True) 
    
    fecha = models.DateField(auto_now_add=True)
    total_invertido_usd = models.DecimalField(max_digits=15, decimal_places=2)
    valor_actual_usd = models.DecimalField(max_digits=15, decimal_places=2)

    class Meta:
        app_label = 'api'
        ordering = ['-fecha']

    def __str__(self):
        # Le sumamos el nombre para que en el Admin sepas de quién es la foto
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