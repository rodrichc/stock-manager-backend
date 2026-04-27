import csv
import io
from datetime import datetime
from rest_framework.decorators import APIView, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from decimal import Decimal

from api.utils.errors import AppError
from .models import Activo, Operacion
from .serializers import RegistroSerializer
from api.services.auth.registro import registrar_usuario_service
from api.services.metrics.mwr import calcular_portfolio_sombra_spy
from api.services.metrics.rendimiento_real import calcular_rendimiento_real
from api.services.operacion.cargar import cargar_operacion_service
from api.services.operacion.listar import listar_operaciones_service
from api.services.portfolio.resumen import calcular_resumen_portfolio
from api.services.portfolio.detalle import calcular_detalle_portfolio
from api.services.portfolio.evolucion import obtener_evolucion_portfolio, obtener_evolucion_activo



class RegistroUsuarioView(APIView):
    permission_classes = [AllowAny] 

    def post(self, request):
        serializer = RegistroSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        registrar_usuario_service(serializer.validated_data)
        
        return Response({"mensaje": "Usuario registrado con éxito"}, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def resumen_portfolio(request):
    data = calcular_resumen_portfolio(request.user)
    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalle_portfolio(request):
    data = calcular_detalle_portfolio(request.user)
    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def evolucion_portfolio(request):
    data = obtener_evolucion_portfolio(request.user)
    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def evolucion_activo(request, ticker):
    data = obtener_evolucion_activo(request.user, ticker)
    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def rendimiento_real(request):
    fecha_inicio_str = request.query_params.get('inicio')
    fecha_fin_str = request.query_params.get('fin')
    
    try:
        data = calcular_rendimiento_real(request.user, fecha_inicio_str, fecha_fin_str)
        return Response(data)
    except AppError as e:
        return Response({"error": e.mensaje}, status=e.status_code)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cargar_operacion(request):
    try:
        data = cargar_operacion_service(request.user, request.data)
        return Response(data, status=status.HTTP_201_CREATED)
    except AppError as e:
        return Response({"error": e.mensaje}, status=e.status_code)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_operaciones(request):
    data = listar_operaciones_service(request.user)
    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_operaciones_por_activo(request, ticker):
    data = listar_operaciones_service(request.user, ticker)
    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def comparativa_sombra_spy(request):
    # Ya no iteramos sobre Posiciones. La Mega Función hace todo el trabajo.
    resultado_completo = calcular_portfolio_sombra_spy(request.user)
    
    if not resultado_completo:
        return Response({"error": "No hay operaciones suficientes o falló Yahoo Finance"}, status=400)
        
    resumen = resultado_completo['resumen']
    
    # Le agregamos quién va ganando para el cartelito rojo/verde
    resumen["ganador"] = "Usuario" if resumen["diferencia_alpha_usd"] > 0 else "SPY"
    
    return Response(resumen)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def importar_csv_broker(request):
    # Angular nos va a mandar el texto del CSV en esta variable
    csv_text = request.data.get('csv_text', '')
    
    if not csv_text:
        return Response({"error": "No se recibió ningún contenido CSV."}, status=400)

    # Magia pura: Convertimos el string gigante en un "archivo virtual" en la memoria RAM
    archivo_virtual = io.StringIO(csv_text)
    
    # Le pasamos el archivo virtual al DictReader (igual que en el comando)
    lector = csv.DictReader(archivo_virtual)
    
    filas_validas = []
    errores_activos = set()

    for fila in lector:
        descripcion = fila.get('Descripcion', '')
        tipo_instrumento = fila.get('Tipo de Instrumento', '')
        
        if tipo_instrumento.strip().lower() != 'cedears':
            continue
        
        desc_upper = descripcion.upper()
        if not (desc_upper.startswith('BOLETO') or 'DIVIDENDO EN ACCIONES' in desc_upper):
            continue
            
        filas_validas.append(fila)
    
    # Ordenamos cronológicamente de vieja a nueva
    filas_validas.sort(key=lambda x: datetime.strptime(x.get('Concertacion', '').strip(), '%Y-%m-%d'))
    
    operaciones_creadas = 0

    # Procesamos
    for fila in filas_validas:
        descripcion = fila.get('Descripcion', '').upper()
        tipo_operacion = 'COMPRA' if ('COMPRA' in descripcion or 'DIVIDENDO EN ACCIONES' in descripcion) else 'VENTA'
        
        ticker_csv = fila.get('Ticker', '').strip()
        activo = Activo.objects.filter(ticker=ticker_csv).first()
        
        if not activo:
            errores_activos.add(ticker_csv)
            continue

        fecha_str = fila.get('Concertacion', '').strip()
        fecha_obj = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        
        cantidad_real = abs(int(fila.get('Cantidad', 0)))
        moneda_nuestra = 'ARS' if fila.get('Moneda', '').strip().lower() == 'pesos' else 'USD'
        
        # Magia Anti-Split
        if 'DIVIDENDO EN ACCIONES' in descripcion:
            precio_real = Decimal('0.0')
        else:
            precio_real = abs(Decimal(str(fila.get('Precio', '0'))))

        # Guardamos en la base de datos
        Operacion.objects.create(
            usuario=request.user, # Usamos el usuario que mandó la petición desde Angular
            activo=activo,
            tipo_operacion=tipo_operacion,
            fecha=fecha_obj,
            nominales=cantidad_real,
            moneda=moneda_nuestra,
            precio_unitario=precio_real
        )
        operaciones_creadas += 1

    return Response({
        "mensaje": "Importación exitosa",
        "operaciones_creadas": operaciones_creadas,
        "tickers_no_encontrados": list(errores_activos)
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def datos_grafico_mwr(request):
    resultado = calcular_portfolio_sombra_spy(request.user)
    if not resultado:
        return Response({"error": "No se pudo calcular el rendimiento."}, status=400)
    return Response(resultado['grafico'])
    