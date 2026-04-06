import yfinance as yf
import csv
import io
from datetime import datetime, timedelta
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status, generics
from decimal import Decimal
from django.contrib.auth import get_user_model

from api.utils.mwr import calcular_portfolio_sombra_spy
from .models import Activo, HistoricoActivo, HistoricoPortfolio, Operacion, Posicion, Cuenta
from .utils.twr import calcular_twr_periodo
from .serializers import OperacionSerializer, ListarOperacionSerializer, RegistroSerializer


User = get_user_model()


# 1. Resumen Global (Ahora incluye la Billetera)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def resumen_portfolio(request):
    # 1. Calculamos el total actual (tu código existente)
    posiciones = Posicion.objects.filter(usuario=request.user, cantidad_nominales__gt=0)
    
    total_bolsillo = Decimal('0.0')
    total_actual = Decimal('0.0')

    for pos in posiciones:
        acciones_enteras = Decimal(str(pos.cantidad_nominales)) / Decimal(str(pos.activo.ratio))
        promedio = pos.precio_promedio_usd
        actual = pos.activo.precio_actual_usd
        
        if promedio is not None and actual is not None:
            total_bolsillo += (acciones_enteras * promedio)
            total_actual += (acciones_enteras * actual)

    rendimiento_global = Decimal('0.0')
    if total_bolsillo > Decimal('0.0'):
        rendimiento_global = ((total_actual / total_bolsillo) - Decimal('1.0')) * Decimal('100.0')

    # ==========================================
    # NUEVO: CÁLCULO DEL RENDIMIENTO DIARIO
    # ==========================================
    # Buscamos la última foto del portfolio (generalmente el cierre de ayer)
    ultima_foto = HistoricoPortfolio.objects.filter(usuario=request.user).order_by('-fecha').first()
    
    ganancia_diaria_usd = Decimal('0.0')
    rendimiento_diario_porcentaje = Decimal('0.0')

    if ultima_foto and ultima_foto.valor_actual_usd > Decimal('0.0'):
        # Cuántos dólares subió o bajó HOY respecto a la foto de ayer
        ganancia_diaria_usd = total_actual - ultima_foto.valor_actual_usd
        
        # Porcentaje de variación diaria
        rendimiento_diario_porcentaje = (ganancia_diaria_usd / ultima_foto.valor_actual_usd) * Decimal('100.0')

    # Buscamos la cuenta del usuario
    cuenta = Cuenta.objects.filter(usuario=request.user).first()
    
    # Si por alguna razón no tiene cuenta, ponemos todo en 0 para que no explote
    ganancia_realizada = cuenta.ganancia_realizada_historica_usd if cuenta else Decimal('0.0')
    # liquidez_ars = cuenta.saldo_ars if cuenta else Decimal('0.0')
    # liquidez_usd = cuenta.saldo_usd if cuenta else Decimal('0.0')

    return Response({
        "capital_invertido_usd": round(total_bolsillo, 2),
        "valor_actual_usd": round(total_actual, 2),
        "ganancia_neta_usd": round(total_actual - total_bolsillo, 2),
        "rendimiento_global_porcentaje": round(rendimiento_global, 2),
        
        # --- Mandamos la data fresca del día a Angular ---
        "ganancia_diaria_usd": round(ganancia_diaria_usd, 2),
        "rendimiento_diario_porcentaje": round(rendimiento_diario_porcentaje, 2),
        
        "ganancia_realizada": round(ganancia_realizada, 2),
    })

