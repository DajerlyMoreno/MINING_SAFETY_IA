@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

:: ════════════════════════════════════════════════════════════════════════════
:: start_system.bat — Inicia todos los servicios del sistema multiagente.
:: Uso:
::   start_system.bat              → inicia todo (backend + frontend)
::   start_system.bat --sin-frontend
::   start_system.bat --solo-backend
::
:: Requisitos:
::   - Python 3.10+ instalado y en PATH
::   - Node.js instalado y en PATH (solo si se usa el frontend)
::   - Entorno virtual en carpeta "env\" (creado automáticamente si no existe)
:: ════════════════════════════════════════════════════════════════════════════

title Sistema Multiagente Mineria UPTC 2026

set "ARG=%~1"
set "PROJECT_ROOT=%~dp0"
:: Quitar barra final
if "%PROJECT_ROOT:~-1%"=="\" set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"
cd /d "%PROJECT_ROOT%"

echo.
echo ════════════════════════════════════════════════════════
echo   Sistema Multiagente Mineria - UPTC 2026
echo   Iniciando servicios en Windows 11...
echo ════════════════════════════════════════════════════════
echo.

:: ── 0. Entorno virtual ───────────────────────────────────────────────────────
if not exist "env\Scripts\activate.bat" (
    echo [1/7] Creando entorno virtual...
    python -m venv env
    if errorlevel 1 (
        echo ERROR: No se pudo crear el entorno virtual.
        echo Verifica que Python este instalado: python --version
        pause & exit /b 1
    )
    echo       Entorno virtual creado en env\
) else (
    echo [1/7] Entorno virtual encontrado: env\
)

:: Activar entorno virtual
call env\Scripts\activate.bat
echo       Activado: %VIRTUAL_ENV%

:: ── 1. Dependencias Python ───────────────────────────────────────────────────
echo.
echo [2/7] Instalando/verificando dependencias Python...
pip install -q -r requirements.txt
if errorlevel 1 (
    echo ERROR: Fallo al instalar dependencias.
    echo Revisa requirements.txt y tu conexion a internet.
    pause & exit /b 1
)
echo       Dependencias OK

:: ── 2. Verificar modelos ─────────────────────────────────────────────────────
echo.
echo [3/7] Verificando modelos entrenados...
python -c "
import sys
try:
    from backend.shared.config import settings
    errores = settings.model_paths.validate()
    if errores:
        print('ADVERTENCIAS:')
        for e in errores: print(f'  {e}')
    else:
        print('  Todos los modelos encontrados')
except Exception as e:
    print(f'  Advertencia config: {e}')
    sys.exit(0)
"

:: ── 3. Base de datos ─────────────────────────────────────────────────────────
echo.
echo [4/7] Inicializando base de datos...
python -c "
import asyncio, sys
try:
    from backend.db.database import init_db
    asyncio.run(init_db())
    print('  Base de datos lista')
except Exception as e:
    print(f'  Advertencia DB: {e}')
    sys.exit(0)
"

:: ── 4. Agentes especializados (cada uno en su propia ventana) ────────────────
echo.
echo [5/7] Iniciando agentes especializados...

:: Agente de Gases — Puerto 8001
start "Agente Gases :8001" cmd /k "^
    cd /d "%PROJECT_ROOT%" ^& ^
    call env\Scripts\activate.bat ^& ^
    echo [AGENTE GASES] Iniciando en puerto 8001... ^& ^
    uvicorn backend.agentes.gases.app:app --host 127.0.0.1 --port 8001 --log-level warning"

:: Agente de Imagenes — Puerto 8002
start "Agente Imagenes :8002" cmd /k "^
    cd /d "%PROJECT_ROOT%" ^& ^
    call env\Scripts\activate.bat ^& ^
    echo [AGENTE IMAGENES] Iniciando en puerto 8002... ^& ^
    uvicorn backend.agentes.imagenes.app:app --host 127.0.0.1 --port 8002 --log-level warning"

