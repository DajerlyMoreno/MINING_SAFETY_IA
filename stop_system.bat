@echo off
chcp 65001 >nul
title Detener Sistema Multiagente

echo.
echo ════════════════════════════════════════════════════════
echo   Deteniendo Sistema Multiagente Mineria - UPTC 2026
echo ════════════════════════════════════════════════════════
echo.

:: Matar procesos uvicorn en los puertos del sistema
echo Terminando procesos uvicorn...

for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000 " ^| findstr LISTENING') do (
    echo   Deteniendo puerto 8000 (PID %%a)...
    taskkill /PID %%a /F >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8001 " ^| findstr LISTENING') do (
    echo   Deteniendo puerto 8001 (PID %%a)...
    taskkill /PID %%a /F >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8002 " ^| findstr LISTENING') do (
    echo   Deteniendo puerto 8002 (PID %%a)...
    taskkill /PID %%a /F >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8003 " ^| findstr LISTENING') do (
    echo   Deteniendo puerto 8003 (PID %%a)...
    taskkill /PID %%a /F >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8004 " ^| findstr LISTENING') do (
    echo   Deteniendo puerto 8004 (PID %%a)...
    taskkill /PID %%a /F >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8005 " ^| findstr LISTENING') do (
    echo   Deteniendo puerto 8005 (PID %%a)...
    taskkill /PID %%a /F >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":3000 " ^| findstr LISTENING') do (
    echo   Deteniendo puerto 3000 - React (PID %%a)...
    taskkill /PID %%a /F >nul 2>&1
)

:: Cerrar las ventanas de cmd del sistema por titulo
taskkill /FI "WINDOWTITLE eq Agente Gases :8001" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Agente Imagenes :8002" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Agente Geomecanico :8003" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Agente Monitor :8004" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Orquestador Central :8000" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Simulador Sensores :8005" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Dashboard React :3000" /F >nul 2>&1

echo.
echo   Sistema detenido correctamente.
echo.
pause
