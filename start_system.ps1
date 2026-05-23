# start_system.ps1
# ════════════════════════════════════════════════════════════════════════════
# Inicia todos los servicios del sistema multiagente en Windows 11.
# Uso:
#   .\start_system.ps1                    -> todo (backend + frontend)
#   .\start_system.ps1 -SinFrontend       -> solo backend
#   .\start_system.ps1 -SoloBackend       -> solo backend
#
# Si PowerShell bloquea la ejecucion, ejecuta primero en PowerShell admin:
#   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
# ════════════════════════════════════════════════════════════════════════════

param(
    [switch]$SinFrontend,
    [switch]$SoloBackend
)

$ErrorActionPreference = "Stop"
$HOST.UI.RawUI.WindowTitle = "Sistema Multiagente Mineria UPTC 2026"

# Colores en PowerShell
function Write-Header($msg) { Write-Host "`n$("=" * 56)" -ForegroundColor Cyan
                               Write-Host "  $msg" -ForegroundColor White
                               Write-Host $("=" * 56) -ForegroundColor Cyan }
function Write-Ok($msg)     { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Info($msg)   { Write-Host "  [>>] $msg" -ForegroundColor Yellow }
function Write-Err($msg)    { Write-Host "  [!!] $msg" -ForegroundColor Red }
function Write-Step($n,$msg){ Write-Host "`n[$n/7] $msg" -ForegroundColor Cyan }

# ── Directorio raíz ──────────────────────────────────────────────────────────
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ROOT

Write-Header "Sistema Multiagente Mineria - UPTC 2026"
Write-Host "  Directorio: $ROOT" -ForegroundColor Gray

# ── 1. Entorno virtual ───────────────────────────────────────────────────────
Write-Step 1 "Entorno virtual Python"

$VENV_ACTIVATE = Join-Path $ROOT "env\Scripts\Activate.ps1"
$VENV_PYTHON   = Join-Path $ROOT "env\Scripts\python.exe"
$VENV_UVICORN  = Join-Path $ROOT "env\Scripts\uvicorn.exe"

if (-not (Test-Path $VENV_ACTIVATE)) {
    Write-Info "Creando entorno virtual en env\ ..."
    python -m venv env
    if ($LASTEXITCODE -ne 0) {
        Write-Err "No se pudo crear el entorno virtual. Verifica: python --version"
        Read-Host "Presiona Enter para salir"; exit 1
    }
}
Write-Ok "Entorno virtual: env\"

# Activar en esta sesión de PS
& $VENV_ACTIVATE
Write-Ok "Activado: $env:VIRTUAL_ENV"

# ── 2. Dependencias ──────────────────────────────────────────────────────────
Write-Step 2 "Dependencias Python"
Write-Info "Instalando desde requirements.txt..."
& $VENV_PYTHON -m pip install -q -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Err "Fallo al instalar dependencias. Revisa requirements.txt."
    Read-Host "Presiona Enter para salir"; exit 1
}
Write-Ok "Dependencias instaladas"

# ── 3. Verificar modelos ─────────────────────────────────────────────────────
Write-Step 3 "Verificando modelos entrenados"
& $VENV_PYTHON -c @"
try:
    from backend.shared.config import settings
    errores = settings.model_paths.validate()
    if errores:
        [print(f'  FALTA: {e}') for e in errores]
    else:
        print('  Todos los modelos encontrados')
except Exception as e:
    print(f'  (config no disponible aun: {e})')
"@

# ── 4. Base de datos ─────────────────────────────────────────────────────────
Write-Step 4 "Base de datos"
& $VENV_PYTHON -c @"
import asyncio, sys
try:
    from backend.db.database import init_db
    asyncio.run(init_db())
    print('  Base de datos lista')
except Exception as e:
    print(f'  Advertencia: {e}')
"@

# ── Función auxiliar: abrir servicio en nueva ventana ────────────────────────
function Start-Servicio {
    param($Titulo, $Puerto, $Modulo, $LogLevel = "warning")

    $cmd = "cd '$ROOT'; " +
           "& '$VENV_ACTIVATE'; " +
           "Write-Host '[" + $Titulo + "] Iniciando en puerto $Puerto...' -ForegroundColor Green; " +
           "& '$VENV_UVICORN' $Modulo --host 127.0.0.1 --port $Puerto --log-level $LogLevel; " +
           "Write-Host 'Servicio detenido. Presiona Enter para cerrar.' -ForegroundColor Red; " +
           "Read-Host"

    Start-Process powershell -ArgumentList "-NoExit", "-Command", $cmd `
                 -WindowStyle Normal `
                 -PassThru
}