:: Agente Geomecanico — Puerto 8003
start "Agente Geomecanico :8003" cmd /k "^
    cd /d "%PROJECT_ROOT%" ^& ^
    call env\Scripts\activate.bat ^& ^
    echo [AGENTE GEOMECANICO] Iniciando en puerto 8003... ^& ^
    uvicorn backend.agentes.geomecanico.app:app --host 127.0.0.1 --port 8003 --log-level warning"

:: Agente Monitor — Puerto 8004
start "Agente Monitor :8004" cmd /k "^
    cd /d "%PROJECT_ROOT%" ^& ^
    call env\Scripts\activate.bat ^& ^
    echo [AGENTE MONITOR] Iniciando en puerto 8004... ^& ^
    uvicorn backend.agentes.monitor.app:app --host 127.0.0.1 --port 8004 --log-level warning"

echo       Esperando 6 segundos para que los agentes levanten...
timeout /t 6 /nobreak >nul
echo       Agentes especializados iniciados (8001-8004)

:: ── 5. Orquestador Central — Puerto 8000 ────────────────────────────────────
echo.
echo [6/7] Iniciando Orquestador Central...

start "Orquestador Central :8000" cmd /k "^
    cd /d "%PROJECT_ROOT%" ^& ^
    call env\Scripts\activate.bat ^& ^
    echo [ORQUESTADOR] Iniciando en puerto 8000... ^& ^
    uvicorn backend.orquestador.app:app --host 127.0.0.1 --port 8000 --log-level info"

timeout /t 4 /nobreak >nul
echo       Orquestador listo

:: Simulador — Puerto 8005
start "Simulador Sensores :8005" cmd /k "^
    cd /d "%PROJECT_ROOT%" ^& ^
    call env\Scripts\activate.bat ^& ^
    echo [SIMULADOR] Iniciando en puerto 8005... ^& ^
    uvicorn backend.simulacion.simulador:sim_app --host 127.0.0.1 --port 8005 --log-level warning"

timeout /t 2 /nobreak >nul

:: ── 6. Frontend React — Puerto 3000 ─────────────────────────────────────────
if /i not "%ARG%"=="--sin-frontend" if /i not "%ARG%"=="--solo-backend" (
    echo.
    echo [7/7] Iniciando Dashboard React...
    if exist "frontend\package.json" (
        if not exist "frontend\node_modules" (
            echo       Instalando dependencias npm...
            cd frontend
            npm install
            cd ..
        )
        start "Dashboard React :3000" cmd /k "^
            cd /d "%PROJECT_ROOT%\frontend" ^& ^
            echo [REACT] Iniciando en puerto 3000... ^& ^
            npm run dev -- --port 3000"
    ) else (
        echo       AVISO: No se encontro frontend\package.json
        echo       Crea el proyecto React con: npm create vite@latest frontend
    )
) else (
    echo [7/7] Frontend omitido por parametro %ARG%
)

:: ── Resumen ──────────────────────────────────────────────────────────────────
echo.
echo ════════════════════════════════════════════════════════
echo   Sistema iniciado. Servicios disponibles:
echo.
echo   Orquestador:      http://localhost:8000/docs
echo   Agente Gases:     http://localhost:8001/docs
echo   Agente Imagenes:  http://localhost:8002/docs
echo   Agente Geo:       http://localhost:8003/docs
echo   Agente Monitor:   http://localhost:8004/docs
echo   Simulador:        http://localhost:8005/docs
echo   Dashboard React:  http://localhost:3000
echo.
echo   Para iniciar la simulacion automatica ejecuta:
echo   curl -X POST http://localhost:8005/iniciar
echo.
echo   Para detener todo el sistema ejecuta:
echo   stop_system.bat
echo ════════════════════════════════════════════════════════
echo.
echo Cada servicio corre en su propia ventana de cmd.
echo Cierra las ventanas individualmente o ejecuta stop_system.bat
echo.
pause
