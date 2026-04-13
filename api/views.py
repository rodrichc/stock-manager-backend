import csv
import io
from datetime import datetime
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status, generics
from decimal import Decimal
from django.contrib.auth import get_user_model

from api.services.mwr import calcular_portfolio_sombra_spy
from .models import Activo, HistoricoActivo, HistoricoPortfolio, Operacion
from .services.twr import calcular_twr_periodo
from .serializers import OperacionSerializer, ListarOperacionSerializer, RegistroSerializer
from api.services.portfolio.resumen import calcular_resumen_portfolio
from api.services.portfolio.detalle import calcular_detalle_portfolio
from api.services.portfolio.evolucion import obtener_evolucion_portfolio


User = get_user_model()


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

# 4. Evolución de un Activo específico
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def evolucion_activo(request, ticker):
    activo = Activo.objects.filter(ticker=ticker.upper()).first()
    if not activo:
        return Response([])

    # Filtramos para que solo vea SUS fotos históricas
    detalles = HistoricoActivo.objects.filter(
        snapshot_global__usuario=request.user, 
        activo=activo
    ).order_by('snapshot_global__fecha')
    
    data = []
    for d in detalles:
        acciones_enteras = Decimal(str(d.nominales)) / Decimal(str(activo.ratio))
        valor_posicion = acciones_enteras * d.precio_usd_diario
        
        data.append({
            "fecha": d.snapshot_global.fecha,
            "nominales": d.nominales,
            "precio_usd": d.precio_usd_diario,
            "cantidad_invertida": d.cantidad_invertida_usd,
            "valor_posicion": round(valor_posicion, 2),
            "ganancia": round(valor_posicion - d.cantidad_invertida_usd, 2)
        })
    
    return Response(data)

# 5. Rendimiento Real (TWR)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def rendimiento_real(request):
    fecha_inicio_str = request.query_params.get('inicio')
    fecha_fin_str = request.query_params.get('fin')
    
    if not fecha_inicio_str or not fecha_fin_str:
        return Response({"error": "Faltan las fechas de inicio y fin"}, status=400)

    # 1. BUSCAMOS LAS FOTOS SEGURAS EN LA BASE DE DATOS
    # Si le pasamos un domingo, esto busca automáticamente la foto del viernes.
    foto_inicio = HistoricoPortfolio.objects.filter(
        usuario=request.user, 
        fecha__lte=fecha_inicio_str
    ).order_by('-fecha').first()
    
    foto_fin = HistoricoPortfolio.objects.filter(
        usuario=request.user, 
        fecha__lte=fecha_fin_str
    ).order_by('-fecha').first()

    if not foto_inicio or not foto_fin:
        return Response({"error": "No hay fotos del portfolio guardadas cerca de esas fechas."}, status=400)

    # Guardamos las fechas REALES de las fotos que encontramos
    fecha_inicio_real = foto_inicio.fecha
    fecha_fin_real = foto_fin.fecha

    # 2. Calculamos tu TWR pasándole las fechas reales (para evitar que devuelva 0 por buscar un domingo)
    resultado_twr = calcular_twr_periodo(request.user, fecha_inicio_real, fecha_fin_real)

    # 3. Calculamos el rendimiento del SPY usando tu base de datos (¡Chau Yahoo Finance!)
    rendimiento_spy = Decimal('0.0')
    precio_spy_ini = foto_inicio.precio_spy_usd
    precio_spy_fin = foto_fin.precio_spy_usd

    if precio_spy_ini and precio_spy_fin and precio_spy_ini > Decimal('0.0'):
        # La matemática del rendimiento. Si es el mismo día, naturalmente da 0.
        rendimiento_spy = round(((precio_spy_fin / precio_spy_ini) - Decimal('1.0')) * Decimal('100.0'), 2)

    # 4. Calculamos la diferencia (El famoso "Alpha")
    diferencia_vs_spy = resultado_twr - rendimiento_spy

    return Response({
        "periodo_solicitado": f"{fecha_inicio_str} al {fecha_fin_str}",
        "periodo_real_evaluado": f"{fecha_inicio_real} al {fecha_fin_real}",
        "tu_rendimiento_twr": resultado_twr,
        "rendimiento_spy": rendimiento_spy,
        "alpha_diferencia": diferencia_vs_spy
    })

# 6. Cargar Compra o Venta
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cargar_operacion(request):
    serializer = OperacionSerializer(data=request.data)
    
    if serializer.is_valid():
        try:
            # Guardamos inyectando el usuario de la sesión automáticamente
            serializer.save(usuario=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except ValueError as e:
            # Atrapa el error si intenta vender más de lo que tiene (el que pusimos en models.py)
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
            
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# 7. Listar TODAS las operaciones del usuario
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_operaciones(request):
    operaciones = Operacion.objects.filter(usuario=request.user).order_by('-fecha', '-id')
    serializer = ListarOperacionSerializer(operaciones, many=True)
    return Response(serializer.data)

# 8. Listar operaciones de UN activo para el usuario
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_operaciones_por_activo(request, ticker):
    operaciones = Operacion.objects.filter(
        usuario=request.user, 
        activo__ticker=ticker.upper()
    ).order_by('-fecha', '-id')
    
    serializer = ListarOperacionSerializer(operaciones, many=True)
    return Response(serializer.data)

class RegistroUsuarioView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = [AllowAny] # ¡Cualquiera puede entrar a esta ruta!
    serializer_class = RegistroSerializer


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
    