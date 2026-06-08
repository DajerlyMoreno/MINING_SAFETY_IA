@echo off
title Detener Sistema Multiagente

echo.
echo ============================================================
echo   Deteniendo Sistema Multiagente Mineria IA - UPTC 2026
echo ============================================================
echo.

echo Terminando procesos por puerto...
echo.

REM Puertos: 8000-8007 (todos los servicios) + 3000 React + 5173 Vite
set PUERTOS=8000 8001 8002 8003 8004 8005 8006 8007 3000 5173

for %%P in (%PUERTOS%) do (
    for /f "tokens=5" %%A in ('netstat -aon 2^>nul ^| findstr /R "[ :]%%P " ^| findstr "LISTENING"') do (
        if not "%%A"=="" (
            echo   Puerto %%P - PID %%A - deteniendo...
            taskkill /PID %%A /F >nul 2>&1
        )
    )
)

echo.
echo Cerrando ventanas por titulo...

taskkill /FI "WINDOWTITLE eq Orquestador :8007"        /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Agente Gases :8001"       /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Agente Imagenes :8002"    /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Agente Geomecanico :8003" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Agente Monitor :8004"     /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Simulador :8005"          /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Bot WhatsApp :8006"       /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Dashboard React :3000"    /F >nul 2>&1

echo Limpiando procesos uvicorn restantes...
taskkill /IM uvicorn.exe /F >nul 2>&1

echo.
echo ============================================================
echo   Sistema detenido. Puertos 8000-8007 y 3000 liberados.
echo ============================================================
echo.
pause
