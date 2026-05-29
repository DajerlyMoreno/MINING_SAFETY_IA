@echo off
chcp 65001 >nul 2>&1
title Detener Sistema Multiagente

echo.
echo ============================================================
echo   Deteniendo Sistema Multiagente Mineria UPTC 2026
echo ============================================================
echo.

echo Terminando procesos en puertos del sistema...
echo.

:: Puertos del backend y frontend
set PUERTOS=8000 8001 8002 8003 8004 8005 3000 5173

for %%P in (%PUERTOS%) do (
    for /f "tokens=5" %%A in ('netstat -aon 2^>nul ^| findstr /R "[ :]%%P " ^| findstr "LISTENING"') do (
        if not "%%A"=="" (
            echo   Puerto %%P - PID %%A - deteniendo...
            taskkill /PID %%A /F >nul 2>&1
        )
    )
)

echo.
echo Cerrando ventanas del sistema por titulo...

taskkill /FI "WINDOWTITLE eq Orquestador :8000" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Agente Gases :8001" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Agente Imagenes :8002" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Agente Geomecanico :8003" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Agente Monitor :8004" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Simulador :8005" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Dashboard React" /F >nul 2>&1

:: Matar todos los uvicorn como red de seguridad
echo Limpiando procesos uvicorn restantes...
taskkill /IM uvicorn.exe /F >nul 2>&1
taskkill /F /FI "IMAGENAME eq python.exe" /FI "WINDOWTITLE eq *uvicorn*" >nul 2>&1

echo.
echo ============================================================
echo   Sistema detenido.
echo ============================================================
echo.
pause
