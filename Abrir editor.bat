@echo off
cd /d "%~dp0"
echo Comprobando numpy...
py -m pip install --quiet --disable-pip-version-check numpy
py pes21editor.py
if errorlevel 1 pause
