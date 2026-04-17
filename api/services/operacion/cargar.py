from api.serializers import OperacionSerializer
from api.utils.errors import AppError

def cargar_operacion_service(usuario, data):
    serializer = OperacionSerializer(data=data)

    if not serializer.is_valid():
        raise AppError(serializer.errors, 400) 

    try:
        serializer.save(usuario=usuario)
        return serializer.data 
        
    except ValueError as e:
        raise AppError(str(e), 400)