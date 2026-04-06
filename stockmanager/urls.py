from django.contrib import admin
from django.urls import path
from api.views import resumen_portfolio, detalle_portfolio, evolucion_activo, evolucion_portfolio, rendimiento_real, cargar_operacion, listar_operaciones, listar_operaciones_por_activo, comparativa_sombra_spy, importar_csv_broker,RegistroUsuarioView

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

urlpatterns = [
    path('admin/', admin.site.urls),

    path('login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('register/', RegistroUsuarioView.as_view(), name='register'),
    
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    path('portfolio/', resumen_portfolio),
    path('portfolio/detalle/', detalle_portfolio),
    path('portfolio/evolucion/', evolucion_portfolio),
    path('portfolio/evolucion/<str:ticker>/', evolucion_activo),
    path('portfolio/rendimiento-real', rendimiento_real),
    path('portfolio/rendimiento-sombra/', comparativa_sombra_spy),
    
    path('operaciones/cargar/', cargar_operacion),
    path('operaciones/cargar/csv', importar_csv_broker),
    path('operaciones/', listar_operaciones),
    path('operaciones/<str:ticker>/', listar_operaciones_por_activo),
]