# start_system.ps1
# ════════════════════════════════════════════════════════════════════════════
# Sistema Multiagente Minería Subterránea IA — UPTC 2026
# Servicios: Gases(8001) + Imágenes(8002) + Geomecánico(8003)
#            + Monitor(8004) + Simulador(8005) + WhatsApp(8006)
#            + Orquestador(8000) + Dashboard React(3000)
#
# Variables de entorno opcionales en .env:
#   GEMINI_API_KEY=AIza...         (LLM — gratis en aistudio.google.com)
#   TWILIO_ACCOUNT_SID=...         (WhatsApp real)
#   TWILIO_AUTH_TOKEN=...
#   WHATSAPP_ALERTAS=+573001234567 (números para alertas críticas)
#
# Uso:
#   .\start_system.ps1                    -> backend completo + frontend
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

Write-Header "Sistema Multiagente Mineria IA - UPTC 2026"
Write-Host "  Capas: cGANs(1) + LLM+RAG(2) + LangGraph+4Agentes(3) + WhatsApp(4)" -ForegroundColor Gray
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
Write-Step 4 5 "Iniciando servicios backend (8 servicios)"

$procs = @()

# Capa 3 — Agentes especializados (arrancar primero)
$procs += Start-Servicio "AGENTE GASES"       8001 "backend.agentes.gases.app:app"
Write-Ok "Agente de Gases iniciado (8001)"
Start-Sleep -Seconds 3

$procs += Start-Servicio "AGENTE IMAGENES"    8002 "backend.agentes.imagenes.app:app"
Write-Ok "Agente de Imágenes iniciado (8002)"
Start-Sleep -Seconds 2

$procs += Start-Servicio "AGENTE GEOMECANICO" 8003 "backend.agentes.geomecanico.app:app"
Write-Ok "Agente Geomecánico iniciado (8003)"
Start-Sleep -Seconds 2

$procs += Start-Servicio "AGENTE MONITOR"     8004 "backend.agentes.monitor.app:app"
Write-Ok "Agente Monitor iniciado (8004)"
Start-Sleep -Seconds 2

# Capa 4 — Bot WhatsApp
$procs += Start-Servicio "BOT WHATSAPP"       8006 "backend.whatsapp.app:app"
Write-Ok "Bot WhatsApp iniciado (8006)"
Start-Sleep -Seconds 2

# Capa 3 — Orquestador central (LangGraph + LLM)
$procs += Start-Servicio "ORQUESTADOR"        8007 "backend.orquestador.app:app" "info"
Write-Ok "Orquestador + LangGraph iniciado (8007)"
Start-Sleep -Seconds 5

# Simulador
$procs += Start-Servicio "SIMULADOR"          8005 "backend.simulacion.simulador:sim_app"
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
            Write-Info "Instalando dependencias pnpm..."
            Push-Location $frontendPath; pnpm install; Pop-Location
        }
        $fCmd = "cd '$frontendPath'; pnpm run dev -- --port 3000; Read-Host"
        Start-Process powershell -ArgumentList "-NoExit", "-Command", $fCmd -WindowStyle Normal
        Write-Ok "Dashboard React iniciado (3000)"
    } else {
        Write-Info "frontend\package.json no encontrado."
        Write-Host "       Para crear el frontend ejecuta:" -ForegroundColor Gray
        Write-Host "       cd frontend; pnpm create vite@latest . -- --template react; pnpm install" -ForegroundColor Yellow
    }
} else {
    Write-Info "Frontend omitido."
}

# ── Resumen ──────────────────────────────────────────────────────────────────
Write-Header "Sistema iniciado — UPTC 2026"
Write-Host ""
Write-Host "  CAPA 2+3 — Orquestador + LangGraph:" -ForegroundColor Cyan
Write-Host "    http://localhost:8007/docs" -ForegroundColor White
Write-Host "  CAPA 3 — Agentes especializados:" -ForegroundColor Cyan
Write-Host "    Gases:       http://localhost:8001/docs" -ForegroundColor White
Write-Host "    Imágenes:    http://localhost:8002/docs" -ForegroundColor White
Write-Host "    Geomecánico: http://localhost:8003/docs" -ForegroundColor White
Write-Host "    Monitor:     http://localhost:8004/docs" -ForegroundColor White
Write-Host "  CAPA 4 — Bot WhatsApp + Dashboard:" -ForegroundColor Cyan
Write-Host "    Bot:         http://localhost:8006/docs" -ForegroundColor White
Write-Host "    Dashboard:   http://localhost:3000" -ForegroundColor White
Write-Host ""
Write-Host "  Simular ciclo clásico:" -ForegroundColor Gray
Write-Host '  Invoke-RestMethod -Method POST "http://localhost:8005/simular?zona=Frente_A_Sogamoso"' -ForegroundColor Yellow
Write-Host ""
Write-Host "  Simular ciclo LangGraph (con memoria acumulativa):" -ForegroundColor Gray
Write-Host '  Invoke-RestMethod -Method POST "http://localhost:8000/orquestar_langgraph" -ContentType "application/json" -Body '"'"'{"zona":"Frente_A_Sogamoso","gases":{"CH4":0.8,"CO":15,"CO2":0.2,"O2":20.8,"H2S":0.3},"imagen":{"deteccion":"normal","confianza":0.95,"n_personas":2},"geo":{"deformacion_mm":1.5,"vibracion_mms":4.0,"presion_kpa":35,"convergencia_mm":2.0,"indice_estabilidad":0.85}}'"'"'' -ForegroundColor Yellow
Write-Host ""
Write-Host "  Chat Bot WhatsApp (prueba web):" -ForegroundColor Gray
Write-Host '  Invoke-RestMethod -Method POST "http://localhost:8006/chat" -ContentType "application/json" -Body '"'"'{"mensaje":"estado"}'"'"'' -ForegroundColor Yellow
Write-Host ""
Write-Host "  Para detener: .\stop_system.ps1" -ForegroundColor Gray
Write-Host $("=" * 56) -ForegroundColor Cyan
Read-Host "Presiona Enter para cerrar (los servicios siguen corriendo)"