# 2. Detalle de Tenencias por Acción
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalle_portfolio(request):
    posiciones = Posicion.objects.filter(usuario=request.user, cantidad_nominales__gt=0)
    detalles = []

    for pos in posiciones:
        acciones_enteras = Decimal(str(pos.cantidad_nominales)) / Decimal(str(pos.activo.ratio))
        promedio = pos.precio_promedio_usd
        actual = pos.activo.precio_actual_usd
        
        # ==========================================
        # NUEVO: RENDIMIENTO DIARIO DEL ACTIVO
        # ==========================================
        # Buscamos la última "foto" que el bot le sacó a ESTE activo para ESTE usuario
        ultimo_historico = HistoricoActivo.objects.filter(
            snapshot_global__usuario=request.user,
            activo=pos.activo
        ).order_by('-snapshot_global__fecha').first()

        rendimiento_diario_porcentaje = Decimal('0.0')
        ganancia_diaria_usd = Decimal('0.0')

        if ultimo_historico and ultimo_historico.precio_usd_diario > Decimal('0.0'):
            precio_ayer = ultimo_historico.precio_usd_diario
            
            # Variación %: (Precio Hoy / Precio Ayer - 1) * 100
            rendimiento_diario_porcentaje = ((actual / precio_ayer) - Decimal('1.0')) * Decimal('100.0')
            
            # Ganancia en $: (Precio Hoy - Precio Ayer) * Cantidad de Acciones
            ganancia_diaria_usd = (actual - precio_ayer) * acciones_enteras
        
        # ==========================================

        if promedio is not None and actual is not None:
            detalles.append({
                "ticker": pos.activo.ticker,
                "nombre": pos.activo.nombre,
                "nominales": pos.cantidad_nominales,
                "precio_promedio": promedio,
                "precio_actual": actual,
                "bolsillo_usd": round(acciones_enteras * promedio, 2),
                "valor_actual_usd": round(acciones_enteras * actual, 2),
                
                # Histórico (Desde que compraste)
                "rendimiento_porcentaje": pos.rendimiento_porcentaje,
                "ganancia_neta_usd": round((acciones_enteras * actual) - (acciones_enteras * promedio), 2),
                
                # Diario (Solo el movimiento de hoy)
                "rendimiento_diario_porcentaje": round(rendimiento_diario_porcentaje, 2),
                "ganancia_diaria_usd": round(ganancia_diaria_usd, 2)
            })

    return Response(detalles)

# 3. Evolución del Portfolio (Gráfico)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def evolucion_portfolio(request):
    # Filtramos por el usuario actual
    historicos = HistoricoPortfolio.objects.filter(usuario=request.user).order_by('fecha')
    
    data = []
    for h in historicos:
        data.append({
            "fecha": h.fecha,
            "invertido": h.total_invertido_usd,
            "valor_actual": h.valor_actual_usd,
            "ganancia": h.valor_actual_usd - h.total_invertido_usd
        })
    
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
    fecha_inicio = request.query_params.get('inicio')
    fecha_fin = request.query_params.get('fin')
    
    if not fecha_inicio or not fecha_fin:
        return Response({"error": "Faltan las fechas de inicio y fin"}, status=400)
    
    # 1. Calculamos tu TWR (Tu ganancia real aislada de tus depósitos/retiros)
    resultado_twr = calcular_twr_periodo(request.user, fecha_inicio, fecha_fin)
    
    print(resultado_twr)

