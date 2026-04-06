import yfinance as yf
from decimal import Decimal
from django.db import models

class Activo(models.Model):
    ticker = models.CharField(max_length=10, unique=True)
    nombre = models.CharField(max_length=100)
    ratio = models.IntegerField(default=1)

    # --- NUEVOS CAMPOS REALES ---
    precio_actual_usd = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    ultima_actualizacion = models.DateTimeField(auto_now=True) # Se actualiza solo cada vez que guardás

    class Meta:
        app_label = 'api'

    def actualizar_precio_desde_yahoo(self):
        """
        Va a Yahoo Finance, trae el precio y lo GUARDA en la base de datos.
        """
        try:
            ticker_data = yf.Ticker(self.ticker)
            historial = ticker_data.history(period="1d")
            
            if not historial.empty:
                precio_float = historial['Close'].iloc[-1]
                self.precio_actual_usd = Decimal(str(round(precio_float, 2)))
                self.save() # Esto lo guarda permanentemente en la base de datos
                return True
        except Exception as e:
            print(f"Error al buscar precio de {self.ticker}: {e}")
            return False

    def __str__(self):
        return f"{self.ticker} - {self.nombre}"