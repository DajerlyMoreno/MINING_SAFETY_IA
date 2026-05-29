# start_system.ps1
# ════════════════════════════════════════════════════════════════════════════
# Inicia los servicios IMPLEMENTADOS del sistema multiagente.
# VERSIÓN ACTUAL: Orquestador + Agente de Gases + Simulador
#
# Uso:
#   .\start_system.ps1                    -> backend + frontend
#   .\start_system.ps1 -SinFrontend       -> solo backend
#
# Si PowerShell bloquea la ejecucion:
#   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
# ════════════════════════════════════════════════════════════════════════════

param(
    [switch]$SinFrontend,
    [switch]$SoloBackend
)

$ErrorActionPreference = "Continue"

function Write-Header($msg) {
    Write-Host "`n$("=" * 56)" -ForegroundColor Cyan
    Write-Host "  $msg" -ForegroundColor White
    Write-Host $("=" * 56) -ForegroundColor Cyan
}
function Write-Ok($msg)   { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Info($msg) { Write-Host "  [>>] $msg" -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host "  [!!] $msg" -ForegroundColor Red }
function Write-Step($n,$total,$msg) { Write-Host "`n[$n/$total] $msg" -ForegroundColor Cyan }

$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ROOT

Write-Header "Sistema Multiagente Mineria - UPTC 2026"
Write-Host "  Servicios activos: Orquestador + Gases + Simulador" -ForegroundColor Gray
Write-Host "  Directorio: $ROOT" -ForegroundColor Gray

# ── Rutas del entorno virtual ────────────────────────────────────────────────
$VENV_ACTIVATE = Join-Path $ROOT "env\Scripts\Activate.ps1"
$VENV_PYTHON   = Join-Path $ROOT "env\Scripts\python.exe"
$VENV_UVICORN  = Join-Path $ROOT "env\Scripts\uvicorn.exe"

# ── 1. Entorno virtual ───────────────────────────────────────────────────────
Write-Step 1 5 "Entorno virtual Python"

if (-not (Test-Path $VENV_ACTIVATE)) {
    Write-Info "Creando entorno virtual en env\ ..."
    python -m venv env
    if ($LASTEXITCODE -ne 0) {
        Write-Err "No se pudo crear el entorno virtual."
        Read-Host "Presiona Enter para salir"; exit 1
    }
}
& $VENV_ACTIVATE
Write-Ok "Entorno virtual listo"

# ── 2. Dependencias ──────────────────────────────────────────────────────────
Write-Step 2 5 "Dependencias Python"
& $VENV_PYTHON -m pip install -q -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Err "Fallo al instalar dependencias."
    Read-Host "Presiona Enter para salir"; exit 1
}
Write-Ok "Dependencias instaladas"

# ── 3. Verificar modelos ─────────────────────────────────────────────────────
Write-Step 3 5 "Verificando modelos"
& $VENV_PYTHON -c @"
try:
    from backend.shared.config import settings
    errores = settings.model_paths.validate()
    if errores:
        [print(f'  ADVERTENCIA: {e}') for e in errores]
    else:
        print('  Todos los modelos encontrados')
except Exception as e:
    print(f'  (config: {e})')
"@

# ── Función para lanzar servicio ─────────────────────────────────────────────
function Start-Servicio {
    param($Titulo, $Puerto, $Modulo, $LogLevel = "warning")

    $cmd = "cd '$ROOT'; " +
           "& '$VENV_ACTIVATE'; " +
           "Write-Host '[$Titulo] Iniciando en :$Puerto...' -ForegroundColor Green; " +
           "& '$VENV_UVICORN' $Modulo --host 127.0.0.1 --port $Puerto --log-level $LogLevel; " +
           "Write-Host 'Servicio detenido.' -ForegroundColor Red; Read-Host"

    Start-Process powershell -ArgumentList "-NoExit", "-Command", $cmd -WindowStyle Normal -PassThru
}

# ── 4. Servicios backend ─────────────────────────────────────────────────────
Write-Step 4 5 "Iniciando servicios backend"

$procs = @()
$procs += Start-Servicio "AGENTE GASES"   8001 "backend.agentes.gases.app:app"
Write-Ok "Agente de Gases iniciado (8001)"
Start-Sleep -Seconds 5

$procs += Start-Servicio "ORQUESTADOR"    8000 "backend.orquestador.app:app" "info"
Write-Ok "Orquestador iniciado (8000)"
Start-Sleep -Seconds 4

$procs += Start-Servicio "SIMULADOR"      8005 "backend.simulacion.simulador:sim_app"
Write-Ok "Simulador iniciado (8005)"
Start-Sleep -Seconds 2

# Guardar PIDs
$procs | ForEach-Object { $_.Id } | Out-File (Join-Path $ROOT ".system_pids.txt") -Encoding UTF8

# ── 5. Frontend React ────────────────────────────────────────────────────────
Write-Step 5 5 "Dashboard React"

if (-not $SinFrontend -and -not $SoloBackend) {
    $frontendPath = Join-Path $ROOT "frontend"
    if (Test-Path (Join-Path $frontendPath "package.json")) {
        if (-not (Test-Path (Join-Path $frontendPath "node_modules"))) {
            Write-Info "Instalando dependencias npm..."
            Push-Location $frontendPath; npm install; Pop-Location
        }
        $fCmd = "cd '$frontendPath'; npm run dev -- --port 3000; Read-Host"
        Start-Process powershell -ArgumentList "-NoExit", "-Command", $fCmd -WindowStyle Normal
        Write-Ok "Dashboard React iniciado (3000)"
    } else {
        Write-Info "frontend\package.json no encontrado."
        Write-Host "       Para crear el frontend ejecuta:" -ForegroundColor Gray
        Write-Host "       cd frontend; npm create vite@latest . -- --template react; npm install" -ForegroundColor Yellow
    }
} else {
    Write-Info "Frontend omitido."
}

# ── Resumen ──────────────────────────────────────────────────────────────────
Write-Header "Sistema iniciado"
Write-Host ""
Write-Host "  Orquestador:   http://localhost:8000/docs" -ForegroundColor White
Write-Host "  Agente Gases:  http://localhost:8001/docs" -ForegroundColor White
Write-Host "  Simulador:     http://localhost:8005/docs" -ForegroundColor White
Write-Host "  Dashboard:     http://localhost:3000" -ForegroundColor White
Write-Host ""
Write-Host "  Simular ciclo manual:" -ForegroundColor Gray
Write-Host '  Invoke-RestMethod -Method POST "http://localhost:8005/simular?zona=Frente_A_Sogamoso"' -ForegroundColor Yellow
Write-Host ""
Write-Host "  Para detener: .\stop_system.ps1" -ForegroundColor Gray
Write-Host $("=" * 56) -ForegroundColor Cyan
Read-Host "Presiona Enter para cerrar (los servicios siguen corriendo)"
