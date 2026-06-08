@echo off
setlocal EnableDelayedExpansion

REM ============================================================================
REM start_system.bat
REM Sistema Multiagente Mineria Subterranea IA - UPTC 2026
REM
REM Servicios:
REM   8007 - Orquestador Central (LangGraph + LLM + RAG)
REM   8001 - Agente de Gases     (LSTM + IsolationForest)
REM   8002 - Agente de Imagenes  (vision artificial)
REM   8003 - Agente Geomecanico  (extensometros / convergimetros)
REM   8004 - Agente Monitor      (gemelo digital de la mina)
REM   8005 - Simulador           (datos sinteticos AR(1))
REM   8006 - Bot WhatsApp        (Twilio / Meta / chat web)
REM   3000 - Dashboard React     (frontend)
REM
REM Variables opcionales en .env:
REM   GEMINI_API_KEY=AIza...
REM   TWILIO_ACCOUNT_SID=...
REM   TWILIO_AUTH_TOKEN=...
REM   WHATSAPP_ALERTAS=+573001234567
REM
REM Uso:
REM   start_system.bat               -> todo el sistema + frontend
REM   start_system.bat --solo-backend -> solo backend sin React
REM ============================================================================

title Sistema Multiagente Mineria IA - UPTC 2026

set "ARG=%~1"
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

cd /d "%ROOT%"

echo.
echo ==========================================================
echo   SISTEMA MULTIAGENTE MINERIA IA - UPTC 2026
echo ==========================================================
echo   Puerto  Servicio
echo   ------  -----------------------------------------
echo   8007    Orquestador Central (LangGraph + LLM)
echo   8001    Agente Gases        (LSTM)
echo   8002    Agente Imagenes
echo   8003    Agente Geomecanico
echo   8004    Agente Monitor      (gemelo digital)
echo   8005    Simulador
echo   8006    Bot WhatsApp
echo   3000    Dashboard React
echo ==========================================================
echo.

REM ============================================================================
REM 1. ENTORNO VIRTUAL
REM ============================================================================

echo [1/6] Entorno virtual Python...

if not exist "%ROOT%\env\Scripts\activate.bat" (
    echo     Creando entorno virtual...
    python -m venv env
    if errorlevel 1 (
        echo ERROR: No se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
)

call "%ROOT%\env\Scripts\activate.bat"
if errorlevel 1 (
    echo ERROR: No se pudo activar el entorno virtual.
    pause
    exit /b 1
)
echo     OK

REM ============================================================================
REM 2. DEPENDENCIAS
REM ============================================================================

echo.
echo [2/6] Instalando dependencias Python...

pip install -r "%ROOT%\requirements.txt" -q
if errorlevel 1 (
    echo ERROR: Fallo instalando dependencias.
    pause
    exit /b 1
)
echo     OK

REM ============================================================================
REM 3. VERIFICAR CONFIGURACION
REM ============================================================================

echo.
echo [3/6] Verificando configuracion y modelos...

python -c "from backend.shared.config import settings; errores=settings.model_paths.validate(); [print('  ADVERTENCIA: '+e) for e in errores]; import os; k=os.getenv('GEMINI_API_KEY',''); print('  LLM: Gemini 2.0 Flash' if k else '  LLM: Fallback (sin GEMINI_API_KEY)')"

echo.

REM ============================================================================
REM 4. AGENTES ESPECIALIZADOS (Capa 3)
REM ============================================================================

echo [4/6] Iniciando agentes especializados...

start "Agente Gases :8001" /d "%ROOT%" cmd /k "call env\Scripts\activate.bat && uvicorn backend.agentes.gases.app:app --host 127.0.0.1 --port 8001 --log-level warning"
timeout /t 4 /nobreak >nul
echo     OK Agente Gases       :8001

start "Agente Imagenes :8002" /d "%ROOT%" cmd /k "call env\Scripts\activate.bat && uvicorn backend.agentes.imagenes.app:app --host 127.0.0.1 --port 8002 --log-level warning"
timeout /t 3 /nobreak >nul
echo     OK Agente Imagenes    :8002

start "Agente Geomecanico :8003" /d "%ROOT%" cmd /k "call env\Scripts\activate.bat && uvicorn backend.agentes.geomecanico.app:app --host 127.0.0.1 --port 8003 --log-level warning"
timeout /t 3 /nobreak >nul
echo     OK Agente Geomecanico :8003

start "Agente Monitor :8004" /d "%ROOT%" cmd /k "call env\Scripts\activate.bat && uvicorn backend.agentes.monitor.app:app --host 127.0.0.1 --port 8004 --log-level warning"
timeout /t 3 /nobreak >nul
echo     OK Agente Monitor     :8004

REM ============================================================================
REM 5. BOT WHATSAPP + ORQUESTADOR + SIMULADOR
REM ============================================================================

echo.
echo [5/6] Iniciando orquestador, bot y simulador...

start "Bot WhatsApp :8006" /d "%ROOT%" cmd /k "call env\Scripts\activate.bat && uvicorn backend.whatsapp.app:app --host 127.0.0.1 --port 8006 --log-level warning"
timeout /t 3 /nobreak >nul
echo     OK Bot WhatsApp       :8006

start "Orquestador :8007" /d "%ROOT%" cmd /k "call env\Scripts\activate.bat && uvicorn backend.orquestador.app:app --host 127.0.0.1 --port 8007 --log-level info"
timeout /t 6 /nobreak >nul
echo     OK Orquestador        :8007

start "Simulador :8005" /d "%ROOT%" cmd /k "call env\Scripts\activate.bat && uvicorn backend.simulacion.simulador:sim_app --host 127.0.0.1 --port 8005 --log-level warning"
timeout /t 3 /nobreak >nul
echo     OK Simulador          :8005

REM ============================================================================
REM 6. FRONTEND REACT (Dashboard)
REM ============================================================================

echo.
echo [6/6] Dashboard React...

if /i "%ARG%"=="--solo-backend" (
    echo     Omitido.
    goto :resumen
)

if not exist "%ROOT%\frontend\package.json" (
    echo     AVISO: frontend\package.json no encontrado.
    goto :resumen
)

if not exist "%ROOT%\frontend\node_modules" (
    echo     Instalando dependencias pnpm...
    cd /d "%ROOT%\frontend"
    pnpm install
    cd /d "%ROOT%"
)

start "Dashboard React :3000" /d "%ROOT%\frontend" cmd /k "pnpm run dev -- --port 3000"
timeout /t 3 /nobreak >nul
echo     OK Dashboard React    :3000

REM ============================================================================
REM RESUMEN
REM ============================================================================

:resumen
echo.
echo ==========================================================
echo   SISTEMA INICIADO
echo ==========================================================
echo.
echo   Swagger UI:
echo     Orquestador : http://localhost:8007/docs
echo     Gases       : http://localhost:8001/docs
echo     Imagenes    : http://localhost:8002/docs
echo     Geomecanico : http://localhost:8003/docs
echo     Monitor     : http://localhost:8004/docs
echo     Simulador   : http://localhost:8005/docs
echo     WhatsApp    : http://localhost:8006/docs
echo.
echo   Dashboard   : http://localhost:3000
echo.
echo   Simular ciclo:
echo     curl -X POST http://localhost:8005/simular?zona=Frente_A_Sogamoso
echo.
echo   Chat bot WhatsApp:
echo     curl -X POST http://localhost:8006/chat -H "Content-Type: application/json" -d "{\"mensaje\":\"estado\"}"
echo.
echo   Para detener: stop_system.bat
echo ==========================================================
echo.

pause
