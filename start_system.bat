@echo off
setlocal EnableDelayedExpansion

REM ============================================================================
REM start_system.bat
REM Sistema Multiagente Mineria
REM Version actual:
REM - Orquestador
REM - Agente de Gases
REM - Simulador
REM ============================================================================

title Sistema Multiagente Mineria UPTC 2026

set "ARG=%~1"
set "PROJECT_ROOT=%~dp0"

REM Eliminar barra final
if "%PROJECT_ROOT:~-1%"=="\" (
    set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"
)

cd /d "%PROJECT_ROOT%"

echo.
echo ==========================================================
echo   Sistema Multiagente Mineria - UPTC 2026
echo ==========================================================
echo   Servicios:
echo   - Orquestador
echo   - Agente de Gases
echo   - Simulador
echo ==========================================================
echo.

REM ============================================================================
REM 1. ENTORNO VIRTUAL
REM ============================================================================

if not exist "env\Scripts\activate.bat" (
    echo [1/5] Creando entorno virtual...

    python -m venv env

    if errorlevel 1 (
        echo ERROR: No se pudo crear el entorno virtual.
        pause
        exit /b 1
    )

    echo Entorno virtual creado.
) else (
    echo [1/5] Entorno virtual encontrado.
)

call env\Scripts\activate.bat

if errorlevel 1 (
    echo ERROR: No se pudo activar el entorno virtual.
    pause
    exit /b 1
)

echo Entorno virtual activado.

REM ============================================================================
REM 2. DEPENDENCIAS
REM ============================================================================

echo.
echo [2/5] Instalando dependencias Python...

pip install -r requirements.txt

if errorlevel 1 (
    echo ERROR: Fallo instalando dependencias.
    pause
    exit /b 1
)

echo Dependencias instaladas correctamente.

REM ============================================================================
REM 3. VERIFICAR CONFIGURACION
REM ============================================================================

echo.
echo [3/5] Verificando configuracion...

python -c "from backend.shared.config import settings; print('Configuracion OK')"

echo.

REM ============================================================================
REM 4. AGENTE DE GASES
REM ============================================================================

echo [4/5] Iniciando Agente de Gases...

start "Agente Gases" cmd /k "cd /d %PROJECT_ROOT% && call env\Scripts\activate.bat && uvicorn backend.agentes.gases.app:app --host 127.0.0.1 --port 8001"

timeout /t 5 /nobreak >nul

echo Agente de Gases iniciado en puerto 8001.

REM ============================================================================
REM 5. ORQUESTADOR
REM ============================================================================

echo.
echo Iniciando Orquestador...

start "Orquestador" cmd /k "cd /d %PROJECT_ROOT% && call env\Scripts\activate.bat && uvicorn backend.orquestador.app:app --host 127.0.0.1 --port 8000"

timeout /t 5 /nobreak >nul

echo Orquestador iniciado en puerto 8000.

REM ============================================================================
REM 6. SIMULADOR
REM ============================================================================

echo.
echo Iniciando Simulador...

start "Simulador" cmd /k "cd /d %PROJECT_ROOT% && call env\Scripts\activate.bat && uvicorn backend.simulacion.simulador:sim_app --host 127.0.0.1 --port 8005"

timeout /t 3 /nobreak >nul

echo Simulador iniciado en puerto 8005.

REM ============================================================================
REM 7. FRONTEND
REM ============================================================================

if /i not "%ARG%"=="--sin-frontend" if /i not "%ARG%"=="--solo-backend" (

    echo.
    echo [5/5] Verificando frontend...

    if exist "frontend\package.json" (

        if not exist "frontend\node_modules" (
            echo Instalando dependencias pnpm...
            cd frontend
            pnpm install
            cd ..
        )

        start "Frontend React" cmd /k "cd /d %PROJECT_ROOT%\frontend && pnpm run dev -- --port 3000"

        echo Frontend iniciado en puerto 3000.

    ) else (

        echo AVISO:
        echo frontend\package.json no encontrado.
    )

) else (

    echo.
    echo Frontend omitido.
)

REM ============================================================================
REM RESUMEN
REM ============================================================================

echo.
echo ==========================================================
echo SISTEMA INICIADO
echo ==========================================================
echo.
echo Orquestador:
echo http://localhost:8000/docs
echo.
echo Agente de Gases:
echo http://localhost:8001/docs
echo.
echo Simulador:
echo http://localhost:8005/docs
echo.
echo Frontend:
echo http://localhost:3000
echo.
echo Simular ciclo:
echo curl -X POST "http://localhost:8005/simular?zona=Frente_A_Sogamoso"
echo.
echo Iniciar simulacion continua:
echo curl -X POST http://localhost:8005/iniciar
echo.
echo ==========================================================
echo.

pause