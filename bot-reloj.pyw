import time
import subprocess
import datetime
import os

RUTA_BAT = r"C:\dev\stock-manager\sacar-foto.bat"
RUTA_MEMORIA = r"C:\dev\stock-manager\memoria-bot.txt"

def disparar_bat():
    subprocess.run([RUTA_BAT], creationflags=subprocess.CREATE_NO_WINDOW)

while True:
    ahora = datetime.datetime.now()
    
    if ahora.weekday() < 5 and ahora.hour >= 18:
        fecha_hoy = ahora.strftime("%Y-%m-%d")
        ya_se_saco_hoy = False
        
        if os.path.exists(RUTA_MEMORIA):
            with open(RUTA_MEMORIA, "r") as f:
                ultima_fecha_guardada = f.read().strip()
                if ultima_fecha_guardada == fecha_hoy:
                    ya_se_saco_hoy = True
        
        if not ya_se_saco_hoy:
            disparar_bat()
            with open(RUTA_MEMORIA, "w") as f:
                f.write(fecha_hoy)
    
    time.sleep(300)