# 2. Calculamos el rendimiento del SPY para el mismo exacto periodo
    rendimiento_spy = Decimal('0.0')
    try:
        fecha_inicio_dt = datetime.strptime(fecha_inicio, '%Y-%m-%d')
        fecha_inicio_segura = (fecha_inicio_dt - timedelta(days=5)).strftime('%Y-%m-%d')
        
        fecha_fin_dt = datetime.strptime(fecha_fin, '%Y-%m-%d') + timedelta(days=1)
        fecha_fin_yf = fecha_fin_dt.strftime('%Y-%m-%d')
        
        import logging
        logging.getLogger('yfinance').setLevel(logging.CRITICAL) 
        
        spy_data = yf.download('SPY', start=fecha_inicio_segura, end=fecha_fin_yf, progress=False)
        
        if not spy_data.empty:
            # EL ARREGLO: .squeeze() rompe la tabla anidada de yfinance y nos deja solo los números puros
            close_data = spy_data['Close'].squeeze()
            
            # Filtramos usando nuestra nueva lista de números limpios
            data_inicio = close_data[close_data.index <= fecha_inicio]
            
            if not data_inicio.empty:
                precio_inicio = Decimal(str(float(data_inicio.iloc[-1])))
            else:
                precio_inicio = Decimal(str(float(close_data.iloc[0])))
                
            precio_fin = Decimal(str(float(close_data.iloc[-1])))
            
            # Matemática del rendimiento
            rendimiento_spy = round(((precio_fin / precio_inicio) - Decimal('1.0')) * Decimal('100.0'), 2)
            
    except Exception as e:
        print(f"Error al traer el SPY desde Yahoo Finance: {e}")
        rendimiento_spy = Decimal('0.0')

    # 3. Calculamos la diferencia (El famoso "Alpha")
    diferencia_vs_spy = resultado_twr - rendimiento_spy

    return Response({
        "periodo": f"{fecha_inicio} al {fecha_fin}",
        "tu_rendimiento_twr": resultado_twr,
        "rendimiento_spy": rendimiento_spy,
        "alpha_diferencia": diferencia_vs_spy # Si es positivo, le ganaste al mercado. Si es negativo, ganó el SPY.
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
    # 1. Calculamos cuánto vale tu portfolio REAL hoy
    posiciones = Posicion.objects.filter(usuario=request.user, cantidad_nominales__gt=0)
    
    total_bolsillo = Decimal('0.0')
    total_actual = Decimal('0.0')

    for pos in posiciones:
        acciones_enteras = Decimal(str(pos.cantidad_nominales)) / Decimal(str(pos.activo.ratio))
        promedio = pos.precio_promedio_usd
        actual = pos.activo.precio_actual_usd
        
        if promedio is not None and actual is not None:
            total_bolsillo += (acciones_enteras * promedio)
            total_actual += (acciones_enteras * actual)
            
    # 2. Corremos la simulación de la Sombra
    resultado_sombra = calcular_portfolio_sombra_spy(request.user)
    
    if not resultado_sombra:
        return Response({"error": "No hay operaciones suficientes o falló Yahoo Finance"}, status=400)
        
    valor_sombra_usd = resultado_sombra['valor_sombra_spy_usd']

   # 3. Rendimiento % (con protección por si vaciaste la cuenta)
    rendimiento_spy = Decimal('0.0')
    rendimiento_portfolio = Decimal('0.0')

    if total_bolsillo > Decimal('0.0'):
        # Pasamos a Decimal el valor que viene del diccionario por las dudas
        valor_sombra_decimal = Decimal(str(resultado_sombra['valor_sombra_spy_usd']))
        
        # ¡Multiplicamos por 100.0 para que sea porcentaje!
        rendimiento_spy = ((valor_sombra_decimal - total_bolsillo) / total_bolsillo) * Decimal('100.0')
        rendimiento_portfolio = ((total_actual - total_bolsillo) / total_bolsillo) * Decimal('100.0')

    print(rendimiento_spy)
    
    # 3. La verdad de la milanesa: El "Alpha" en dólares
    alpha_usd = total_actual - valor_sombra_usd
    
    # Si alpha es positivo -> Sos mejor que el SPY.
    # Si alpha es negativo -> El SPY te ganó.
    
    return Response({
        "capital_bolsillo_usd": resultado_sombra['capital_invertido_usd'],
        "tu_portfolio_real_usd": round(total_actual, 2),
  
        "tu_portfolio_real_porcentaje": round(rendimiento_portfolio, 2), 
        
        "portfolio_sombra_spy_usd": resultado_sombra['valor_sombra_spy_usd'],
        "portfolio_sombra_spy_porcentaje": round(rendimiento_spy, 2),
        
        "diferencia_alpha_usd": round(alpha_usd, 2),
        "ganador": "Usuario" if alpha_usd > 0 else "SPY"
    })

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