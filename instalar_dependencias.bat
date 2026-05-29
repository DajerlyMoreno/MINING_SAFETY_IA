@echo off
chcp 65001 >nul 2>&1
title Instalador de Dependencias - Sistema Mineria UPTC 2026

echo.
echo ============================================================
echo   Instalador de Dependencias - Mineria UPTC 2026
echo ============================================================
echo.

:: Verificar que existe el entorno virtual
if not exist "env\Scripts\activate.bat" (
    echo [ERROR] No se encontro el entorno virtual.
    echo Crea uno con: python -m venv env
    pause
    exit /b 1
)

:: Activar entorno virtual
call env\Scripts\activate.bat
echo [OK] Entorno virtual activado.
echo.

:: Paso 1: Desinstalar paquetes conflictivos
echo [1/5] Limpiando paquetes conflictivos...
pip uninstall keras tensorflow-intel -y >nul 2>&1
echo [OK] Limpieza completada.
echo.

:: Paso 2: Instalar dependencias fijas de TF 2.15 PRIMERO
echo [2/5] Instalando dependencias base de TensorFlow 2.15...
pip install numpy==1.26.4 protobuf==4.25.3 ml-dtypes==0.2.0 h5py==3.11.0 --quiet
if errorlevel 1 (
    echo [ERROR] Fallo instalando dependencias base.
    pause
    exit /b 1
)
echo [OK] Dependencias base instaladas.
echo.

:: Paso 3: Instalar TensorFlow y tf-keras
echo [3/5] Instalando TensorFlow 2.15.0 y tf-keras...
pip install tensorflow==2.15.0 tf-keras==2.15.0 --quiet
if errorlevel 1 (
    echo [ERROR] Fallo instalando TensorFlow.
    pause
    exit /b 1
)
echo [OK] TensorFlow y tf-keras instalados.
echo.

:: Paso 4: Instalar el resto de dependencias
echo [4/5] Instalando resto de dependencias...
pip install ^
    fastapi==0.111.0 ^
    "uvicorn[standard]==0.30.1" ^
    httpx==0.27.0 ^
    python-dotenv==1.0.1 ^
    "pydantic==2.7.4" ^
    "websockets>=12.0" ^
    langchain==0.2.16 ^
    langchain-community==0.2.16 ^
    langchain-core==0.2.38 ^
    faiss-cpu==1.8.0 ^
    sentence-transformers==3.0.1 ^
    scikit-learn==1.5.1 ^
    pandas==2.2.2 ^
    matplotlib==3.8.4 ^
    seaborn==0.13.1 ^
    plotly==5.23.0 ^
    colorama==0.4.6 ^
    tabulate==0.9.0 ^
    aiosqlite==0.20.0 ^
    --quiet
if errorlevel 1 (
    echo [ADVERTENCIA] Algunas dependencias tuvieron errores. Revisa arriba.
) else (
    echo [OK] Dependencias instaladas correctamente.
)
echo.

:: Paso 5: Verificar instalacion critica
echo [5/5] Verificando instalacion...
python -c "import tensorflow as tf; import tf_keras; import h5py; import numpy as np; print('TF:', tf.__version__); print('tf_keras:', tf_keras.__version__); print('h5py:', h5py.__version__); print('numpy:', np.__version__)"
if errorlevel 1 (
    echo [ERROR] Verificacion fallida. Revisa los errores anteriores.
) else (
    echo.
    echo ============================================================
    echo   Instalacion completada exitosamente.
    echo   Ya puedes ejecutar start_system.bat
    echo ============================================================
)
echo.
pause