# ── 5. Agentes especializados ────────────────────────────────────────────────
Write-Step 5 "Agentes especializados"

$procs = @()
$procs += Start-Servicio "AGENTE GASES"       8001 "backend.agentes.gases.app:app"
$procs += Start-Servicio "AGENTE IMAGENES"    8002 "backend.agentes.imagenes.app:app"
$procs += Start-Servicio "AGENTE GEOMECANICO" 8003 "backend.agentes.geomecanico.app:app"
$procs += Start-Servicio "AGENTE MONITOR"     8004 "backend.agentes.monitor.app:app"

Write-Info "Esperando 6 segundos para que los agentes levanten..."
Start-Sleep -Seconds 6
Write-Ok "Agentes especializados iniciados (8001-8004)"

# ── 6. Orquestador y Simulador ───────────────────────────────────────────────
Write-Step 6 "Orquestador Central y Simulador"

$procs += Start-Servicio "ORQUESTADOR" 8000 "backend.orquestador.app:app" "info"
Start-Sleep -Seconds 4
Write-Ok "Orquestador listo (8000)"

$procs += Start-Servicio "SIMULADOR" 8005 "backend.simulacion.simulador:sim_app"
Start-Sleep -Seconds 2
Write-Ok "Simulador listo (8005)"

# ── 7. Frontend React ────────────────────────────────────────────────────────
Write-Step 7 "Dashboard React"

if (-not $SinFrontend -and -not $SoloBackend) {
    $frontendPath = Join-Path $ROOT "frontend"
    if (Test-Path (Join-Path $frontendPath "package.json")) {
        if (-not (Test-Path (Join-Path $frontendPath "node_modules"))) {
            Write-Info "Instalando dependencias npm..."
            Push-Location $frontendPath
            npm install
            Pop-Location
        }
        $frontendCmd = "cd '$frontendPath'; " +
                       "Write-Host '[REACT] Iniciando en puerto 3000...' -ForegroundColor Green; " +
                       "npm run dev -- --port 3000; " +
                       "Read-Host 'Presiona Enter para cerrar'"
        $procs += Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd `
                               -WindowStyle Normal -PassThru
        Write-Ok "Dashboard React iniciado (3000)"
    } else {
        Write-Info "frontend\package.json no encontrado. Crea el proyecto con:"
        Write-Host "       npm create vite@latest frontend -- --template react" -ForegroundColor Gray
    }
} else {
    Write-Info "Frontend omitido."
}

# ── Guardar PIDs para stop_system.ps1 ────────────────────────────────────────
$pidsFile = Join-Path $ROOT ".system_pids.txt"
$procs | ForEach-Object { $_.Id } | Out-File $pidsFile -Encoding UTF8
Write-Info "PIDs guardados en .system_pids.txt (usado por stop_system.ps1)"

# ── Resumen ──────────────────────────────────────────────────────────────────
Write-Header "Sistema iniciado correctamente"
Write-Host ""
Write-Host "  Orquestador:      http://localhost:8000/docs" -ForegroundColor White
Write-Host "  Agente Gases:     http://localhost:8001/docs" -ForegroundColor White
Write-Host "  Agente Imagenes:  http://localhost:8002/docs" -ForegroundColor White
Write-Host "  Agente Geo:       http://localhost:8003/docs" -ForegroundColor White
Write-Host "  Agente Monitor:   http://localhost:8004/docs" -ForegroundColor White
Write-Host "  Simulador:        http://localhost:8005/docs" -ForegroundColor White
Write-Host "  Dashboard React:  http://localhost:3000"      -ForegroundColor White
Write-Host ""
Write-Host "  Para iniciar la simulacion automatica:" -ForegroundColor Gray
Write-Host "  Invoke-RestMethod -Method POST http://localhost:8005/iniciar" -ForegroundColor Yellow
Write-Host "  -- o con curl --" -ForegroundColor Gray
Write-Host "  curl -X POST http://localhost:8005/iniciar" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Para detener todo: .\stop_system.ps1" -ForegroundColor Gray
Write-Host $("=" * 56) -ForegroundColor Cyan
Write-Host ""
Read-Host "Presiona Enter para cerrar esta ventana (los servicios siguen corriendo)"
