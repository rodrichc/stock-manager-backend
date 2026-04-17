from api.serializers import OperacionSerializer
from api.utils.errors import AppError


def cargar_operacion_service(usuario, data):
    serializer = OperacionSerializer(data=data)
    print(data)

    if serializer.is_valid():
        try:
            serializer.save(usuario=usuario)
            return serializer.data
        except ValueError as e:
            return AppError({"error": str(e)}, 400)
            
    return AppError(serializer.errors, 400)