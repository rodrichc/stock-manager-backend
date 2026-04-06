from django.conf import settings
from django.db import models

class Cuenta(models.Model):

    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    saldo_ars = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    saldo_usd = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    ganancia_realizada_historica_usd = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    class Meta:
        app_label = 'api'

    def __str__(self):
        return f"Billetera de {self.usuario.username} (${self.saldo_ars} ARS)"