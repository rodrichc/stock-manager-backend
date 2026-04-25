from api.models.operacion import Operacion
from api.serializers import ListarOperacionSerializer


def listar_operaciones_service(usuario):
    operaciones = Operacion.objects.select_related('activo').filter(usuario=usuario).order_by('-fecha', '-id')
    serializer = ListarOperacionSerializer(operaciones, many=True)

    return serializer.data