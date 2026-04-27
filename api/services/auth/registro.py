from django.contrib.auth import get_user_model

Usuario = get_user_model()

def registrar_usuario_service(datos_validados):
    usuario = Usuario.objects.create_user(
        username=datos_validados['username'],
        email=datos_validados.get('email', ''),
        password=datos_validados['password']
    )
    
    #acá creamos la billetera o mandamos mail a la hora del registro

    return usuario