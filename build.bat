@echo off
echo ====================================================
echo COMPILANDO SOFTWARE KEYBOARD WEDGE PARA BALANZA POS
echo ====================================================

python -m pip install -r requirements.txt

pyinstaller --noconsole --onefile --name "ScaleWedgePOS" scale_wedge.py

echo.
echo ====================================================
echo Compilacion finalizada con exito!
echo El ejecutable final esta en: dist\ScaleWedgePOS.exe
echo ====================================================
pause
