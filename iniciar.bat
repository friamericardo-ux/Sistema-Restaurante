
@echo off
title Comanda Digital
cls
echo ========================================
echo   COMANDA DIGITAL - INICIANDO
echo ========================================
echo.
echo [1] Verificando ambiente virtual...
echo.

cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    echo [OK] Ambiente virtual encontrado!
    echo.
    echo [2] Iniciando servidor Flask...
    echo.
    echo Acesse: http://127.0.0.1:5000/login
    echo.
    echo Para parar: pressione CTRL+C
    echo ========================================
    echo.
    .venv\Scripts\python.exe app.py
) else (
    echo [ERRO] Ambiente virtual nao encontrado!
    echo.
    echo Execute no terminal:
    echo python -m venv .venv
    echo.
    pause
)