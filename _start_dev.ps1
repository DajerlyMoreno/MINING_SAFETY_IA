param([string]$Accion = "arrancar")
$ErrorActionPreference = "Continue"
Set-Location "C:\proyectos-inteligencia-computacional\MINING_SAFETY_IA"

$VENV_PYTHON = Join-Path $PWD "env\Scripts\python.exe"
$VENV_UVICORN = Join-Path $PWD "env\Scripts\uvicorn.exe"

function Start-Svc {
    param($Titulo, $Puerto, $Modulo, $LogLevel = "warning")
    $cmd = "Set-Location '$PWD';& '$VENV_UVICORN' $Modulo --host 127.0.0.1 --port $Puerto --log-level $LogLevel"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $cmd -WindowStyle Normal -PassThru
}

switch ($Accion) {
    "arrancar" {
        Write-Host "Arrancando Agente de Gases (8001)..." -ForegroundColor Cyan
        Start-Svc "AGENTE GASES" 8001 "backend.agentes.gases.app:app"
        Start-Sleep -Seconds 3

        Write-Host "Arrancando Simulador (8005)..." -ForegroundColor Cyan
        Start-Svc "SIMULADOR" 8005 "backend.simulacion.simulador:sim_app"
        Start-Sleep -Seconds 2

        Write-Host "Arrancando Orquestador (8007)..." -ForegroundColor Cyan
        Start-Svc "ORQUESTADOR" 8007 "backend.orquestador.app:app" "info"
        Start-Sleep -Seconds 3

        Write-Host ""
        Write-Host "=== SERVICIOS ARRANCADOS ===" -ForegroundColor Green
        Write-Host "Agente Gases:  http://localhost:8001/docs" -ForegroundColor White
        Write-Host "Simulador:     http://localhost:8005/docs" -ForegroundColor White
        Write-Host "Orquestador:  http://localhost:8007/docs" -ForegroundColor White
        Write-Host ""
        Write-Host "Para probar ciclo:" -ForegroundColor Gray
        Write-Host '  Invoke-RestMethod -Method POST "http://localhost:8005/simular?zona=Frente_A_Sogamoso"' -ForegroundColor Yellow
    }
    "detener" {
        Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
        Write-Host "Procesos Python detenidos." -ForegroundColor Yellow
    }
}
