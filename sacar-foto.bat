@echo off
:: carpeta del proyecto
cd "C:\dev\stock-manager\"

call env\Scripts\activate.bat

python manage.py tomar_foto

deactivate