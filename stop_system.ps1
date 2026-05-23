# stop_system.ps1 — Detiene todos los servicios del sistema multiagente.

$ROOT     = Split-Path -Parent $MyInvocation.MyCommand.Definition
$pidsFile = Join-Path $ROOT ".system_pids.txt"

Write-Host "`n$("=" * 56)" -ForegroundColor Cyan
Write-Host "  Deteniendo Sistema Multiagente - UPTC 2026" -ForegroundColor White
Write-Host $("=" * 56) -ForegroundColor Cyan

# Matar por PIDs guardados
if (Test-Path $pidsFile) {
    Write-Host "`n  Leyendo PIDs de procesos..." -ForegroundColor Yellow
    Get-Content $pidsFile | ForEach-Object {
        $pid_ = $_.Trim()
        if ($pid_ -match '^\d+$') {
            try {
                Stop-Process -Id $pid_ -Force -ErrorAction Stop
                Write-Host "  [OK] Proceso PID $pid_ detenido" -ForegroundColor Green
            } catch {
                Write-Host "  [--] PID $pid_ ya no existe" -ForegroundColor Gray
            }
        }
    }
    Remove-Item $pidsFile -Force
}

# Liberar puertos por si acaso quedaron procesos huerfanos
$puertos = @(8000, 8001, 8002, 8003, 8004, 8005, 3000)
foreach ($puerto in $puertos) {
    $conn = netstat -aon | Select-String ":$puerto " | Select-String "LISTENING"
    if ($conn) {
        $pid_ = ($conn -split '\s+')[-1]
        if ($pid_ -match '^\d+$' -and $pid_ -ne '0') {
            try {
                Stop-Process -Id $pid_ -Force -ErrorAction SilentlyContinue
                Write-Host "  [OK] Puerto $puerto liberado (PID $pid_)" -ForegroundColor Green
            } catch {}
        }
    }
}

Write-Host "`n  Sistema detenido correctamente.`n" -ForegroundColor Green
Read-Host "Presiona Enter para cerrar"
