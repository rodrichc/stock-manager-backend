from django.contrib import admin
from .models import Usuario, Activo, Operacion, HistoricoActivo, HistoricoPortfolio, Posicion, Cuenta

class OperacionAdmin(admin.ModelAdmin):
    # Agregué 'usuario' para que sepas de quién es la operación
    list_display = ('usuario', 'activo', 'nominales', 'precio_unitario', 'moneda', 'precio_total_gastado', 'costo_accion_entera_usd')
    list_filter = ('usuario', 'activo') # Un filtrito extra que te va a venir joya

class ActivoAdmin(admin.ModelAdmin):
    # Dejamos solo lo que le pertenece al catálogo global
    # Saqué el precio_actual_usd de acá para que no te trabe la carga de la página
    list_display = ('ticker', 'nombre', 'ratio')

class HistoricoPortafolioAdmin(admin.ModelAdmin):
    list_display = ('total_invertido_usd', 'valor_actual_usd', 'fecha')

# --- LOS NUEVOS PANELES ---

class PosicionAdmin(admin.ModelAdmin):
    # Acá reviven tus columnas de cálculos, pero ahora filtradas por usuario
    list_display = ('usuario', 'activo', 'cantidad_nominales', 'precio_promedio_usd', 'rendimiento_porcentaje')
    list_filter = ('usuario', 'activo')

class CuentaAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'saldo_ars', 'saldo_usd')


# --- REGISTROS ---
admin.site.register(Usuario)
admin.site.register(Activo, ActivoAdmin)
admin.site.register(Operacion, OperacionAdmin)
admin.site.register(HistoricoActivo)
admin.site.register(HistoricoPortfolio, HistoricoPortafolioAdmin)
# Registramos las nuevas:
admin.site.register(Posicion, PosicionAdmin)
admin.site.register(Cuenta, CuentaAdmin)