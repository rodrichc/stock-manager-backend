from api.models.operacion import Operacion
from api.serializers import ListarOperacionSerializer


def listar_operaciones_service(usuario, ticker=None):
    queryset = Operacion.objects.select_related('activo').filter(usuario=usuario)
    
    if ticker:
        queryset = queryset.filter(activo__ticker=ticker.upper())
        
    operaciones = queryset.order_by('-fecha', '-id')
    serializer = ListarOperacionSerializer(operaciones, many=True)

    return serializer.data